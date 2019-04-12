.. # Links
.. _API: https://cdn.turbonomic.com/wp-content/uploads/docs/VMT_REST2_API_PRINT.pdf
.. _vmt-connect: https://github.com/rastern/vmt-connect/
.. _Turbonomic: http://www.turbonomic.com

==========
User Guide
==========

*vmt-plan* utilizes `vmt-connect`_ for base communication with the `Turbonomic`_ `API`_,
while providing additional planning capabilities.

Creating Plans
==============

Basic Plans
-----------

Using the :class:`~vmtconnect.Connection` class to connect to Turbonomic.

.. code:: python

   import vmtconnect as vc
   import vmtplanner as vp

   vmt = vc.Connection(host='localhost', username='bob', password='*****')

With this we have a connection setup and ready to use. Now we can create a plan
scenario. Here will will do a simple projection plan using two groups of VMs.

.. code:: python

   # scoping to two groups by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']
   scenario = vp.PlanSpec('Custom Scenario', vp.PlanType.CUSTOM, scope)

   # add 5 copies of a VM immediately
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['1341c28a-c9b7-46a5-ab25-321260482a91'],
                          projection=[0],
                          count=5)

   # add 1 copy each month for 3 months, starting next month
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['1341c28a-c9b7-46a5-ab25-321260482a91'],
                          projection=[30, 60, 90],
                          count=1)

With the scenario created, and VMs added, we can initialize the market and run
the plan using our connection in the first example.

.. code:: python

   plan = vp.Plan(vmt, scenario)
   plan.run()

When the plan is finished, we can retrieve the stats for the market plan we ran.
Plan results will be listed for each period the plan ran, with a minimum of one
period.

.. code:: python

   if plan.is_complete():
       plan.get_stats()


Advanced Plans
--------------

The plan engine is capable of complex multi-stage plans. For instance, you may
want to see what happens when you let Turbonomic fully control your environment
before making new VM placements, and compare it against simply adding the VMs
in the current environment. Multi-staged plans are also called plan-on-plan
projections because we are running a plan on top of the results of a previous
plan.

Let's say we want to simulate merging two clusters before adding workload. First
we need to deal with the clusters and let Turbonomic sort out the environment.

.. code:: python

   # scoping to two clusters by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']

   cluster_merge = vp.PlanSpec(name='Custom Scenario',
                               type=vp.PlanType.CUSTOM,
                               scope=scope)

   cluster_merge.change_automation_setting(vp.AutomationSetting.SUSPEND_PM, True)
   cluster_merge.change_automation_setting(vp.AutomationSetting.SUSPEND_DS, True)
   cluster_merge.change_auotmation_setting(vp.AutomationSetting.RESIZE, True)

   stage1 = vp.Plan(vmt, cluster_merge)
   stage1.run()

After the plan finishes, we can utilize the first stage market as the input to
the next stage, into which we will add our new workload.

.. code:: python

   # new scenario called add_workload
   add_workload = vp.PlanSpec(name='custom scenario',
                              type=vp.PlanType.CUSTOM)

   # add 10 copies of a VM immediately
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['1341c28a-c9b7-46a5-ab25-321260482a91'],
                          projection=[0],
                          count=10)

   stage2 = vp.Plan(vmt, add_workload,
                    market=stage1.market_id)
   stage2.run()

In this case we did not need to re-scope the second plan because the results
market from stage1 already contains only the clusters we want, and we want
everything in the results market. You'll note when creating the :class:`~vmtplanner.Plan`
we specify we are using a market other than the default one by passing in the
market uuid from `stage1`.

Addtional Information
---------------------

Additional information on supported plan types and their requirements, as well
as examples, is provided in the :ref:`plan_configuration` section.


.. _scenario-parameters:

Scenario Parameters
===================

Turbonomic now accepts these parameters as part of the base DTO, and the use of GET parameters
has been deprecated within vmt-plan. As of version 2.0.0 you must make use of :class:`AutomationSetting`
in conjunction with :meth:`PlanSpec.change_automation_setting`.


.. _market-parameters:

Market Parameters
=================

Market parameters are now handled transplarently by the :class:`PlanSpec` class.


.. _plan_periods:

Plan Periods
============

Most settings within a plan include either a single integer ``projectionDay``
or list of integer values as ``projectionDays`` for which the setting is to be
applied. Legacy methods and compatibility aliases may refer to this value as
either ``period`` or ``periods`` in the parameters, for backwards compatibilty
reasons.

In all cases the purpose is the same. Turbonomic applies the specific plan
setting at the given number of days counted from today. If the setting accepts a
list, then it is applied at each given date calculated as days from today. The
easiest to understand example is when adding a specific workload at a regular
interval. For instance, if you wanted to add 1 VM per month, for 6 months, you
would have ``projectionDays`` as follows: ``[0, 30, 60, 90, 120, 180]``. Lists of
periods are most appropirate to workload changes in the plan, whereas most other
settings accept only a single value as to when the setting takes place; for
which you will nearly always use the value ``0`` to have the setting take effect
immediately.

Changing settings at a future date, for which all workload changes occure before
the setting change is undocumented behavior and should be avoided. Toggling or
otherwise changing a non-workload setting multiple times within a plan, at
different periods is also undocumented behavior, and should be avoided. When
in doubt all settings other than workload changes should be set at period ``0``.


.. _deprecated:

Deprecated Interfaces
=====================

With the release of version 2.0 several interfaces have been deprecated. Most
notably, the management of entities is moved entirely to :meth:`~vmtplanner.PlanSpec.change_entity`.
Additionally, the spec initialization no longer supports automation settings
passed in as parameters. In most cases, the previous methods are maintained as
aliases to their replacements, and fully support the original parameters including
if using keyword assignment. Automation settings, however, must be set utilizing
the new :meth:`~vmtplanner.PlanSpec.change_automation_setting` method.

To illustrate, the first plan example from above could still be run in the
previous manner as shown below.

.. code:: python

   # scoping to two groups by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']
   scenario = vp.PlanSpec('custom scenario', vp.PlanType.CUSTOM, scope)

   # add 5 copies of a VM immediately
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=5, periods=[0])

   # add 1 copy each month for 2 months
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=1, periods=[30, 60])

While using deprecated methods is provided for convenience, you are strongly
encouraged to update to the newer interfaces as soon as possible. Deprecated
interfaces will throw warnings, and will be removed completely in a future release.
