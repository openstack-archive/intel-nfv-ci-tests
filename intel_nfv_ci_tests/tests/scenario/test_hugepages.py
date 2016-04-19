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

import subprocess

from tempest import clients
from tempest.common import credentials_factory as common_creds
from tempest.common import waiters
from tempest.lib.common.utils import data_utils
from tempest.scenario import manager


# Using 2M hugepages
HUGEPAGE_SIZE = 2048


def command(args, args2=None):
    '''
    Command: returns the output of the given command(s)
    Input: up to 2 commands
    Output: String representing the output of these commands

    Note: Using shell=False means that the following are unsupported:
        - Using pipes: Separate your commands
              i.e. "cat /dev/null | grep anything" ->
                       ["cat", "/dev/null"], ["grep", "anything"]
        - Using wildcards: use glob to expand wildcards in dir listings
            i.e. ["cat", "/proc/*info"]  ->
                    ["cat"]+glob.glob("/proc/*info")
        - String in commands: split manually
              e.g. awk {'print $2'} -> str.split()[1]
    '''
    if args2:
        process1 = subprocess.Popen(args, stdout=subprocess.PIPE,
                                    shell=False)

        process2 = subprocess.Popen(args2, stdin=process1.stdout,
                                    stdout=subprocess.PIPE, shell=False)
        # Allow process_curl to receive a SIGPIPE if process_wc exits.
        process1.stdout.close()
        return process2.communicate()[0]

    else:
        return subprocess.Popen(args,
                                stdout=subprocess.PIPE,
                                shell=False).communicate()[0]


def _get_number_free_hugepages(pagesize=HUGEPAGE_SIZE):
    # original command:
    #    "cat /sys/kernel/mm/hugepages/hugepages-${size}kB/"
    return command(["cat",
                    "/sys/kernel/mm/hugepages/hugepages-{}kB/free_hugepages"
                    .format(pagesize)])


class TestHugepages(manager.ScenarioTest):
    run_ssh = True
    disk_config = 'AUTO'

    @classmethod
    def setup_credentials(cls):
        super(TestHugepages, cls).setup_credentials()
        cls.manager = clients.Manager(
            credentials=common_creds.get_configured_credentials(
                'identity_admin', fill_in=False))

    def setUp(self):
        super(TestHugepages, self).setUp()
        self.meta = {'hello': 'world'}
        self.accessIPv4 = '1.1.1.1'
        self.name = data_utils.rand_name('server')
        self.client = self.servers_client
        cli_resp = self.create_server(
            name=self.name,
            flavor=self.create_flavor_with_extra_specs(),
            )
        self.server_initial = cli_resp
        waiters.wait_for_server_status(self.client, self.server_initial['id'],
                                       'ACTIVE')
        self.server = self.client.show_server(self.server_initial['id'])

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

    def test_hugepage_backed_instance(self):
        # Check system hugepages
        hugepages_init = int(_get_number_free_hugepages())
        # Calc expected hugepages
        # flavor memory/hugepage_size, rounded up
        # create instance with hugepages flavor

        flavor_id = self.create_flavor_with_extra_specs("hugepages_flavor")

        self.create_server(flavor=flavor_id, wait_until='ACTIVE')

        required_hugepages = 64 / (HUGEPAGE_SIZE / 1024.)  # ram/hugepages_size
        expected_hugepages = int(hugepages_init - required_hugepages)
        actual_hugepages = int(_get_number_free_hugepages(HUGEPAGE_SIZE))

        self.assertEqual(required_hugepages, 32)
        self.assertEqual(expected_hugepages, actual_hugepages)
