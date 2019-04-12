Scenario Parameters
===================

Turbonomic now accepts these parameters as part of the base DTO, and the use of GET parameters
has been deprecated within vmt-plan. As of version 2.0.0 you must make use of :class:`AutomationSetting`
in conjunction with :meth:`PlanSpec.change_automation_setting`.