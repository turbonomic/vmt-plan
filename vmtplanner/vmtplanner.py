# Copyright 2017-2020 R.A. Stern
# Portions Copyright 2020 Turbonomic, Inc
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

from collections import defaultdict, namedtuple
from collections.abc import Mapping
import copy
import datetime
from enum import Enum
from functools import wraps
import json
import math
import time
import traceback
import warnings

from urllib.parse import urlencode
import umsg
from umsg.mixins import LoggingMixin

import vmtconnect as vc



umsg.init()
_VERSION_REQ = ['5.9.0+']
_VERSION_EXC = []


## ----------------------------------------------------
##  Error Classes
## ----------------------------------------------------
class ContinueOuter(Exception):
    pass

# base market error
class MarketError(Exception):
    """Base market exception class."""
    pass


class InvalidMarketError(MarketError):
    """Raised when trying to reference a market that does not exist."""
    pass


# base plan error
class PlanError(Exception):
    """Base plan exception class."""
    pass


# plan running
class PlanRunning(PlanError):
    """Raised when a plan is already running."""
    pass


# unable to run a plan
class PlanRunFailure(PlanError):
    """Raised when a plan fails to run properly."""
    pass


# plan deprovisioning failure
class PlanDeprovisionError(PlanError):
    """Raised when there is an error removing a plan."""
    pass


# plan timeout exceeded
class PlanExecutionExceeded(PlanError):
    """Raised when a plan exceeds the timeout period specified."""
    pass


# settings errors
class PlanSettingsError(Exception):
    pass


# value mapping error
class InvalidValueMapError(PlanSettingsError):
    pass



## ----------------------------------------------------
##  Enumerated Classes
## ----------------------------------------------------
class AutomationSetting(Enum):
    """Automation Settings."""
    #: Provision new datastores
    PROVISION_DS = 'provisionDS'
    #: Provision new hosts
    PROVISION_PM = 'provisionPM'
    #: Resize VMs
    RESIZE = 'resize'
    #: Suspend datastores
    SUSPEND_DS = 'suspendDS'
    #: Suspend hosts
    SUSPEND_PM = 'suspendPM'
    #: Desired state - performance / efficiency (i.e. center)
    UTIL_TARGET = 'utilTarget' # efficiency
    #: Desired state - width / narrowness (i.e. diameter)
    TARGET_BAND = 'targetBand' # narrowness


class CloudLicense(Enum):
    """Cloud OS licensing."""
    #:
    LINUX = 'linuxByol'
    #:
    RHEL = 'rhelByol'
    #:
    SLES = 'slesByol'
    #:
    SUSE = 'slesByol'
    #:
    WINDOWS = 'windowsByol'


class CloudOS(Enum):
    """Cloud OS definitions."""
    #: Generic Linux OS
    LINUX = 'LINUX'
    #: Redhat Enterprise Linux
    RHEL = 'RHEL'
    #: SUSE Enterprise Linux Server
    SLES = 'SLES'
    #: Convenience alias for SLES
    SUSE = 'SLES'
    #: Microsoft Windows
    WINDOWS = 'WINDOWS'


class CloudTargetOS(Enum):
    """Cloud Target OS definitions."""
    #:
    LINUX = 'linuxTargetOs'
    #:
    RHEL = 'rhelTargetOs'
    #:
    SLES = 'slesTargetOs'
    #:
    SUSE = 'slesTargetOs'
    #:
    WINDOWS = 'windowsTargetOs'


class ConstraintCommodity(Enum):
    """Plan constraint commodities."""
    #:
    CLUSTER = 'ClusterCommodity'
    #:
    NETWORK = 'NetworkCommodity'
    #:
    #Datastore = 'DatastoreCommodity'
    #:
    STORAGECLUSTER = 'StorageClusterCommodity'
    #:
    DATACENTER = 'DataCenterCommodity'


class EntityAction(Enum):
    """Plan entity changes."""
    #:
    ADD = 'add'
    #:
    MIGRATE = 'migrate'
    #:
    REMOVE = 'remove'
    #:
    REPLACE = 'replace'


class MarketState(Enum):
    """Market states."""
    #: Indicates the plan scope is being copied.
    COPYING = 'copy'
    #: Indicates the market was created.
    CREATED = 'created'
    #: Indicates the market plan is being deleted.
    DELETING = 'del'
    #: Indicates market plan is setup and ready to be run.
    READY_TO_START = 'ready'
    #: Indicates the market plan is running.
    RUNNING = 'run'
    #: Indicates the market plan stopped.
    STOPPED = 'stop'
    #: Indicates the market plan succeeded.
    SUCCEEDED = 'success'
    #: Indicates the market plan was stop manually by a user.
    USER_STOPPED = 'user_stop'


class PlanType(Enum):
    """Plan scenario types."""
    #: Increase Workload
    ADD_WORKLOAD = 'ADD_WORKLOAD'
    #: Move workload from a hot cluster to a cold cluster
    ALLEVIATE_PRESSURE = 'ALLEVIATE_PRESSURE'
    #: Cloud Specific Migration
    CLOUD_MIGRATION = 'CLOUD_MIGRATION'
    #: Fully Custom
    CUSTOM = 'CUSTOM'
    #: Host Decommissioning
    DECOMMISSION_HOST = 'DECOMMISSION_HOST'
    #: On-Prem Optimization
    OPTIMIZE_ONPREM = 'OPTIMIZE_ONPREM'
    #: Future Workload Change
    PROJECTION = 'PROJECTION'
    #: Host Hardware Reconfiguration
    RECONFIGURE_HARDWARE = 'RECONFIGURE_HARDWARE'
    #: On-Premis Workload Migration
    WORKLOAD_MIGRATION = 'WORKLOAD_MIGRATION'


class ServerResponse(Enum):
    """Turbonomic service responses."""
    #:
    TRUE = True
    #:
    FALSE = False
    #:
    SUCCESS = 'success'
    #:
    ERROR = 'error'


# Map DSL
# $ substitute (regular variable)
# @ map variable value to new value
# [] group by operator

# basic structure
# <setting name>: <definition>
# Dictionary values (sets) will be overwritten if the same key is repeated
#   - depth is relevant
# List values will be appended (nested lists in dicts require explicit grouping)
# 6.x & 7.x maps should be applied additively, 590 is an outlier

