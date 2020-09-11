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

from collections import defaultdict
import copy
import datetime
import decimal
from enum import Enum, auto
from itertools import chain, product
import json
from pprint import pprint
from statistics import mean
import time

import umsg.mixins

import vmtplanner
import vmtplanner.plans

try:
    import iso8601

    def read_isodate(date):
        return iso8601.parse_date(date)
except ModuleNotFoundError:
    try:
        import dateutil.parser

        def read_isodate(date):
            return dateutil.parser.parse(date)
    except ModuleNotFoundError:
        raise Exception('Unable to import pyiso8601 or python-dateutil.')



D = decimal.Decimal
decimal.getcontext().prec = 4



class HeadroomMode(Enum):
    """Headroom Calculation Modes"""
    #: Per-template headroom
    SEPARATE = auto()
    #: Split evenly amongst all templates in a group, i.e. average all templates
    AVERAGE = auto()
    #: Combined templates in a group, i.e. summed
    SUM = auto()


class HeadroomEncoder(json.JSONEncoder):
    """Headroom results encoder for JSON output

    Example:
        .. code-block:: python

           with open(OUTFILE, 'w') as fp:
               json.dump(plan.headroom(), fp, indent=2, cls=HeadroomEncoder)
    """
    def default(self, obj):
        "" # squash sphinx pulling in native docstring
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (Group, Template)):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class Group:
    """Headroom group

    Groups provide partitioning within a cluster, and are not required if no
    subdivision of the cluster is necessary, as each cluster has a default group
    for all ungrouped members.. Groups need not be created per cluster either,
    as all entities will be partitioned on cluster boundaries before being assigned
    to their respective groups. Groups cannot be used to create super clusters.

    Args:
        name (str): Group name. One of **name** or **uuid** is required.
        uuid (str): Group UUID.

    Attributes:
        name (str): Group display name.
        uuid (str): Group UUID.
        type (str): Trubonomic "groupType" of the group:
        members (list): List of group real-time market members.

    Raises:
        ValueError: If both name and uuid are None.

    Notes:
        One of **name** or **uuid** is required to lookup the group, if both are
        provided **uuid** will override.
    """
    __slots__ = ['uuid', 'name', 'type', 'members']

    def __init__(self, name=None, uuid=None):
        self.uuid = uuid
        self.name = name
        self.type = None
        self.members = None

        if not uuid and not name:
            raise ValueError('Name or uuid required.')

    def __repr__(self):
        return json.dumps({
            'uuid': self.uuid,
            'name': self.name,
            'type': self.type,
            'members': self.members
        }, cls=HeadroomEncoder)

    def get_members(self, conn):
        if self.uuid:
            group = conn.get_groups(self.uuid)[0]
            self.name = group['displayName']
        elif self.name:
            group = conn.get_group_by_name(self.name)[0]
            self.uuid = group['uuid']

        self.type = group['groupType']

        # memberUuidList only exists in XL
        if 'memberUuidList' in group:
            self.members = group['memberUuidList']
        else:
            members = conn.get_group_members(self.uuid)
            self.members = [x['uuid'] for x in members]


