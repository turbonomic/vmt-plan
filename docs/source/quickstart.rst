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


Complex Plans
-------------

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

   cluster_merge = vp.PlanSpec(name='custom scenario',
                               type=vp.PlanType.CUSTOM,
                               scope=scope,
                               host_suspension=True,
                               datastore_removal=True
                               resize=True)

   stage1 = vp.Plan(vmt, cluster_merge)
   stage1.run()

After the plan finishes, we can utilize the first stage market as the input to
the next stage, into which we will add our new workload.

.. code:: python

   # new scenario called add_workload
   add_workload = vp.PlanSpec(name='custom scenario',
                              type=vp.PlanType.CUSTOM)

   # add 10 copies of a VM immediately
   add_workload.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91',
                           count=10, periods=[0])

   stage2 = vp.Plan(vmt, add_workload,
                    market=stage1.market_id)
   stage2.run()

In this case we did not need to re-scope the second plan because the results
market from stage1 already contains only the clusters we want, and we want
everything in the results market. You'll note when creating the :class:`Plan`
we specify we are using a market other than the default one by passing in the
market uuid from `stage1`.
