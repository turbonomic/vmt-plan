from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime, time, math
import vmtconnect

try:
    from enum import Enum
except ImportError:
    try:
        from aenum import Enum
    except ImportError:
        print('Critical failure: no enum module found')


__version__ = '0.0.0.dev'



## ----------------------------------------------------
##  Error Classes
## ----------------------------------------------------
# base market error
class MarketError(Exception):
    pass


class InvalidMarketError(MarketError):
    pass


# base plan error
class PlanError(Exception):
    pass


# plan running
class PlanRunning(PlanError):
    pass


# unable to run a plan
class PlanRunFailure(PlanError):
    pass


# plan deprovisioning failure
class PlanDeprovisionError(PlanError):
    pass


# plan timeout exceeded
class PlanExecutionExceeded(PlanError):
    pass



## ----------------------------------------------------
##  Enumerated Classes
## ----------------------------------------------------
#PlanType = Enum('PlanType', 'full headroom')

#HostState = Enum('HostState', 'maintenanceOn maintenanceOff powerOn powerOff failoverOn failoverOff')

MarketState = Enum('MarketState', 'READY_TO_START COPYING DELETING RUNNING SUCCEEDED STOPPED')

#TemplateType = Enum('TemplateType', 'VirtualMachineProfile PhysicalMachineProfile StorageProfile')

class ProfileType(Enum):
    entity = 'entities'
    group = 'groups'
    template = 'templates'


class PlanSetting(Enum):
    true = 'true'
    false = 'false'
    enabled = 'enabled'
    disabled = 'disabled'
    run = 'run'
    stop = 'stop'
    add = 'add'
    delete = 'delete'
    replace = 'replace'


class ServerResponse(Enum):
    true = True
    false = False
    success = 'success'
    error = 'ERROR'


