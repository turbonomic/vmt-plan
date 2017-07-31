.. # Links
.. _API: https://cdn.turbonomic.com/wp-content/uploads/docs/VMT_REST2_API_PRINT.pdf
.. _vmt-connect: https://github.com/rastern/vmt-connect/

Quickstart Guide
================

vmt-plan utilizes `vmt-connect`_ for base communication with the Turbonomic API_,
while providing additional planning capabilities.


Getting Connected
-----------------

Using the :class:`~vmtconnect.VMTConnection` class to connect to Turbonomic.

.. code:: python

   import vmtconnect as vc
   import vmtplanner as vp

   vmt = vc.VMTConnection(host='localhost', username='bob', password='*****')

With this we have a connection setup and ready to use. Now we can create a plan
scenario. Here will will do a simple projection plan using two groups of VMs.

.. code:: python

   # scoping to two groups by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']
   scenario = vp.PlanSpec('custom scenario', vp.PlanType.CUSTOM, scope)

   # add 5 copies of a VM immediately
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=5, periods=[0])

   # add 1 copy each month for 2 months
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=1, periods=[30, 60])

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
