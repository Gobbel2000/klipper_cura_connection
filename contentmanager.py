import time
import uuid

import curaconnection
from Models.Http.ClusterPrinterStatus import ClusterPrinterStatus
from Models.Http.ClusterPrintJobStatus import ClusterPrintJobStatus


class ContentManager:

    def __init__(self):
        self.printer_status = ClusterPrinterStatus(
            enabled=True,
            firmware_version=curaconnection.version,
            friendly_name="Super Sayan Printer",
            ip_address="192.168.178.50",
            machine_variant="Ultimaker 3",
            status="enabled",
            unique_name="super_sayan_printer",
            uuid=self.new_uuid(),
            configuration=[{"extruder_index": 0}],
            )
        self.print_jobs = []
    
    def add_print_job(self, 
        new_print_job = ClusterPrintJobStatus(
            created_at=None,
            force=False,
            machine_variant=None,
            name=None,
            started=False,
            status=None,
            time_total=None,
            uuid=self.new_uuid(),
            configuration=[{"extruder_index": 0}],
            constraints=None,
            )
        self.print_jobs.append(new_print_job)

    @staticmethod
    def new_uuid():
        """Returns a newly generated UUID"""
        return str(uuid.uuid1())

    def get_printer_status(self):
        """
        Update the data and return the printer status serialized
        into a dictionary that can be parsed by json.dump.
        """
        #TODO Update
        return self.printer_status.serialize()

    def get_print_jobs(self):
        return [m.serialize() for m in self.print_jobs]
