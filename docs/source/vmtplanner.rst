===================================
vmtplanner --- Developer Interfaces
===================================

.. module:: vmtplanner

*vmt-plan* provides a single module called ``vmtplanner``. This module provides
a plan engine class called :class:`Plan`, which executes a plan as defined by
the settings in a :class:`PlanSpec`.


Enumerations
============

.. autoclass:: AutomationSetting
   :members:

.. autoclass:: CloudOS
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


.. _scenario_param:

.. include:: scenario_param.rst


.. _market_param:

.. include:: market_param.rst


.. _plan_periods:

.. include:: plan_periods.rst