class Template:
    """Headroom template

    Templates may be linked to both groups and clusters, and will apply to all
    members at the level applied respecitvely. Because groups can span
    across clusters, you may want to assign specific templates to specific
    cluster group combinations. You can specify a cluster or clusters
    to lock a template to, which will cause the template to only be applied to
    group members of the listed clusters.

    Args:
        name (str): Template name. One of **name** or **uuid** is required.
        uuid (str): Template UUID.
        targets (list): List of groups and/or clusters to apply the template to.
        clusters (list, optional): List of clusters to limit the template to.

    Attributes:
        name (str): Template display name.
        uuid (str): Template UUID.
        targets (list): List of group names or UUIDs to apply the template to.
        clusters (list): List of clusters to limit the template to.
        cpu (Decimal): Template CPU value.
        cpu_provisioned (Decimal): Template CPU provisioned value.
        mem (Decimal): Template memory value.
        mem_provisioned (Decimal): Template memory provisioned value.
        storage_amount (Decimal): Template storage value.
        storage_provisioned (Decimal): Template storage provisioned value.

    Raises:
        TypeError: If the retrieved template is not a VirtualMachine template.
        ValueError: If both name and uuid are None; or no targets provided.

    Notes:
        One of **name** or **uuid** is required to lookup the template, if both
        are provided **uuid** will override.
    """
    __slots__ = [
        'uuid',
        'name',
        'targets',
        'clusters',
        'cpu',
        'cpu_provisioned',
        'mem',
        'mem_provisioned',
        'storage_amount',
        'storage_provisioned'
    ]

    def __init__(self, name=None, uuid=None, targets=None, clusters=None):
        self.uuid = uuid
        self.name = name
        self.targets = [targets] if isinstance(targets, str) else targets
        self.clusters = clusters

        self.cpu = 0
        self.cpu_provisioned = 0
        self.mem = 0
        self.mem_provisioned = 0
        self.storage_amount = 0
        self.storage_provisioned = 0

        if not uuid and not name:
            raise ValueError('Name or uuid required.')

        if not targets:
            raise ValueError('One or more targets required.')

    def __repr__(self):
        return json.dumps({
            'uuid': self.uuid,
            'name': self.name,
            'targets': self.targets,
            'cpu': self.cpu,
            'cpu_provisioned': self.cpu_provisioned,
            'mem': self.mem,
            'mem_provisioned': self.mem_provisioned,
            'storage_amount': self.storage_amount,
            'storage_provisioned': self.storage_provisioned
        }, cls=HeadroomEncoder)

    def get_resources(self, conn):
        resources = {
                'numOfCpu': 0,
                'cpuSpeed': 0,
                'cpuConsumedFactor': 0,
                'memorySize': 0,
                'memoryConsumedFactor': 0,
                'diskSize': 0,
                'diskConsumedFactor': 0,
        }

        if self.uuid:
            t = conn.get_templates(self.uuid)[0]
            self.name = t['displayName']
        elif self.name:
            t = conn.get_template_by_name(self.name)[0]
            self.uuid = t['uuid']

        if self.clusters:
            for x in range(len(self.clusters)):
                # try to resolve names, else it's assumed to be a UUID
                try:
                    self.clusters[x] = conn.search(q=self.clusters[x],
                                              types=['Cluster'],
                                              group_type='PhysicalMachine')[0]['uuid']
                except Exception:
                    pass

        if t['className'] != 'VirtualMachineProfile':
            raise TypeError(f'Received [{t["className"]}] template, expected VirtualMachineProfile.')

        for s in chain(t['computeResources'][0]['stats'], t['storageResources'][0]['stats']):
            if s['name'] in resources:
                if s.get('units') == '%':
                    resources[s['name']] = D(str(s['value']))/100
                else:
                    resources[s['name']] = D(str(s['value']))

        # computed values for headroom
        self.cpu = resources['cpuSpeed'] * resources['numOfCpu'] * resources['cpuConsumedFactor']
        self.cpu_provisioned = resources['numOfCpu'] * resources['cpuSpeed']
        self.mem = resources['memorySize'] * resources['memoryConsumedFactor']
        self.mem_provisioned = resources['memorySize']
        self.storage_amount = resources['diskSize'] * resources['diskConsumedFactor']
        self.storage_provisioned = resources['diskSize']


