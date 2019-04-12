.. # Links
.. _API: https://cdn.turbonomic.com/wp-content/uploads/docs/VMT_REST2_API_PRINT.pdf
.. _vmt-connect: https://github.com/rastern/vmt-connect/

===================
Plan Configurations
===================

*vmt-plan* provides the necessary interfaces to the Turbonomic API required to
setup and run any of the supported plan types in Turbonomic. For some plan
types, Turbonomic provides a UI wizard that simplifies establishing the plan
parameters, prior to running the plan itself. *vmt-plan* does not perform plan
type validation, therefore, it is up to the developer to ensure that the required
parameters for the given :class:`vmtplanner.PlanType` are established.

Although Turbonomic, Inc. does not provide detailed developer documentation
for the API, the reference given below for each plan type should cover most
use cases required. This is unfortunately not meant to be exhaustive, and if
in doubt, the recommended course of action is to first create the plan in the
UI to ensure it is valid.

In the examples below, all assume you have established a connection and stored
it in an object called ``vmt``, as well as imported ``vmtplanner`` under the
name ``vp`` as follows:

.. code:: python

   import vmtplanner as vp

Add Workload
============

Add Workload plans run a simple simulation of additional workload being added
into the environment at a given time. The workload can be an existing entity,
which will be copied, a group of entities, or a template.

Description
-----------

Turbonomic describes the plan as follows:

  See whether you can add more workload without provisioning more hosts or datastores.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.ADD_WORKLOAD`
  * Addition of one or more new workloads

Example
-------

.. code:: python

   # scoping to 'real-time' market
   scope = ['Market']
   scenario = vp.PlanSpec('Add Workload', vp.PlanType.ADD_WORKLOAD, scope)

   # add copies of a VM immediately
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['1341c28a-c9b7-46a5-ab25-321260482a91'])


Decommission Hosts
==================

In order to simulate the effect from removing one or more hosts on an existing
environment, without altering hardware, you can run a Decommission Hosts plan.

Description
-----------

Turbonomic describes the plan as follows:

  See whether you can remove hosts from the environment and still assure performance for your workload. This shows whether your environment is overprovisioned, and how many hosts you can remove.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.DECOMMISSION_HOST`
  * Removal of one or more host entities
  * Disabling host provisioning

Example
-------

.. code:: python

   # scoping to 'real-time' market
   scope = ['Market']
   scenario = vp.PlanSpec('Decommission Hosts', vp.PlanType.DECOMMISSION_HOST, scope)

   # remove hosts
   scenario.change_entity(action=vp.EntityAction.REMOVE,
                          targets=['4238a9ea-0c49-31dd-7a7e-87fdab53c974'])

   # disable host provisioning
   scenario.change_automation_setting(vp.AutomationSetting.PROVISION_PM, False)


Hardware Refresh
================

Running a Hardware Refresh plan simulates upgrading or altering the underlying
host and storage entities in the environment. This is most commonly run in
anticipation of replacing host or storage hardware with newer models.

Description
-----------

Turbonomic describes the plan as follows:

  View the effect on your environment when you reconfigure your hosts and storage devices.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.RECONFIGURE_HARDWARE`
  * One or more entity replacements

Example
-------

.. code:: python

   # scoping to 'real-time' market
   scope = ['Market']
   scenario = vp.PlanSpec('Reconfigure Hardware', vp.PlanType.RECONFIGURE_HARDWARE, scope)

   # replace hosts
   scenario.change_entity(action=vp.EntityAction.REPLACE,
                          targets=['4238a9ea-0c49-31dd-7a7e-87fdab53c974', '34313133-3630-4d58-5138-333941325459'],
                          new_target='_v0Q70spiEd-hypXfJzX8Wg')


Migrate to Public Cloud
=======================

Cloud Migration plans provide cost based analysis for running existing workloads
in one of the supported cloud infrastructure providers. The destination details
may be tailored to the desired analysis to be performed, such as permitting
migration to any available provider, specifying a specific provider, or narrowing
down to a region within a provider.

.. important::

   In order for the cost analysis to isolate only the workload being migrated,
   the plan must be set to ignore all existing workloads by removing them from
   the simulation.

In the first example, the catch-all group "All Cloud Zones" is used to allow
Turbonomic to select the cloud provider. In the second example, AWS is selected
explicitly, and in the third example a region is used to narrow the migration
further. Additional options such as OS migration mapping may also be used, as
in the fourth example.

Description
-----------

Turbonomic describes the plan as follows:

  Calculate the cost to run your workload on a public cloud provider.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.CLOUD_MIGRATION`
  * One or more entity migrations
  * Remove all workloads in all cloud zones

