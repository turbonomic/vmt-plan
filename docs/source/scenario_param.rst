Scenario Parameters
-------------------

The following scenario parameters are supported as keyword arguments. Unless
otherwise stated, all are independent and optional.

* description (`str)`: Description of the plan scenario.
* add_historical (`bool`): Add VMs based on inventory changes in the last month.
* datastore_provision (`bool`): Permit datastore provisioning.
* datastore_removal (`bool`): Permit datastore removal.
* host_provision (`bool`): Permit host provisioning.
* host_suspension (`bool`): Permit host suspensions.
* include_reservations (`bool`): Include reservations in the plan.
* resize (`bool`): Permit Virtual Machine resizing.
* time (`timestamp`):  (unix timestamp, optional): A Unix timestamp in miliseconds to utilize as a baseline for the plan workload.
