.. _installation: https://rastern.github.io/vmt-plan/start.html#install
.. _vmt-connect: https://github.com/rastern/vmt-connect

vmt-plan: Turbonomic API plan engine
=======================================

vmt-plan is a single file Python module that provides a more user-friendly wrapper for running plans using the second generation Turbonomic API. This module handles planning exclusively, and relies on `vmt-connect`_ for connection brokering.


Installation
------------

To install vmt-plan, copy the *vmtplanner.py* file to your project folder, or
alternatively, manually install it in your python modules path. For detailed
instructions please see the `installation`_ section of the documentation.

vmt-plan does not support PyPi installation via pip or setuputils.


Usage
-----

Basic Plan
''''''''''

.. code:: python

   import vmtconnect as vc
   import vmtplanner as vp

   vmt = vc.VMTConnection(host='localhost', username='bob', password='*****')

   # scoping to two groups by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']
   scenario = vp.PlanSpec('custom scenario', vp.PlanType.CUSTOM, scope)

   # add 5 copies of a VM immediately
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=5, periods=[0])

   # add 1 copy each month for 2 months
   scenario.add_entity('1341c28a-c9b7-46a5-ab25-321260482a91', count=1, periods=[30, 60])

   plan = vp.Plan(vmt, scenario)
   plan.run()


Documentation
-------------

Detailed documentation is available `here <https://rastern.github.io/vmt-plan>`_.


How to Contribute
-----------------

vmt-plan is provided as a read-only repository, and is not accepting pull requests.