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

import socket

from oslo_concurrency import processutils
from tempest import clients
from tempest.common import credentials_factory as common_creds
from tempest.common import waiters
from tempest.lib.common import ssh
from tempest.lib.common.utils import data_utils
from tempest.scenario import manager


# Using 2M hugepages
HUGEPAGE_SIZE = 2048


class TestHugepages(manager.ScenarioTest):
    run_ssh = True
    disk_config = 'AUTO'
    credentials = ['primary', 'admin']

    @classmethod
    def setup_credentials(cls):
        super(TestHugepages, cls).setup_credentials()
        cls.manager = clients.Manager(
            credentials=common_creds.get_configured_admin_credentials(
                fill_in=False))

    @classmethod
    def setup_clients(cls):
        super(TestHugepages, cls).setup_clients()
        cls.admin_servers_client = cls.os_admin.servers_client

    def setUp(self):
        super(TestHugepages, self).setUp()
        self.meta = {'hello': 'world'}
        self.accessIPv4 = '1.1.1.1'
        self.name = data_utils.rand_name('server')
        self.client = self.servers_client
        self.flavors_client = self.os_admin.flavors_client
        cli_resp = self.create_server(
            name=self.name,
            flavor=self.create_flavor_with_extra_specs(),
            )
        self.server_initial = cli_resp
        waiters.wait_for_server_status(self.client, self.server_initial['id'],
                                       'ACTIVE')
        self.server = self.admin_servers_client.show_server(
            self.server_initial['id'])

    def create_flavor_with_extra_specs(self, name='hugepages_flavor', count=1):
        flavor_with_hugepages_name = data_utils.rand_name(name)
        flavor_with_hugepages_id = data_utils.rand_int_id(start=1000)
        ram = 64
        vcpus = 1
        disk = 0

        # set numa pagesize
        extra_specs = {"hw:mem_page_size": str(HUGEPAGE_SIZE)}
        # Create a flavor with extra specs
        resp = (self.flavors_client.
                create_flavor(name=flavor_with_hugepages_name,
                              ram=ram, vcpus=vcpus, disk=disk,
                              id=flavor_with_hugepages_id))
        self.flavors_client.set_flavor_extra_spec(flavor_with_hugepages_id,
                                                  **extra_specs)
        self.addCleanup(self.flavor_clean_up, flavor_with_hugepages_id)
        self.assertEqual(200, resp.response.status)

        return flavor_with_hugepages_id

    def flavor_clean_up(self, flavor_id):
        resp = self.flavors_client.delete_flavor(flavor_id)
        self.assertEqual(resp.response.status, 202)
        self.flavors_client.wait_for_resource_deletion(flavor_id)

    def _get_number_free_hugepages(self, pagesize=HUGEPAGE_SIZE):
        cmd = ('cat /sys/kernel/mm/hugepages/'
               'hugepages-%dkB/free_hugepages' % pagesize)
        hostname = self.server['server']['OS-EXT-SRV-ATTR:host']
        if hostname == socket.gethostname():
            return processutils.execute(cmd)
        else:
            ssh_client = ssh.Client(hostname, 'root', look_for_keys=True)
            return ssh_client.exec_command(cmd)

    def test_hugepage_backed_instance(self):
        # Check system hugepages
        hugepages_init = int(self._get_number_free_hugepages())
        # Calc expected hugepages
        # flavor memory/hugepage_size, rounded up
        # create instance with hugepages flavor

        flavor_id = self.create_flavor_with_extra_specs("hugepages_flavor")

        self.create_server(flavor=flavor_id, wait_until='ACTIVE')

        required_hugepages = 64 / (HUGEPAGE_SIZE / 1024.)  # ram/hugepages_size
        expected_hugepages = int(hugepages_init - required_hugepages)
        actual_hugepages = int(self._get_number_free_hugepages())

        self.assertEqual(required_hugepages, 32)
        self.assertEqual(expected_hugepages, actual_hugepages)
