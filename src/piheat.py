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

# Imports for reading from gmail
import imaplib2
import email
import netrc

# Imports for communicating with superhub
import urllib.parse
import requests
import re
from bs4 import BeautifulSoup

debug = True
import logging
if debug:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')
else:
    logging.basicConfig(filename='/var/log/piheat.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Import python MySQL module
import MySQLdb


"""GPIO setup"""
# Import a Raspberry Pi GPIO module
import RPi.GPIO as GPIO

# Turn off GPIO warnings
GPIO.setwarnings(False)
# Set the GPIO numbering convention to be header pin numbers
GPIO.setmode(GPIO.BOARD)

# Define which RPi pins connect to which relays
ST699   = 11
DHW_OFF = 13
DHW_ON  = 15
CH_ON   = 16
gpio_outputs = {'dhw_off':DHW_OFF, 'dhw_on':DHW_ON, 'ch_on':CH_ON}

# Configure each GPIO pin as an output & initialise
GPIO.setup(ST699, GPIO.OUT, initial = 1)
for relay in gpio_outputs.values():
    GPIO.setup(relay, GPIO.OUT, initial = 0)
"""End of GPIO setup"""



class CheckNet(object):

    def test(self):
        """Trys connecting to a reliable website.
        
        return: boolean
        """
        try:
            rv = requests.get("http://www.google.com")
            logging.debug(("Response code: ", rv.status_code))
            return True
        except requests.ConnectionError:
            logging.error("Could not connect to website. Lost internet connection?")
            return False

    
    
class UserData(object):
    def get_secrets(self, machine):
        """Class method to provide log in data for other classes.
        
        machine: string
        return: tuple
                    of the form (login(string), account(string), password(string))
        """
        secrets = netrc.netrc()
        return secrets.authenticators(machine)



class Gmail(object):

    def login(self):
        """Log in to Gmail account.
        
        return: boolean
                    (True:  if successfully reach the 'AUTH' state)
                    (False: if not)
        """
        mailhost = 'imap.gmail.com'
        g_secrets = UserData()
        self.mail = imaplib2.IMAP4_SSL(host=mailhost)
        self.piheat_db = DBase()

        # Read from .netrc file
        login, account, password = g_secrets.get_secrets(mailhost)
        logging.debug("Logging into Gmail")
        response, empty = self.mail.login(login, password)
        logging.debug(("Response is...", response))
        logging.debug(("mail.state is", self.mail.state))
        if (response == 'OK') and (self.mail.state == 'AUTH'):
            logging.debug("Login successful")
            return True
        else:
            logging.error("Gmail login failed")
            return False
            
            
    def get_mail_state(self):
        """Getter method returns the mail.state command
        
        return: string ('NONAUTH', 'AUTH', or 'SELECTED')
        """
        logging.debug(self.mail.state)
        return self.mail.state
            

    def noop(self):
        """IMAP NOOP command.
        
        Used by test program.
        The responses specified in RFC3501 are:
        If successful it returns: ('OK', 'noop completed')
        If not, it returns: ('BAD', 'command unknown or arguments invalid')
        
        return: tuple
                    (response(string), message(string))
        """
        return self.mail.noop()
        
        
    def select(self, mailbox):
        """IMAP SELECT command.
        
        The responses specified in RFC3501 are:
        ('OK', 'select completed, now in selected state')
        ('NO', 'select failure, now in authenticated state:
                        no such mailbox, can't access mailbox')
        ('BAD', 'command unknown or arguments invalid')
                
        return: tuple
                    (response(string), message(string))
        """
        return self.mail.select(mailbox)
        
        
    def get_commands(self):
        """Gets the list of commands and returns it.
        
        return: list of strings
        """
        return self.commands
        
        
    def get_target_temp(self):
        """Gets and returns the value of the self.target_temp variable.
        
        return: int or float
        """
        return self.target_temp


    def read_folder(self, mailbox, mail_state):
        """Selects mailbox and waits for new email, then returns its subject header.
        
        mailbox: string
        mail_state: string ('NONAUTH', 'AUTH', or 'SELECTED')
        
        return: string
        """
        # Gmail was timing out & causing the service to stop
        # so need to check connection to Gmail, if it fails, login again
        # Now with use of IMAP IDLE command this should no longer be necessary.
        if mail_state == 'SELECTED':
            pass
        elif mail_state == 'AUTH':
            logging.debug("Select mailbox")
            response, empty = self.select(mailbox)
            if response == 'OK':
                logging.debug("Mailbox selected.")
            else:
                logging.error("Response was:")
                logging.error(response)
                raise RuntimeError("read_folder:  Could not select mailbox.")
        else:
            raise RuntimeError("read_folder:  Not in 'AUTH' or 'SELECTED' state.")
        # We have reached the 'SELECTED' state, so we can continue
        self.mail.idle()
        # 'empty' collects the response from 'self.mail.search'
        empty, data = self.mail.search(None, 'ALL')
        id_list = data[0].split()
        # Any emails?
        if id_list:
            latest_email_id = int( id_list[-1] )
            for i in range( latest_email_id, latest_email_id-1, -1):
                # 'empty' collects the response from 'self.mail.fetch'
                empty, data = self.mail.fetch( i, '(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_string(response_part[1])
                    logging.debug("Message subject is.....")
                    logging.debug(msg['subject'])
            var_subject = msg['subject']
            if 'Notification' in var_subject:
                var_subject = var_subject.replace('Notification', '')
            self.check_subject(var_subject, latest_email_id)
            return var_subject
        else:
            logging.debug(("No emails in selected folder", mailbox))
            return None



    def check_subject(self, var_subject, latest_email_id=0):
        """Looks for specific command codes in the email subject.
        
        var_subject: string
        latest_email_id: int (default is 0)
        
        return: tuple
                    (piheat_command(string), piheat_control(string))
        """
        # Initialise these variables so that we can check they are non-zero later
        sub_data = None
        piheat_control = None
        target_temp = None
        piheat_command = None
        ctrl_pio = Pio()
        self.piheat_db.my_login()
        self.commands = ["st699", "CH", "HW"]
        for command in self.commands:
            if command in var_subject:
                # Build the search string
                search = "\'(SUBJECT \"" + command + "\")\'"
                # 'empty' collects the response from 'self.mail.search'
                empty, sub_data = self.mail.search(None, search)
                piheat_command = command
                if 'on' in var_subject:
                    piheat_control = 'on'
                    if command is 'st699':
                        ctrl_pio.st699_on()
                    elif command is 'HW':
                        ctrl_pio.hw_on()
                    elif command is 'CH':
                        # Get actual temperature
                        livtemp = self.piheat_db.my_query("SELECT livtemp FROM temp_log")
                        if not target_temp:
                            # Use a default value
                            self.target_temp = 20
                        ctrl_pio.ch_on(livtemp, self.target_temp)
                elif '=' in var_subject:
                    if command is 'CH':
                        piheat_control = 'on'
                        livtemp = self.piheat_db.my_query("SELECT livtemp FROM temp_log")
                        empty, target_temp = var_subject.split('=')
                        target_temp = target_temp.split()
                        sql = "UPDATE target_temp SET temp=(%s)"
                        self.piheat_db.my_update(sql, target_temp)
                        self.target_temp = float(target_temp[0])
                        ctrl_pio.ch_on(livtemp, self.target_temp)
                elif 'off' in var_subject:
                    piheat_control = 'off'
                    if command is 'st699':
                        ctrl_pio.st699_off()
                    elif command is 'CH':
                        ctrl_pio.ch_off()
                    elif command is 'HW':
                        ctrl_pio.hw_off()
                else:
                    logging.warning(("No control specified for", command))
                if piheat_control:
                    message = "Turning " + command + ' ' + piheat_control
                    logging.debug(message)
        #  Updates the 'control' in the 'piheat' table for the chosen 'command'
        if piheat_command and piheat_control:
            try:
                sql = "UPDATE piheat SET piheat_control=(%s) WHERE piheat_function=(%s)"
                self.piheat_db.my_update(sql, piheat_control, piheat_command)
            except:
                self.piheat_db.rollback()
        else:
            logging.warning("No data to write!")

        # Remove all but the most recent email from mailbox, for the specified command
        if sub_data:
            del_list = sub_data[0].split()
            for num in enumerate(del_list):
                i = int(num[1])
                if (i != latest_email_id):
                    self.mail.store(num[1], '+FLAGS', '\\Deleted')
        else:
            logging.debug("No matching emails were found")
        self.mail.expunge()
        return (piheat_command, piheat_control)


    def logout(self):
        logging.debug("Closing MySQL connection")
        self.piheat_db.my_logout()
        logging.debug("Closing IMAP connection")
        self.mail.close()
        self.mail.logout()



class VMSuperHub(CheckNet):
    def __init__(self):
        superhub_address = "http://192.168.0.1"
        req = requests.Session()
        home_url = superhub_address + "/home.html"
        r = req.get(home_url)


    def vm_login(self):
        """Logs in to SuperHub"""
        v_secrets = UserData()
        login, account, password = v_secrets.get_secrets('superhub')
        # Check if logged in
        if r.url == home_url:
            logged_in = True
        else:
            logged_in = False

        while not logged_in:
            soup = BeautifulSoup(r.text)
            password_name = soup.find("input", id="password")["name"]
            login_url = superhub_address + "/cgi-bin/VmLoginCgi"
            data = urllib.parse.urlencode({password_name: password}).encode("utf-8")
            headers       = {"Content-Type":"application/x-www-form-urlencoded"}
            req.post(login_url, data = data, headers = headers)
            # Check again if logged in, to break loop
            r = req.get(home_url)
            if r.url == home_url:
                logged_in = True
            else:
                logged_in = False
        rv = req.get(superhub_address + "/VmRgRebootRestoreDevice.html")
        rv = re.search('name=\"([^\"]*?)\" value=\"0\"', r.text)
        logging.debug("Logged in is...", logged_in)
        reset_address = "/cgi-bin/VmRgRebootResetDeviceCfgCgi"
        data = {"VMRebootResetChangeCache":"1",m.group(1).encode('ascii','ignore'):"0"}
        rv = req.post(superhub_address + reset_address, data=data)



class Pio(object):

    def check_io(self, pin):
        """Check the output state of a GPIO.
        
        pin: int
        return: int
        """
        pin_state = GPIO.input(pin) 
        return pin_state
        

    def st699_off(self):
        """Switches the old programmer off.

        Because the old programmer is powered from an NC relay contact,
        it will be 'off' when the GPIO is high, and 'on' when it is low!
        Unlike all the other controls, which are connected to the NO contact
        on the relays.
        """
        logging.info("Switching ST699 off.")
        GPIO.output(ST699, 1)


    def st699_on(self):
        """Switches the old programmer on.

        And switches off the controls from all the other relays.
        """
        logging.info("Switching ST699 on.")
        GPIO.output(ST699, 0)
        for relay in gpio_outputs.values():
            GPIO.output(relay, 0)


    def hw_off(self):
        """Switches the hot water off.

        Sets dhw_on = 0 and dhw_off = ch_on.  Switches the GPIO controlling
        the dhw_on relay off, and switches the dhw_off relay according to the
        state of the ch_on relay.
        """
        logging.info("Switching hot water off.")
        GPIO.output(DHW_ON,  0)
        GPIO.output(DHW_OFF, (self.check_io(CH_ON)))


    def hw_on(self):
        logging.info("Switching hot water on.")
        GPIO.output(DHW_OFF, 0)
        GPIO.output(DHW_ON,  1)


    def ch_off(self):
        logging.info("Switching central heating off.")
        GPIO.output(CH_ON,   0)
        GPIO.output(DHW_OFF, 0)


    def ch_on(self, actual_temp, target_temp=20):
        """Switches the central heating on if target_temp > actual_temp.
        
        actual_temp: float
        target_temp: int or float
        
        return: boolean
        """
        logging.info("Switching central heating on.")
        logging.debug(actual_temp)
        logging.debug(target_temp)
        # Check target temperature against actual room temperature
        if actual_temp < target_temp:
            logging.info("room is not warm enough")
            GPIO.output(CH_ON, 1)
            
            # While ch_on == high, dhw_off = not dhw_on
            GPIO.output(DHW_OFF, (not self.check_io(DHW_ON)))
            return True
        else:
            logging.info("room is warm enough")
            GPIO.output(CH_ON,   0)
            GPIO.output(DHW_OFF, 0)
            return False



class DBase(object):

    def my_login(self):
        """Uses MySQLdb to connect to database.
        
        return: boolean
                    True: connected
                    False: not connected
        """
        # Read from .netrc file
        my_secrets = UserData()
        login, account, password = my_secrets.get_secrets('mysql')
        self.db = MySQLdb.connect(db=account, user=login)
        self.cursor = self.db.cursor()
        if self.db:
            logging.debug("MySQLdb connected successfully")
            return True
        else:
            logging.error("MySQLdb failed to connect")
            return False
        

    def my_query(self, sql):
        self.cursor.execute(sql)
        data = self.cursor.fetchone()
        return data[0]


    def my_update(self, sql, *values):
        """Forms a MySQL instruction from the arguments.
        
        This is designed to work with a variable number of arguments,
        and will perform string substitution to insert the value(s)
        provided into the instruction.
        
        sql: string
        *values: string(s)
        """
        assert sql.count('%s') == len(values), (sql, values)
        placeholders = []
        new_values = []
        for value in values:
            if isinstance(value, (list, tuple)):
                placeholders.append(', '.join(['%s'] * len(value)))
                new_values.extend(value)
            else:
                placeholders.append('%s')
                new_values.append(value)
        sql = sql % tuple(placeholders)
        values = tuple(new_values)

        self.cursor.execute(sql, values)
        self.db.commit()


    def my_logout(self):
        """Clean up and close connection."""
        self.cursor.close()
        logging.debug("Closing MySQL connection")
        self.db.close()



def main():
    """The main piheat.py function."""
    logged_in = False
    conn = CheckNet()
    connection = conn.test()
    if connection:
        piheat  = Gmail()
        logged_in = piheat.login()
    else:
        hub = VMSuperHub()
        # Should reset the hub
        hub.vm_login()
    check_pio = Pio()
    while (check_pio.check_io(ST699)) and logged_in:
        try:
            connection = conn.test()
            if connection:
                gmail_state = piheat.get_mail_state()
                if (gmail_state == 'AUTH') or (gmail_state == 'SELECTED'):
                    piheat.read_folder('piheat', gmail_state)
                elif gmail.state == 'NONAUTH':
                    logged_in = piheat.login()
                else:
                    logging.error("\n\nCannot connect to Gmail IMAP server.")
                    logging.error("State repsonse is:")
                    logging.error(gmail_state)
            else:
                # Should reset the hub
                hub.vm_login()
                st699_state = check_pio.check_io(ST699)
                break
        except (KeyboardInterrupt):
            # On Ctrl-c cleanup & exit
            logging.info("PROGRAM STOPPING!  Closing MySQL and IMAP connections")
            break
    try:
        piheat.logout()
    except:
        pass
    logging.shutdown()


# Only run the main function when not under test
if __name__ == "__main__":
    main()
