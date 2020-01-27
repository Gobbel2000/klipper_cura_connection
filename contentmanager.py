import uuid

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
            uuid=str(uuid.uuid1()),
            configuration=[{"extruder_inder": 0}],
            )
