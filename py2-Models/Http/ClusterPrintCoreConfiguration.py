# Copyright (c) 2019 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.
from .ClusterPrinterConfigurationMaterial import ClusterPrinterConfigurationMaterial
from ..BaseModel import BaseModel


## Class representing a cloud cluster printer configuration
#  Also used for representing slots in a Material Station (as from Cura's perspective these are the same).
class ClusterPrintCoreConfiguration(BaseModel):

    ## Creates a new cloud cluster printer configuration object
    #  \param extruder_index: The position of the extruder on the machine as list index. Numbered from left to right.
    #  \param material: The material of a configuration object in a cluster printer. May be in a dict or an object.
    #  \param nozzle_diameter: The diameter of the print core at this position in millimeters, e.g. '0.4'.
    #  \param print_core_id: The type of print core inserted at this position, e.g. 'AA 0.4'.
    def __init__(self, extruder_index, material = None, print_core_id = None, **kwargs):
        self.extruder_index = extruder_index
        self.material = self.parseModel(ClusterPrinterConfigurationMaterial, material) if material else None
        self.print_core_id = print_core_id
        super().__init__(**kwargs)