class Cluster(umsg.mixins.LoggingMixin):
    """Headroom cluster

    Individual cluster objects, used by a :py:class:`ClusterHeadroom` plan.

    Args:
        connection (:py:class:`~vmtconnect.Connection`): :class:`~vmtconnect.Connection` or :class:`~vmtconnect.Session`.
        uuid (int): Cluster UUID.
        name (str): Cluster display name.
        members (list, optional): List of cluster member UUIDs.
        realtime_members (list, optional): List of realtime market member UUIDs.
        mode (:py:class:`HeadroomMode`, optional): Headroom calculation mode.
            (default: :py:class:`HeadroomMode.SEPARATE`)

    Attributes:
        name (str): Cluser display name.
        datacenter (str): Datacenter the cluster belongs to.
        groups (dict): Dictionary of cluster groups for headroom analysis.
        growth (float): Cluster growth.
        members (list): List of cluster member UUIDs.
        mode (:py:class:`HeadroomMode`): Headroom calculation mode.
        realtime_members (list): List of realtime market member UUIDs.
        uuid (str): Cluster UUID.
    """
    entity_parts = ['uuid', 'displayName', 'state']
    commodities = ['CPU', 'Mem', 'StorageAmount']
    member_types = ['PhysicalMachine', 'Storage']
    type_commodity = {
        'PhysicalMachine': ['CPU', 'Mem'],
        'Storage': ['StorageAmount']
    }
    template_commodity = {
        'CPU': 'cpu',
        'Mem': 'mem',
        'StorageAmount': 'storage_amount'
    }
    group_template = {
        'templates': None,
        'members': {}
    }

    def __init__(self, connection, uuid, name, members=None, realtime_members=None,
                 mode=HeadroomMode.SEPARATE):
        super().__init__()

        self._vmt = connection
        self.uuid = uuid
        self.name = name
        self.datacenter = ''
        self.members = members if members else set()
        self.realtime_members = realtime_members if realtime_members else set()
        self.groups = {x: {0: copy.deepcopy(Cluster.group_template)} for x in Cluster.member_types}
        self.growth = 0
        self.headroom = defaultdict(lambda: None)
        self.headroom_mode = mode

        self.log(f'Initializing [{self.uuid}]:[{self.name}]')
        try:
            memberlist = []
            response = self._vmt.get_groups(self.uuid)[0]

            try:
                memberlist = response['memberUuidList']
            except KeyError:
                # Classic compatibility
                memberlist = [x['uuid'] for x in self._vmt.get_group_members(self.uuid)]

            self.realtime_members = set(copy.deepcopy(memberlist))
        except Exception as e:
            self.log(f'Exception while processing cluster [{self.uuid}]:[{self.name}]: {e}', level='debug')
            return None

    @staticmethod
    def exhaustdays(g, c):
        if g > 0:
            return int(D(c) / D(g))
        else:
            return -1

    @staticmethod
    def group_commodity_headroom(members, commodity, templates, mode=HeadroomMode.AVERAGE):
        headroom = {
            'Available': 0,
            'Capacity': 0
        }

        # map the template commodity
        tc = Cluster.template_commodity[commodity]

        if mode == HeadroomMode.AVERAGE:
            tcount = 1
            required = mean([D(getattr(t, tc)) for t in templates])
        elif mode == HeadroomMode.SUM:
            tcount = len(templates)
            required = sum([D(getattr(t, tc)) for t in templates])
        else:
            raise ValueError(f'Unknown mode [{mode}]')

        for m in members.keys():
            if 'statistics' not in members[m]:
                #self.log(f'Skipping entity [{members[m]["displayName"]}], no statistics', level='debug')
                continue

            mcap = D(members[m]['statistics'][commodity]['capacity'])
            mused = D(members[m]['statistics'][commodity]['value'])
            mavail = mcap - mused
            headroom['Available'] += 0 if required <= 0 else tcount * int(mavail / required)
            headroom['Capacity'] += 0 if required <= 0 else tcount * int(mcap / required)

        if headroom['Capacity'] == 0:
            headroom['Available'] = headroom['Capacity'] = -1

        return headroom

    def _apply_templates(self, type, group, name, templates):
        m = HeadroomMode
        mode = m.AVERAGE if self.headroom_mode == m.SEPARATE else self.headroom_mode
        self.headroom[type][name] = {}

        for o in Cluster.type_commodity[type]:
            self.headroom[type][name][o] = self.group_commodity_headroom(
                    self.groups[type][group]['members'], o, templates, mode)

            self.headroom[type][name][o]['DaysToExhaustion'] = \
                self.exhaustdays(self.growth,
                                 self.headroom[type][name][o]['Available'])

            self.headroom[type][name][o]['TemplateCount'] = len(templates)
            self.headroom[type][name][o]['GrowthPerDay'] = self.growth

    def add_member(self, entity, type, realtimeid=None):
        try:
            self.groups[type][0]['members'][entity['uuid']] = entity
            self.members.add(entity['uuid'])

            if realtimeid:
                self.realtime_members.add(realtimeid)
        except KeyError as e:
            pass

    def apply_templates(self):
        self.log(f'Calculating [{self.uuid}]:[{self.name}] headroom')

        for type in self.groups:
            self.headroom[type] = {}
            comms = Cluster.type_commodity[type]

            # compute type groups
            for group in self.groups[type]:
                if not self.groups[type][group]['members']:
                    self.log(f'Skipping [{type}] group [{group}], no group members.', level='debug')
                    continue

                if self.groups[type][group]['templates'] is None:
                    self.log(f'Skipping [{type}] group [{group}], no template assigned.', level='debug')
                    continue

                # TODO: potentially instantiate member filtering here
                # members = self.groups[type][group]['members']

                # calculate commodity headroom based on mode
                if self.headroom_mode == HeadroomMode.SEPARATE:
                    for i in self.groups[type][group]['templates']:
                        self._apply_templates(type, group, i.name, [i])
                else:
                    if self.headroom_mode == HeadroomMode.SUM:
                        name = '__SUM__'
                    elif self.headroom_mode == HeadroomMode.AVG:
                        name = '__AVG__'

                    self._apply_templates(type,
                                          group,
                                          name,
                                          self.groups[type][group]['templates'])
            # end group loop ---
        # end type loop ---

    def get_default_template(self, cache=None):
        if not cache:
            cache = self._vmt.get_templates(fetch_all=True)

        if self._vmt.is_xl():
            # OM-58566 changed the naming in XL to fix a collision issue,
            # so we must check for both styles
            names = [
                f"{self.datacenter}::AVG:{self.name} for last 10 days",
                f"AVG:{self.name} for last 10 days"
            ]
        else:
            # this is likely a bug, VM templates should not
            # be prefixed PMs_, but we see them this way
            names = [
                f"AVG:PMs_{self.name} for last 10 days",
                f"AVG:VMs_{self.name} for last 10 days"
            ]

        # gets the sys generated cluster AVG template
        for i in cache:
            if i['displayName'] in names \
            and i['className'] == 'VirtualMachineProfile':
                return i['displayName']

        return False

    def get_growth(self, from_ts):
        self.log(f'Calculating cluster growth')
        stats = ['numVMs']

        try:
            response = self._vmt.get_entity_stats(scope=[self.uuid],
                                                  start_date=from_ts,
                                                  end_date=from_ts,
                                                  stats=stats,
                                                  fetch_all=True)[0]
            then = response['stats'][0]['statistics'][0]['value']
            start = read_isodate(response['stats'][0]['date'])
        except (IndexError, KeyError):
            then = 0
            start = datetime.datetime.fromtimestamp(from_ts/1000, datetime.timezone.utc)

        try:
            response = self._vmt.get_entity_stats(scope=[self.uuid],
                                                  stats=stats,
                                                  fetch_all=True)[0]
            now = response['stats'][0]['statistics'][0]['value']
            end = read_isodate(response['stats'][0]['date'])
        except (IndexError, KeyError):
            now = 0
            end = datetime.datetime.today(datetime.timezone.utc)

        # (cur val - prev val) / days delta
        growth = D(now - then) / D((end - start).days)

        self.growth = growth if growth > 0 else D(0)
        self.log(f'Cluster [{self.uuid}]:[{self.name}] growth: {self.growth}', level='debug')

    def get_stats(self, market):
        dto = {
            'scopes': list(self.members),
            'period': {
                'startDate': self._vmt.get_markets(uuid=market)[0]['runDate'],
                'statistics': vmtplanner.kw_to_list_dict('name', Cluster.commodities)
            }
        }

        return self._vmt.get_market_entities_stats(market, filter=json.dumps(dto), fetch_all=True)

    def update_stats(self, market):
        self.log(f'Updating statistics', level='debug')

        if not self.members:
            self.log(f'Cluster [{self.uuid}]:[{self.name}] has empty member list, skipping', level='warn')
            return

        for s in self.get_stats(market):
            if s['className'] not in Cluster.member_types:
                continue

            if s['uuid'] in self.groups[s['className']][0]['members']:
                newstats = {}

                for stat in s['stats'][0]['statistics']:
                    newstats[stat['name']] = {
                        'capacity': stat['capacity']['total'],
                        'name': stat['name'],
                        'units': stat['units'],
                        'value': stat['value']
                    }

                self.groups[s['className']][0]['members'][s['uuid']]['statistics'] = newstats

    def update_groups(self, groups, templates, cache=None):
        self.log(f'Updating groups', level='debug')
        remove = []

        for e, g in product(self.members, groups):
            # Classic compatibility - resolve copied entity references
                try:
                    ref_id = self.groups[g.type][0]['members'][e].get('realtimeUuid', e)
                except KeyError:
                    # not a member of this group type
                    continue

                if ref_id in g.members:
                    # if e is a member, re-group it
                    if g.name not in self.groups[g.type]:
                        self.groups[g.type][g.name] = copy.deepcopy(Cluster.group_template)

                    self.groups[g.type][g.name]['members'][e] = self.groups[g.type][0]['members'][e]
                    remove.append((e, g.type))

        # remove regrouped members from inverse group
        for e, t in remove:
            if e in self.groups[t][0]['members']:
                del self.groups[t][0]['members'][e]

        for type in self.groups:
            for name in self.groups[type]:
                count = len(self.groups[type][name]['members'])
                self.log(f'[{type}]:[{name}]:{count}', level='debug')
                self.update_group_templates(type, name, templates, cache)

    def update_group_templates(self, type, name, templates, cache=None):
        # defualt ungrouped cluster entitites
        if name == 0:
            # ungrouped cluster entities match on cluster target
            tpl = [x for x in templates if self.name in x.targets]

            if not tpl:
                try:
                    tpl_name = self.get_default_template(cache)
                    x = Template(tpl_name, targets=[self.name])
                    x.get_resources(self._vmt)

                    self.log(f'Using default cluster template [{tpl_name}]', level='debug')
                    tpl = set([x])
                except ValueError:
                    self.log(f'Unable to locate default system average template.', level='debug')
        else:
            # user grouped entities
            tpl = [x for x in templates
                   if name in x.targets and
                   (not x.clusters or self.name in x.clusters)]

        if not tpl:
            self.log(f'No template not provided for [{name}] in [{self.uuid}]:[{self.name}]', level='warn')
        else:
            self.groups[type][name]['templates'] = tpl