# ----------------------------------------------------
#  API Wrapper Classes
# ----------------------------------------------------
class Plan(object):
    # system level markets to block certain actions
    __system = ['Market', 'Market_Default']

    def __init__(self, session, spec=None):
        self.__vmt = session
        self.__init = False
        self.__scenario_id = None
        self.__scenario_name = spec.plan_name if spec is not None else self.__gen_scenario_name()
        self.__market_id = None
        self.__market_name = self.__gen_market_name()
        self.__plan = spec
        self.__plan_start = None
        self.__plan_end = None
        self.__plan_duration = None
        self.base_market = 'Market'

    @property
    def state(self):
        if self.__init:
            return self.get_state()
        else:
            return False

    @property
    def initialized(self):
        return self.__init

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
            elif self.__plan.timeout > 0 and datetime.datetime.now() >= (self.__plan_start + datetime.timedelta(minutes=self.__plan.timeout)):
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

    def __conf_add_entity(self, uuid, type=ProfileType.entity, count=1, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(uuid, type)

        conf['type'] = 'ADD_REPEAT' if len(projection) > 1 else 'ADDED'
        conf['targets'] = [tgt]
        conf['value'] = int(count)
        conf['projectionDays'] = projection

        return conf

    def __conf_replace_entity(self, target, template, type=ProfileType.entity, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(target, type=type)
        tmp = self.get_entity_profile(template, type=ProfileType.template)

        conf['type'] = 'REPLACED'
        conf['targets'] = [tgt, tmp]
        conf['projectionDays'] = projection

        return conf

    def __conf_del_entity(self, uuid, type=ProfileType.entity, projection=[0]):
        conf = {}
        tgt = self.get_entity_profile(uuid, type=type)

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
            scope.append(self.get_entity_profile(uuid, ProfileType.group))

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
            if e['action'] == PlanSetting.delete:
                conf.append(self.__conf_del_entity(e['id'], e['type']))
            elif e['action'] == PlanSetting.add:
                conf.append(self.__conf_add_entity(e['id'], e['type'], e['count'], e['projection']))
            elif e['action'] == PlanSetting.replace:
                conf.append(self.__conf_replace_entity(e['id'], e['template'], e['type']))

        return conf

    def __init_scenario(self):
        dto = {'changes': []}
        dto['changes'].append(self.__build_scope(self.__plan))
        dto['changes'].append(self.__build_projection(self.__plan))
        dto['changes'] += self.__build_entities(self.__plan)
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

    def get_entity_profile(self, uuid, type=ProfileType.entity):
        conf = {}
        detail = self.__vmt.request(type.value, uuid=uuid)

        # fix inconsistency in server responses
        if isinstance(detail, list):
            detail = detail[0]

        conf['uuid'] = detail['uuid']

        return conf

    def get_template_profile(self, uuid):
        return self.get_entity_profile(uuid, type=ProfileType.template)

    def get_stats(self):
        return self.__vmt.get_market_stats(self.__market_id)

    def get_start(self):
        return self.__plan_start

    def get_duration(self):
        return self.__plan_duration

    def is_system(self):
        if self.__market_name in self.__system:
            return True

        return False

    def is_state(self, state):
        try:
            if self.get_state() == state:
                return True
            else:
                return False
        except KeyError:
            return None

    def is_complete(self):
        return self.is_state(MarketState.SUCCEEDED)

    def is_ready(self):
        return self.is_state(MarketState.READY_TO_START)

    def is_stopped(self):
        return self.is_state(MarketState.STOPPED)

    def is_running(self):
        return self.is_state(MarketState.RUNNING)

    def get_state(self):
        try:
            market = self.__vmt.get_markets(uuid=self.__market_id)
            self.__init = True

            return MarketState[market['state']]
        except Exception:
            raise

    def run(self):
        try:
            self.__init_scenario()
            self.__apply_scenario_options()
            self.__init_market()
            self.__init = True
            self.__plan_start = datetime.datetime.now()
            self.__wait_for_plan()
            self.__plan_duration = (datetime.datetime.now() - self.__plan_start).total_seconds()

            return self.state
        except vmtconnect.HTTP500Error:
            raise
        except PlanExecutionExceeded:
            # retry
            raise
        except PlanError:
            # plan failed
            raise
        except Exception as e:
            raise PlanError('Error running plan: {}'.format(e))

    def stop(self):
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
        if self.is_system():
            raise InvalidMarketError('Attempting to delete system market')
        elif not self.__init:
            raise InvalidMarketError('Market does not exist')

        if self.__delete() == ServerResponse.true:
            self.__init = False
            return True
        else:
            return False


class PlanSpec(object):
    # status polling interval in seconds, 0 - dynamic
    poll_freq = 0

    # plan timeout in minutes, 0 = infinite
    timeout = 0

    # abort timeout in minutes
    abort_timeout = 5

    # abort status polling interval in seconds
    abort_poll_freq = 5

    # retry limit for abort
    max_retry = 3

    # query settings
    scenario_options = ['description', 'add_historical', 'include_reservations', 'time', 'host_provision', 'host_suspension', 'datastore_provision', 'datastore_removal', 'resize']
    market_options = ['ignore_constraints', 'plan_market_name']

    def __init__(self, name, **kwargs):
        self.plan_name = name
        self.market_settings = self.__parse_options(self.market_options, kwargs)
        self.scenario_settings = self.__parse_options(self.scenario_options, kwargs)
        self.entities = []

        # <uuid>
        self.scope = kwargs['scope'] if isinstance(kwargs['scope'], list) and 'scope' in kwargs else []

        # [{'id': <uuid>, 'type': ProfileType.template, 'action': PlanSetting.add, 'count': <int>, 'projection': <int>}]
        self.entities = self.entities + kwargs['template'] if isinstance(kwargs['template'], list) and 'template' in kwargs else []

        # [{'id': <uuid>, 'type': <entity|group|template>, 'action': <add|delete|replace>, 'template': <uuid>, 'count': <int>}]
        self.entities = self.entities + kwargs['entities'] if isinstance(kwargs['entities'], list) and 'entities' in kwargs else []

    def __parse_options(self, fields, args):
        return {f: args[f] for f in fields if f in args}

    def add_template(self, id, type=ProfileType.template, count=1, periods=[0]):
        self.add_entity(id, type, count, periods)

    def add_entity(self, id, type=ProfileType.entity, count=1, periods=[0]):
        self.entities.append({'id': id, 'type': type, 'action': PlanSetting.add, 'count': count, 'projection': periods})

    def replace_entity(self, id, template_id, type=ProfileType.entity, count=1, periods=[0]):
        self.entities.append({'id': id, 'type': type, 'template': template_id, 'action': PlanSetting.replace, 'count': count, 'projection': periods})

    def delete_entity(self, id, type=ProfileType.entity, periods=[0]):
        self.entities.append({'id': id, 'type': type, 'action': PlanSetting.delete, 'projection': periods})
