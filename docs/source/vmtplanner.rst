==========
vmtplanner
==========

The base module of *vmt-plan* package provides a plan engine class called :py:class:`~vmtplanner.Plan`,
which executes a Turbonomic plan as defined by the settings in a :py:class:`~vmtplanner.PlanSpec`.


Enumerations
============

.. autoclass:: vmtplanner.AutomationSetting
   :members:

.. autoclass:: vmtplanner.AutomationValue
   :members:

.. autoclass:: vmtplanner.CloudLicense
   :members:

.. autoclass:: vmtplanner.CloudOS
   :members:

.. autoclass:: vmtplanner.CloudTargetOS
   :members:

.. autoclass:: vmtplanner.ConstraintCommodity
   :members:

.. autoclass:: vmtplanner.EntityAction
   :members:

.. autoclass:: vmtplanner.MarketState
   :members:

.. autoclass:: vmtplanner.PlanType
   :members:

.. autoclass:: vmtplanner.ServerResponse
   :members:


Classes
=======

.. autoclass:: vmtplanner.Plan
   :members:

.. autoclass:: vmtplanner.PlanSpec
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