# 5.9.x+ - to be removed when classic deprecated
_dto_map_scenario_settings_590 = {
    'name': {'displayName': '$value'},
    'type': {'type': '$value'},

    'scope': {'changes': [{'type': 'SCOPE', 'scope[scope]': [{'uuid': '$value'}]}]},
    'projection': {'changes': [{'type': 'PROJECTION_PERIODS', 'projectionDays': '$list'}]},
    'desiredstate': {'changes': [{'type': 'SET', 'projectionDays': [0], 'center': '$center', 'diameter': '$diameter'}]},
    'histbaseline': {'changes': [{'type': 'SET_HIST_BASELINE', 'value': '$value'}]},
    'peakbaseline': {'changes': [{'type': 'SET_PEAK_BASELINE', 'value': '$value', 'targets[ids]': [{'uuid': '$uuid'}]}]},
    'addhist': {'changes': [{'type': 'ADD_HIST', 'enable': '$value'}]},
    'includereserved': {'changes': [{'type': 'INCLUDE_RESERVED', 'enable': '$value'}]},
    'maxutil': {'changes': [{'type': 'SET_MAX_UTILIZATION', 'maxUtilType': '$type', 'value': '$util', 'targets[ids]': [{'uuid': '$uuid'}]}]},
    'curutil': {'changes': [{'type': 'SET_USED', 'value': '$util', 'projectionDays': ['$projection'], 'targets[ids]': [{'uuid': '$uuid'}]}]},

    AutomationSetting.PROVISION_PM: {'changes': [{'type': 'SET_ACTION_SETTING', 'name': 'provision', 'value': 'PhysicalMachine', 'enable': '$value'}]},
    AutomationSetting.SUSPEND_PM: {'changes': [{'type': 'SET_ACTION_SETTING', 'name': 'suspend', 'value': 'PhysicalMachine', 'enable': '$value'}]},
    AutomationSetting.PROVISION_DS: {'changes': [{'type': 'SET_ACTION_SETTING', 'name': 'provision', 'value': 'Storage', 'enable': '$value'}]},
    AutomationSetting.SUSPEND_DS: {'changes': [{'type': 'SET_ACTION_SETTING', 'name': 'suspend', 'value': 'Storage', 'enable': '$value'}]},
    AutomationSetting.RESIZE: {'changes': [{'type': '$type', 'name': 'resize', 'enable': '$value', 'description': '$desc'}]},

    'constraint': {'changes': [{'type': 'CONSTRAINTCHANGED', 'projectionDays': ['$projection'], 'name': '$name', 'enable': '$value', 'targets': [{'uuid': '$uuid'}]}]},

    EntityAction.ADD: {'changes': [{'type': 'ADDED', 'projectionDays': '$projection', 'targets': [{'uuid': '$target'}, {'uuid': '$new_target'}]}]},
    EntityAction.MIGRATE: {'changes': [{'type': 'MIGRATION', 'projectionDays': '$projection', 'targets': [{'uuid': '$target'}, {'uuid': '$new_target'}]}]},
    EntityAction.REMOVE: {'changes': [{'type': 'REMOVED', 'projectionDays': '$projection', 'targets': [{'uuid': '$target'}]}]},
    EntityAction.REPLACE: {'changes': [{'type': 'REPLACED', 'projectionDays': '$projection', 'targets': [{'uuid': '$target'}, {'uuid': '$new_target'}]}]},
}

_scenario_settings_collations_590 = {
    'maxutil': {'type': 'list_value', 'groups': [{'label': 'ids', 'fields': ['uuid']}], 'opt': {'field_value': 'keeplast'}},
    'curutil': {'type': 'list_value', 'groups': [{'label': 'ids', 'fields': ['uuid']}], 'opt': {'field_value': 'keeplast'}},
    'peakbaseline': {'type': 'list_value', 'groups': [{'label': 'ids', 'fields': ['uuid', 'value']}], 'opt': {'field_value': 'keeplast'}},
}

# 6.1.x+
_dto_map_scenario_settings_610 = {
    'name': {'displayName': '$value'},
    'type': {'type': '$value'},
    'scope': {'scope[scope]': [{'uuid': '$value'}]},
    'projection': {'projectionDays': '$list'},

    'desiredstate': {'configChanges': {'automationSettingList': [{'uuid': 'utilTarget', 'value': '$center'}, {'uuid': 'targetBand', 'value': '$diameter'}]}},
    AutomationSetting.PROVISION_PM: {'configChanges': {'automationSettingList': [{'uuid': '$uuid', 'value': '$value', 'entityType': 'PhysicalMachine'}]}},
    AutomationSetting.SUSPEND_PM: {'configChanges': {'automationSettingList': [{'uuid': '$uuid', 'value': '$value', 'entityType': 'PhysicalMachine'}]}},
    AutomationSetting.PROVISION_DS: {'configChanges': {'automationSettingList': [{'uuid': '$uuid', 'value': '$value', 'entityType': 'Storage'}]}},
    AutomationSetting.SUSPEND_DS: {'configChanges': {'automationSettingList': [{'uuid': '$uuid', 'value': '$value', 'entityType': 'Storage'}]}},
    AutomationSetting.RESIZE: {'configChanges': {'automationSettingList': [{'uuid': '$uuid', 'value': '$value', 'entityType': 'VirtualMachine'}]}},

    'osmigration': {'configChanges': {'osMigrationSettingsList': [{'uuid': '$setting', 'value': '$value'}]}},
    'constraint': {'configChanges': {'removeConstraintList': [{'projectionDay': '$projection', 'constraintType': '$name', 'target': {'uuid': '$uuid'}}]}},

    'histbaseline': {'loadChanges': {'baselineDate': '$date'}},
    'peakbaseline': {'loadChanges': {'peakBaselineList': [{'date': '$date', 'target': {'uuid': '$uuid'}}]}},
    'maxutil': {'loadChanges': {'maxUtilizationList': [{'maxPercentage': '$util', 'projectionDay': '$projection', 'target': {'uuid': '$uuid'}}]}},
    'curutil': {'loadChanges': {'utilizationList': [{'percentage': '$util', 'projectionDay': '$projection', 'target': {'uuid': '$uuid'}}]}},

    'addhist': {'timebasedTopologyChanges': {'addHistoryVMs': '$value'}},
    'includereserved': {'timebasedTopologyChanges': {'includeReservation': '$value'}},

    EntityAction.ADD: {'topologyChanges': {'addList': [{'count': '$count', 'projectionDays': '$projection', 'target': {'uuid': '$target'}}]}},
    EntityAction.MIGRATE: {'topologyChanges': {'migrateList': [{'projectionDay': '$projection', 'source': {'uuid': '$source'}, 'destination': {'uuid': '$destination'}}]}},
    EntityAction.REMOVE: {'topologyChanges': {'removeList': [{'projectionDay': '$projection', 'target': {'uuid': '$target'}}]}},
    EntityAction.REPLACE: {'topologyChanges': {'replaceList': [{'projectionDay': '$projection', 'target': {'uuid': '$target'}, 'template': {'uuid': '$new_target'}}]}},
    'relievepressure': {'topologyChanges': {'relievePressureList': [{'projectionDay': '$projection', 'sources': [{'uuid': '$source'}], 'destinations': [{'uuid': '$destination'}],}]}},
}

