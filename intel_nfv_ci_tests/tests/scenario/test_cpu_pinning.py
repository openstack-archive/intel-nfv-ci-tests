# Copyright 2015 Intel Corporation
# All Rights Reserved.
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

import libvirt
from tempest.lib.common.utils import data_utils
import testtools
import xml.etree.ElementTree as ET

from tempest.api.compute import base
from tempest.common import waiters
from tempest import config
from tempest import test


CONF = config.CONF


def get_siblings_list(sib):
    """
    list of siblings can consist of comma-separated lists (0,5,6)
    or hyphen-separated ranges (0-3) or both

    Test a combination of '-' and ','
    >>> get_siblings_list('0-2,3,4,5-6,9')
    [0, 1, 2, 3, 4, 5, 6, 9]
    """
    siblings = []
    for sub_sib in sib.split(','):
        if '-' in sub_sib:
            start_sib, end_sib = sub_sib.split('-')
            siblings.extend(range(int(start_sib),
                                  int(end_sib) + 1))
        else:
            siblings.append(int(sub_sib))

    return siblings


def get_host_cpu_siblings():
    """Return core to sibling mapping of the host CPUs

        {core_0: [sibling_a, sibling_b, ...],
         core_1: [sibling_a, sibling_b, ...],
         ...}

    libvirt's getCapabilities() is called to get details about the host
    then a list of siblings per CPU is extracted and formatted to single level
    list
    """
    siblings = {}
    conn = libvirt.openReadOnly('qemu:///system')
    capxml = ET.fromstring(conn.getCapabilities())
    cpu_cells = capxml.findall('./host/topology/cells/cell/cpus')

    for cell in cpu_cells:
        cpus = cell.findall('cpu')
        for cpu in cpus:
            cpu_id = int(cpu.get('id'))
            sib = cpu.get('siblings')
            _siblings = get_siblings_list(sib)

            siblings.update({cpu_id: _siblings})

    return siblings


