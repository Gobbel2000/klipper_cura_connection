# This module is now integrated into [klippo](https://github.com/D4SK/klippo)

klipper\_cura\_connection was developed for [D4SK/klippo](https://github.com/D4SK/klippo)
and used to be included as a submodule in that project.
It is now fully integrated into that repository under the name `cura_connection`.
This repository will no longer be maintained here.

# Klipper Cura Connection

Klipper module that allows network connection with the Ultimaker Cura slicer
software.

When running, this printer can be added as a networked printer in Cura, showing
the status of the current print and any queued print jobs. Print jobs can be
sent from Cura to a connected printer using the _Print over Network_ button that
appears after slicing.

When a camera is installed, the live camera stream can be viewed within Cura.


## Features

* Send print jobs to your printer directly from Cura.
* Queue multiple print jobs to be printed after one another.
* Monitor what's currently printing and its progress.
* Pause or abort the current print job.
* Reorder the queue.
* Get information about the material currently loaded by the printer.
* View a live stream of a camera installed in the printer.


## Security considerations

When using this piece of software you should be aware of what your printer will
be exposed to. The networking doesn't implement any encryption or
authentication measures, meaning anyone in your network can use Cura to control
the printer the same way you can. This shouldn't be an issue if the printer is
located in your private home network that only trusted persons have access to.
But be careful when connecting the printer to a public network, someone could
make your printer execute dangerous G-Codes.

Communication is done via port 80 (and port 8080 for the camera stream). If you
set up your router to forward that port to the printer, literally everyone can
get control over it, so don't do that, ever. If you wish to control the printer
from outside your network, setting up a VPN could be a safe option.


## Connecting with Cura

* Make sure this server is up and running
* Add the printer using the _Add Printer_ dialogue. It should pop as a
  networked printer. The options _Add printer by IP_ and _Add cloud printer_
  are not supported.
* Because we make use of the interface for the Ultimaker 3 printer, your
  printer will always show up as an Ultimaker 3. You will need to change
  some settings to match your printer. This is done under _Machine Settings_
  when the appropriate printer is selected in the Printer preferences. The
  printer must be activated in order to access its settings. The folowing
  values are most important to be changed:
    * Change G-Code flavor to **Marlin**
    * Number of extruders
    * Adjust the _Compatible material diameter_ for each extruder. Ultimaker
      printers use 2.85mm nozzles, but most printers need **1.75mm**.
    * Printer size (X, Y and Z)
    * Set the start and end gcodes as needed
