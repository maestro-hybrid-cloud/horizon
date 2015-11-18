# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2013 NTT MCL Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

import boto.vpc

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponse  # noqa
from django.utils.translation import ugettext_lazy as _
from django.views.generic import View  # noqa
import django.views

from horizon import exceptions
from horizon import views
from horizon import messages
from openstack_dashboard import api
from openstack_dashboard import policy
from openstack_dashboard.usage import quotas
from openstack_dashboard.dashboards.project.hybrid_cloud.instances \
    import tables as instances_tables
from openstack_dashboard.dashboards.project.hybrid_cloud.networks \
    import tables as networks_tables
from openstack_dashboard.dashboards.project.hybrid_cloud.ports \
    import tables as ports_tables
from openstack_dashboard.dashboards.project.hybrid_cloud.routers \
    import tables as routers_tables
from openstack_dashboard.dashboards.project.hybrid_cloud.subnets \
    import tables as subnets_tables
from openstack_dashboard.dashboards.project.instances import\
    console as i_console
from openstack_dashboard.dashboards.project.instances import\
    views as i_views
from openstack_dashboard.dashboards.project.instances.workflows import\
    create_instance as i_workflows
from openstack_dashboard.dashboards.project.networks.subnets import\
    views as s_views
from openstack_dashboard.dashboards.project.networks.subnets import\
    workflows as s_workflows
from openstack_dashboard.dashboards.project.networks import\
    views as n_views
from openstack_dashboard.dashboards.project.networks import\
    workflows as n_workflows
from openstack_dashboard.dashboards.project.routers.ports import\
    views as p_views
from openstack_dashboard.dashboards.project.routers import\
    views as r_views
from openstack_dashboard.utils import metering as metering_utils

class TestView(View):
    template_name = 'project/'


class NTAddInterfaceView(p_views.AddInterfaceView):
    success_url = "horizon:project:hybrid_cloud:index"
    failure_url = "horizon:project:hybrid_cloud:index"

    def get_success_url(self):
        return reverse("horizon:project:hybrid_cloud:index")

    def get_context_data(self, **kwargs):
        context = super(NTAddInterfaceView, self).get_context_data(**kwargs)
        context['form_url'] = 'horizon:project:hybrid_cloud:interface'
        return context


class NTCreateRouterView(r_views.CreateView):
    template_name = 'project/hybrid_cloud/create_router.html'
    success_url = reverse_lazy("horizon:project:hybrid_cloud:index")
    page_title = _("Create a Router")


class NTCreateNetwork(n_workflows.CreateNetwork):
    def get_success_url(self):
        return reverse("horizon:project:hybrid_cloud:index")

    def get_failure_url(self):
        return reverse("horizon:project:hybrid_cloud:index")


class NTCreateNetworkView(n_views.CreateView):
    workflow_class = NTCreateNetwork


class NTLaunchInstance(i_workflows.LaunchInstance):
    success_url = "horizon:project:hybrid_cloud:index"


class NTLaunchInstanceView(i_views.LaunchInstanceView):
    workflow_class = NTLaunchInstance


class NTCreateSubnet(s_workflows.CreateSubnet):
    def get_success_url(self):
        return reverse("horizon:project:hybrid_cloud:index")

    def get_failure_url(self):
        return reverse("horizon:project:hybrid_cloud:index")


class NTCreateSubnetView(s_views.CreateView):
    workflow_class = NTCreateSubnet


class InstanceView(i_views.IndexView):
    table_class = instances_tables.InstancesTable
    template_name = 'project/hybrid_cloud/iframe.html'


class RouterView(r_views.IndexView):
    table_class = routers_tables.RoutersTable
    template_name = 'project/hybrid_cloud/iframe.html'


class NetworkView(n_views.IndexView):
    table_class = networks_tables.NetworksTable
    template_name = 'project/hybrid_cloud/iframe.html'


class RouterDetailView(r_views.DetailView):
    table_classes = (ports_tables.PortsTable, )
    template_name = 'project/hybrid_cloud/iframe.html'

    def get_interfaces_data(self):
        pass


