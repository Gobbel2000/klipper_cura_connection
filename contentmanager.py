from datetime import datetime
import uuid

#import curaconnection
from Models.Http.ClusterPrinterStatus import ClusterPrinterStatus
from Models.Http.ClusterPrintJobStatus import ClusterPrintJobStatus


class ContentManager:

    def __init__(self):
        self.printer_status = ClusterPrinterStatus(
            enabled=True,
            firmware_version="5.2.11",
            friendly_name="Super Sayan Printer",
            ip_address="192.168.178.50",
            machine_variant="Ultimaker 3",
            status="enabled",
            unique_name="super_sayan_printer",
            uuid=self.new_uuid(),
            configuration=[{"extruder_index": 0}],
            )
        self.print_jobs_by_uuid = {} # {UUID (str): ClusterPrinJobStatus}
    
    def add_print_job(self, filename, time_total=0, force=False):
        uuid = self.new_uuid()
        new_print_job = ClusterPrintJobStatus(
            created_at=self.get_time_str(),
            force=force,
            machine_variant="Ultimaker 3",
            name=filename,
            started=False,
            status="pause",
            time_total=time_total,
            uuid=uuid,
            configuration=[{"extruder_index": 0}],
            constraints=[],
            )
        self.print_jobs_by_uuid[uuid] = new_print_job

    @staticmethod
    def new_uuid():
        """Returns a newly generated UUID"""
        return str(uuid.uuid1())

    @staticmethod
    def get_time_str():
        """Returns the current time in a string as parsed by BaseModel.parseDate()"""
        now = datetime.utcnow()
        return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def get_printer_status(self):
        return self.printer_status.serialize()

    def get_print_jobs(self):
        return [m.serialize() for m in self.print_jobs]