Example 1
---------

.. warning::

   This plan setup may take excessively long to run. You should always use the
   most narrow scope possible for Cloud Migration plans.

.. code:: python

   # scope to the entities we're working with
   scope = ['_yrLMoFY9EemGOqc0YaqTpg', '_lRrTYB--EeewItqBJctLGw']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.CLOUD_MIGRATION, scope)

   # migrate entities in a group
   # '_lRrTYB--EeewItqBJctLGw' is the system group "All Cloud Zones"
   # the UUID may change between versions
   scenario.change_entity(action=vp.EntityAction.MIGRATE,
                          targets=['_yrLMoFY9EemGOqc0YaqTpg'],
                          new_target='_lRrTYB--EeewItqBJctLGw')

   # remove all existing workloads
   # '_nJUm4FvLEemGOqc0YaqTpg' is the system group "All VMs In All Cloud Zones"
   # the UUID may change between versions
   scenario.change_entity(action=vp.EntityAction.REMOVE,
                          targets=['_nJUm4FvLEemGOqc0YaqTpg'])

Example 2
---------

.. code:: python

   # scope to the entities we're working with
   scope = ['_yrLMoFY9EemGOqc0YaqTpg', 'GROUP-PMsByTargetType_AWS']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.CLOUD_MIGRATION, scope)

   # migrate entities in a group
   # 'GROUP-PMsByTargetType_AWS' is the system generated group "PMs_AWS"
   # the UUID may change between versions
   scenario.change_entity(action=vp.EntityAction.MIGRATE,
                          targets=['_yrLMoFY9EemGOqc0YaqTpg'],
                          new_target='GROUP-PMsByTargetType_AWS')

   # remove all existing workloads
   # '_MNqUoFxuEemz8-rKgfgVNQ' is the system generated group "All VMs In PMs_AWS"
   # the UUID may change between versions
   scenario.change_entity(action=vp.EntityAction.REMOVE,
                          targets=['_MNqUoFxuEemz8-rKgfgVNQ'])

Example 3
---------

.. code:: python

   # scope to the entities we're working with
   scope = ['_yrLMoFY9EemGOqc0YaqTpg', '709593f226ce7055eddc39f753103ef891268769']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.CLOUD_MIGRATION, scope)

   # migrate entities in a group
   # '709593f226ce7055eddc39f753103ef891268769' is the system generated group
   # "PMs_aws-US East (N. Virginia)"
   # the UUID may be different for you
   scenario.change_entity(action=vp.EntityAction.MIGRATE,
                          targets=['_yrLMoFY9EemGOqc0YaqTpg'],
                          new_target='709593f226ce7055eddc39f753103ef891268769')

   # remove all existing workloads
   # '_pD8jcFxuEemz8-rKgfgVNQ' is the system generated group
   # "All VMs In PMs_aws-US East (N. Virginia)"
   # the UUID may be different for you
   scenario.change_entity(action=vp.EntityAction.REMOVE,
                          targets=['_pD8jcFxuEemz8-rKgfgVNQ'])

Example 4
---------

