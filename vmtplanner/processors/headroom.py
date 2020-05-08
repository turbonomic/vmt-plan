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

from ..vmtplanner import MarketState, PlanRunFailure, kw_to_list_dict
from ..plans import BaseBalancePlan

from collections import defaultdict
import copy
import datetime
import decimal
from enum import Enum, auto
from itertools import chain, product
import json
from pprint import PrettyPrinter, pprint
from statistics import mean
import time

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
    def default(self, obj):
        if isinstance(obj, (decimal.Decimal, Group, Template)):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class Group:
    """Headroom group

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

    Args:
        name (str): Template name. One of **name** or **uuid** is required.
        uuid (str): Template UUID.
        targets (list): List of group names to apply the template to.
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

        If you use multi-cluster groups and want to use per-cluster templates you
        may indicate which clusters to lock the template to with the optional
        **clusters** list.
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


class ClusterHeadroom(BaseBalancePlan):
    """Cluster headroom plan

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

        self.clusters = defaultdict(lambda: None)
        self.growth_lookback = growth_lookback
        self.types = ['PhysicalMachine', 'Storage']
        self.entity_parts = ['uuid', 'displayName', 'state']
        self.commodities = ['CPU', 'Mem', 'StorageAmount']
        self.type_commodity = {
            'PhysicalMachine': ['CPU', 'Mem'],
            'Storage': ['StorageAmount']
        }
        self.template_commodity = {
            'CPU': 'cpu',
            'Mem': 'mem',
            'StorageAmount': 'storage_amount'
        }
        self.groups = groups
        self.templates = templates
        self.mode = mode

        # cluster group struct template
        self.group_template = {
            'templates': None,
            'members': {}
        }

        self.log('ClusterHeadroom initialized', level='debug')

    def _commodity_headroom(self, members, commodity, templates, mode=HeadroomMode.AVERAGE):
        headroom = {
            'Available': 0,
            'Capacity': 0
            }

        # map the template commodity
        tc = self.template_commodity[commodity]

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
                umsg.log(f'Skipping entity [{members[m]["displayName"]}], no statistics', level='debug')
                continue

            mcap = D(members[m]['statistics'][commodity]['capacity'])
            mused = D(members[m]['statistics'][commodity]['value'])
            mavail = mcap - mused
            headroom['Available'] += 0 if required <= 0 else tcount * int(mavail / required)
            headroom['Capacity'] += 0 if required <= 0 else tcount * int(mcap / required)

        return headroom

    def _add_cluster_member(self, cluster, entity, group, realtimeId=None):
        try:
            self.clusters[cluster]['groups'][group][0]['members'][entity['uuid']] = entity
            self.clusters[cluster]['members'].add(entity['uuid'])

            if realtimeId:
                self.clusters[cluster]['realtimeMembers'].add(realtimeId)
        except KeyError:
            pass

    @staticmethod
    def _filter_members(members, filters):
        pass

    def _get_stats(self, entities, commodities):
        dto = {
            'scopes': entities,
            'period': {
                'startDate': self._vmt.get_markets(uuid=self.market_id)[0]['runDate'],
                'statistics': kw_to_list_dict('name', commodities)
            }
        }

        #return
        x = self._vmt.get_market_entities_stats(self.market_id, filter=json.dumps(dto), fetch_all=True)
        #print(x)
        return x

    def _init_clusters(self):
        try:
            scenario_scope = self._vmt.get_markets(uuid=self.market_id)[0]['scenario']['scope']
        except KeyError:
            # Classic compatibility
            scenario_scope = self._vmt.get_scenarios(uuid=self.scenario_id)[0]['scope']

        for c in [x for x in scenario_scope if x['className'] == 'Cluster']:
            try:
                memberlist = []
                clstr = self._vmt.get_groups(c['uuid'])[0]

                try:
                    memberlist = clstr['memberUuidList']
                except KeyError:
                    # Classic compatibility
                    memberlist = [x['uuid'] for x in self._vmt.get_group_members(c['uuid'])]
            except Exception:
                clstr = None

            if not clstr or not memberlist:
                self.log(f'Skipping empty cluster [{c["uuid"]}]:[{c["displayName"]}]', level='debug')
                continue

            self.log(f'Initializing [{c["uuid"]}]:[{c["displayName"]}]')
            self.clusters[c['uuid']] = {
                'name': c['displayName'],
                'members': set(),
                'realtimeMembers': set(copy.deepcopy(memberlist)),
                'groups': {
                    'PhysicalMachine': {0: copy.deepcopy(self.group_template)},
                    'Storage': {0: copy.deepcopy(self.group_template)},
                },
                'growth': 0,
                'headroom': {}
            }

    def _update_cluster_members(self):
        if self._vmt.is_xl():
            self._update_cluster_members_xl()
        else:
            self._update_cluster_members_classic()

    def _update_cluster_members_xl(self):
        cache = {}
        response = self._vmt.get_supplychains(self.market_id,
                                              types=self.types,
                                              detail='entity',
                                              pager=True)

        while not response.complete:
            cache = {**cache, **condense_supplychain(response.next)}
            keys = list(cache.keys())

            for e in keys:
                if e not in cache:
                    # storages
                    continue

                for c in self.clusters:
                    if e in self.clusters[c]['members']:
                        ent = {x: cache[e][x] for x in self.entity_parts}

                        if cache[e]['className'] == 'PhysicalMachine':
                            self._add_cluster_member(c, ent, 'PhysicalMachine')

                            # pull in storages if available
                            for s in cache[e]['providers']:
                                if s['className'] != 'Storage' or s['uuid'] not in cache:
                                    continue
                                self._add_cluster_member(c, s['uuid'], 'Storage')
                                del cache[s['uuid']]

                        del cache[e]


    def _update_cluster_members_classic(self):
        # Classic doesn't provide the consumer/provider details in the supplychain
        # so we must link hosts and storages to the cluster by cross-referencing
        # their real-time counterparts against the cluster supplychain
        #
        # market host => realtime host => cluster
        # market storage => realtime storage => cluster
        def addent(c, entity):
            real_id = entity['realtimeMarketReference']['uuid']
            ent = {x: entity[x] for x in self.entity_parts}
            ent['realtimeUuid'] = real_id
            self._add_cluster_member(c, ent, entity['className'], real_id)

        def processchain(type):
            response = self._vmt.get_supplychains(self.market_id,
                                                  types=[type],
                                                  detail='entity',
                                                  pager=True)
            while not response.complete:
                entities = condense_supplychain(response.next)

                for c in self.clusters:
                    try:
                        res = self._vmt.get_supplychains(c,
                                                         types=[type],
                                                         detail='entity',
                                                         pager=True)
                        cmember = condense_supplychain(res.all)
                    except Exception:
                        self.log(f'Cluster [{c}]:[{self.clusters[c]["name"]}] has no members of type {type}', level='warn')
                        continue

                    keys = list(entities.keys())

                    for k in keys:
                        if entities[k]['realtimeMarketReference']['uuid'] \
                        in cmember:
                            addent(c, entities[k])
                            del entities[k]

        for t in self.types:
            processchain(t)

    def _update_cluster_stats(self, id):
        # update cluster statistics
        for s in self._get_stats(list(self.clusters[id]['members']), self.commodities):
            if s['className'] not in self.types:
                continue

            if s['uuid'] in self.clusters[id]['groups'][s['className']][0]['members']:
                newstats = {}
                for stat in s['stats'][0]['statistics']:
                    newstats[stat['name']] = {
                        'capacity': stat['capacity']['total'],
                        'name': stat['name'],
                        'units': stat['units'],
                        'value': stat['value']
                    }

                self.clusters[id]['groups'][s['className']][0]['members'][s['uuid']]['statistics'] = newstats

    def _update_cluster_subgroups(self, id):
        # split cluster members by groups
        for e in self.clusters[id]['members']:
            remove = []

            for g in self.groups:
                # Classic compatibility - resolve copied entity references
                try:
                    ref_id = self.clusters[id]['groups'][g.type][0]['members'][e].get('realtimeUuid', e)
                except KeyError:
                    # not a member of this group type
                    continue

                if ref_id in g.members:
                    # if e is a member, re-group it
                    if g.name not in self.clusters[id]['groups'][g.type]:
                        self.clusters[id]['groups'][g.type][g.name] = copy.deepcopy(self.group_template)

                    self.clusters[id]['groups'][g.type][g.name]['members'][e] = self.clusters[id]['groups'][g.type][0]['members'][e]
                    remove.append((e, g.type))

            # remove regrouped members from inverse group
            for e, t in remove:
                if e in self.clusters[id]['groups'][t][0]['members']:
                    del self.clusters[id]['groups'][t][0]['members'][e]

    def _update_cluster_vm_growth(self):
        # calculate vm growth for each cluster
        scope = [c for c in self.clusters.keys()]
        timestamp = int(time.mktime((datetime.datetime.now() + datetime.timedelta(days=-1*self.growth_lookback)).timetuple()) * 1000)
        stats = ['numVMs']

        then = self._vmt.get_entity_stats(scope=scope, start_date=timestamp, end_date=timestamp, stats=stats, fetch_all=True)
        now = self._vmt.get_entity_stats(scope=scope, stats=stats, fetch_all=True)

        for n in now:
            curdate = read_isodate(n['stats'][0]['date'])
            cur = n['stats'][0]['statistics'][0]['value']
            self.clusters[n['uuid']]['growth'] = cur

            for t in then:
                try:
                    if t['uuid'] == n['uuid']:
                        olddate = read_isodate(t['stats'][0]['date'])
                        growth = (cur - t['stats'][0]['statistics'][0]['value']) / (curdate - olddate).days
                        self.clusters[n['uuid']]['growth'] = growth if growth > 0 else 0
                        break
                except KeyError:
                    pass

            self.log(f'Cluster [{n["uuid"]}]:[{self.clusters[n["uuid"]]["name"]}] growth: {self.clusters[n["uuid"]]["growth"]}', level='debug')

    def _prepare_templates(self):
        # initializes templates and calculates commodity values
        cache = self._vmt.get_templates(fetch_all=True)

        def find_default(name):
            # gets the sys generated cluster AVG template
            for i in cache:
                if i['displayName'] == name:
                    return True

            return False

        # init
        for x in self.templates:
            x.get_resources(self._vmt)

        # assign
        for c in self.clusters:
            for t in self.clusters[c]['groups']:
                for g in self.clusters[c]['groups'][t]:
                    if g == 0:
                        # defualt ungrouped cluster entitites
                        if not self.clusters[c]['groups'][t][g]['members']:
                            continue

                        templates = [x for x in self.templates if self.clusters[c]['name'] in x.targets]

                        if not templates:
                            name = f'AVG:{self.clusters[c]["name"]} for last 10 days'

                            if find_default(name):
                                x = Template(name, [self.clusters[c]['name']])
                                x.get_resources(self._vmt)

                                # by adding it to the template list, it can be reused (e.g. for PM & Storage)
                                self.log(f'Adding default cluster template [{name}]', level='debug')
                                self.templates.append(x)
                                templates = (x)
                            else:
                                continue

                        self.clusters[c]['groups'][t][g]['templates'] = templates
                    elif g != 0:
                        # user grouped entities
                        templates = [x for x in self.templates
                                     if g in x.targets and
                                     (not x.clusters
                                      or self.clusters[c]['name'] in x.clusters)]

                        self.clusters[c]['groups'][t][g]['templates'] = templates

                    if not self.clusters[c]['groups'][t][g]['templates']:
                        self.log(f'No template not provided for [{g}] in [{c}]:[{self.clusters[c]["name"]}]', level='warn')

    def _apply_templates(self):
        def exhaustdays(g, c):
            if g > 0:
                return int(D(c) / D(g))
            else:
                return -1

        for c in self.clusters:
            cluster_headroom = {}
            growth = D(0) if D(self.clusters[c]['growth']) < 0 else D(self.clusters[c]['growth'])
            self.log(f'Calculating [{c}]:[{self.clusters[c]["name"]}] headroom')

            for t in self.clusters[c]['groups']:
                cluster_headroom[t] = {}
                comms = self.type_commodity[t]

                # compute type groups
                for key, group in self.clusters[c]['groups'][t].items():
                    if group['templates'] is None:
                        self.log(f'Skipping [{t}] group [{key}], no template assigned.', level='debug')
                        continue

                    members = group['members']
                    # TODO : add filtering
                    #members = filter_members()

                    # calculate commodity headroom based on mode
                    if self.mode == HeadroomMode.SEPARATE:
                        for i in group['templates']:
                            cluster_headroom[t][i.name] = {}
                            for o in comms:
                                cluster_headroom[t][i.name][o] = self._commodity_headroom(members, o, [i])
                                cluster_headroom[t][i.name][o]['DaysToExhaustion'] = exhaustdays(growth, cluster_headroom[t][i.name][o]['Available'])
                                cluster_headroom[t][i.name][o]['TemplateCount'] = 1
                    else:
                        for o in comms:
                            cluster_headroom[t][o] = self._commodity_headroom(members, o, group['templates'], self.mode)
                            cluster_headroom[t][o]['DaysToExhaustion'] = exhaustdays(growth, cluster_headroom[t][o]['Available'])
                            cluster_headroom[t][o]['TemplateCount'] = len(group['templates'])
                # end group loop ---
            # end type loop ---
            self.clusters[c]['headroom'] = cluster_headroom

    def _post_cluster_headroom(self):
        # main processor
        if self.result != MarketState.SUCCEEDED:
            raise PlanRunFailure(f'Invalid target plan market state: {self.results}')

        self.log('Fetching group data', level='debug')
        for x in self.groups:
            x.get_members(self._vmt)

        self.log('Initializing clusters')
        self._init_clusters()
        self._update_cluster_members()

        for c in self.clusters:
            self.log(f'Updating statistics for [{c}]:[{self.clusters[c]["name"]}]', level='debug')
            self._update_cluster_stats(c)

            self.log(f'Updating groups for [{c}]:[{self.clusters[c]["name"]}]', level='debug')
            self._update_cluster_subgroups(c)

            # debug
            for t in self.clusters[c]['groups']:
                for g in self.clusters[c]['groups'][t]:
                    count = len(self.clusters[c]['groups'][t][g]['members'])
                    self.log(f'[{t}]:[{g}]:{count}', level='debug')

        self.log(f'Calculating cluster growth over {self.growth_lookback} days')
        self._update_cluster_vm_growth()

        self.log(f'Preparing templates')
        self._prepare_templates()

        # pp = PrettyPrinter(depth=3, width=80)
        # pp.pprint(self.clusters)
        # return

        self.log(f'Calculating headroom')
        self._apply_templates()

        return self.clusters

    def headroom(self):
        headroom = {}

        for c in self.clusters:
            headroom[c] = self.clusters[c]['headroom']

        return headroom



def condense_supplychain(chain, types=None):
    # flattens the separate supplychain types to a single dictionary of all
    # entities for the given types list
    if types is None:
        return {k2: v2 for k, v in chain[0]['seMap'].items() for k2, v2 in v['instances'].items()}

    return {k2: v2 for k, v in chain[0]['seMap'].items() if k in types for k2, v2 in v['instances'].items()}


def calc_strict_dist(members, commodity, required, vmcount):
    headroom_available = 0
    headroom_capacity = 0

    for m in members:
        if 'statistics' not in members[m]:
            umsg.log(f'Skipping entity [{members[m]["displayName"]}], no statistics', level='debug')
            continue

        cap = D(members[m]['statistics'][commodity]['capacity'])
        used = D(members[m]['statistics'][commodity]['value'])
        avail = cap - used
        headroom_available += 0 if required <= 0 else vmcount * int(avail / required)
        headroom_capacity += 0 if required <= 0 else vmcount * int(cap / required)

    return headroom_available, headroom_capacity
