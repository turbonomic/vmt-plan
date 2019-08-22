.. _vmt-connect: https://github.com/rastern/vmt-connect

vmt-plan: Turbonomic API plan engine
=======================================

vmt-plan is a companion library to vmt-connect_ for working with the Turbonomic API. The core purpose of the library is to provide interfaces for constructing and running plans within Turbonomic.


Installation
------------

Prior to version 2.0, vmt-plan was distributed as a stand-alone single file Python module, which could be placed into the same folder as the calling script. As of version 2.0, vmt-plan is now distributed as a Python wheel package to be installed via pip. The package is not available on PyPi at this time.

.. code:: bash

   pip install vmtplan-2.0.0-py3-none-any.whl


Usage
-----

Basic Plan
''''''''''

.. code:: python

   import vmtconnect as vc
   import vmtplanner as vp

   vmt = vc.Session(host='localhost', username='bob', password='*****')

   # scoping to two groups by UUID
   scope = ['430e28cbaabf35522a180859d4160562d123ac78',
            'e48fd3270917221d3e6290e1affead34b872e95b']
   scenario = vp.PlanSpec('custom scenario', scope=scope)

   # add 5 copies of a VM immediately using positional arguments
   scenario.change_entity(vp.EntityAction.ADD, ['1341c28a-c9b7-46a5-ab25-321260482a91'], [0], 5)

   # add 1 copy each month for 2 months using named arguments
   scenario.change_entity(action=vp.EntityAction.ADD,
                          targets=['1341c28a-c9b7-46a5-ab25-321260482a91'],
                          count=1,
                          projection=[30, 60])

   plan = vp.Plan(vmt, scenario)
   plan.run()


Documentation
-------------

Detailed documentation is available online at https://rastern.github.io/vmt-plan.


How to Contribute
-----------------

vmt-plan is provided as a read-only repository, and is not accepting pull requests. You may fork the project for your own purposes under the `Apache 2.0 <https://github.com/rastern/vmt-plan/blob/master/LICENSE>`_ license.
