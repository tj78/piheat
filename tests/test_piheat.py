#!/usr/bin/env python

# Import the file being tested
from piheat import *



# Remove the 'FileHandler' set in piheat.py so that output from the test suite can be logged in a different file.
log = logging.getLogger()
for hdlr in log.handlers[:]:  # remove all old handlers
    log.removeHandler(hdlr)

# Set the logging level to 'DEBUG' so that ALL messages are sent to the log file.
log.setLevel(logging.DEBUG)

#  'w' denotes that the log will be overwritten each time the tests are run
logfile = logging.FileHandler('/var/log/test_piheat.log', 'w')
log.addHandler(logfile)


# Define a dictionary for storing the results from each test.
# This is stored as {'test name':test result}, where test result is a boolean, True == 'passed', False == 'failed'
test_results = {}


def cleanup_gpio():
    """Set the defined Raspberry Pi GPIO outputs to zero."""
    for relay in gpio_outputs.values():
        GPIO.output(relay, 0)


def check_gpio():
    """Prints to logging output the state of each GPIO output."""
    for relay in gpio_outputs.keys():
        logging.debug(relay, "is set to", GPIO.input(gpio_outputs[relay]))


def test_mysql_temp():
    """Unit test for mysql_temp function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_mysql_temp'")

    # Read the temperature from MySQL
    temp = mysql_temp(secrets)

    if temp:
        # Check the reading is a realistic value
        if (0 < temp < 40):
            return True
        else:
            return False
    else:
        return False


def test_mysql_temp_time():
    """Gets timestamp from MySQL table and checks if it was in the last half hour.

    Testing the time that the temperature was written to MySQL to check that
    the Raspberry Pi recording the living room temperature is still up and running.
    This isn't testing a function in piheat.py, it is simply testing the environment around it.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Runnng 'test_mysql_temp_time'")

    # Connect to db
    host = 'mysql'
    # Read login details from .netrc file
    login, account, password = secrets.authenticators(host)
    logging.debug("Connecting to MySQL database")
    db = MySQLdb.connect(db="site_db", user=login)
    # Setup cursor
    logging.debug("Setup cursor")
    cursor = db.cursor()
    try:
        logging.info("Checking time livtemp was last written")
        cursor.execute("SELECT date FROM temp_log")
        date = cursor.fetchone()
        # MySQL data is returned as a tuple, where the second element is empty.  We just want the first element.
        date = date[0]
        logging.debug(("livtemp was written at:", date.isoformat()))
        # Get today's date
        today = date.today()
        # Calculate the difference between the MySQL table's timestamp and now
        diff = (today - date)
        # Convert this to minutes
        diff = diff.seconds/60
        # If the actual temperature hasn't changed then the date isn't updated,
        #  because of this I check if its changed in the last half hour for testing
        if diff < 30:
            return True
        else:
            return False
    except:
        logging.error("ERROR   - can't read date from temp_log!")
        db.rollback
        return False
    finally:
        db.close()


