from datetime import datetime
import os
import uuid
import xml.etree.ElementTree as ET

from Models.Http.ClusterMaterial import ClusterMaterial
from Models.Http.ClusterPrintCoreConfiguration import (
        ClusterPrintCoreConfiguration)
from Models.Http.ClusterPrinterStatus import ClusterPrinterStatus
from Models.Http.ClusterPrintJobStatus import ClusterPrintJobStatus


class ContentManager(object):

    def __init__(self, module):
        self.module = module

        self.printer_status = ClusterPrinterStatus(
            enabled=True,
            firmware_version=self.module.VERSION,
            friendly_name="Super Sayan Printer",
            ip_address=self.module.ADDRESS,
            machine_variant="Ultimaker 3",
            # One of: idle, printing, error, maintenance, booting
            status="idle",
            unique_name="super_sayan_printer",
            uuid=self.new_uuid(), # Use consistent UUID or not?
            configuration=[],
        )
        self.print_jobs = [] # type: [ClusterPrintJobStatus]
        self.materials = [] # type: [ClusterMaterial]

    def start(self):
        """
        Add to the list of local materials.
        Must be called later so that filament_manager is available.
        """
        for guid in self.module.filament_manager.guid_to_path:
            version = int(self.module.filament_manager.get_material_info(guid,
                    "./m:metadata/m:version"))
            self.materials.append(ClusterMaterial(
                guid=guid,
                version=version,
            ))

    def get_print_job_status(self, path):
        return ClusterPrintJobStatus(
            created_at=self.get_time_str(),
            force=False,
            machine_variant="Ultimaker 3",
            name=os.path.basename(path),
            started=False,
            # One of: wait_cleanup, finished, sent_to_printer, pre_print,
            # pausing, paused, resuming, queued, printing, post_print
            # (possibly also aborted and aborting)
            status="queued",
            time_total=0, #TODO set from the beginning
            time_elapsed=0,
            uuid=self.new_uuid(),
            configuration=self.printer_status.configuration, #TODO
            constraints=[],
        )

    def add_test_print(self, path):
        """
        Testing only: add a print job outside of klipper and pretend
        we're printing.
        """
        self.print_jobs.append(self.get_print_job_status(path))
        self.print_jobs[0].status = "printing"
        self.print_jobs[0].started = True
        self.print_jobs[0].time_total = 10000
        self.print_jobs[0].time_elapsed += 2
        self.print_jobs[0].assigned_to = self.printer_status.uuid

        self.printer_status.status = "printing"

    def update_printers(self):
        """Update currently loaded material (TODO) and state"""
        configuration = []
        fm = self.module.filament_manager
        loaded_materials = fm.loaded_materials
        for i, material in enumerate(loaded_materials):
            if material is None:
                continue
            guid = material[0]
            brand = fm.get_material_info(guid, "./m:metadata/m:name/m:brand")
            color = fm.get_material_info(guid, "./m:metadata/m:name/m:color")
            material = fm.get_material_info(guid,
                    "./m:metadata/m:name/m:material")
            configuration.append(ClusterPrintCoreConfiguration(
                extruder_index=i,
                material={
                    "guid": guid,
                    "brand": brand,
                    "color": color,
                    "material": material,
                },
            ))
        self.printer_status.configuration = configuration
        if self.module.testing:
            return
        state = self.module.sdcard.get_status()["state"]
        if state in {"printing", "paused"}:
            self.printer_status.status = "printing"
        else:
            self.printer_status.status = "idle"

    def update_print_jobs(self):
        """Read queue, Update status, elapsed time"""
        s = self.module.sdcard.get_status()

        # Update self.print_jobs with the queue
        new_print_jobs = []
        for i, path in enumerate(s["queued_files"]):
            print_job = None
            fname = os.path.basename(path)
            for j, pj in enumerate(self.print_jobs):
                if pj.name == fname:
                    print_job = self.print_jobs.pop(j)
                    break
            if print_job is None: # Newly add print job
                new_print_jobs.append(self.get_print_job_status(path))
            else:
                new_print_jobs.append(print_job)
        self.print_jobs = new_print_jobs

        if self.print_jobs: # Update first print job if there is one
            elapsed = self.module.sdcard.get_printed_time()
            self.print_jobs[0].time_elapsed = int(elapsed)
            self.print_jobs[0].assigned_to = self.printer_status.uuid
            if s["estimated_remaining_time"] is None:
                self.print_jobs[0].time_total = int(elapsed + 10000) #FIXME
            else:
                self.print_jobs[0].time_total = int(
                        s["estimated_remaining_time"] + elapsed)

            if s["state"] in {"printing", "paused"}: # Should cover all cases
                self.print_jobs[0].status = s["state"]
            if s["state"] == "printing":
                self.print_jobs[0].started = True

    @staticmethod
    def new_uuid():
        """Returns a newly generated UUID as a str"""
        # uuid1() returns a uuid based on time and IP address
        # uuid4() would generate a completely random uuid
        return str(uuid.uuid1())

    @staticmethod
    def get_time_str():
        """Returns the current UTC time in a string in ISO8601 format"""
        now = datetime.utcnow()
        return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

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
