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

from oslo_concurrency import processutils

from tempest.api.compute import base
from tempest.common.utils.linux import remote_client
from tempest import config
from tempest.lib.common.utils import data_utils

CONF = config.CONF


class NUMARemoteClient(remote_client.RemoteClient):

    def get_numa_topology(self):
        nodes = []

        node_count = self.exec_command(
            'ls /sys/devices/system/node | grep node | wc -l')
        for i in range(int(node_count)):
            node_cmd = 'cat /sys/devices/system/node/node%d/' % i

            node = {}
            node['cpu'] = self.exec_command(node_cmd + 'cpulist')
            node['mem'] = self.exec_command(node_cmd + 'meminfo')
            nodes.append(node)

        return nodes


class NUMAServersTest(base.BaseV2ComputeAdminTest):
    disk_config = 'AUTO'

    @classmethod
    def setup_credentials(cls):
        cls.prepare_instance_network()
        super(NUMAServersTest, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(NUMAServersTest, cls).setup_clients()
        cls.flavors_client = cls.os_adm.flavors_client
        cls.client = cls.servers_client

    @classmethod
    def resource_setup(cls):
        # TODO(stephenfin): Do we need this?
        cls.set_validation_resources()
        super(NUMAServersTest, cls).resource_setup()

    def create_flavor(self):
        flavor_name = data_utils.rand_name('numa_flavor')
        flavor_id = data_utils.rand_int_id(start=1000)

        # TODO(stephenfin): Consider dropping this to 512 or similar
        ram = 2048
        vcpus = 4
        disk = 0
        extra_specs = {
            "hw:numa_nodes": "2",
        }

        # Create a flavor with extra specs
        flavor = self.flavors_client.create_flavor(name=flavor_name, ram=ram,
                                                   vcpus=vcpus, disk=disk,
                                                   id=flavor_id)['flavor']
        self.flavors_client.set_flavor_extra_spec(flavor['id'], **extra_specs)
        self.addCleanup(self.flavor_clean_up, flavor['id'])

        return flavor['id']

    def flavor_clean_up(self, flavor_id):
        self.flavors_client.delete_flavor(flavor_id)
        self.flavors_client.wait_for_resource_deletion(flavor_id)

    def get_placement(self, server, vcpu):
        out, _ = processutils.execute('ps -eo pid,cmd,args | awk \'/%s/ && '
                                      '!/grep/ {print $1}\'' %
                                      server['id'], shell=True)
        if not out:
            return

        cgroup, _ = processutils.execute('grep cpuset /proc/%s/cgroup'
                                         % out.strip(), shell=True)
        cgroup = cgroup.split(":")[-1].strip()
        if cgroup.index('emulator'):
            cgroup = cgroup + '/..'

        placement = []
        for i in range(vcpu):
            cpus, _ = processutils.execute('cgget -n -v -r cpuset.cpus %s'
                                           % (cgroup.replace('\\', '\\\\') +
                                              '/vcpu' + str(i)), shell=True)
            placement.append(cpus.strip())

        return placement

    def test_verify_created_server_numa_topology(self):
        """Smoke test NUMA support.

        Validates NUMA support by launching an instance with a NUMA
        topology defined and validating the correctness of the topology
        on both host and guest.
        """
        flavor_id = self.create_flavor()

        admin_pass = self.image_ssh_password

        server = self.create_test_server(
            validatable=True,
            wait_until='ACTIVE',
            adminPass=admin_pass,
            flavor=flavor_id)

        server = self.client.show_server(server['id'])['server']
        linux_client = NUMARemoteClient(
            self.get_server_ip(server),
            self.ssh_user,
            admin_pass,
            self.validation_resources['keypair']['private_key'],
            server=server,
            servers_client=self.client)

        # Validate guest topology
        # TODO(stephenfin): Validate more of the NUMA topology than this
        numa_nodes = linux_client.get_numa_nodes()
        self.assertEqual(2, len(numa_nodes))

        # Validate host topology
        placement = self.get_placement(server, 4)
        self.assertEqual(placement[0], placement[1])
        self.assertNotEqual(placement[1], placement[2])
        self.assertEqual(placement[2], placement[3])