class NetworkDetailView(n_views.DetailView):
    table_classes = (subnets_tables.SubnetsTable, )
    template_name = 'project/hybrid_cloud/iframe.html'


class HybridTopologyView(views.HorizonTemplateView):
    template_name = 'project/hybrid_cloud/index.html'
    page_title = _("Hybrid Cloud Manager")

    def _has_permission(self, policy):
        has_permission = True
        policy_check = getattr(settings, "POLICY_CHECK_FUNCTION", None)

        if policy_check:
            has_permission = policy_check(policy, self.request)

        return has_permission

    def _quota_exceeded(self, quota):
        usages = quotas.tenant_quota_usages(self.request)
        available = usages[quota]['available']
        return available <= 0

    def get_context_data(self, **kwargs):
        context = super(HybridTopologyView, self).get_context_data(**kwargs)
        network_config = getattr(settings, 'OPENSTACK_NEUTRON_NETWORK', {})

        context['launch_instance_allowed'] = self._has_permission(
            (("compute", "compute:create"),))
        context['instance_quota_exceeded'] = self._quota_exceeded('instances')
        context['create_network_allowed'] = self._has_permission(
            (("network", "create_network"),))
        context['network_quota_exceeded'] = self._quota_exceeded('networks')
        context['create_router_allowed'] = (
            network_config.get('enable_router', True) and
            self._has_permission((("network", "create_router"),)))
        context['router_quota_exceeded'] = self._quota_exceeded('routers')
        context['console_type'] = getattr(
            settings, 'CONSOLE_TYPE', 'AUTO')
        context['show_ng_launch'] = getattr(
            settings, 'LAUNCH_INSTANCE_NG_ENABLED', False)
        context['show_legacy_launch'] = getattr(
            settings, 'LAUNCH_INSTANCE_LEGACY_ENABLED', True)
        return context


