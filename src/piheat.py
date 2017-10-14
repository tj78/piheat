#!/usr/bin/python3

"""Need to produce these signals in order to replace ST699 programmer
  -----------------------------------------
 | All off || HW only || CH only || All on |
 |=========================================|
 |dhw_off  ||    0    ||    1    ||   0    |
 |-----------------------------------------|
 |dhw_on   ||    0    ||    0    ||   1    |
 |-----------------------------------------|
 |ch_on    ||    0    ||    1    ||   1    |
  -----------------------------------------
"""

# Imports for reading from gmail
import imaplib2
import email
import netrc

# Use login details from .netrc
secrets = netrc.netrc()

# redis setup
import redis
# Read from .netrc file
host, port, password = secrets.authenticators('redis')
r = redis.Redis(host=host, port=port, password=password, decode_responses=True)

# Import for time function
import time

from datetime import datetime
    
# Define & initialise global variables
mail       = 'EMPTY'
varSubject = 'EMPTY'

# Define which RPi pins connect to which relays
ST699   = 11
DHW_OFF = 13
DHW_ON  = 15
CH_ON   = 16



# Print extra messages in debug mode only
debug = True

 ############
# Debug mode #
def log(message):
  if debug:  print(message)


 ############
# GPIO setup #
try:
    import RPi.GPIO as GPIO
except RuntimeError:
    log("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")

# Turn off GPIO warnings
GPIO.setwarnings(False)

# Set the GPIO numbering convention to be header pin numbers
GPIO.setmode(GPIO.BOARD)

# Configure each GPIO pin as an output & initialise
GPIO.setup(ST699,   GPIO.OUT, initial=GPIO.LOW)  # controls power to the ST699 controller
GPIO.setup(DHW_OFF, GPIO.OUT, initial=GPIO.LOW)  # HW OFF
GPIO.setup(DHW_ON,  GPIO.OUT, initial=GPIO.LOW)  # HW ON
GPIO.setup(CH_ON,   GPIO.OUT, initial=GPIO.LOW)  # CH ON



 ################
# Login to Gmail #
def login_gmail(secrets):
    global mail
    host = 'imap.gmail.com'
    try:
        mail = imaplib2.IMAP4_SSL(host)
        # Read from .netrc file
        login, account, password = secrets.authenticators(host)
        mail.login(login, password)
    except:
        log("Can't connect to Gmail")
        # Need to call the function to reboot superhub

 #####################
# Read the latest email in selected, 'mailbox'
def read_folder(mailbox):
    global mail
    global varSubject

    # Gmail was timing out & causing the service to stop 
    # so need to check connection to Gmail, if it fails, login again
    try:
        mail.select(mailbox)
    except:
        log("Logged out, need to log back in...")
        login_gmail(secrets)
        mail.select(mailbox)

    typ, data = mail.search(None, 'ALL')
    id_list = data[0].split()

    # Any emails?
    if id_list:
        latest_email_id = int( id_list[-1] )
        for i in range( latest_email_id, latest_email_id-1, -1):
            typ, data = mail.fetch( i, '(RFC822)')

        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_string(response_part[1])

        varSubject = msg['subject']

        # Remove all but the most recent email from mailbox
        for num in enumerate(id_list):
            if (num[0] != 0):
                mail.store(num[0], '+FLAGS', '\\Deleted')

        mail.expunge()
    mail.close()
    return str(varSubject)

 ####################
# Turn Hot Water off #
def HWoff():
    r.hmset('HW', {'status':'off', 'time':datetime.now()})
    GPIO.output(DHW_ON,  GPIO.LOW)
    if GPIO.input(CH_ON) == 0:
        # HW is off & CH is off, so dhw_off needs to be LOW
        log("HW=CH=off so dhw_off is LOW")
        GPIO.output(DHW_OFF, GPIO.LOW)
    else:
        # HW is off & CH is on, so dhw_off needs to be HIGH
        log("HW=off, CH=on so dhw_off is HIGH")
        GPIO.output(DHW_OFF, GPIO.HIGH)

 ###################
# Turn Hot Water on #
def HWon():
    r.hmset('HW', {'status':'on', 'time':datetime.now()})
    # If HW is on, dhw_off is always LOW
    GPIO.output(DHW_OFF, GPIO.LOW)
    GPIO.output(DHW_ON,  GPIO.HIGH)

 ##########################
# Turn Central Heating off #
def CHoff():
    r.hmset('CH', {'status':'off', 'time':datetime.now()})
    # If CH is off, then dhw_off should always be LOW
    log("CH=off so dhw_off is always LOW")
    GPIO.output(DHW_OFF, GPIO.LOW)
    GPIO.output(CH_ON, GPIO.LOW)

 #########################
# Turning Central Heating on #
def CHon(ch_settemp):
    r.hmset('CH', {'status':'on', 'time':datetime.now()})
    # Unpack single element list
    livtemp, = r.hmget('livtemp', 'temp')
    print("   livtemp is: ", livtemp)
    # Check target temperature against actual room temperature
    if (float(livtemp)) < ch_settemp:
        print("room is not warm enough")
        GPIO.output(CH_ON, GPIO.HIGH)
        # Check status of dhw_on to determine state of dhw_off
        if GPIO.input(DHW_ON) == 0:
            log("CH=on & HW=off so dhw_off is HIGH")
            GPIO.output(DHW_OFF, GPIO.HIGH)
        else:
            log("CH=HW=on so dhw_off is LOW")
            GPIO.output(DHW_OFF, GPIO.LOW)
    else:
        print("room is warm enough")
        GPIO.output(CH_ON,   GPIO.LOW)
        GPIO.output(DHW_OFF, GPIO.LOW)

 ############################################
# Check email subject for Hot Water controls #
def check_HW():
#    HW_state = varSubject
    if "HWoff" in varSubject:
        print("Hot Water off!")
        HWoff()
    elif "HWon" in varSubject:
        print("Hot Water on!")
        HWon()

 ##################################################
# Check email subject for Central Heating controls #
def check_CH():
#    CH_state = varSubject
    if 'CHoff' in varSubject:
        print("Central Heating off!")
        CHoff()
    elif 'CH=' in varSubject:
        listSubject = varSubject.split('=')
        ch_settemp = listSubject[1].split()
        print("TARGET TEMPERATURE is.......", ch_settemp[0])
        # Change from str value to float so that a comparison can be made!
        ch_settemp[0] = float(ch_settemp[0])
        r.hmset('target_temp', {'temp':ch_settemp[0], 'time':datetime.now()})
        CHon(ch_settemp[0])



 ##############
# Main Program #
login_gmail(secrets)
while GPIO.input(ST699) == 0:
    try:
        read_folder('st699')
        if 'st699on' in varSubject:
            GPIO.output(ST699,   GPIO.HIGH)
            GPIO.output(DHW_OFF, GPIO.LOW)
            GPIO.output(DHW_ON,  GPIO.LOW)
            GPIO.output(CH_ON,   GPIO.LOW)
        elif 'st699off' in varSubject:
            read_folder('HW')
            check_HW()
            read_folder('CH')
            check_CH()
            time.sleep(60)
    except KeyboardInterrupt:
        # On Ctrl-c cleanup & exit
        mail.logout()
        break
mail.logout()

