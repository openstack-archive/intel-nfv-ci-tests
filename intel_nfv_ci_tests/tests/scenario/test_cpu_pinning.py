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
import multiprocessing
from tempest_lib.common.utils import data_utils
from tempest_lib import decorators
from tempest_lib import exceptions as lib_exc
import testtools
import xml.etree.ElementTree as ET

from tempest.api.compute import base
from tempest.common import waiters
from tempest import config
from tempest import test


CONF = config.CONF


def get_core_mappings():
    """Return core mapping for a dual-socket, HT-enabled board.

    Generate mappings for CPU. Has following structure:

        {numa_node_a: ([core_1_thread_a, core_2_thread_a, ...],
                       [core_1_thread_b, core_2_thread_b, ...]),
         ...}

    The physical cores are assigned indexes first (0-based) and start
    at node 0. The virtual cores are then listed.

        >>> get_core_mappings(2)
        {0: ([0, 1], [4, 5]), 1: ([2, 3], [6, 7])}
    """
    # get number of real CPUs per socket, assuming a dual-socket,
    # HT-enabled board (2 * 2)
    cpu_per_soc = multiprocessing.cpu_count() / (2 * 2)

    # calculate mappings
    core_mappings = {
        soc: (range(soc * cpu_per_soc, (soc + 1) * cpu_per_soc),
              range((soc + 2) * cpu_per_soc, (soc + 3) * cpu_per_soc))
        for soc in range(0, 2)
    }
    return core_mappings


class FlavorsAdminTestJSON(base.BaseV2ComputeAdminTest):

    """
    Tests Flavors API Create and Delete that require admin privileges
    """

    @classmethod
    def skip_checks(cls):
        super(FlavorsAdminTestJSON, cls).skip_checks()
        if not test.is_extension_enabled('OS-FLV-EXT-DATA', 'compute'):
            msg = "OS-FLV-EXT-DATA extension not enabled."
            raise cls.skipException(msg)

    @classmethod
    def setup_clients(cls):
        super(FlavorsAdminTestJSON, cls).setup_clients()
        cls.flavors_client = cls.os_adm.flavors_client
        cls.servers_client = cls.os_adm.servers_client

    @classmethod
    def resource_setup(cls):
        super(FlavorsAdminTestJSON, cls).resource_setup()

        cls.flavor_name_prefix = 'test_hw_'
        cls.ram = 512
        cls.vcpus = 4
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
        self.servers_client.resize(server['id'], flavor['id'])

        # get more information
        server = self.servers_client.show_server(server['id'])['server']

        return server

    def _reboot_server(self, server, reboot_type):
        self.servers_client.reboot_server(server['id'], reboot_type)

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

    @decorators.skip_because(bug='0')
    def test_cpu_dedicated_threads_separate(self):
        """Ensure vCPUs *are not* placed on thread siblings."""
        flavor = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='separate')
        server = self._create_server(flavor)
        cpu_pinnings = self._get_cpu_pinning(server)
        core_mappings = get_core_mappings()

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        # if the 'prefer' policy is used, then when one thread is used
        # the other should never be used.
        for vcore in set(cpu_pinnings):
            pcpu = cpu_pinnings[vcore]
            if pcpu in core_mappings[0][0]:
                index = core_mappings[0][0].index(pcpu)
                self.assertNotIn(core_mappings[0][1][index],
                                 cpu_pinnings.values())
            else:
                index = core_mappings[0][1].index(pcpu)
                self.assertNotIn(core_mappings[0][0][index],
                                 cpu_pinnings.values())

    def test_cpu_dedicated_threads_prefer(self):
        """Ensure vCPUs *are* placed on thread siblings."""
        flavor = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')
        server = self._create_server(flavor)
        cpu_pinnings = self._get_cpu_pinning(server)
        core_mappings = get_core_mappings()

        self.assertEqual(len(cpu_pinnings), self.vcpus)

        # if the 'prefer' policy is used, then when one thread is used
        # the other should also be used.
        for vcore in set(cpu_pinnings):
            pcpu = cpu_pinnings[vcore]
            if pcpu in core_mappings[0][0]:
                index = core_mappings[0][0].index(pcpu)
                self.assertIn(core_mappings[0][1][index],
                              cpu_pinnings.values())
            else:
                index = core_mappings[0][1].index(pcpu)
                self.assertIn(core_mappings[0][0][index],
                              cpu_pinnings.values())

    @decorators.skip_because(bug='0')
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

    @decorators.skip_because(bug='0')
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

    def test_oversubscribed_server(self):
        flavor = self._create_flavor(
            cpu_policy='dedicated', cpu_threads_policy='prefer')

        # TODO(sfinucan) - this relies on the fact that the CPU quota
        # is 20 which isn't truly representative. Find out how to
        # change the quotas programatically.
        for _ in xrange(0, 5):
            self._create_server(flavor)

        self.assertRaises(lib_exc.Forbidden, self._create_server, flavor)
