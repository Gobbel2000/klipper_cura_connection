from datetime import datetime
import os
import uuid as uuid_lib

from .Models.Http.ClusterMaterial import ClusterMaterial
from .Models.Http.ClusterPrintCoreConfiguration import (
        ClusterPrintCoreConfiguration)
from .Models.Http.ClusterPrinterStatus import ClusterPrinterStatus
from .Models.Http.ClusterPrintJobStatus import ClusterPrintJobStatus


class ContentManager:

    def __init__(self, module):
        self.module = module
        self.reactor = module.reactor
        self.printer_status = ClusterPrinterStatus(
            enabled=True,
            firmware_version=self.module.VERSION,
            friendly_name=self.module.NAME, # hostname
            ip_address=self.module.ADDRESS,
            machine_variant="Ultimaker 3",
            # One of: idle, printing, error, maintenance, booting
            status="idle",
            unique_name=self.get_mac_address(),
            uuid=self.new_uuid(),
            configuration=[],
        )
        self.klippy_jobs = []
        self.print_jobs = [] # type: [ClusterPrintJobStatus]
        # type: [ClusterMaterial]
        self.materials = self.reactor.cb(self.obtain_material, process='printer', wait=True)

    @staticmethod
    def obtain_material(e, printer):
        """
        Add to the list of local materials.
        Must be called later so that filament_manager is available.
        """
        fm = printer.objects['filament_manager']
        return [ClusterMaterial(
            guid=guid,
            version=int(fm.get_info(guid, "./m:metadata/m:version")))
                for guid in fm.guid_to_path]

    def create_cluster_print_job(self, klippy_pj):
        """Return a print job model for the given path"""
        md = self.module.metadata.get_metadata(klippy_pj.path)
        configuration = []
        for i in range(md.get_extruder_count()):
            configuration.append(ClusterPrintCoreConfiguration(
                extruder_index=i,
                material={
                    "guid": md.get_material_guid(i),
                    "brand": md.get_material_brand(i),
                    "color": md.get_material_info("./m:metadata/m:name/m:color", i),
                    "material": md.get_material_type(i),
                },
                print_core_id="AA 0.4",
            ))
        return ClusterPrintJobStatus(
            created_at=self.get_time_str(),
            force=False,
            machine_variant="Ultimaker 3",
            name=os.path.basename(klippy_pj.path),
            started=False,
            # One of: wait_cleanup, finished, sent_to_printer, pre_print,
            # pausing, paused, resuming, queued, printing, post_print
            # (possibly also aborted and aborting)
            status="queued",
            time_total=md.get_time() or 0,
            time_elapsed=0,
            uuid=klippy_pj.uuid,
            configuration=configuration,
            constraints=[],
        )

    def add_test_print(self, path):
        """
        Testing only: add a print job outside of klipper and pretend
        we're printing.
        """
        self.print_jobs.append(self.create_cluster_print_job(path))
        self.print_jobs[0].status = "printing"
        self.print_jobs[0].started = True
        self.print_jobs[0].time_total = 10000
        self.print_jobs[0].time_elapsed += 2
        self.print_jobs[0].assigned_to = self.printer_status.uuid
        self.printer_status.status = "printing"

    @staticmethod
    def obtain_loaded_material(e, printer):
        fm = printer.objects['filament_manager']
        loaded_materials = fm.material["loaded"]
        materials = []
        for m in loaded_materials:
            guid = m['guid']
            if guid:
                materials.append({
                    'guid': guid,
                    'brand': fm.get_info(guid, "./m:metadata/m:name/m:brand"),
                    'color': fm.get_info(guid, "./m:metadata/m:name/m:color"),
                    'material': fm.get_info(guid, "./m:metadata/m:name/m:material")})
            else:
                materials.append(None)
        return materials

    @classmethod
    def obtain_material_printjobs(cls, e, printer):
        materials = cls.obtain_loaded_material(e, printer)
        printjobs = cls.obtain_print_jobs(e, printer)
        return materials, printjobs

    def update_printers(self):
        """Update currently loaded material and state"""
        materials, klippy_jobs = self.reactor.cb(
                self.obtain_material_printjobs, wait=True)
        self.printer_status.configuration = [ClusterPrintCoreConfiguration(
            extruder_index=i,
            print_core_id="AA 0.4",
            material=material)
                for i, material in enumerate(materials)]
        if self.module.testing:
            return

        if klippy_jobs and klippy_jobs[0].state in {
                "printing", "paused", "pausing", "aborting"}:
            self.printer_status.status = "printing"
        else:
            self.printer_status.status = "idle"

    @staticmethod
    def obtain_print_jobs(e, printer):
        return printer.objects['virtual_sdcard'].get_status()['jobs']

    @staticmethod
    def obtain_remaining_time(e, printer):
        return printer.objects['print_stats'].get_print_time_prediction()[0]

    @classmethod
    def obtain_printjobs_time(cls, e, printer):
        time = cls.obtain_remaining_time(e, printer)
        printjobs = cls.obtain_print_jobs(e, printer)
        return printjobs, time

    def update_print_jobs(self):
        """Read queue, Update status, elapsed time"""
        # Update self.print_jobs with the queue
        klippy_jobs, remaining = self.reactor.cb(
                self.obtain_printjobs_time, wait=True)
        new_print_jobs = []
        for klippy_job in klippy_jobs:
            print_job = None
            # Find first cura print job with the same name
            for j, cura_pj in enumerate(self.print_jobs):
                if cura_pj.name == os.path.basename(klippy_job.path):
                    print_job = self.print_jobs.pop(j)
                    break
            if print_job is None: # Newly added print job
                new_print_jobs.append(self.create_cluster_print_job(klippy_job))
            else:
                new_print_jobs.append(print_job)
        self.print_jobs = new_print_jobs
        self.klippy_jobs = klippy_jobs

        # Update first print job if there is one
        if self.print_jobs:
            elapsed = klippy_jobs[0].get_printed_time() if klippy_jobs else 0

            self.print_jobs[0].time_elapsed = int(elapsed)
            self.print_jobs[0].assigned_to = self.printer_status.uuid
            self.print_jobs[0].time_total = int(elapsed +
                    (1 if remaining is None else remaining))

            # State
            self.print_jobs[0].status = klippy_jobs[0].state
            if klippy_jobs[0].state == "printing":
                self.print_jobs[0].started = True

    @staticmethod
    def new_uuid():
        """Returns a newly generated UUID as a str"""
        # uuid4() generates a completely random uuid
        return str(uuid_lib.uuid4())

    @staticmethod
    def get_time_str():
        """Returns the current UTC time in a string in ISO8601 format"""
        now = datetime.utcnow()
        return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    @staticmethod
    def get_mac_address():
        """Return the mac address in form XX:XX:XX:XX:XX:XX"""
        raw = uuid_lib.getnode()
        hex_ = []
        while raw:
            hex_.insert(0, hex(int(raw % 0x100))) # raw is long
            raw = raw >> 8
        return ":".join([i.lstrip("0x").zfill(2) for i in hex_])

    def uuid_to_print_job(self, uuid):
        """
        Return a tuple (index, print job) for the print job with the given
        UUID.  Return (None, None) if the UUID could not be found.
        """
        return next(iter((i, pj) for i, pj in enumerate(self.print_jobs)
            if pj.uuid == uuid), (None, None))

    def get_printer_status(self):
        self.update_printers()
        return [self.printer_status.serialize()]
    def get_print_jobs(self):
        if not self.module.testing:
            self.update_print_jobs()
        return [m.serialize() for m in self.print_jobs]
    def get_materials(self):
        return [m.serialize() for m in self.materials]
