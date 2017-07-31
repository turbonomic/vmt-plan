:mod:`vmtplanner` --- Developer Interfaces
==========================================

.. module:: vmtplanner

vmt-plan provides a plan engine class called :class:`Plan`, which executes a plan
as defined by the settings in a :class:`PlanSpec`.


Enumerations
------------

.. autoclass:: MarketState
   :members:

.. autoclass:: PlanSetting
   :members:

.. autoclass:: PlanType
   :members:

.. autoclass:: ServerResponse
   :members:


Classes
-------

.. autoclass:: Plan
   :members:

.. autoclass:: PlanSpec
   :members:


Exceptions
----------

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


.. _entity spec:

.. include:: entity_spec.rst
