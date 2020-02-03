# Copyright (c) 2019 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.
from ..BaseModel import BaseModel


## Class representing the system status of a printer.
class PrinterSystemStatus(BaseModel):

    def __init__(self, guid, firmware, hostname, name, platform, variant,
                 hardware, **kwargs
                 ):
        self.guid = guid
        self.firmware = firmware
        self.hostname = hostname
        self.name = name
        self.platform = platform
        self.variant = variant
        self.hardware = hardware
        super().__init__(**kwargs)