class JSONView(View):

    def __init__(self):
        super(JSONView, self).__init__(self)
        self._vpc_conn = None

    def vpc(self):
        if self._vpc_conn is None:
            self._vpc_conn = boto.vpc.VPCConnection()
        return self._vpc_conn

    @property
    def is_router_enabled(self):
        network_config = getattr(settings, 'OPENSTACK_NEUTRON_NETWORK', {})
        return network_config.get('enable_router', True)

    def add_resource_url(self, view, resources):
        tenant_id = self.request.user.tenant_id
        for resource in resources:
            if (resource.get('tenant_id')
                    and tenant_id != resource.get('tenant_id')):
                continue
            resource['url'] = reverse(view, None, [str(resource['id'])])

    def _check_router_external_port(self, ports, router_id, network_id):
        for port in ports:
            if (port['network_id'] == network_id
                    and port['device_id'] == router_id):
                return True
        return False

    def _get_servers(self, request, stack):
        stack_resources = self._get_resources_from_stack(request, stack)

        data = []
        for resource in stack_resources:
            resource_data = {'name': resource.resource_name,
                                 'id': resource.physical_resource_id,
                                 'type': resource.resource_type,
                                 'status': resource.resource_status,
                                 'stack_id': stack.id,
                                 'stack_name': stack.stack_name }

            if resource.resource_type == 'OS::Heat::ScaledResource':
                server = api.nova.server_get(request, resource_data['id'])

                console_type = getattr(settings, 'CONSOLE_TYPE', 'AUTO')
                # lowercase of the keys will be used at the end of the console URL.
                try:
                    console = i_console.get_console(
                        request, console_type, server)[0].lower()
                except exceptions.NotAvailable:
                    console = None

                server_data = {'name': server.name,
                               'status': server.status,
                               'task': getattr(server, 'OS-EXT-STS:task_state'),
                               'id': server.id}
                if console:
                    server_data['console'] = console

                self.add_resource_url('horizon:project:instances:detail', data)
                data.append(server_data)

            elif resource.resource_type == 'AWS::VPC::EC2Instance':
                server_data = {'name': resource_data['name'],
                           'status': resource_data['status'],
                           'task': None,
                           'id': resource_data['id']}

                server_data['console'] = None
                data.append(server_data)

        return data

    def _get_networks(self, request, stack):
        stack_resources = self._get_resources_from_stack(request, stack)

        networks = []
        for resource in stack_resources:
            resource_data = {'name': resource.resource_name,
                             'id': resource.physical_resource_id,
                             'type': resource.resource_type,
                             'status': resource.resource_status,
                             'stack_id': stack.id,
                             'stack_name': stack.stack_name }

            if resource.resource_type == 'OS::Neutron::Net':
                network = api.neutron.network_get(request, resource_data['id'])

                obj = {'name': network.name,
                       'id': network.id,
                       'subnets': [{'id': subnet.id,
                                    'cidr': subnet.cidr}
                                   for subnet in network.subnets],
                       'status': network.status,
                       'router:external': network['router:external']}
                self.add_resource_url('horizon:project:networks:subnets:detail',
                                      obj['subnets'])
                networks.append(obj)

            elif resource.resource_type == 'AWS::VPC::VPC':
                subnets = self.vpc().get_all_subnets(filters={'vpcId': resource_data['id']})
                networks.append({'name': resource_data['name'],
                       'id': resource_data['id'],
                       'subnets': [{'id': subnet.id,
                                    'cidr': subnet.cidr_block}
                                   for subnet in subnets],
                       'status': resource_data['status'],
                       'router:external': True})

        # Add public networks to the networks list
        if self.is_router_enabled:
            try:
                neutron_public_networks = api.neutron.network_list(
                    request,
                    **{'router:external': True})
            except Exception:
                neutron_public_networks = []
            my_network_ids = [net['id'] for net in networks]
            for publicnet in neutron_public_networks:
                if publicnet.id in my_network_ids:
                    continue
                try:
                    subnets = []
                    for subnet in publicnet.subnets:
                        snet = {'id': subnet.id,
                                'cidr': subnet.cidr}
                        self.add_resource_url(
                            'horizon:project:networks:subnets:detail', snet)
                        subnets.append(snet)
                except Exception:
                    subnets = []
                networks.append({
                    'name': publicnet.name,
                    'id': publicnet.id,
                    'subnets': subnets,
                    'status': publicnet.status,
                    'router:external': publicnet['router:external']})

        self.add_resource_url('horizon:project:networks:detail',
                              networks)

        return sorted(networks,
                      key=lambda x: x.get('router:external'),
                      reverse=True)

    def _get_routers(self, request, stack):
        if not self.is_router_enabled:
            return []

        stack_resources = self._get_resources_from_stack(request, stack)

        routers = []
        for resource in stack_resources:
            resource_data = {'name': resource.resource_name,
                             'id': resource.physical_resource_id,
                             'type': resource.resource_type,
                             'status': resource.resource_status,
                             'stack_id': stack.id,
                             'stack_name': stack.stack_name }

            if resource.resource_type == 'AWS::VPC::VPNGateway':
                routers.append({'id': resource_data['id'],
                        'name': resource_data['name'],
                        'status': resource_data['status']})

            elif resource.resource_type == 'OS::Neutron::Router':
                router = api.neutron.router_get(request, resource_data['id'])
                routers.append({'id': router.id,
                            'name': router.name,
                            'status': router.status,
                            'external_gateway_info': router.external_gateway_info})

                self.add_resource_url('horizon:project:routers:detail', routers)
                return routers

    def _get_ports(self, request):
        try:
            neutron_ports = api.neutron.port_list(request)
        except Exception:
            neutron_ports = []

        ports = [{'id': port.id,
                  'network_id': port.network_id,
                  'device_id': port.device_id,
                  'fixed_ips': port.fixed_ips,
                  'device_owner': port.device_owner,
                  'status': port.status}
                 for port in neutron_ports
                 if port.device_owner != 'network:router_ha_interface']
        self.add_resource_url('horizon:project:networks:ports:detail',
                              ports)
        return ports

    def _get_stacks(self, request):
        heat_stacks = []
        try:
            heat_stacks, self._more, self._prev = api.heat.stacks_list(request)
        except Exception:
            self._prev = False
            self._more = False
            msg = _('Unable to retrieve stack list.')
            exceptions.handle(self.request, msg)

        return heat_stacks

    def _get_stack_include_aws_autoscaling_group(self, request):
        all_stacks = self._get_stacks(request)

        result_stacks = []
        for stack in all_stacks:
            heat_resources = []
            try:
                heat_resources = api.heat.resources_list(request, stack.stack_name, 3)
            except Exception:
                msg = _('Unable to retrieve resource list.')
                exceptions.handle(request, msg)

            for resource in heat_resources:
                if resource.resource_type == 'OS::Heat::AWSHybridAutoScalingGroup':
                    result_stacks.append(stack)
                    break

        return result_stacks

    def _get_resources_from_stack(self, request, stack):
        heat_resources = []
        try:
            heat_resources = api.heat.resources_list(request, stack.stack_name, 3)
        except Exception:
            msg = _('Unable to retrieve resource list.')
            exceptions.handle(self.request, msg)

        return heat_resources

    def _prepare_gateway_ports(self, routers, ports):
        # user can't see port on external network. so we are
        # adding fake port based on router information
        for router in routers:
            external_gateway_info = router.get('external_gateway_info')
            if not external_gateway_info:
                continue
            external_network = external_gateway_info.get(
                'network_id')
            if not external_network:
                continue
            if self._check_router_external_port(ports,
                                                router['id'],
                                                external_network):
                continue
            fake_port = {'id': 'gateway%s' % external_network,
                         'network_id': external_network,
                         'device_id': router['id'],
                         'fixed_ips': []}
            ports.append(fake_port)

    def get(self, request, *args, **kwargs):
        stacks = self._get_stack_include_aws_autoscaling_group(request)

        data = {'servers': [],
                'networks': [],
                'ports': [],
                'routers': [],
                'stacks': []}

        for stack in stacks:
            data = {'servers': self._get_servers(request, stack),
                'networks': self._get_networks(request, stack),
                'ports': self._get_ports(request),
                'routers': self._get_routers(request, stack)}

        self._prepare_gateway_ports(data['routers'], data['ports'])
        json_string = json.dumps(data, ensure_ascii=False)
        return HttpResponse(json_string, content_type='text/json')

