from datetime import datetime
import os
import uuid
import xml.etree.ElementTree as ET

from Models.Http.ClusterMaterial import ClusterMaterial
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
            status="enabled",
            unique_name="super_sayan_printer",
            uuid=self.new_uuid(),
            configuration=[{"extruder_index": 0,
                "material": {"brand": "Generic", "guid": "60636bb4-518f-42e7-8237-fe77b194ebe0",
                "color": "#8cb219", "material": "ABS"}}],
            )
        self.print_jobs_by_uuid = {} # type: {UUID (str): ClusterPrinJobStatus}
        self.materials = [] # type: [ClusterMaterial]
        self.parse_materials()

    def parse_materials(self):
        """
        Read all material files and generate a ClusterMaterial Model.
        For the model only the GUID and version fields are required.
        """
        ns = {"m": "http://www.ultimaker.com/material", "cura": "http://www.ultimaker.com/cura"}
        for fname in os.listdir(self.module.MATERIAL_PATH):
            if not fname.endswith(".xml.fdm_material"):
                continue
            path = os.path.join(self.module.MATERIAL_PATH, fname)
            tree = ET.parse(path)
            root = tree.getroot()
            metadata = root.find("m:metadata", ns)
            uuid = metadata.find("m:GUID", ns).text
            version = int(metadata.find("m:version", ns).text)
            self.add_material(uuid, version)

    def add_material(self, uuid, version):
        new_material = ClusterMaterial(
            guid=uuid,
            version=version,
            )
        self.materials.append(new_material)

    def add_print_job(self, filename, time_total=10000, force=False, owner=None):
        uuid_ = self.new_uuid()
        if self.print_jobs_by_uuid:
            status = "pause"
        else:
            status = "print"
            self.module.send_print(filename)

        new_print_job = ClusterPrintJobStatus(
            created_at=self.get_time_str(),
            force=force,
            machine_variant="Ultimaker 3",
            name=filename,
            started=False,
            status=status,
            time_total=time_total,
            time_elapsed=0,
            uuid=uuid_,
            configuration=[{"extruder_index": 0}],
            constraints=[],
            # Optional
            owner=owner,
            printer_uuid=self.printer_status.uuid,
            assigned_to=self.printer_status.unique_name,
            )
        self.print_jobs_by_uuid[uuid_] = new_print_job

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
