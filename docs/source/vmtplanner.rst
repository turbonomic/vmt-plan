==========
vmtplanner
==========

.. module:: vmtplanner

The base module of *vmt-plan* package provides a plan engine class called :class:`Plan`,
which executes a Turbonomic plan as defined by the settings in a :class:`PlanSpec`.


Enumerations
============

.. autoclass:: AutomationSetting
   :members:

.. autoclass:: CloudLicense
   :members:

.. autoclass:: CloudOS
   :members:

.. autoclass:: CloudTargetOS
   :members:

.. autoclass:: ConstraintCommodity
   :members:

.. autoclass:: EntityAction
   :members:

.. autoclass:: MarketState
   :members:

.. autoclass:: PlanType
   :members:

.. autoclass:: ServerResponse
   :members:


Classes
=======

.. autoclass:: Plan
   :members:

.. autoclass:: PlanSpec
   :members:


Exceptions
==========

.. autoexception:: vmtplanner.MarketError
.. autoexception:: vmtplanner.InvalidMarketError
.. autoexception:: vmtplanner.PlanError
.. autoexception:: vmtplanner.PlanRunning
.. autoexception:: vmtplanner.PlanRunFailure
.. autoexception:: vmtplanner.PlanDeprovisionError
.. autoexception:: vmtplanner.PlanExecutionExceeded
