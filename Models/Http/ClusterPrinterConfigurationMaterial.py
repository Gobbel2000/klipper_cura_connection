# Copyright (c) 2019 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

from typing import Optional

from ..BaseModel import BaseModel


## Class representing a cloud cluster printer configuration
class ClusterPrinterConfigurationMaterial(BaseModel):

    ## Creates a new material configuration model.
    #  \param brand: The brand of material in this print core, e.g. 'Ultimaker'.
    #  \param color: The color of material in this print core, e.g. 'Blue'.
    #  \param guid: he GUID of the material in this print core, e.g. '506c9f0d-e3aa-4bd4-b2d2-23e2425b1aa9'.
    #  \param material: The type of material in this print core, e.g. 'PLA'.
    def __init__(self, brand: Optional[str] = None, color: Optional[str] = None, guid: Optional[str] = None,
                 material: Optional[str] = None, **kwargs) -> None:
        self.guid = guid
        self.brand = brand
        self.color = color
        self.material = material
        super().__init__(**kwargs)