.. code:: python

   # scope to the entities we're working with
   scope = ['_yrLMoFY9EemGOqc0YaqTpg', '709593f226ce7055eddc39f753103ef891268769']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.CLOUD_MIGRATION, scope)

   # migrate entities in a group
   # '709593f226ce7055eddc39f753103ef891268769' is the system generated group
   # "PMs_aws-US East (N. Virginia)"
   # the UUID may be different for you
   scenario.change_entity(action=vp.EntityAction.MIGRATE,
                          targets=['_yrLMoFY9EemGOqc0YaqTpg'],
                          new_target='709593f226ce7055eddc39f753103ef891268769')

   # remove all existing workloads
   # '_pD8jcFxuEemz8-rKgfgVNQ' is the system generated group
   # "All VMs In PMs_aws-US East (N. Virginia)"
   # the UUID may be different for you
   scenario.change_entity(action=vp.EntityAction.REMOVE,
                          targets=['_pD8jcFxuEemz8-rKgfgVNQ'])

   # set source RHEL and SUSE OSes to generic Linux at destination
   cloud_os_profile(source=vp.CloudOS.RHEL, target=vp.CloudOS.Linux, unlicensed=True)
   cloud_os_profile(source=vp.CloudOS.SUSE, target=vp.CloudOS.Linux, unlicensed=True)


Optimize Cloud
==============

An Optimize Cloud plan will analyze the targeted cloud environment, usually a
region, for the most cost efficient template sizes and can take into account
reserved instances.

.. important::

   Reserved instance settings are not yet implemented in *vmt-plan*.

Description
-----------

Turbonomic describes the plan as follows:

  See how to maximize savings in your cloud environment, while also assuring application performance

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.OPTIMIZE_CLOUD`
  * Resizing enabled

Example
-------

.. code:: python

   # scoping to a region
   scope = ['4cb9f02f906cd330e52323c9c6615b1a42ee26c3']
   scenario = vp.PlanSpec('Optimize Cloud', vp.PlanType.OPTIMIZE_CLOUD, scope)

   # set resizing on, so we can optimize
   scenario.change_automation_setting(vp.AutomationSetting.RESIZE, True)

   # TODO: RI settings are not yet implemented, and would need to be set


On-Prem Workload Migration
==========================

On-Prem Migration plans simulate adding workload to a cluster in order to evaluate
the capacity requirements, such as if new hosts or storage capacity is required.
In its current form, On-Prem Migration operates equivalent to a scoped Add
Workload plan without distinction.

Description
-----------

Turbonomic describes the plan as follows:

  View the results of moving workload from one cluster to another — Say from the Development cluster to the Production cluster. See whether Production has enough supply, or whether you must add new hosts.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.WORKLOAD_MIGRATION`
  * Addition of workloads from source
  * Scope set to destination cluster

Example
-------

.. code:: python

   # scoping to the destination cluster
   scope = ['97e9154697ac16f9e193bd8ba2bdc41b3172dcd8']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.WORKLOAD_MIGRATION, scope)

   # add the workload from the source
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['bae429974e7013362c070429292144003e025f64'])


Alleviate Pressure
==================

An Alleviate Pressure plan is similar in nature to a Migration plan, with the
distinct purpose being to move as little workload as possible from the "Hot"
cluster into the "Cold" cluster.

Description
-----------

Turbonomic describes the plan as follows:

  Reduce pressure from a hot cluster by moving a minimal number of VMs into another one.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.ALLEVIATE_PRESSURE`
  * Scope set to hot and cold clusters
  * Relieve pressure setting

Example
-------

.. code:: python

   # scoping to the affected clusters
   scope = ['97e9154697ac16f9e193bd8ba2bdc41b3172dcd8', '99408929-82cf-4dc7-a532-9d998063fa95']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.ALLEVIATE_PRESSURE, scope)

   # move minimal amount of workload
   scenario.relieve_pressure(sources=['97e9154697ac16f9e193bd8ba2bdc41b3172dcd8'],
                             targets=['99408929-82cf-4dc7-a532-9d998063fa95'])

Custom
======

Custom plans allow for more customization of the plan parameters. From the UI
perspective, this type does not utilize a plan wizard, whereas other types do.

Description
-----------

Turbonomic describes the plan as follows:

  Create custom plan to calculate optimal workload distribution across your environment.

Requirements
------------
  * Plan Type: :class:`vmtplanner.PlanType.CUSTOM`

Example
-------

.. code:: python

   # scoping to 'real-time' market
   scope = ['Market']
   scenario = vp.PlanSpec('Migrate to Cloud', vp.PlanType.CUSTOM, scope)

   # simple rebalance plan
   scenario.change_automation_setting(vp.AutomationSetting.RESIZE, True)

   # optionally could ignore constrains completely, for the most optimal
   scenario.remove_constraints()
