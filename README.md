# Klipper Cura connection

A Klipper module that enables a network connection with Cura.


## Good to know

Id, key, name are all synonymously used for the name property
set as name in the zeroconf property dictionary.

Device refers to detected, usable printers, Machine refers
to printers added in Cura.

### Great Developer Blogs

1) [GCode](https://community.ultimaker.com/topic/15555-inside-the-ultimaker-3-day-1-gcode/)
2) [Remote access (part 1)](https://community.ultimaker.com/topic/15574-inside-the-ultimaker-3-day-2-remote-access-part-1/)
3) [Remote access (part 2)](https://community.ultimaker.com/topic/15604-inside-the-ultimaker-3-day-3-remote-access-part-2/)
4) [Electronics](https://community.ultimaker.com/topic/15649-inside-the-ultimaker-3-day-4-electronics/)
5) [Developer mode & Linux/Systemd](https://community.ultimaker.com/topic/15664-inside-the-ultimaker-3-day-5-developer-mode-linuxsystemd/)
6) [Active leveling](https://community.ultimaker.com/topic/15687-inside-the-ultimaker-3-day-6-active-leveling/)

### Printer

Status strings as of DevBlog2:

* **idle**
* **printing**
* **error**
* **maintenance**
* **booting**

### Print Jobs

* assigned\_to != None to be "active"
* setPrintJobState sends one of "print", "pause", "abort"
* timeTotal is a continuously updated estimate
* All status strings as of
    `KlipperNetworkPrinting/resources/qml/MonitorPrintJobProgressBar.qml`
    and DevBlog2 (indicaded by #)
    * **wait_cleanup** stopped (aborted or finished)
    * **finished**
    * **sent_to_printer**
    * **pre_print** Active leveling?, Heating #
    * **aborting** Unused by Cura Connect, used by Cura
    * **aborted** see above
    * **pausing** #
    * **paused** #
    * **resuming** #
    * **queued** needed to show in Cura queue
    * **printing** #
    * **post_print** Cooling down, stopping #

### Possible BOM Numbers:

BOM     |printer\_type
--------|-------------------
9066    |ultimaker3
9511    |ultimaker3\_extended
213482  |ultimaker\_s3
9051    |ultimaker\_s5
214475  |ultimaker\_s5


## TODO

* Figure out if it is really necessary to disguise as an Ultimaker3  
    Otherwise custom sizes will need to be set manually.


## What's happening in Cura?

* The Output plugin detects networked printers via zeroconf
* They get checked for some values in the zeroconf property dict
* When the user adds that device, a new machine (Stack) is created
* Further communication happens via the IP address on HTTP
* On Startup missing _material_ xml files are sent to the printer
* Every 2 seconds _\_update()_ is called on all device objects.
    This continuously requests _printers_ and _print_jobs_ status data
* When clicking _Print over network_ the file is sent in a multipart POST request.


## Setup

Executing `install.sh` sets everything up as needed.
The following steps are made:

Install zeroconf:

`pip3 install zeroconf==0.28.5`

### Port redirection

Root privileges are required to listen to port 80, the default HTTP port.
Because of that we redirect packets to 8080 and listen to that instead.
We then make these persistent with installing iptables-persistent.
With the configurations set first the installation is automatic and the
rules we just set are written to /etc/iptables/rule.v4.

```bash
sudo iptables -A PREROUTING -t nat -p tcp --dport 80 -j REDIRECT --to-ports 8008
echo iptables-persistent iptables-persistent/autosave_v4 boolean false | sudo debconf-set-selections
echo iptables-persistent iptables-persistent/autosave_v6 boolean false | sudo debconf-set-selections
sudo apt -y install iptables-persistent
```

### Mjpg Streamer

Install mjpg-streamer from source:
```bash
git clone https://github.com/jacksonliam/mjpg-streamer.git
cd mjpg-streamer/mjpg-streamer-experimental
make
sudo make install
```

The systemd service mjpg\_streamer.service in this directory can be used
to start mjpg\_streamer.


## Info on possible requests

Most come from `KlipperNetworkPrinting/src/Network/ClusterApiClient.py`

|Name                   |Type   |URL (/cluster-api/v1 if not !) |Data (sent or requested)       |Requested at           |Implemented
|-----------------------|-------|-------------------------------|-------------------------------|-----------------------|-----------
|getSystem              |GET    |!/api/v1/system                |PrinterSystemStatus            |At manual connection   |False
|getMaterials           |GET    |/materials                     |[ClusterMaterial]              |At startup             |True
|getPrinters            |GET    |/printers                      |[ClusterPrinterStatus]         |Periodically           |True
|getPrintJobs           |GET    |/print\_jobs                   |[ClusterPrintJobStatus]        |Periodically           |True
|setPrintJobState       |PUT    |/print\_jobs/UUID/action       |{action:(pause\|print\|abort)} |GUI                    |True
|movePrintJobToTop      |POST   |/print\_jobs/UUID/action/move  |{to\_position:0,list:queued}   |GUI                    |True
|forcePrintJob          |PUT    |/print\_jobs/UUID              |{force:True}                   |GUI (Override)         |True
|deletePrintJob         |DELETE |/print\_jobs/UUID              |None                           |GUI                    |True
|getPrintJobPreviewImage|GET    |/print\_jobs/UUID/preview\_image|Image bytes (PNG file works)  |At job creation        |True
|startPrintJobUpload    |POST   |/print\_jobs/                  |owner & .gcode file (MIME)     |"Print over Network"   |True
|sendMaterials          |POST   |/materials/                    |.xml.fdm-material file (MIME)  |Sent if not on printer |True
|stream                 |GET    |!/?action=stream               |Redirect                       |Open stream            |True
|snapshot               |GET    |!/?action=snapshot             |Redirect                       |None                   |True
|?                      |GET    |!/print\_jobs                  |?                              |Browser view           |False
