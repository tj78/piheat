# piheat
Raspberry Pi heating &amp; hot water controller

For a full background to the project, with reference materials, please read [background.md](./docs/background.md)

# Updates
- Changed whole program from structure to Object Oriented.
- Fixed 'bugs' [#4](../../issues/4) & [#5](../../issues/5).
- Implemented 'enhancements' [#3](../../issues/3) & [#6](../../issues/6).
- Status has been stored in a MySQL database.
- [Web page](./src/piheat.php) in HTML & PHP gets the status from MySQL and displays it (OK on mobile too!).
# To be done...
- Fix ['bug' #2](../../issues/2).
- Change from MySQL to Redis - will reduce the load on the Raspberry Pi and should prolong the life of the SD card.

# Usage
## [piheat.py](./src/piheat.py)
Root privileges are required to run [piheat.py](./src/piheat.py)

    sudo python piheat.py
On Raspbian jessie or later, or other systemd linux OS's,  a service can be set up to run the program on system startup.  An example of this is [piheat.service](./scripts/piheat.service) which should be stored in '/etc/systemd/system/'

A log file will be created in '/var/log/', called piheat.log.  The location of this and the logging level can be edited inside the [piheat.py](./src/piheat.py) file.
## [templog.py](./src/templog.py)
Expects to be on a linux system with a DS18B20 digital one-wire thermometer connected.  It can be hosted on the same system as [piheat.py](./src/piheat.py) or remotely.  A cron job is the simplest method for running the code.  This can be done by typing:

    crontab -e
and then adding a line such as:

    */5 * * * * /usr/bin/python templog.py
where 'templog.py' should be replaced by the full path to the file.  This wil execute the file every 5 minutes.
## [create_temp_log.sql](./scripts/create_temp_log.sql)
You need to log in to the MySQL host server to run this, and type:

    use db;
where 'db' is the name of the database you are using.

    source create_temp_log.sql;
where 'create_temp_log.sql' should be the full path for the file.

# Motivation
Originally this project started from a desire to improve upon my old boiler controller/programmer.  However, it has evolved into an educational aid/tool.  Making improvements to already implemented functionality, or adding new features, is done not only to improve the overall design, but as a starting point for research and a means to test it.

# Getting Started
## Prerequisites:
MySQL, pthyon, and a number of python libraries that will be prompted for when trying to execute [piheat.py](./src/piheat.py)
A .netrc file containing login information for Gmail and the MySQL database, stored in the root user's home directory.
## Installation
On the main page of this repository, click on the 'Clone or download' button, and either click 'Download ZIP', or follow the [GitHub instructions](https://help.github.com/articles/cloning-a-repository/), then follow the [Usage](#usage) instructions.

# Running the tests
## [test_piheat.py](./src/test_piheat.py)
Needs to be executed with root privileges:

    sudo python ./src/test_piheat.py
This will run unit tests for each of the functions in [piheat.py](./src/piheat.py) and generate a log file '/var/log/test_piheat.log'

# License
This project is licensed under the GNU GPL Version 3 License - please see the [LICENSE](./LICENSE) file for details.

# Acknowledgements
[Raspberry Pi powered heating controller](http://www.whizzy.org/2014/01/raspberry-pi-powered-heating-controller-part-1/)    - was invaluable for understanding the original system I was modifying.

[How to build a homemade Nest thermostat](https://www.stuff.tv/features/how-build-homemade-nest-thermostat)    - was used as a starting point for this project.