class SamplesView(django.views.generic.TemplateView):
    def get(self, request, *args, **kwargs):
        meter = 'cpu_util'
        meter_name = meter.replace(".", "_")
        date_options = 7
        date_from = None
        date_to = None
        stats_attr = 'avg'
        group_by = 'project'
        try:
            date_from, date_to = metering_utils.calc_date_args(date_from,
                                                               date_to,
                                                               date_options)
        except Exception:
            exceptions.handle(self.request, _('Dates cannot be recognized.'))

        if request.GET.get('instance_id') != None:
           query = metering_utils.MeterQuery(request, date_from, date_to, 3600 * 24)
           resources, unit = query.filter_by_instance_id(meter, date_from, date_to, request.GET.get('instance_id'))
           series = metering_utils.series_for_meter(request, resources, request.GET.get('instance_id'),
                                                    meter, meter_name, 'avg', unit)
           settings =  {'yMin': 0, 'yMax': 100, 'higlight_last_point': True,
                                                "auto_size": False, 'auto_resize': True}
        else:
           query = metering_utils.ProjectAggregatesQuery(request, date_from, date_to, 3600 * 24)
           resources, unit = query.query(meter)
           series = metering_utils.series_for_meter_with_threshold_and_max(request, resources, group_by, meter,
                                                                           meter_name, stats_attr, unit,
                                                                           50.0, 100.0)
           settings =  {'yMin': 0, 'yMax': 100, 'higlight_last_point': True,
                                                "auto_size": False, 'auto_resize': False}

        series = metering_utils.normalize_series_by_unit(series)
        ret = {'series': series, 'settings': settings}
        return HttpResponse(json.dumps(ret), content_type='application/json')
