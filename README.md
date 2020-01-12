# Klipper Cura connection

A Klipper module that enables a network connection with Cura.

## Important files to look at:

* cura/Machines/Models/DiscoveredPrintersModel.py
* cura/PrinterOutput/NetworkedPrinterOutputDevice.py

### Objects

* GlobalStack (Machine) and ContainerStack etc.
* OutputDevice(Manager)

## Good to know

Id, key, name are all synonymously used for the name property
set as name in the zeroconf property dictionary.

Device refers to detected, usable printers, Machine refers
to printers added in Cura.

## TODO

* HTTP server
    * Receive files
    * Decompress files
    * Handle other messages and requests
    * Send data
* Convince cura that it can send files that way
    (Currently a restart of this zeroconf part is needed)
* Figure out if it is really necessary to disguise as an Ultimaker3
    Probably not, as custom sizes etc. will need to be set :/
* Figure out a way to determine a unique printer name (hostname?)
* Receive IPv4 Address from network manager
    (dbus implemented function exists: kgui/nm\_dbus.py)
* The server needs to be run as root to be able to listen to
    port 80. Workaround needed.

## What's happening in Cura?

* The Output plugin detects networked printers via zeroconf
* They get checked for some values in the propertie dict
* When the user adds that device, a new machine (Stack) is created
* Further communication happens via the IP address on HTTP

## Setup

python-libcharon needed to be installed for me so that the
UFPWriter and UFPReader plugins of Cura can work. Otherwise
an exception is generated when trying to send a file.

