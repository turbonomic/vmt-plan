from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import time
import math
import json
import vmtconnect

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

try:
    from enum import Enum
except ImportError:
    try:
        from aenum import Enum
    except ImportError:
        print('Critical failure: no enum module found')


__version__ = '1.2.0.dev'
__all__ = [
    'MarketError',
    'InvalidMarketError',
    'PlanError',
    'PlanRunning',
    'PlanRunFailure',
    'PlanDeprovisionError',
    'PlanExecutionExceeded',
    'MarketState',
    'PlanSetting',
    'PlanType',
    'ServerResponse',
    'Plan',
    'PlanSpec'
]

_VERSION_REQ = ['5.8.5+']
_VERSION_EXC = []


## ----------------------------------------------------
##  Error Classes
## ----------------------------------------------------
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
    """Raised when a plan fails to start."""
    pass


# plan deprovisioning failure
class PlanDeprovisionError(PlanError):
    """Raised when there is an error removing a plan."""
    pass


# plan timeout exceeded
class PlanExecutionExceeded(PlanError):
    """Raised when a plan exceeds the timeout period specified."""
    pass



## ----------------------------------------------------
##  Enumerated Classes
## ----------------------------------------------------
#HostState = Enum('HostState', 'maintenanceOn maintenanceOff powerOn powerOff failoverOn failoverOff')

class MarketState(Enum):
    """Market states."""

    #: Indicates market plan is setup and ready to be run.
    READY_TO_START = 'ready'

    #: Indicates the plan scope is being copied.
    COPYING = 'copy'

    #: Indicates the market plan is being deleted.
    DELETING = 'del'

    #: Indicates the market plan is running.
    RUNNING = 'run'

    #: Indicates the market plan succeeded.
    SUCCEEDED = 'success'

    #: Indicates the market plan stopped.
    STOPPED = 'stop'


class PlanType(Enum):
    """Plan scenario types."""
    #:
    ADD_WORKLOAD = 'ADD_WORKLOAD'
    #:
    CLOUD_MIGRATION = 'CLOUD_MIGRATION'
    #:
    CUSTOM = 'CUSTOM'
    #:
    DECOMMISSION_HOST = 'DECOMMISSION_HOST'
    #:
    PROJECTION = 'PROJECTION'
    #:
    RECONFIGURE_HARDWARE = 'RECONFIGURE_HARDWARE'
    #:
    WORKLOAD_MIGRATION = 'WORKLOAD_MIGRATION'


class PlanSetting(Enum):
    """Plan settings."""
    #:
    TRUE = 'true'
    #:
    FALSE = 'false'
    #:
    ENABLED = 'enabled'
    #:
    DISABLED = 'disabled'
    #:
    RUN = 'run'
    #:
    STOP = 'stop'
    #:
    ADD = 'add'
    #:
    DELETE = 'delete'
    #:
    REPLACE = 'replace'


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


