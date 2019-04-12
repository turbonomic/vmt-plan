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