class ClusterHeadroom(vmtplanner.plans.BaseBalancePlan):
    """Cluster headroom plan

    In basic form, this provides cluster headroom parity with Turbonomics
    native 10 Day average templates. When combined with groups and templates,
    :py:class:`ClusterHeadroom` provides highly customizable headroom analysis.

    Args:
        connection (:py:class:`~vmtconnect.Connection`): :class:`~vmtconnect.Connection` or :class:`~vmtconnect.Session`.
        spec (:py:class:`PlanSpec`, optional): Settings override to apply to the
            market. Default behavior is to run a balance plan first.
        market (str, optional): Base market UUID to apply the settings to.
            (default: ``Market``)
        scope (list, optional): Scope of the plan market. If ``None``, then a
            list of all clusters in the given market will be used.
        groups (list): List of :py:class:`Group` objects.
        templates (list): List of :py:class`Template` objects.
        growth_lookback (int): Number of days to use for growth calcuation.
        mode (:py:class:`HeadroomMode`, optional): Headroom calculation mode.

    Attributes:
        commodities (list): Commodities to calculate for headroom.
        clusters (list): List of clusters in the plan.
        groups (list): List of :py:class:`Group` objects.
        growth_lookback (int): VM growth period in days.
        mode (:py:class:`HeadroomMode`): Headroom calculation mode.
        templates (list): List of :py:class`Template` objects.
        tempalte_commodity (dict): Dictionary map of commodities to template
            attributes.
    """
    def __init__(self, connection, spec=None, market='Market', scope=None,
                 groups=None, templates=None, growth_lookback=7,
                 mode=HeadroomMode.SEPARATE):
        super().__init__(connection, spec, market, name=f'Custom Headroom Plan {str(int(time.time()))}')
        self.hook_post(self._post_cluster_headroom)

        self.__e_cache = None # entity cache, shared across clusters
        self.__t_cache = None # template cache, shared across clusters
        self.mode = mode
        self.clusters = []
        self.groups = groups
        self.templates = templates

        self.growth_ts = int(time.mktime((datetime.datetime.now() + datetime.timedelta(days=-1*growth_lookback)).timetuple()) * 1000)

        self.log('ClusterHeadroom initialized', level='debug')

    def _init_groups(self):
        self.log('Fetching group data', level='debug')

        for x in self.groups:
            x.get_members(self._vmt)

    def _init_templates(self):
        self.log('Fetching template data', level='debug')

        for x in self.templates:
            try:
                x.get_resources(self._vmt)
            except TypeError:
                self.log(f'Error retrieving template information for [{x.name or x.uuid}]', level='warn')

    def _get_plan_scope(self):
        try:
            return self._vmt.get_markets(uuid=self.market_id)[0]['scenario']['scope']
        except KeyError:
            # Classic compatibility
            return self._vmt.get_scenarios(uuid=self.scenario_id)[0]['scope']

    def _update_members(self, cluster):
        if self._vmt.is_xl():
            self._update_members_xl(cluster)
        else:
            self._update_members_classic(cluster)

    def _update_members_xl(self, cluster):
        if not self.__e_cache:
            self.__e_cache = {}
            response = self._vmt.get_supplychains(self.market_id,
                                                  types=Cluster.member_types,
                                                  detail='entity',
                                                  pager=True)
            self.__e_cache = condense_supplychain(response.all)

        keys = list(self.__e_cache.keys())

        for e in keys:
            if e not in self.__e_cache:
                # removed storages
                continue

            if e in cluster.realtime_members:
                ent = {x: copy.deepcopy(self.__e_cache[e][x]) for x in Cluster.entity_parts}

                if self.__e_cache[e]['className'] == 'PhysicalMachine':
                    cluster.add_member(ent, self.__e_cache[e]['className'])

                    # pull in storages if available
                    for s in self.__e_cache[e]['providers']:
                        if s['className'] != 'Storage' or s['uuid'] not in self.__e_cache:
                            continue

                        ent = {x: copy.deepcopy(self.__e_cache[s['uuid']][x]) for x in Cluster.entity_parts}
                        cluster.add_member(ent, self.__e_cache[s['uuid']]['className'])
                        del self.__e_cache[s['uuid']]

                del self.__e_cache[e]

    def _update_members_classic(self, cluster):
        # Classic doesn't provide the consumer/provider details in the supplychain
        # so we must link hosts and storages to the cluster by cross-referencing
        # their real-time counterparts against the cluster supplychain
        #
        # market host => realtime host => cluster
        # market storage => realtime storage => cluster
        def processchain(type):
            try:
                res = self._vmt.get_supplychains(cluster.uuid,
                                                 types=[type],
                                                 detail='entity',
                                                 pager=True)
                cmember = condense_supplychain(res.all)
            except Exception:
                self.log(f'Cluster [{cluster.uuid}]:[{cluster.name}] has no members of type {type}', level='warn')
            else:
                keys = list(self.__e_cache[type].keys())

                for k in keys:
                    if self.__e_cache[type][k]['realtimeMarketReference']['uuid'] \
                    in cmember:
                        rid = self.__e_cache[type][k]['realtimeMarketReference']['uuid']
                        ent = {x: self.__e_cache[type][k][x] for x in cluster.entity_parts}
                        ent['realtimeUuid'] = rid
                        cluster.add_member(ent, self.__e_cache[type][k]['className'], rid)
                        del self.__e_cache[type][k]
        # end def ---

        if not self.__e_cache:
            self.__e_cache = defaultdict(lambda: None)

        for type in Cluster.member_types:
            if not self.__e_cache[type]:
                self.__e_cache[type] = {}
                response = self._vmt.get_supplychains(self.market_id,
                                                      types=[type],
                                                      detail='entity',
                                                      pager=True)
                self.__e_cache[type] = condense_supplychain(response.all)

            processchain(type)

    def _post_cluster_headroom(self):
        # main processor
        if self.result != vmtplanner.MarketState.SUCCEEDED:
            raise vmtplanner.PlanRunFailure(f'Invalid target plan market state: {self.results}')

        self._init_groups()
        self._init_templates()

        self.__t_cache = self._vmt.get_templates(fetch_all=True)

        self.log('Processing clusters')
        for c in [x for x in self._get_plan_scope() if x['className'] == 'Cluster']:
            obj = Cluster(self._vmt, c['uuid'], c['displayName'], mode=self.mode)

            if obj:
                self.clusters.append(obj)
            else:
                self.log(f'Skipping empty cluster [{c["uuid"]}]:[{c["displayName"]}]', level='debug')
                continue

            # add members based on market supplychain
            self._update_members(obj)
            obj.update_stats(self.market_id)
            obj.update_groups(self.groups, self.templates, self.__t_cache)
            obj.get_growth(self.growth_ts)
            obj.apply_templates()

        self.__e_cache = None
        self.__t_cache = None
        return self.clusters

    def headroom(self):
        headroom = {}

        for c in self.clusters:
            headroom[c.name] = c.headroom

        return headroom



def condense_supplychain(chain, types=None):
    # flattens the separate supplychain types to a single dictionary of all
    # entities for the given types list
    if types is None:
        return {k2: v2 for k, v in chain[0]['seMap'].items() for k2, v2 in v['instances'].items()}

    return {k2: v2 for k, v in chain[0]['seMap'].items() if k in types for k2, v2 in v['instances'].items()}
