from datetime import datetime
import uuid

from Models.Http.ClusterMaterial import ClusterMaterial
from Models.Http.ClusterPrinterStatus import ClusterPrinterStatus
from Models.Http.ClusterPrintJobStatus import ClusterPrintJobStatus


class ContentManager(object):

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
        self.print_jobs_by_uuid = {} # type: {UUID (str): ClusterPrinJobStatus}
        self.materials = [] # type: [ClusterMaterial]

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

    def add_material(self, uuid, version):
        new_material = ClusterMaterial(
            guid=uuid,
            version=version,
            )
        self.materials.append(new_materials)

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

    def get_printer_status(self):
        return [self.printer_status.serialize()]

    def get_print_jobs(self):
        return [m.serialize() for m in self.print_jobs_by_uuid.values()]

    def get_materials(self):
        return [m.serialize() for m in self.materials]
