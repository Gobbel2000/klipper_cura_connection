# Copyright (c) 2019 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.
from .ClusterBuildPlate import ClusterBuildPlate
from .ClusterPrintJobConfigurationChange import ClusterPrintJobConfigurationChange
from .ClusterPrintJobImpediment import ClusterPrintJobImpediment
from .ClusterPrintCoreConfiguration import ClusterPrintCoreConfiguration
from .ClusterPrintJobConstraint import ClusterPrintJobConstraints
from ..BaseModel import BaseModel


## Model for the status of a single print job in a cluster.
class ClusterPrintJobStatus(BaseModel):

    ## Creates a new cloud print job status model.
    #  \param assigned_to: The name of the printer this job is assigned to while being queued.
    #  \param configuration: The required print core configurations of this print job.
    #  \param constraints: Print job constraints object.
    #  \param created_at: The timestamp when the job was created in Cura Connect.
    #  \param force: Allow this job to be printed despite of mismatching configurations.
    #  \param last_seen: The number of seconds since this job was checked.
    #  \param machine_variant: The machine type that this job should be printed on.Coincides with the machine_type field
    #       of the printer object.
    #  \param name: The name of the print job. Usually the name of the .gcode file.
    #  \param network_error_count: The number of errors encountered when requesting data for this print job.
    #  \param owner: The name of the user who added the print job to Cura Connect.
    #  \param printer_uuid: UUID of the printer that the job is currently printing on or assigned to.
    #  \param started: Whether the job has started printing or not.
    #  \param status: The status of the print job.
    #  \param time_elapsed: The remaining printing time in seconds.
    #  \param time_total: The total printing time in seconds.
    #  \param uuid: UUID of this print job. Should be used for identification purposes.
    #  \param deleted_at: The time when this print job was deleted.
    #  \param printed_on_uuid: UUID of the printer used to print this job.
    #  \param configuration_changes_required: List of configuration changes the printer this job is associated with
    #       needs to make in order to be able to print this job
    #  \param build_plate: The build plate (type) this job needs to be printed on.
    #  \param compatible_machine_families: Family names of machines suitable for this print job
    #  \param impediments_to_printing: A list of reasons that prevent this job from being printed on the associated
    #       printer
    def __init__(self, created_at, force, machine_variant, name, started, status, time_total, uuid,
                 configuration, constraints, last_seen = None, network_error_count = None,
                 owner = None, printer_uuid = None, time_elapsed = None, assigned_to = None, deleted_at = None,
                 printed_on_uuid = None, configuration_changes_required = None, build_plate = None,
                 compatible_machine_families = None, impediments_to_printing = None, **kwargs):
        self.assigned_to = assigned_to
        self.configuration = self.parseModels(ClusterPrintCoreConfiguration, configuration)
        self.constraints = self.parseModels(ClusterPrintJobConstraints, constraints)
        self.created_at = created_at
        self.force = force
        self.last_seen = last_seen
        self.machine_variant = machine_variant
        self.name = name
        self.network_error_count = network_error_count
        self.owner = owner
        self.printer_uuid = printer_uuid
        self.started = started
        self.status = status
        self.time_elapsed = time_elapsed
        self.time_total = time_total
        self.uuid = uuid
        self.deleted_at = deleted_at
        self.printed_on_uuid = printed_on_uuid

        self.configuration_changes_required = self.parseModels(ClusterPrintJobConfigurationChange,
                                                               configuration_changes_required) \
            if configuration_changes_required else []
        self.build_plate = self.parseModel(ClusterBuildPlate, build_plate) if build_plate else None
        self.compatible_machine_families = compatible_machine_families if compatible_machine_families else []
        self.impediments_to_printing = self.parseModels(ClusterPrintJobImpediment, impediments_to_printing) \
            if impediments_to_printing else []

        super().__init__(**kwargs)