# 7.21.x+
_dto_map_scenario_settings_721 = {
    AutomationSetting.PROVISION_PM: {'configChanges': {'automationSettingList': [{'uuid': 'provision', 'value': '@value:ENABLED;DISABLED', 'entityType': 'PhysicalMachine'}]}},
    AutomationSetting.SUSPEND_PM: {'configChanges': {'automationSettingList': [{'uuid': 'suspend', 'value': '@value:ENABLED;DISABLED', 'entityType': 'PhysicalMachine'}]}},
    AutomationSetting.PROVISION_DS: {'configChanges': {'automationSettingList': [{'uuid': 'provision', 'value': '@value:ENABLED;DISABLED', 'entityType': 'Storage'}]}},
    AutomationSetting.SUSPEND_DS: {'configChanges': {'automationSettingList': [{'uuid': 'suspend', 'value': '@value:ENABLED;DISABLED', 'entityType': 'Storage'}]}},
    AutomationSetting.RESIZE: {'configChanges': {'automationSettingList': [{'uuid': 'resize', 'value': '@value:ENABLED;DISABLED', 'entityType': 'VirtualMachine'}]}},
}



## ----------------------------------------------------
##  Decorators
## ----------------------------------------------------
def deprecated(*fargs):
    name = None

    def _deprecated(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            text = f'{name or func.__name__} is deprecated'

            if msg:
                text += f', use {msg} instead.'

            warnings.warn(text, DeprecationWarning)

            return func(*args, **kwargs)
        return wrapper

    if callable(fargs[0]):
        name = fargs[0].__name__
        msg = None
        return _deprecated(fargs[0])

    msg = fargs[0]
    return _deprecated



# ----------------------------------------------------
#  API Wrapper Classes
# ----------------------------------------------------
PlanHook = namedtuple('PlanHook', ['name', 'args'])


class Plan(LoggingMixin):
    """Plan instance.

    Args:
        connection (:class:`~vmtconnect.Connection`): :class:`~vmtconnect.Connection` or :class:`~vmtconnect.Session`.
        spec (:class:`PlanSpec`, optional): Settings to apply to the market, if
            running a plan.
        market (str, optional): Base market UUID to apply the settings to.
        name (str, optional): Plan display name.

    Attributes:
        duration (int): Plan duration in seconds, or ``None`` if unavailable.
        initialized (bool): ``True`` if the market is initialized and usable.
        market_id (str): Market UUID, read-only attribute.
        market_name (str): Market name, read-only attribute.
        result (:class:`~vmtplanner.MarketState`): Market run result state.
        scenario_id (str): Scenario UUID, read-only attribute.
        scenario_name (str): Scenario name, read-only attribute.
        script_duration (int): Plan script duration in seconds.
        server_duration (int): Plan server side duration in seconds.
        state (:class:`MarketState`): Current state of the market.
        start (:class:`~datetime.datetime`): :class:`~datetime.datetime` object
            representing the start time, or ``None`` if no plan has been run.
        unplaced_entities (bool): ``True`` if there are unplaced entities.
    """
    # system level markets to block certain actions
    __system = ['Market', 'Market_Default']

    __datetime_format = "%Y-%m-%dT%H:%M:%S%z"

    def __init__(self, connection, spec=None, market='Market', name=None):
        super().__init__()
        self._vmt = connection
        self.__init = False
        self.__scenario_id = None
        self.__scenario_name = spec.name if spec is not None else None
        self.__market_id = None
        self.__market_name = name if name else self.__gen_market_name()
        self.__plan = spec
        self.__plan_start = None
        self.__plan_end = None
        self.__plan_duration = None
        self.__plan_server_start = None
        self.__plan_server_end = None
        self.__plan_server_duration = None
        self.__hook_preprocessor = None
        self.__hook_postprocessor = None
        self.result = None
        self.unplaced = None
        self.base_market = market

        # enforce module specific version exclusions
        vspec = vc.VersionSpec(_VERSION_REQ, exclude=_VERSION_EXC)
        vspec.check(self._vmt.version)

        # assign the spec version to build
        if self.__plan.version is None:
            self.__plan.version = self._vmt.version

        # instance version monkey patching magic, default is pre 5.9.1
        if vc.VersionSpec.cmp_ver(self.__plan.version.base_version, '5.9.1') >= 0:
            self.__init_scenario_request = self.__init_scenario_request_591

        self.log('Plan initialized', level='debug')

    @property
    def initialized(self):
        return self.__init

    @property
    def state(self):
        if self.__init:
            return self.get_state()

        return False

    @property
    def start(self):
        return self.__plan_start

    @property
    def duration(self):
        if self.__plan_server_duration is not None:
            return self.__plan_server_duration

        return self.__plan_duration

    @property
    def server_duration(self):
        return self.__plan_server_duration

    @property
    def script_duration(self):
        return self.__plan_duration

    @property
    def scenario_id(self):
        return self.__scenario_id

    @property
    def scenario_name(self):
        return self.__scenario_name

    @property
    def market_id(self):
        return self.__market_id

    @property
    def market_name(self):
        return self.__market_name

    @property
    def unplaced_entities(self):
        return self.unplaced

    @property
    def results(self):
        # for backwards compatibility
        return self.result

    def __gen_market_name(self):
        user = self._vmt.get_users('me')[0]['username']
        return f'CUSTOM_{user}_{str(int(time.time()))}'

    def __sync_server_data(self):
        market = self._vmt.get_markets(uuid=self.__market_id)[0]

        try:
            self.__market_id = market['uuid']
            self.__market_name = market['displayName']
            self.unplaced = market['unplacedEntities']
            self.__plan_server_start = datetime.datetime.strptime(market['runDate'], self.__datetime_format)
            self.__plan_server_end = datetime.datetime.strptime(market['runCompleteDate'], self.__datetime_format)
            self.__plan_server_duration = (self.__plan_server_end - self.__plan_server_start).total_seconds()
        except Exception:                                                      # pylint: disable=W0703
            pass

    def __wait_for_stop(self):
        if self.__plan.abort_timeout < self.__plan.abort_poll_freq:
            self.__plan.abort_poll_freq = self.__plan.abort_timeout

        start = datetime.datetime.now()

        while True:
            if self.is_complete() or self.is_stopped():
                return True

            run_time = (datetime.datetime.now() - start).total_seconds() / 60

            if run_time > self.__plan.abort_timeout:
                break

            time.sleep(self.__plan.abort_poll_freq)

        raise PlanError

    def __wait_for_plan(self):
        def rnd_up(number, multiple):
            num = math.ceil(number) + (multiple - 1)
            return num - (num % multiple)

        while True:
            if self.is_complete() or self.is_stopped():
                break
            elif self.__plan.timeout > 0 \
                 and datetime.datetime.now() >= (self.__plan_start + \
                     datetime.timedelta(minutes=self.__plan.timeout)):
                try:
                    self.stop()
                except vc.HTTP502Error:
                    pass
                except vc.HTTP500Error:
                    raise PlanError('Server error stopping plan')
                except vc.HTTPError:
                    raise PlanError('Plan stop command error')

                raise PlanExecutionExceeded(f'Plan execution time exceeded maximum allowed, market state: {self.get_state()}')
            else:
                if self.__plan.poll_freq > 0:
                    wait = self.__plan.poll_freq
                else:
                    run_time = (datetime.datetime.now() - self.__plan_start).total_seconds()
                    wait = rnd_up(run_time/12, 5) if run_time < 600 else 60

                time.sleep(wait)

                if self.is_state(MarketState.CREATED):
                    # catches a failed start after the first wait,
                    # indicates a stuck plan
                    raise PlanRunFailure(f'Plan failed to properly initialize. Check catalina.out for more details. Market ID: [{self.__market_id}], Scenario ID: [{self.__scenario_id}]')

    def __delete(self, scenario=True):
        m = self._vmt.del_market(self.__market_id)
        s = True if scenario else self._vmt.del_scenario(self.__scenario_id)

        if m and s:
            return True

        raise PlanDeprovisionError()

    def __init_scenario_request(self, dto):                                    # pylint: disable=E0202
        # pre 5.9.1 compatibility (upto & including 5.9.0)
        return self._vmt.request('scenarios/' + self.__plan.name,
                                  method='POST', dto=dto)[0]

    def __init_scenario_request_591(self, dto):
        # 5.9.1 and later compatibility
        return self._vmt.request('scenarios', method='POST', dto=dto)[0]

    def __init_scenario(self):
        if vc.VersionSpec.cmp_ver(self.__plan.version.base_version, '7.21.0') >= 0 and \
           vc.VersionSpec.cmp_ver(self.__plan.version.base_version, '7.21.5') < 0:
            # special case for OM-57067
            # we must augement scope input to work around the bug
            dto = json.loads(self.__plan.json)

            for i, _ in enumerate(dto['scope']):
                ent = self._vmt.search(uuid=dto['scope'][i]['uuid'])[0]
                dto['scope'][i]['displayName'] = ent['displayName']
                dto['scope'][i]['className'] = ent['className']

            response = self.__init_scenario_request(json.dumps(dto))
        else:
            # create the scenario for the plan
            response = self.__init_scenario_request(self.__plan.json)

        self.__scenario_id = response['uuid']
        self.__scenario_name = response['displayName']

        return response['uuid']

    def __init_market(self):
        # create the plan market, and apply the scenario
        path = 'markets/{}/scenarios/{}'.format(self.base_market, self.__scenario_id)
        param = {'plan_market_name': self.__market_name}

        if self.__plan.params:
            param.update(self.__plan.params)

        response = self._vmt.request(path, method='POST', query=param)[0]

        self.__market_id = response['uuid']
        self.__market_name = response['displayName']

        return response['uuid']

    def __run(self, async=False):
        # main plan execution control
        self.__init_scenario()
        self.__init_market()
        self.__init = True
        self.__plan_start = datetime.datetime.now()

        if async:
            return self.state

        self.__wait_for_plan()
        self.__sync_server_data()
        self.__plan_duration = (datetime.datetime.now() - self.__plan_start).total_seconds()

        return self.state

    def get_stats(self):
        """Returns statistics for the market.

        Returns:
            list: A list of statistics by period.
        """
        return self._vmt.get_market_stats(self.__market_id)

    def is_system(self):
        """Checks if the market is a protected system market.

        Returns:
            bool: ``True`` if the market is a designated system market, ``False`` otherwise.
        """
        if self.__market_name in self.__system:
            return True

        return False

    def is_state(self, state):
        """Checks if the market is in the given state.

        Args:
            state (:obj:`MarketState`): Market state to compare to.

        Returns:
            bool: ``True`` if matched, ``False`` otherwise.
        """
        return bool(self.get_state() == state)

    def is_complete(self):
        """Returns ``True`` if the market completed successfully."""
        return self.is_state(MarketState.SUCCEEDED)

    def is_ready(self):
        """Returns ``True`` if market is initialized and ready to start."""
        return self.is_state(MarketState.READY_TO_START)

    def is_stopped(self):
        """Returns ``True`` if market state is stopped."""
        return self.is_state(MarketState.STOPPED)

    def is_running(self):
        """Returns ``True`` if market state is currently running."""
        return self.is_state(MarketState.RUNNING)

    def get_state(self):
        """Returns the current market state.

        Returns:
            :class:`MarketState`: Current market state.
        """
        try:
            market = self._vmt.get_markets(uuid=self.__market_id)
            self.__init = True

            return MarketState[market[0]['state']]

        except KeyError:
            return None

    def hook_pre(self, name, *args, **kwargs):
        self.__hook_preprocessor = PlanHook(name, args)

    def hook_post(self, name, *args, **kwargs):
        self.__hook_postprocessor = PlanHook(name, args)

    def run(self):
        """Runs the market with currently applied scenario and settings.

        Raises:
            PlanError if retry limit is reached.
        """
        if self.__hook_preprocessor:
            self.__hook_preprocessor.name(*self.__hook_preprocessor.args)

        run = 0
        ret = None
        trace = None

        while run < self.__plan.max_retry:
            try:
                self.result = self.__run()
                break
            except (vc.HTTP500Error, PlanError):
                trace = traceback.format_exc()
                run += 1
                pass

        if not self.result:
            raise PlanError(f'Retry limit reached. Last error:\n{trace}')

        if self.__hook_postprocessor:
            return self.__hook_postprocessor.name(*self.__hook_postprocessor.args)

        return self.result

    def run_async(self):
        # TODO: make async threaded so it is called with hooks and settings
        """Runs the market plan in asynchronous mode.

        When run asynchronously the plan will be started and the state returned
        immediately. All settings pertaining to polling, timeout, and retry
        will be ignored. The :class:`~Plan.duration` will not be recorded, and
        plan hooks are not called.
        """
        return self.__run(async=True)

    def stop(self):
        """Stops the market.

        Returns:
            bool: ``True`` upon success. Raises an exception otherwise.

        Raises:
            vmtconnect.HTTP500Error
            PlanError: Error stopping plan
        """
        try:
            self._vmt.request('markets', uuid=self.__market_id, method='PUT',
                               query='operation=stop')
            self.__wait_for_stop()
            self.__plan_duration = (datetime.datetime.now() - self.__plan_start).total_seconds()

        except vc.HTTP500Error:
            raise
        except Exception as e:
            raise PlanError(f'Error stopping plan: {e}')

        return True

    def delete(self, scenario=True):
        """Removes the market, and the scenario.

        Args:
            scenario (bool, optional): If ``True``, removes the scenario as well. (default: ``True``)

        Returns:
            bool: ``True`` upon success, ``False`` otherwise.

        Raises:
            InvalidMarketError: Attempting to delete system market
            InvalidMarketError: Market does not exist
            PlanDeprovisionError: Error removing the plan
        """
        if self.is_system():
            raise InvalidMarketError('Attempting to delete system market')

        if not self.__init:
            raise InvalidMarketError('Market does not exist')

        if self.__delete(scenario) == ServerResponse.TRUE:
            self.__init = False
            return True

        return False


# adapted from pytur
class PlanSpec:
    """Plan scenario specification.

    Args:
        name (str, optional): Name of the plan scenario.
        type (:class:`PlanType`, optional): Type of plan to be run. (default: :class:`PlanType.CUSTOM`)
        scope (list, optional): Scope of the plan market.
        version (:class:`vmt-connect.Version`, optional): PlanSpec version.

    Attributes:
        abort_timeout (int): Abort timeout in minutes.
        abort_poll_freq (int): Abort status polling interval in seconds.
        max_retry (int): Plan retry limit.
        poll_freq (int): Status polling interval in seconds, 0 = dynamic.
        timeout (int): Plan timeout in minutes, 0 = infinite.

    Notes:
        The `changes` and `entities` parameters were removed in v2.0.0.
        If `version` is not supplied, the :class:`~vmt-connect.Connection` version
        will be used when the scenario is evaluated by the :class:`Plan` class.
        If you need to generate a scenario DTO without a :class:`Plan` class,
        you will need to supply the `version` prior to calling :meth:`.to_json`
        or accessing the `json` property.
    """
    def __init__(self, name=None, type=PlanType.CUSTOM, scope=None, version=None):
        # private
        self.__settings = []
        self.__projection = [0]

        # public
        self.version = version
        self.name = name if name else self.__gen_scenario_name()
        self.type = type
        self.ignore_constraints = False

        self.abort_timeout = 5
        self.abort_poll_freq = 5
        self.max_retry = 3
        self.poll_freq = 0
        self.timeout = 0

        self.set_scope(scope)

    @staticmethod
    def __gen_scenario_name():
        return 'CUSTOM_' + datetime.datetime.today().strftime('%Y%m%d_%H%M%S')

    @property
    def json(self):
        return self.to_json(self.version, indent=2)

    @property
    def params(self):
        return self.get_params()

    def __setting_add(self, setting, values):
        self.__settings.append({setting: values})

    def __setting_update(self, setting, values, filter=None):
        found = False

        for v in self.__settings:
            key = list(v)[0]

            if key == setting:
                try:
                    for fk, fv in filter.items():
                        if not check_key_value(v[key], fk, fv):
                            raise ContinueOuter

                        found = True

                except AttributeError:
                    found = True
                    pass
                except ContinueOuter:
                    continue

                for nk, nv in values.items():
                    set_key_value(v[key], nk, nv)

        if not found:
            self.__setting_add(setting, values)

    def __setting_remove(self, setting, filter=None):
        for v in self.__settings:
            key = list(v)[0]

            if key == setting:
                try:
                    for fk, fv in filter.items():
                        if not check_key_value(v[key], fk, fv):
                            raise ContinueOuter

                except AttributeError:
                    pass
                except ContinueOuter:
                    continue

                del v[key]

    @deprecated('change_entity')
    def add_entity(self, id, count=1, periods=None):
        """Add copies of an entity.

        Important:
            Deprecated legacy interface. Use :meth:`.change_entity` instead.

            This is an alias for :meth:`.change_entity` provided for backward
            compatibility.

        Args:
            id (str): Target entity UUID.
            count (int, optional): Number of copies to add. (default: ``1``)
            periods (list, optional): List of periods to add copies. (default: `[0]`)

        See Also:
            See :ref:`plan_periods`.
        """
        if periods is None:
            periods = [0]

        self.change_entity(EntityAction.ADD, targets=[id], count=count, projection=periods)

    def add_historical(self, value=True):
        """Add VMs based on previous month.

        Args:
            value (bool): ``True`` or ``False``. (default: ``True``)
        """
        self.__setting_update('addhist', {'value': value})

    def add_hist(self, value=True):
        """Alias for :meth:`.add_historical`."""
        self.add_historical(value)

    @deprecated('change_entity')
    def add_template(self, id, count=1, periods=None):
        """Add copies of a template.

        Important:
            Deprecated legacy interface. Use :meth:`.change_entity` instead.

            This is an alias for :meth:`.change_entity` provided for backward
            compatibility.

        Args:
            id (str): Target entity UUID.
            count (int, optional): Number of copies to add. (default: ``1``)
            periods (list, optional): List of periods to add copies. (default: ``[0]``)

        See Also:
            See :ref:`plan_periods`.
        """
        if periods is None:
            periods = [0]

        self.change_entity(EntityAction.ADD, targets=[id], count=count, projection=periods)

    def change_automation_setting(self, setting, value):
        """Change plan automation settings.

        Args:
            setting (:class:`AutomationSetting`): Setting to modify.
            value : For most settings, the value will be a :obj:`bool`. For desired
              state changes, the value will be an :obj:`int`.
        """
        if setting in (AutomationSetting.UTIL_TARGET, AutomationSetting.TARGET_BAND):
            label = 'center' if setting == AutomationSetting.UTIL_TARGET else 'diameter'
            self.__setting_update('desiredstate', {label: value})

        elif setting == AutomationSetting.RESIZE:
            type = 'ENABLED' if value else 'DISABLED'
            desc = 'Resize ' + type.lower() # debugging disambiguation
            self.__setting_update(setting, {'uuid': setting.value, 'value': value, 'type': type, 'desc': desc})

        else:
            self.__setting_add(setting, {'uuid': setting.value, 'value': value})

    def change_entity(self, action, targets, projection=[0], count=None, new_target=None):
        """Change entities in the environment.

        Change entities handles adding, removing, replacing, and migrating entities
        within the plan. Each :class:`EntityAction` has different required parameters,
        as defined below.

            Common Parameters
                * action - required
                * targets - required
                * projection - optional

            Add Entity Specific Parameters
                * count - optional

            Replace Entity Specific Parameters
                * new_target - required

            Migrate Entity Specific Parameters
                * new_target - required

        Args:
            action (:class:`EntityAction`): Change to effect on the entity.
            targets (list): List of entity or group UUIDs.
            projection (list): List of days from today at which to make change.
                (default: ``[0]``)
            count (int): Number of copies to add. (default: ``1``)
            new_target (str): Template UUID to replace `target` with. Destination
              group or host UUID for migrations.

        See Also:
            See :ref:`plan_periods`.
        """
        if isinstance(targets, str):
            targets = [targets]

        if isinstance(projection, int):
            projection = [projection]

        self.__projection = list(set(self.__projection + projection))

        for id in targets:
            change = {'target': id}

            if action == EntityAction.ADD:
                change['count'] = count or 1

            elif action == EntityAction.REPLACE:
                change['template'] = new_target

            elif action == EntityAction.MIGRATE:
                change['source'] = id
                change['destination'] = new_target

            change['projection'] = projection if action == EntityAction.ADD else projection[0]

            self.__setting_add(action, change)

        # TODO: this needs some additional investigation on how the UI determines what to remove
        #if self.type == PlanType.CLOUD_MIGRATION:
        #    self.set_scope(targets)
        #    self.change_entity(EntityAction.REMOVE, new_target, projection)

    def change_max_utilization(self, targets, type='', value=0, projection=0):
        """Set the max percentage of a commodity's capacity a VM or group of
        VMs can consume.

        Args:
            targets (list): List of entity or group UUIDs.
            type (str, conditional): Commodity type to modify. (ignored in 6.1.0+)
            value (int): Utilization value as a positive integer 0 to 100.
            projection (int, optional): Singular period in which to set the setting.
                (default: ``0``)

        Notes:
            This method provides backwards compatibility with previous versions of
            Turbonomic which require deprecated parameters. The `type` parameter
            is required by versions of Turbonomic prior to 6.1.0, and ignored
            otherewise.
        """
        if isinstance(targets, str):
            targets = [targets]

        for id in targets:
            self.__setting_update('maxutil', {'uuid': id, 'util': value, 'projection': projection, 'type': type}, filter={'uuid': id})

    def change_utilization(self, targets, value, projection=0):
        """Change load of virtual machines by specified percentage.

        Args:
            targets (list): List of entity or group UUIDs.
            value (int): Utilization value as a positive integer 0 to 100.
            projection (int, optional): Singular period in which to set the
                setting.
        """
        if isinstance(targets, str):
            targets = [targets]

        for id in targets:
            self.__setting_update('curutil', {'uuid': id, 'util': value, 'projection': projection, 'type': type}, filter={'uuid': id})

    def cloud_os_profile(self, match_source=None, unlicensed=None, source=None, target=None, custom_map=None):
        """Configures OS migration profile for Migrate to Cloud plans.

        Custom mapping :obj:`dict` format:
          {'source': :class:`CloudOS`, 'target': :class:`CloudOS`, 'unlicensed': :obj:`bool`}

        Args:
            match_source (bool, optional): If ``True``, the source OS will be
                matched.
            unlicensed (bool, optional): If ``True``, destination targets will
                be selected without licensed OSes.
            source (:class:`CloudOS`): Source OS to map from.
            target (:class:`CloudOS`): Target OS to map to.
            custom (list, optional): List of :obj:`dict` custom OS settings.

        """
        if custom_map is not None:
            self.cloud_os_profile(match_source=False)

            for v in custom_map:
                self.__setting_update('osmigration', {'uuid': CloudTargetOS[v['source'].value], 'value': v['target'].value}, filter={'uuid': CloudTargetOS[v['source'].value]})

                if 'unlicensed' in v.keys():
                    self.__setting_update('osmigration', {'uuid': CloudLicense[v['source'].value], 'value': v['unlicensed'].value}, filter={'uuid': CloudLicense[v['source'].value]})

        elif source is not None and target is not None:
            self.__setting_update('osmigration', {'uuid': CloudTargetOS[source.value], 'value': target.value}, filter={'uuid': CloudTargetOS[source.value]})

            if unlicensed is not None:
                self.__setting_update('osmigration', {'uuid': CloudLicense[source.value], 'value': unlicensed}, filter={'uuid': CloudLicense[source.value]})

        else:
            if match_source is not None:
                self.__setting_update('osmigration', {'uuid': 'matchToSource', 'value': match_source}, filter={'uuid': 'matchToSource'})

            if unlicensed is not None:
                for i in CloudOS:
                    self.__setting_update('osmigration', {'uuid': CloudLicense[i.value], 'value': unlicensed}, filter={'uuid':  CloudLicense[i.value]})

    @deprecated('change_entity')
    def delete_entity(self, id, periods=None):
        """Remove an entity.

        Important:
            Deprecated legacy interface. Use :meth:`.change_entity` instead.

            This is an alias for :meth:`.change_entity` provided for backward
            compatibility.

        Args:
            id (str): Target entity UUID.
            periods (list, optional): List of periods to add copies. (default: ``[0]``)

        See Also:
            See :ref:`plan_periods`.
        """
        if periods is None:
            periods = [0]

        self.change_entity(EntityAction.REMOVE, targets=[id], projection=periods)

    def get_params(self):
        if self.ignore_constraints:
            return {'ignore_constraints': self.ignore_constraints}

        return None

    def get_settings(self):
        settings = []
        settings.append({'name': {'value': self.name}})
        settings.append({'projection': {'list': self.__projection}})

        if self.__scope is not None:
            settings.append({'scope': {'scope': self.__scope}})

        settings.append({'type': {'value': self.type.value}})
        settings.extend(self.__settings)

        return settings

    def include_reserved(self, value=True):
        """Setting to include reserved VMs in the plan.

        Args:
            value (bool): ``True`` or ``False``. (default: ``True``)
        """
        self.__setting_update('includereserved', {'value': value})

    def migrate_entity(self, id, destination_id, period=0):
        """Migrate entity.

        Important:
            Deprecated legacy interface. Use :meth:`.change_entity` instead.

            This is an alias for :meth:`.change_entity` provided for backward
            compatibility.

        Args:
            id (str): Target entity or group UUID to migrate.
            destination_id (str): Destination entity or group UUID.
            period (int, optional): Period in which to migrate. (default: ``0``)

        See Also:
            See :ref:`plan_periods`.
        """
        self.change_entity(EntityAction.MIGRATE, targets=id, projection=period, new_target=destination_id)

    def remove_constraints(self, targets=None, commodity=None, projection=0):
        """Removes specific constraints for selected entities, or all constraints for the entire market.

        Args:
            targets (list, optional): List of entity or group UUIDs.
            commodity (:class:`ConstraintCommodity`, optional): Commodity constraint to remove on a target.
                `targets` is required with this parameter, or it is ignored.
            projection (int, optional): Singular period in which to set the setting.

        Notes:
            To remove all constraints from the entire market (global level),
            leave the `targets` and `commodity` fields empty.

        """
        if targets and commodity:
            if isinstance(targets, str):
                targets = [targets]

            base = {'projection': projection, 'value': False}

            if commodity:
                base['name'] = commodity.value

            for id in targets:
                values = base.copy()
                values['uuid'] = id
                self.__setting_update('constraint', values, filter={'uuid': id})
        elif not targets and not commodity:
            self.ignore_constraints = True

    def replace_entity(self, id, replacement_id, count=1, periods=None):
        """Replace an entity with a template.

        Important:
            Deprecated legacy interface. Use :meth:`.change_entity` instead.

            This is an alias for :meth:`.change_entity` provided for backward
            compatibility.

        Args:
            id (str): UUID of the entity to replace.
            replacement_id (str): Template UUID to use as a replacement.
            count (int, optional): Number of copies to add. (default: ``1``)
            periods (list, optional): List of periods to add copies. (default: ``[0]``)

        See Also:
            See :ref:`plan_periods`.
        """
        if periods is None:
            periods = [0]

        self.change_entity(EntityAction.REPLACE, targets=id, new_target=replacement_id, count=count, projection=periods)

    def relieve_pressure(self, sources, targets, projection=0):
        """Migrates hot clusters to cold clusters to alleviate resource pressure.

        Scope should not be set to market for this plan type. Unlike other entity
        methods, :meth:`.relieve_pressure` is primairly purposed for the
        ``ALLEVIATE_PRESSURE`` plan type. It should only be used in
        ``ALLEVIATE_PRESSURE`` or ``CUSTOM`` plans.

        Args:
            sources (list): list of one or more cluster UUIDs to migrate.
            targets (list): list of one or more destination cluster UUIDs.
            projection (int, optional): Period in which to migrate.
        """
        if isinstance(sources, str):
            sources = [sources]

        if isinstance(targets, str):
            targets = [targets]

        self.set_scope(sources, append=True)
        self.set_scope(targets, append=True)

        self.__setting_add('relievepressure', {'source': sources, 'destination': targets, 'projection': projection})

    @deprecated('change_automation_setting')
    def set(self, center=None, diameter=None, description=None):               # pylint: disable=W0613
        """Deprecated - see :meth:`.change_automation_setting`"""
        self.change_automation_setting(AutomationSetting.UTIL_TARGET, center)
        self.change_automation_setting(AutomationSetting.TARGET_BAND, diameter)

    def set_historical_baseline(self, value):
        """Set the used and peak utilization for the plan based on historical data.

        Args:
            value (int): Date as a Unix timestamp in milliseconds.
        """
        self.__setting_update('histbaseline', {'value': value, 'date': epoch_to_ts(value)})

    def set_hist_baseline(self, value):
        """Alias for `set_historical_baseline()`."""
        self.set_historical_baseline(value)

    @deprecated('change_max_utilization')
    def set_max_utilization(self, type, value, ids, periods=None):
        """Deprecated - see :meth:`.change_max_utilization`"""
        if periods is None:
            periods = [0]

        self.change_max_utilization(type=type, value=value, targets=ids, projection=periods[0])

    def set_peak_baseline(self, targets, value):
        """Loads a peak baseline from history.

        Args:
            value (int): Date as a Unix timestamp in milliseconds.
            ids (list): List of VM cluster UUIDs.
        """
        if isinstance(targets, str):
            targets = [targets]

        for id in targets:
            self.__setting_update('peakbaseline', {'uuid': id, 'value': value, 'date': epoch_to_ts(value)})

    def set_scope(self, targets, append=False):
        """Sets the plan scope.

        Args:
            targets (list): List of entity or group UUIDs.
            append (bool, optional): If ``True``, scope will be extended. (default: ``False``)
        """
        if not targets:
            self.__scope = []
            return

        if isinstance(targets, str):
            targets = [targets]

        ids = kw_to_list_dict('value', targets)

        if append and self.__scope:
            self.__scope.extend(ids)
        else:
            self.__scope = ids

    @deprecated('change_utilization')
    def set_used(self, value, ids):
        """Deprecated - see :meth:`.change_utilization`"""
        self.change_utilization(value=value, targets=ids)

    @deprecated('change_max_utilization')
    def set_utilization(self, type, value, ids):
        """Deprecated - see :meth:`.change_max_utilization`"""
        self.change_max_utilization(type=type, value=value, targets=ids)

    def to_json(self, version=None, **kwargs):
        """Returns the version specific DTO for the scenario.

        Args:
            version (object, optional): :class:`Version` object.
            **kwargs: Additional JSON processing arguments.

        Raises:
            PlanError if no version definition is supplied.
        """
        def updatemap(d, s):
            for i in s:
                d[i] = s[i]

        version = version if version else self.version

        if not version:
            raise PlanError('Unable to map settings to version type of None')

        dto = {}
        fix59 = False

        # TODO: more elegant solution
        if vc.VersionSpec.cmp_ver(version.base_version, '6.1.0') >= 0:
            map = _dto_map_scenario_settings_610

            # patch for XL
            if vc.VersionSpec.cmp_ver(version.base_version, '7.21') >= 0:
                updatemap(map, _dto_map_scenario_settings_721)

            settings = self.get_settings()
        # 5.9 support to be removed when classic is deprecated (if ever?)
        elif vc.VersionSpec.cmp_ver(version.base_version, '5.9.0') >= 0:
            fix59 = True
            collation = copy.deepcopy(_scenario_settings_collations_590)
            map = _dto_map_scenario_settings_590
            settings = collate_settings(self.get_settings(), collation)
        else:
            raise PlanSettingsError(f'No settings map for version: {version.base_version}')

        for i in settings:
            key = list(i)[0]
            dto = map_settings(map[key], i[key], dto)

        # fix 5.9 ADDED / ADD_REPEAT
        if fix59:
            try:
                for i in dto['changes']:
                    if i['type'] == 'ADDED' and len(i['projectionDays']) > 1:
                        i['type'] = 'ADD_REPEAT'
            except KeyError:
                pass

        return json.dumps(dto, sort_keys=True, **kwargs)



## ----------------------------------------------------
##  General functions
## ----------------------------------------------------
def epoch_to_ts(value):
    """Returns an ISO 8601 format timestamp from the given epoch value.

    Args:
        value (int): epoch time string given in either seconds or milliseconds.
    """
    try:
        return datetime.datetime.utcfromtimestamp(value).strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        return datetime.datetime.utcfromtimestamp(value/1000).strftime('%Y-%m-%dT%H:%M:%SZ')


def kw_to_dict(**kwargs):
    """Returns a dictionary based on keyword arguments.

    Args:
        **kwargs: Arguments to convert.

    Returns:
        dict: A formatted dictionary.

    Example:
        ``kw_to_dict(foo='Hello', bar='World')`` returns ``{'foo': 'Hello', 'bar': 'World'}``
    """
    return {k: v for k, v in kwargs.items()}


def kw_to_list_dict(key, values):
    """Returns a list of single entry dictionaries with key of ``key`` and value
    from ``values``.

    Args:
        key (str): String representing the key name to use for all values.
        values (list): List of values to be paired individually with the key.

    Returns:
        list: A list of formatted dictionaries.

    Example:
        ``kw_to_list_dict('uuid', [1,2,3])`` returns ``[{'uuid': 1}, {'uuid': 2}, {'uuid': 3}]``
    """
    return [{key: x} for x in values]


def check_key_value(data, key, value):
    """Checks a key for the given value within a dictionary recursively."""
    if isinstance(key, dict):
        for k, v in key.items():
            return check_key_value(data[k], v, value)

    if data[key] == value:
        return True

    return False


def set_key_value(data, key, value):
    """Updates a key with the given value within a dictionary recursively."""
    if isinstance(key, dict):
        for k, v in key.items():
            set_key_value(data[k], v, value)
    else:
        data[key] = value


def map_value(value, mapdef):
    """Value resolution map.

    Args:
        mapdef (str): Mapping definition
        value: Value to be mapped

    Notes:
        The map is expected as sets of equality pairs (old=new), or a single set
        of boolean values separated by a semicolons (;). All values except
        boolean values will be treated as strings. For example:
            boolean set: ENABLED;DISABLED
            list of pairs: on=ENABLED;off=DISABLED;closed=DISABLED

    Returns:
        Mapped value.

    Raises:
        InvalidValueMapError: If the value map is malformed
    """
    try:
        if '=' in mapdef:
            for x in mapdef.split(';'):
                src, dest = x.split('=')

                if src == value:
                    return dest
        else:
            t, f = mapdef.split(';')

            if value:
                return t

            return f
    except Exception:
        raise InvalidValueMapError('Value not resolvable for the given value map')

    return value


def resolve_value(var, values):
    """Resolves variables in settings map.

    Args:
        var: Variable to be resolved.
        values (dict): Dictionary of settings values.

    Returns:
        Resolved value, if there's an error it returns the unresolved variable.
    """
    def _sub(v):
        return values[v]

    def _map(v):
        _var, _map = v.split(':')
        return map_value(values[_var], _map)

    if isinstance(var, str):
        try:
            if var[0] == '$':
                return _sub(var[1:])
            if var[0] == '@':
                return _map(var[1:])
        except Exception:
            return var

    if isinstance(var, list):
        for i, v in enumerate(var):
            var[i] = resolve_value(v, values)

        return var

    return var


def map_settings(map, values, setting=None):
    """Maps a settings definition against the API version and values.

    Args:
        map (dict): Key value pair mappings for individual setting.
        values (dict): Values to resolve.
        setting (dict, optional): Existing settings to update.

    Returns:
        Modified `setting` dictionary.

    Notes:
        Dictionary values will be overwritten if the same key is called again,
        while list values will be extended.
    """
    if setting is None:
        setting = {}

    for k, v in map.items():
        # nested syntax
        if isinstance(v, Mapping):
            setting[k] = map_settings(v, values, setting.get(k, {}))

        # list of values
        elif isinstance(v, list):
            # group by
            if '[' in k:
                _list = []
                group = k[k.find('[')+1:k.find(']')]
                k = k[0:k.find('[')]
                _list += [map_settings(x, i) for x in v for i in values[group]]
            else:
                _list = [map_settings(x, values) for x in v]

            if isinstance(setting.get(k, {}), list):
                setting[k].extend(_list)
            else:
                setting[k] = _list

        # simple case
        else:
            setting[k] = resolve_value(v, values)

    return setting


def collate_settings(s, c):
    """Collates fields across settings entries based on a collation mapping.

    Collates multiple individual settings entries into a single combined entry
    where a collation mapping exists.
    type - type of collation to perform (currently only list_value)
    groups - list of groupings to collate based on labels
    label - a tag for the groupable field name, appended in square brackets: [ids]
    fields - list of fields to group to a label
    opt - optional list of grouping settings
        keepfirst - keeps the first value for non-groupable values (default)
        keeplast  - keeps the last value for non-groupable values

    Args:
        s (list): List of settings
        c (list): List of collation instructions
    """
    _set = []
    ignore = []
    # parse settings
    for i, val in enumerate(s):
        key = list(val)[0]
        # ignore already processed
        if key in ignore:
            continue

        # check collating map exists for this setting
        if key in c:
            _t = {}
            fieldgroups = {y: x['label'] for x in c[key]['groups'] for y in x['fields']}

            # group settings entries into single entry based on collation map
            if c[key]['type'] == 'list_value':
                for j, val2 in enumerate(s):
                    # skip ones we don't care about
                    if j < i:
                        continue

                    _grp = defaultdict(lambda: {})
                    # parse fields
                    for k, v in val2[key].items():
                        # group by
                        if k in fieldgroups:
                            _grp[fieldgroups[k]].update({k: v})
                        else:
                            # non-grouped field options
                            try:
                                fv_opt = c[key]['opt']['field_value']
                            except KeyError:
                                fv_opt = 'keepfirst'

                            if k not in _t or \
                               (fv_opt == 'keepfirst' and k not in _t) or \
                               fv_opt == 'keeplast':
                                _t[k] = v            # add back non-group value

                    for k, v in _grp.items():
                        _t[k] = _t.get(k, [])
                        _t[k].append(v)
            _set.append({key: _t})
            ignore.append(key) # prevent double processing settings
        # noop
        else:
            _set.append(val)
    return _set