def test_login_gmail():
    """Unit test for login_gmail function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_login_gmail'")
    if login_gmail(secrets):
        return True
    else:
        return False


def test_read_folder():
    """Unit test for read_folder function.

    This test relies on test_login_gmail passing,
    so if that fails this will also!

    return: boolean
            (where True == 'passed' and False == 'failed)
    """
    logging.info("Running 'test_read_folder'")

    test_passes = 0
    sub_tests   = 5
    mailboxes   = ['st699', 'CH', 'HW']

    # Check that reading a non-existent mailbox returns None
    if read_folder('fail') is None:
        test_passes += 1

    # Check a real mailbox that is empty returns None
    if read_folder('Inbox') is None:
        test_passes += 1

    # Check each used mailbox that it is not empty
    for mailbox in mailboxes:
        if read_folder(mailbox):
            test_passes += 1

    logging.debug(("read_folder passed", test_passes, "of", sub_tests, "sub_tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


def test_HWoff():
    """Unit test for HWoff function.

    The Raspberry Pi can treat an output as an input in order to read its state.
    So we need to set values for 'ch_on' and then check the state of 'dhw_off'

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_HWoff'")

    test_passes = 0
    sub_tests   = 2
    GPIO.output(ch_on, 0)
    HWoff()
    # If the 'HWoff' function is run then 'dhw_on' should always be 0
    if (GPIO.input(dhw_on) == 0) and (GPIO.input(dhw_off) == 0):
        test_passes += 1

    GPIO.output(ch_on, 1)
    HWoff()
    if (GPIO.input(dhw_on) == 0) and (GPIO.input(dhw_off) == 1):
        test_passes += 1

    # End of testing so turn all the relays off
    cleanup_gpio()
    logging.debug(("HWoff passed", test_passes, "of", sub_tests, "sub-tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


def test_HWon():
    """Unit test for HWon function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_HWon'")

    HWon()
    if (GPIO.input(dhw_off) == 0) and (GPIO.input(dhw_on) == 1):
        cleanup_gpio()
        return True
    else:
        cleanup_gpio()
        return False


def test_CHoff():
    """Unit test for CHoff function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_CHoff'")

    CHoff()
    if (GPIO.input(dhw_off) == 0) and (GPIO.input(ch_on) == 0):
        cleanup_gpio()
        return True
    else:
        cleanup_gpio()
        return False


def test_CHon():
    """Unit test for CHon function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_CHon'")

    actual_temp = mysql_temp(secrets)
    test_passes = 0
    sub_tests   = 8

    # Check that the function returns False when actual_temp > target_temp
    if not CHon(actual_temp - 1):
        test_passes += 1
    # Test that if actual_temp > target_temp, ch_on is 0
    if not GPIO.input(ch_on):
        test_passes += 1
    # Test that if ch_on is 0, dhw_off is always 0
    if not GPIO.input(dhw_off):
        test_passes += 1

    # Set dhw_on to 1 and check that dhw_off is still 0
    GPIO.output(dhw_on, 1)
    CHon(actual_temp - 1)
    if not GPIO.input(dhw_off):
        test_passes += 1

    # Check that the function returns True when actual_temp < target_temp
    if CHon(actual_temp + 1):
        test_passes += 1
    if GPIO.input(ch_on):
        test_passes += 1

    GPIO.output(dhw_on, 0)
    CHon(actual_temp + 1)
    if GPIO.input(dhw_off):
        test_passes += 1

    GPIO.output(dhw_on, 1)
    CHon(actual_temp + 1)
    if not GPIO.input(dhw_off):
        test_passes += 1

    # End of testing so turn all the relays off
    cleanup_gpio()
    logging.debug(("CHon passed", test_passes, "of", sub_tests, "sub-tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


def test_check_HW():
    """Unit test for check_HW function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_check_HW'")
    test_passes = 0
    sub_tests   = 3
    # Should return False if varSubject contains 'HWoff'
    if not check_HW('HWoff'):
        test_passes += 1
    # Should return True if varSubject contains 'HWon'
    if check_HW('HWon'):
        test_passes += 1
    # If varSubject does not contain either of the expected strings, check_hw should return None
    if check_HW('fail') is None:
        test_passes += 1
    # End of testing so turn all the relays off
    cleanup_gpio()
    logging.debug(("check_HW passed", test_passes, "of", sub_tests, "sub-tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


def test_check_CH():
    """Unit test for check_CH function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_check_CH'")
    test_passes = 0
    sub_tests   = 6
    # Test the function returns False if 'CHoff' is in varSubject
    if not check_CH('CHoff'):
        test_passes += 1
    # Test the function returns True if 'CH=' is in varSubject
    if check_CH('CH=0'):
        test_passes += 1
    # Check that if the email sets target_temp < actual_temp, ch_on is 0
    if not GPIO.input(ch_on):
        test_passes += 1

    if check_CH('CH=99'):
        test_passes += 1
    # and check that if the email sets target_temp > actual_temp, ch_on is 1
    if GPIO.input(ch_on):
        test_passes += 1

    # If varSubject does not contain either of the expected strings, check_hw should return None
    if check_CH('fail') is None:
        test_passes += 1

    # End of testing so turn all the relays off
    cleanup_gpio()
    logging.debug(("check_HW passed", test_passes, "of", sub_tests, "sub-tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


def test_check_st699():
    """Unit test for check_st699 function.

    return: boolean
            (where True == 'passed' and False == 'failed')
    """
    logging.info("Running 'test_check_st699'")
    test_passes = 0
    sub_tests   = 7

    # Should return False if 'st699off' is in varSubject
    if not check_st699('st699off'):
        test_passes += 1
    # Check 'st699' is 1(off)
    if GPIO.input(st699):
        test_passes += 1

    # Should return True if 'st699on' is in varSubject
    if check_st699('st699on'):
        test_passes += 1
    # Check that all GPIO outputs are set to zero
    if not GPIO.input(st699):
        for relay in gpio_outputs.values():
            if not GPIO.input(relay):
                test_passes += 1

    # If varSubject does not contain either of the expected strings, check_st699 should return None
    if check_st699('fail') is None:
        test_passes += 1

    # End of testing so turn all the relays off
    cleanup_gpio()
    logging.debug(("check_st699 passed", test_passes, "of", sub_tests, "sub-tests"))
    if test_passes == sub_tests:
        return True
    else:
        return False


test_results['mysql_temp'] = test_mysql_temp()
test_results['mysql_temp_time'] = test_mysql_temp_time()
test_results['login_gmail'] = test_login_gmail()
test_results['read_folder'] = test_read_folder()
test_results['HWoff'] = test_HWoff()
test_results['HWon'] = test_HWon()
test_results['CHoff'] = test_CHoff()
test_results['CHon'] = test_CHon()
test_results['check_HW'] = test_check_HW()
test_results['check_CH'] = test_check_CH()
test_results['check_st699'] = test_check_st699()


# Create a list containing the name of each test that failed
failed_tests = []
for testcase in test_results:
    if not test_results[testcase]:
        failed_tests.append(testcase)
if failed_tests:
    logging.error(("The tests that failed are:", failed_tests))
else:
    logging.info("All tests passed succesfully")


logging.info(test_results)

# Clean up & close logging
logging.shutdown()
