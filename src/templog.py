#!/usr/bin/env python

"""Reads the temperature from a DS18B20 digital one-wire thermometer.

The temperature is converted to celcius and written to a MySQL database.
"""
import time

import MySQLdb
import logging
# Appends logging messages to the specified file, with a timestamp for each entry
logging.basicConfig(filename='/var/log/livtemp.log', level=logging.INFO, format='%(asctime)s %(message)s')

import netrc
secrets = netrc.netrc()


# Points to the DS18B20, where 28-...... is the serial number of the probe
temp_sensor = "/sys/devices/w1_bus_master1/28-051686a14fff/w1_slave"



def temp_raw():
    """Reads the raw data from DS18B20

    return: list
                lines is a list of strings where each element of the list is a line
                from the file being read
    """
    f = open(temp_sensor, 'r')
    lines = f.readlines()
    f.close()
    return lines


def read_temp():
    """Gets the raw data, finds the temperature and converts to celcius.

    return: float
    """
    lines = temp_raw()
    # Check for a successful temperature reading, will return "YES" at end of reading,
    while lines[0].strip()[-3:] != 'YES':
        # if not successful, sleep for 0.2sec & repeat
        time.sleep(0.2)
        lines = temp_raw()

    # Reads the temperature & processes into celcius
    temp_output = lines[1].find('t=')
    if temp_output != -1:
        temp_string = lines[1].strip()[temp_output+2:]
        temp_c = float(temp_string) / 1000.0
    return temp_c


def update_mysql(temp_c):
    """Updates a temperatue value in a MySQL database.

    temp_c: float
    return: boolean
    """
    # Read from .netrc
    login, account, password = secrets.authenticators('mysql')
    try:
        logging.debug("Connecting to MySQL database")
        db = MySQLdb.connect(db="site_db", host=account)

        logging.debug("Setup cursor")
        cursor = db.cursor()

        logging.debug("Update temperature")
        cursor.execute("UPDATE temp_log SET livtemp=(%s)",(temp_c,))
        db.commit()
        return True
    except:
        db.rollback()
        return False
    finally:
        cursor.close()
        db.close()


def main():
    """Gets a temperature reading and updates a database."""
    temp_c = read_temp()
    logging.debug(("Living room temperature is", temp_c))

    success = update_mysql(temp_c)
    if success:
        logging.debug("Database was updated successfully")
    else:
        logging.error("Error - Database could not be updated")


# Only run the main function when not under test
if __name__ == "__main__":
    main()
    
