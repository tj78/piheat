#!/usr/bin/env python

"""Raspberry Pi heating & hot water controller

=================================================================
Needs to produce these signals in order to replace old programmer
-----------------------------------------------------------------
 =========================================
| All off || HW only || CH only || All on |
|=========================================|
|dhw_off  ||    0    ||    1    ||   0    |
|-----------------------------------------|
|dhw_on   ||    0    ||    0    ||   1    |
|-----------------------------------------|
|ch_on    ||    0    ||    1    ||   1    |
 =========================================
"""

# Import and set the level for debug, error, etc. messages
import logging
# Appends logging messages to the specified file, with a timestamp for each entry
logging.basicConfig(filename='/var/log/piheat.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Imports for reading from gmail
import imaplib2
import email
import netrc

# Use login details from .netrc
secrets = netrc.netrc()

# Import for time function
import time

# Import python MySQL module
import MySQLdb


# Define & initialise global variables
mail = 'EMPTY'

# Define which RPi pins connect to which relays
st699   = 11
dhw_off = 13
dhw_on  = 15
ch_on   = 16
# Don't include 'st699' in the outputs dictionary as it works the opposite way to the others
gpio_outputs = {'dhw_off':dhw_off, 'dhw_on':dhw_on, 'ch_on':ch_on}



##############
# GPIO setup #
##############
try:
    import RPi.GPIO as GPIO
except RuntimeError:
    logging.error("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")

# Turn off GPIO warnings
GPIO.setwarnings(False)

# Set the GPIO numbering convention to be header pin numbers
GPIO.setmode(GPIO.BOARD)

# Configure each GPIO pin as an output & initialise
GPIO.setup(st699, GPIO.OUT, initial = 1)
for relay in gpio_outputs.values():
    # initialise each of the GPIO controlling relays and set the relays to be off
    GPIO.setup(relay, GPIO.OUT, initial = 0)



def mysql_temp(secrets):
    """Get the living room temperature from a MySQL database.

    secrets: string (.netrc file login details)
    return: string
                livtemp is a decimal number, but using .fetchone() to get the
                result from the MySQL 'SELECT' command returns a string.  This
                is converted to a float later.
    return: False
                if there is any problem with connecting to the database or running the command
                this function will return False.
    """
    # Connect to db
    host = 'mysql'
    # Read from .netrc file
    login, account, password = secrets.authenticators(host)
    logging.debug("Connecting to MySQL database")
    try:
        db = MySQLdb.connect(db="site_db", user=login)
        # Setup cursor
        logging.debug("Setup cursor")
        cursor = db.cursor()
        logging.info("Reading living room temperature")
        cursor.execute("SELECT livtemp FROM temp_log")
        livtemp = cursor.fetchone()
        livtemp = livtemp[0]
        logging.info(livtemp)
    except:
        logging.error("ERROR - couldn't read temperature")
        db.rollback()
        return False
    finally:
        db.close()
    return livtemp



def login_gmail(secrets):
    """Log in to Gmail account.

    secrets: string (.netrc file login details)
    return: boolean
                True:  if successfully reach the 'AUTH' state
                False: if not
    """
    global mail
    host = 'imap.gmail.com'
    try:
        mail = imaplib2.IMAP4_SSL(host)
        # Read from .netrc file
        login, account, password = secrets.authenticators(host)
        response = mail.login(login, password)
        logging.debug(("login response is...", response))
        logging.debug(("mail state is", mail.state))
        if ('OK' in response[0]) and (mail.state == 'AUTH'):
            return True
        else:
            logging.error("Gmail login failed")
            return False
    except:
        logging.error("Can't connect to Gmail")
        # Need to call the function to reboot superhub
        return False



def read_folder(mailbox):
    """Read the most recent email in the selected mailbox.

    mailbox: string
                is the mailbox to be selected.
    return:  string
                varSubject is the subject header from the most recent email.
    """
    global mail

    # Gmail was timing out & causing the service to stop
    # so need to check connection to Gmail, if it fails, login again
    rv = mail.select(mailbox)
    if 'NO' in rv[0]:
        if mail.state == 'NONAUTH':
            logging.debug("Not logged in, try to log in again...")
            logged_in = login_gmail(secrets)
            if not logged_in:
                logging.error("Cannot log in to Gmail")
                return None
            else:
                read_folder(mailbox)
        else:
            logging.debug(("mail.state is", mail.state))
            logging.error("Logged in but can't select mailbox!?")
            return None
    else:
        typ, data = mail.search(None, 'ALL')
        id_list = data[0].split()

    # Any emails?
    if id_list:
        latest_email_id = int(id_list[-1])
        for i in range(latest_email_id, latest_email_id-1, -1):
            typ, data = mail.fetch(i, '(RFC822)')

        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_string(response_part[1])

        varSubject = msg['subject']

        # Remove all but the most recent email from mailbox
        for num in enumerate(id_list):
            if (num[0] != 0):
                mail.store(num[0], '+FLAGS', '\\Deleted')

        mail.expunge()
    else:
        logging.info(("No emails in selected folder", mailbox))
        return None
    mail.close()
    return varSubject



def HWoff():
    """Sets dhw_on = 0 and dhw_off = ch_on

    Switches the GPIO controlling the dhw_on relay off,
    and switches the dhw_off relay according to the state
    of the ch_on relay.
    """
    GPIO.output(dhw_on,  0)
    GPIO.output(dhw_off, (GPIO.input(ch_on)))



def HWon():
    """Sets dhw_off = 1 and dhw_on = 0

    Switches the GPIO controlling the dhw_on relay on,
    and dhw_off to off.
    """
    GPIO.output(dhw_on,  1)
    GPIO.output(dhw_off, 0)



def CHoff():
    """Sets ch_on = 0 and dhw_off = 0

    Switches the GPIO controlling the ch_on relay off,
    and dhw_off to off.
    """
    GPIO.output(ch_on,   0)
    GPIO.output(dhw_off, 0)



def CHon(ch_settemp=20):
    """If actual_temp < target_temp: ch_on = 1, elif actual_temp > target_temp: ch_on = 0

    ch_settemp: float
                    Has a default value of 20, if none is set in the 'CH=' email
    return: boolean
                True:  if ch_on = 1
                False: if ch_on = 0
    """
    # Check target temperature against actual room temperature
    if (mysql_temp(secrets)) < ch_settemp:
        ch_state = True
        logging.info("room is not warm enough")
        GPIO.output(ch_on, 1)

        # While ch_on is high, dhw_off needs to be the inverse of dhw_on
        GPIO.output(dhw_off, (not GPIO.input(dhw_on)))

        # When the actual temperature is < target_temp, return True
        return True
    else:
        logging.info("room is warm enough")
        GPIO.output(ch_on,   0)
        GPIO.output(dhw_off, 0)
        # When the actual temperature is > target_temp, return False
        return False



def check_HW(varSubject):
    """Switches the hot water on or off depending on the contents of varSubject.

    varSubject: string
    return: boolean
                True:  if Hot Water is on
                False: if Hot Water is off
            None
                returns Nonetype if varSubject doesn't contain a valid command.
    """
    if "HWoff" in varSubject:
        logging.info("Hot Water off!")
        HWoff()
        return False
    elif "HWon" in varSubject:
        logging.info("Hot Water on!")
        HWon()
        return True
    else:
        logging.warning("Email subject in folder 'HW' doesn't contain a valid command")
        return None



def check_CH(varSubject):
    """Switches the central heating on or off depending on the contents of varSubject.

    varSubject: string
    return: boolean
                True:  if Central Heating is on
                False: if Central Heating is off
            None
                returns Nonetype if varSubject doesn't contain a valid command.
    """
    if 'CHoff' in varSubject:
        logging.info("Central Heating off!")
        CHoff()
        return False
    elif 'CH=' in varSubject:
        listSubject = varSubject.split('=')
        ch_settemp = listSubject[1].split()
        logging.info(("TARGET TEMPERATURE is.......", ch_settemp[0]))
        # Change from str value to float so that a comparison can be made!
        ch_settemp = float(ch_settemp[0])
        CHon(ch_settemp)
        return True
    else:
        logging.warning("Email subject in folder 'CH' doesn't contain a valid command")
        return None


def check_st699(varSubject):
    """Switches the old boiler programmer on or off as a fallback.

    Because the old connector is powered from an NC relay connector, it operates in the
    opposite way to all the other relays.  So in this case:
        GPIO.output(st699, 1)   - turns it off
        GPIO.output(st699, 0)   - turns it on

    varSubject: string
    return: boolean
                True:  if Programmer is on
                False: if Programmer is off
            None
                returns Nonetype if varSubject doesn't contain a valid command.
    """
    if 'st699on' in varSubject:
        GPIO.output(st699, 0)
        for relay in gpio_outputs.values():
            GPIO.output(relay, 0)
        return True
    elif 'st699off' in varSubject:
        GPIO.output(st699, 1)
        return False
    else:
        return None



def main():
    """The main piheat.py function that calls all other functions."""
    login_gmail(secrets)
    while GPIO.input(st699):
        try:
            varSubject = read_folder('st699')
            st699_state = check_st699(varSubject)
            if st699_state is None:
                logging.warning("Email subject in folder 'st699' doesn't contain a valid command")
            # If st699 is set to 0(on), break out of the while loop and cleanup before closing
            elif not st699_state:
                break
            else:
                varSubject = read_folder('HW')
                check_HW(varSubject)
                varSubject = read_folder('CH')
                check_CH(varSubject)
                time.sleep(5)
        except KeyboardInterrupt:
            # On Ctrl-c cleanup & exit
            break
    mail.logout()
    logging.shutdown()


# Only run the main function when not under test
if __name__ == "__main__":
    main()
