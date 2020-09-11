# Copyright 2020 Turbonomic, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# libraries

from vmtplanner import AutomationSetting, Plan, PlanSpec, PlanType



class BaseBalancePlan(Plan):
    """Base Balance plan.

    Args:
        connection (:py:class:`~vmtconnect.Connection`): :py:class:`~vmtconnect.Connection` or :py:class:`~vmtconnect.Session`.
        spec (:py:class:`PlanSpec`, optional): Settings override to apply to the
            market, if running a plan.
        market (str, optional): Base market UUID to apply the settings to.
            (default: ``Market``)
        scope (list, optional): Scope of the plan market. If ``None``, then a
            list of all clusters in the given market will be used.

    """
    def __init__(self, connection, spec=None, market='Market', scope=None, **kwargs):
        # we must initialize some values here because we need them to build the spec
        # _before_ we call the parent class
        self._vmt = connection
        self.base_market = market

        if spec is None and market == 'Market':
            spec = self.__std_spec(scope)

        super().__init__(connection, spec, market, **kwargs)
        self.log('BaseBalancePlan initialized', level='debug')

    def __std_spec(self, scope):
        # default "balance" plan for headroom calcs
        settings = [
            AutomationSetting.PROVISION_DS,
            AutomationSetting.SUSPEND_DS,
            AutomationSetting.PROVISION_PM,
            AutomationSetting.SUSPEND_PM,
            AutomationSetting.RESIZE,
        ]

        if scope is None:
            res = self._vmt.search(types=['Cluster'], scopes=[self.base_market])
            scope = [x['uuid'] for x in res]

        spec = PlanSpec(type=PlanType.OPTIMIZE_ONPREM, scope=scope)

        for x in settings:
            spec.change_automation_setting(x, False)

        return spec