class CPUPolicyTest(base.BaseV2ComputeAdminTest):

    """
    Tests CPU policy support.
    """

    @classmethod
    def skip_checks(cls):
        super(CPUPolicyTest, cls).skip_checks()
        if not test.is_extension_enabled('OS-FLV-EXT-DATA', 'compute'):
            msg = "OS-FLV-EXT-DATA extension not enabled."
            raise cls.skipException(msg)

    @classmethod
    def setup_clients(cls):
        super(CPUPolicyTest, cls).setup_clients()
        cls.flavors_client = cls.os_adm.flavors_client
        cls.servers_client = cls.os_adm.servers_client

    @classmethod
    def resource_setup(cls):
        super(CPUPolicyTest, cls).resource_setup()

        cls.flavor_name_prefix = 'test_hw_'
        cls.ram = 64
        cls.vcpus = 2
        cls.disk = 0
        cls.ephemeral = 0
        cls.swap = 0
        cls.rxtx_factor = 2

    def flavor_clean_up(self, flavor_id):
        self.flavors_client.delete_flavor(flavor_id)
        self.flavors_client.wait_for_resource_deletion(flavor_id)

    def server_clean_up(self, server_id):
        self.servers_client.delete_server(server_id)
        waiters.wait_for_server_termination(self.servers_client, server_id)

    def _create_flavor(self, cpu_policy='shared',
                       cpu_threads_policy=None):
        flavor_name = data_utils.rand_name(self.flavor_name_prefix)
        flavor_id = data_utils.rand_int_id(start=1000)

        flavor = self.flavors_client.create_flavor(
            name=flavor_name, ram=self.ram, vcpus=self.vcpus,
            disk=self.disk, id=flavor_id,
            swap=self.swap,
            rxtx_factor=self.rxtx_factor)['flavor']
        self.addCleanup(self.flavor_clean_up, flavor['id'])

        specs = {'hw:cpu_policy': cpu_policy}
        if cpu_policy == 'dedicated':
            specs['hw:cpu_thread_policy'] = cpu_threads_policy

        self.flavors_client.set_flavor_extra_spec(flavor['id'], **specs)

        return flavor

    def _create_server(self, flavor):
        server = self.create_test_server(
            flavor=flavor['id'], wait_until='ACTIVE')
        self.addCleanup(self.server_clean_up, server['id'])

        # get more information
        server = self.servers_client.show_server(server['id'])['server']

        return server

    def _resize_server(self, server, flavor):
        self.servers_client.resize_server(server['id'], flavor['id'])

        waiters.wait_for_server_status(self.servers_client, server['id'],
                                       'VERIFY_RESIZE')
        self.servers_client.confirm_resize_server(instance_id)
        waiters.wait_for_server_status(self.servers_client, server['id'],
                                       'ACTIVE')

        # get more information
        server = self.servers_client.show_server(server['id'])['server']
        self.assertEqual(self.flavor['id'], server['flavor']['id'])

        return server

    def _reboot_server(self, server, reboot_type):
        self.servers_client.reboot_server(server['id'], type=reboot_type)
        waiters.wait_for_server_status(self.servers_client,
                                       server['id'], 'ACTIVE')
        # get more information
        server = self.servers_client.show_server(server['id'])['server']

        return server

    def _get_cpu_pinning(self, server):
        instance_name = server['OS-EXT-SRV-ATTR:instance_name']

        conn = libvirt.openReadOnly('qemu:///system')
        dom0 = conn.lookupByName(instance_name)
        root = ET.fromstring(dom0.XMLDesc())

        vcpupin_nodes = root.findall('./cputune/vcpupin')
        cpu_pinnings = {int(x.get('vcpu')): int(x.get('cpuset'))
                        for x in vcpupin_nodes if x is not None}

        return cpu_pinnings

    def test_cpu_shared(self):
        flavor = self._create_flavor(cpu_policy='shared')
        self._create_server(flavor)

    def test_cpu_dedicated_threads_isolate(self):
        """Ensure vCPUs *are not* placed on thread siblings."""
        flavor = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='isolate')
        server = self._create_server(flavor)
        cpu_pinnings = self._get_cpu_pinning(server)
        pcpu_siblings = get_host_cpu_siblings()

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        # if the 'isolate' policy is used, then when one thread is used
        # the other should never be used.
        for vcpu in set(cpu_pinnings):
            pcpu = cpu_pinnings[vcpu]
            sib = pcpu_siblings[pcpu]
            sib.remove(pcpu)
            self.assertTrue(set(sib).isdisjoint(cpu_pinnings.values()))

    def test_cpu_dedicated_threads_prefer(self):
        """Ensure vCPUs *are* placed on thread siblings."""
        flavor = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')
        server = self._create_server(flavor)
        cpu_pinnings = self._get_cpu_pinning(server)
        pcpu_siblings = get_host_cpu_siblings()

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        # if the 'prefer' policy is used, then when one thread is used
        # the other should also be used.
        for vcpu in set(cpu_pinnings):
            pcpu = cpu_pinnings[vcpu]
            sib = pcpu_siblings[pcpu]
            sib.remove(pcpu)
            self.assertFalse(set(sib).isdisjoint(cpu_pinnings.values()))

    @testtools.skipUnless(CONF.compute_feature_enabled.resize,
                          'Resize not available.')
    def test_resize_pinned_server_to_unpinned(self):
        flavor_a = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')
        server = self._create_server(flavor_a)
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        flavor_b = self._create_flavor(cpu_policy='shared')
        server = self._resize_server(server, flavor_b)
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), 0)

    @testtools.skipUnless(CONF.compute_feature_enabled.resize,
                          'Resize not available.')
    def test_resize_unpinned_server_to_pinned(self):
        flavor_a = self._create_flavor(cpu_policy='shared')
        server = self._create_server(flavor_a)
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), 0)

        flavor_b = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')
        server = self._resize_server(server, flavor_b)
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), self.vcpus)

    def test_reboot_pinned_server(self):
        flavor_a = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')
        server = self._create_server(flavor_a)
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        server = self._reboot_server(server, 'HARD')
        cpu_pinnings = self._get_cpu_pinning(server)

        self.assertEqual(len(cpu_pinnings), self.vcpus)
