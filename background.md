# Background
This project started from a desire to improve upon the basic boiler programmer that was currently installed, which only allowed two time periods (switching on and off twice each day, every day), and the hot water and central heating could each be set to 'Off', 'Continuous', 'Once', or 'Twice', which didn't allow for much flexibility.


Looking around for some inspiration I found an online article (https://www.stuff.tv/features/how-build-homemade-nest-thermostat) that acted as a starting point for my code.  A lot of instances where other people are doing the same thing, including in this example, the Raspberry Pi is only controlling the heating, probably because it is being used with a combi-boiler so there is hot water on demand.  However, I have a separate hot water tank and I wanted to make sure that I can turn the boiler on to produce hot water independent from the central heating timings if needed.


The article above uses IFTTT (https://ifttt.com/) as a major part of the control system, but when I tested working this way I found there were very inconsistent delays between a time being set and an email being sent, which wasn't what I was looking for.

What I did like about the setup was the use of a Gmail account, which allows the Raspberry Pi to receive commands via email from anywhere (for controlling the heating/hot water remotely), as long as there was an active internet connection.

The Gmail account also has a linked calendar that could be used to do the scheduling.  In the calendar an event can be created with a command as the 'Event Title', if 'Notifications' is set to 'Email', with '0 minutes' as the warning, it will send an email to the account owner with the 'Event Title' in the subject line, at the time the event is set for.

I have found this method to be very reliable and it is easy to set singular events or recurring events, or to make changes to these events.  In this way the schedule can be set as far in advance as you like, and it can be synced with a computer through a browser, or to a phone using an app.

I've set up filters on the email account so that it will separate emails with valid commands into separate folders ('st699, 'ch', and 'hw'), but only from specified email addresses (including the calendar notifications).  This seemed an easy way of implementing an 'allowed users' list.

## Commands
The valid commands are:
    st699on:    switches the old programmer on, and all other relays off
    st699off:   switches the old programmer off

    HWoff:      switches the hot water off
    HWon:       switches the hot water on

    CHoff:      switches the central heating off
    CH=:        switches the central heating on until it reaches the temperature specified after the '='
                    When the target temperature value is extracted by the python code it is converted to a 'float' for comparison with the actual room temperature.

## Setup
I already had a Raspberry Pi in my living room, which is where I wanted to measure the room temperature.  So I connected a cheap ds18b20 temperature sensor, and I've set up to run a cron job every 5 minutes, writing the temperature to a MySQL database on my new Raspberry Pi Zero.

I chose the Raspberry Pi Zero to be the main controller as it is cheap and small, so with the addition of a micro USB WiFi dongle it can be placed near to the existing programmer and still receive the temperature from the probe in the living room.

In order to keep the wiring simple I wanted to replace the each signal that the old programmer produced.  These signals are shown in the following ASCII diagram:

All off | HW only | CH only | All on
:------:|:-------:|:-------:|:------:
dhw_off | 0       | 1       | 0
dhw_on	| 0       | 0       | 1
ch_on   | 0       | 1       | 1

The names dhw_off (hot water off), dhw_on (hot water on) and ch_on (central heating on) are taken from the old programmer's manual.  The dhw_off signal is needed to operate a valve that allows the hot water from the pump to be directed to the radiators, or the hot water tank, or both.  This website (https://www.whizzy.org/2014/01/raspberry-pi-powered-heating-controller-part-1/) explains and illustrates this very well.

The Raspberry Pi can't control the boiler directly because it can only produce up to 3.3V, not the required 240V.  So the Raspberry Pi is used to control a set of relays that do the actual switching, whilst separating the 3.3V and 240V circuits.  A word of warning for anyone trying to attempt a project like this, MAINS VOLTAGE IS VERY DANGEROUS, so if you're not confident in what you are doing, DO NOT TOUCH IT!  If you decide to go ahead, take all necessary precautions and make sure that the sockets and circuitry you are working on are definitely off.

For the relays, I've used the ModMyPI PiOT Relay Board (https://www.modmypi.com/raspberry-pi/breakout-boards/modmypi/modmypi-piot-relay-board) because I was confident that it would be OK to connect it to the mains voltage (through a fused connection) without any issues.  Also, it could be directly connected to the Raspberry Pi Zero, and then fully enclosed, so as to prevent accidents.

The relays on the board are of the SPDT (Single Pole Double Throw) type (http://www.electronics-tutorials.ws/io/io_5.html).



The ASCII diagram below shows a representation of the connections in my setup.

##### KEY
    COM - Common
    NC  - Normally Closed
    NO  - Normally Open
    S/L - Switched Live:  has a fuse between it and the mains live
    +   - shows where lines that cross are connected, i.e. all the COM connections are connected to S/L

     ===============================
    |       Raspberry Pi Zero       |
    |                               |
    |                       microUSB|--->WiFi dongle
    |                               |
    |                               |
    |GPIO     GPIO      GPIO    GPIO|
    | 11       13        15      16 | 
     ===============================
       |        |         |       |
     st699   dhw_off   dhw_on   ch_on
       |        |         |       |
       |        |         |       |
     ================================================
    |             ModMyPi PiOT Relay Board           |
    |                                                |
    | NO COM NC     NO COM NC   NO COM NC  NO COM NC |
     ================================================
      |   |  |      |   |  |    |   |  |   |   |  |
          |  |      |   |       |   |      |   |
          +=============+===========+==========+
          |  |      |           |          |
         S/L |      |           |          |
             |      |           |          |
             |   dhw_off      dhw_on     ch_on
             |
           powers
          the ST699



By powering the ST699 from the NC connection, it means that by default the old programmer is powered up if the Raspberry Pi is shut down.  It is also possible for piheat.py to hand back control to the old programmer if wanted.

The original system has a number of safety features built in, so by just replacing the signals from the old programmer I don't have to worry about controlling the valve (dhw_off already does this), the hot water tank thermostat can still cut off at the same temperature, and the room thermostat can still be used if there is any problem with the digital temperature probe or it sending its data.

## Issues
This setup has now been working successfully for more than three months.  The only issues have been:

    1. Getting automatically disconnected from Gmail - this has been fixed by checking to see if we are logged in, if not, log back in.  In a future update this will be fixed more elegantly by using the IMAP IDLE command.

    2. On the rare occasions that we have lost our internet connection, piheat.py crashes because it can't connect to Gmail.  I have already written a python program that will connect to my router and reset it, which usually fixes the problem.  This will be incorporated into a future update when I've found a satisfactory solution.