# ----------------------------------------------------
#  API Wrapper Classes
# ----------------------------------------------------
class Plan(object):
    """Plan instance.

    Args:
        connection (object): :class:`~vmtconnect.VMTConnection` object.
        spec (object, optional): :class:`PlanSpec` settings to apply to the market.
        market (str, optional): Base market UUID to apply the settings to.
            (default: Market)

    Attributes:
        duration (int): Plan duration in seconds, or None if unavailable.
        initialized (bool): Returns ``True`` if the market is initialized and usable.
        market_id (str): Market UUID, read-only attribute.
        market_name (str): Market name, read-only attribute.
        scenario_id (str): Scenario UUID, read-only attribute.
        scenario_name (str): Scenario name, read-only attribute.
        state (:class:`MarketState`): Current state of the market.
        start (:class:`~datetime.datetime`): Datetime object representing the
            start time, or None if no plan has been run.
    """
    # system level markets to block certain actions
    __system = ['Market', 'Market_Default']

    def __init__(self, connection, spec=None, market='Market'):
        self.__vmt = connection
        self.__init = False
        self.__scenario_id = None
        self.__scenario_name = spec.plan_name if spec is not None else self.__gen_scenario_name()
        self.__market_id = None
        self.__market_name = self.__gen_market_name()
        self.__plan = spec
        self.__plan_start = None
        self.__plan_end = None
        self.__plan_duration = None
        self.base_market = market

        ver = vmtconnect.VMTVersion(_VERSION_REQ, exclude=_VERSION_EXC)
        ver.check(connection.version)

    @property
    def initialized(self):
        return self.__init

    @property
    def state(self):
        if self.__init:
            return self.get_state()
        else:
            return False

    @property
    def start(self):
        return self.__plan_start

    @property
    def duration(self):
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

    def __gen_scenario_name(self):
        return 'CUSTOM_' + datetime.datetime.today().strftime('%Y%m%d_%H%M%S')

    def __gen_market_name(self):
        return 'CUSTOM_' + self.__vmt.get_users('me')['username'] + '_' + str(int(time.time()))

    def __wait_for_stop(self):
        for x in range(0, self.__plan.abort_timeout):
            time.sleep(self.__plan.abort_poll_freq)
            if self.is_complete() or self.is_stopped():
                return True

        raise PlanError

    def __wait_for_plan(self):
        done = False

        def rnd_up(number, multiple):
            num = math.ceil(number) + (multiple - 1)
            return num - (num % multiple)

        while not done:
            if self.is_complete() or self.is_stopped():
                done = True
            elif self.__plan.timeout > 0\
                 and datetime.datetime.now() >= (self.__plan_start + datetime.timedelta(minutes=self.__plan.timeout)):
                try:
                    self.stop()
                except vmtconnect.HTTP502Error:
                    pass
                except vmtconnect.HTTP500Error:
                    raise PlanError('Server error stopping plan')
                except vmtconnect.HTTPError:
                    raise PlanError('Plan stop command error')

                raise PlanExecutionExceeded()
            else:
                if self.__plan.poll_freq > 0:
                    wait = self.__plan.poll_freq
                else:
                    run_time = (datetime.datetime.now() - self.__plan_start).total_seconds()
                    wait = rnd_up(run_time/12, 5) if run_time < 600 else 60

                time.sleep(wait)

    def __delete(self):
        try:
            m = self.__vmt.request('markets', method='DELETE', uuid=self.__market_id)
            s = self.__vmt.request('scenarios', method='DELETE', uuid=self.__scenario_id)

            if m and s:
                return True
            else:
                raise PlanDeprovisionError()
        except:
            raise

    def __conf_add_entity(self, uuid, count=1, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(uuid)

        conf['type'] = 'ADD_REPEAT' if len(projection) > 1 else 'ADDED'
        conf['targets'] = [tgt]
        conf['value'] = int(count)
        conf['projectionDays'] = projection

        return conf

    def __conf_replace_entity(self, target, template, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(target)
        tmp = self.get_entity_profile(template)

        conf['type'] = 'REPLACED'
        conf['targets'] = [tgt, tmp]
        conf['projectionDays'] = projection

        return conf

    def __conf_del_entity(self, uuid, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(uuid)

        conf['type'] = 'REMOVED'
        conf['targets'] = [tgt]
        conf['projectionDays'] = projection

        return conf

    def __build_scope(self, spec):
        conf = {}
        scope = []

        if spec.scope is None:
            return self.__build_scope('Market')

        for uuid in spec.scope:
            scope.append(self.get_entity_profile(uuid))

        conf['type'] = 'SCOPE'
        conf['scope'] = scope

        return conf

    def __build_projection(self, spec):
        conf = {}
        days = [0]

        if spec.entities is not None:
            for e in spec.entities:
                if 'projection' in e:
                    days += e['projection']

        conf['type'] = 'PROJECTION_PERIODS'
        conf['projectionDays'] = list(set(days))
        conf['projectionDays'].sort()

        return conf

    def __build_entities(self, spec):
        conf = []

        for e in spec.entities:
            if e['action'] == PlanSetting.DELETE:
                conf.append(self.__conf_del_entity(e['id'], e['projection']))
            elif e['action'] == PlanSetting.ADD:
                conf.append(self.__conf_add_entity(e['id'], e['count'],
                                                   e['projection']))
            elif e['action'] == PlanSetting.REPLACE:
                conf.append(self.__conf_replace_entity(e['id'], e['template'],
                                                       e['projection']))

        return conf

    def __init_scenario(self):
        changes = []
        dto = {}

        changes.append(self.__build_scope(self.__plan))
        changes.append(self.__build_projection(self.__plan))
        changes += self.__build_entities(self.__plan)

        dto['type'] = self.__plan.type.value
        dto['changes'] = changes
        dto_string = json.dumps(dto, sort_keys=False)

        response = self.__vmt.request('scenarios/' + self.__scenario_name, method='POST', dto=dto_string)

        self.__scenario_id = response['uuid']
        self.__scenario_name = response['displayName']

        return response['uuid']

    def __apply_scenario_options(self):
        param = urlencode({k: v for k,v in self.__plan.scenario_settings.items() if v is not None}) or None

        self.__vmt.request('scenarios/' + self.__scenario_id, method='PUT', query=param)

        return True

    def __init_market(self):
        if 'plan_market_name' not in self.__plan.market_settings:
            self.__plan.market_settings.update({'plan_market_name': self.__market_name})

        param = urlencode({k: v for k,v in self.__plan.market_settings.items() if v is not None}) or None
        path = 'markets/{}/scenarios/{}'.format(self.base_market, self.__scenario_id)

        response = self.__vmt.request(path, method='POST', query=param)

        self.__market_id = response['uuid']
        self.__market_name = response['displayName']

        return response['uuid']

    def __run(self, async=False):
        self.__init_scenario()
        self.__apply_scenario_options()
        self.__init_market()
        self.__init = True
        self.__plan_start = datetime.datetime.now()

        if async:
            return self.state

        self.__wait_for_plan()
        self.__plan_duration = (datetime.datetime.now() - self.__plan_start).total_seconds()

        return self.state

    def get_entity_profile(self, uuid):
        """Returns the given UUID in the required format for an input DTO.

        Args:
            uuid (str): UUID to format.

        Returns:
            dict: A formatted UUID.
        """
        return {'uuid': uuid}

    def get_stats(self):
        """Returns statistics for the market.

        Returns:
            list: A list of statistics by period.
        """
        return self.__vmt.get_market_stats(self.__market_id)

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
        try:
            if self.get_state() == state:
                return True
            else:
                return False
        except KeyError:
            return None

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
            market = self.__vmt.get_markets(uuid=self.__market_id)
            self.__init = True

            return MarketState[market[0]['state']]
        except Exception:
            raise

    def run(self):
        """Runs the market with currently applied scenario and settings."""
        run = 1

        while run < self.__plan.max_retry:
            try:
                return self.__run()
            except (vmtconnect.HTTP500Error, PlanError):
                run += 1
                pass

        raise PlanError('Retry limit reached.')

    def run_async(self):
        """Runs the market plan in asynchronous mode.

        When run asynchronously the plan will be started and the state returned
        immediately. All settings pertaining to polling, timeout, and retry
        will be ignored. The :class:`~Plan.duration` will not be recorded.
        """
        return self.__run(async=True)

    def stop(self):
        """Stops the market.

        Returns:
            bool: ``True`` upon success. Raises an exception otherwise.
        """
        try:
            self.__vmt.request('markets', uuid=self.__market_id, method='PUT', query='operation=stop')
            self.__wait_for_stop()
            self.__plan_duration = (datetime.datetime.now() - self.__plan_start).total_seconds()

        except vmtconnect.HTTP500Error:
            raise
        except Exception as e:
            raise PlanError('Error stopping plan: {}'.format(e))

        return True

    def delete(self):
        """Removes the market.

        Returns:
            bool: ``True`` upon success, ``False`` otherwise.
        """
        if self.is_system():
            raise InvalidMarketError('Attempting to delete system market')
        elif not self.__init:
            raise InvalidMarketError('Market does not exist')

        if self.__delete() == ServerResponse.TRUE:
            self.__init = False
            return True
        else:
            return False


class PlanSpec(object):
    """Plan specification.

    Args:
        name (str): Name of the plan scenario.
        type (:class:`PlanType`): Type of plan to be run.
        scope (list, optional): Scope of the plan market.
        entities (list, optional): List of `entity definitions` to alter plan with. See `entity spec`_.
        **kwargs: Additional :ref:`scenario_param` and, or :ref:`market_param`.

    Attributes:
        abort_timeout (int): Abort timeout in minutes.
        abort_poll_freq (int): Abort status polling interval in seconds.
        max_retry (int): Plan retry limit.
        poll_freq (int): Status polling interval in seconds, 0 = dynamic.
        timeout (int): Plan timeout in minutes, 0 = infinite.
    """
    abort_timeout = 5
    abort_poll_freq = 5
    max_retry = 3
    poll_freq = 0
    timeout = 0

    # GET Query settings.
    __scenario_options = ['add_historical',
                          'datastore_provision',
                          'datastore_removal',
                          'description',
                          'host_provision',
                          'host_suspension',
                          'include_reservations',
                          'resize',
                          'set_hist_baseline',
                          'time']
    __market_options = ['ignore_constraints', 'plan_market_name']

    def __init__(self, name, type=PlanType.CUSTOM, scope=[], entities=[], **kwargs):
        self.plan_name = name
        self.market_settings = self.__parse_options(self.__market_options, kwargs)
        self.scenario_settings = self.__parse_options(self.__scenario_options, kwargs)
        self.entities = entities
        self.scope = scope
        self.type = type

    def __parse_options(self, fields, args):
        return {f: args[f] for f in fields if f in args}

    def add_template(self, id, count=1, periods=[0]):
        """Add a template.

        Alias to :class:`~PlanSpec.add_entity` provided for convenience.

        Args:
            id (str): Target entity UUID.
            count (int, optional): Number of copies to add. (default: 1)
            periods (list, optional): List of periods to add copies. (default: [0])
        """
        self.add_entity(id, count, periods)

    def add_entity(self, id, count=1, periods=[0]):
        """Add copies of an entity.

        Args:
            id (str): Target entity UUID.
            count (int, optional): Number of copies to add. (default: 1)
            periods (list, optional): List of periods to add copies. (default: [0])

        Notes:
            See plan periods.
        """
        self.entities.append({'id': id,
                              'action': PlanSetting.ADD,
                              'count': count,
                              'projection': periods})

    def replace_entity(self, id, replacement_id, count=1, periods=[0]):
        """Replace an entity with a template.

        Args:
            id (str): UUID of the entity to replace.
            replacement_id (str): Template UUID to use as a replacement.
            count (int, optional): Number of copies to add. (default: 1)
            periods (list, optional): List of periods to add copies. (default: [0])

        Notes:
            See plan periods.
        """
        self.entities.append({'id': id,
                              'template': replacement_id,
                              'action': PlanSetting.REPLACE,
                              'count': count,
                              'projection': periods})

    def delete_entity(self, id, periods=[0]):
        """Remove an entity.

        Args:
            id (str): Target entity UUID.
            periods (list, optional): List of periods to add copies. (default: [0])

        Notes:
            See plan periods.
        """
        self.entities.append({'id': id,
                              'action': PlanSetting.DELETE,
                              'projection': periods})
