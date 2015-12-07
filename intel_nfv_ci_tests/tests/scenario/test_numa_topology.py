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


import multiprocessing
from oslo_concurrency import processutils
from oslo_log import log as logging

from tempest import config
from tempest.scenario import manager
from tempest.scenario import utils as test_utils
from tempest import test
from tempest_lib.common.utils import data_utils

CONF = config.CONF

LOG = logging.getLogger(__name__)

load_tests = test_utils.load_tests_input_scenario_utils


class TestServerNumaBase(manager.NetworkScenarioTest):
    credentials = ['admin']

    @classmethod
    def setup_clients(cls):
        cls.manager = cls.admin_manager
        super(manager.NetworkScenarioTest, cls).setup_clients()
        # Use admin client by default

    def setUp(self):
        super(TestServerNumaBase, self).setUp()
        # Setup image and flavor the test instance
        # Support both configured and injected values
        if not hasattr(self, 'image_ref'):
            self.image_ref = CONF.compute.image_ref
        if not hasattr(self, 'flavor_ref'):
            self.flavor_ref = CONF.compute.flavor_ref
        self.image_utils = test_utils.ImageUtils(self.manager)
        if not self.image_utils.is_flavor_enough(self.flavor_ref,
                                                 self.image_ref):
            raise self.skipException(
                '{image} does not fit in {flavor}'.format(
                    image=self.image_ref, flavor=self.flavor_ref
                )
            )
        self.run_ssh = True
        self.keypair = self.create_keypair()
        self.ssh_user = self.image_utils.ssh_user(self.image_ref)
        LOG.debug('Starting test for i:{image}, f:{flavor}. '
                  'Run ssh: {ssh}, user: {ssh_user}'.format(
                        image=self.image_ref, flavor=self.flavor_ref,
                        ssh=self.run_ssh, ssh_user=self.ssh_user))

    def create_flavor_with_numa(self,
                                numa_nodes=2,
                                ram=2048,
                                vcpus=4,
                                disk=0,
                                specs=dict()):
        flavor_with_numa = data_utils.rand_name('numa_flavor')
        flavor_with_numa_id = data_utils.rand_int_id(start=1000)
        extra_specs = specs
        extra_specs["hw:numa_nodes"] = str(numa_nodes)

        # Create a flavor with extra specs
        resp = (self.flavors_client.create_flavor(name=flavor_with_numa,
                                                  ram=ram, vcpus=vcpus,
                                                  disk=disk,
                                                  id=flavor_with_numa_id))
        self.flavors_client.set_flavor_extra_spec(flavor_with_numa_id,
                                                  **extra_specs)
        self.addCleanup(self.flavor_clean_up, flavor_with_numa_id)
        self.assertEqual(200, resp.response.status)

        return flavor_with_numa_id

    def flavor_clean_up(self, flavor_id):
        resp = self.flavors_client.delete_flavor(flavor_id)
        self.assertEqual(resp.response.status, 202)
        self.flavors_client.wait_for_resource_deletion(flavor_id)

    def boot_instance(self, flavor=None):
        # Create server with image and flavor from input scenario
        security_groups = [{'name': self.security_group['name']}]
        create_kwargs = {
            'key_name': self.keypair['name'],
            'security_groups': security_groups
        }
        if flavor is None:
            flavor = self.create_flavor_with_numa()
        self.instance = self.create_server(
            image_id=self.image_ref,
            flavor=flavor,
            **create_kwargs)

    def verify_ssh(self):
        # Obtain a floating IP
        floating_ip = self.compute_floating_ips_client.create_floating_ip()[
            'floating_ip']
        self.addCleanup(self.delete_wrapper,
                        self.compute_floating_ips_client.delete_floating_ip,
                        floating_ip['id'])
        # Attach a floating IP
        self.compute_floating_ips_client.associate_floating_ip_to_server(
            floating_ip['ip'], self.instance['id'])
        # Check ssh
        return self.get_remote_client(
            server_or_ip=floating_ip['ip'],
            username='cirros',
            private_key=self.keypair['private_key'])

    def get_placement(self, vcpu):
        out, _ = processutils.execute('pgrep --full %s' % self.instance['id'],
                                      shell=True)
        if not out:
            return
        cgroup, _ = processutils.execute('grep name  /proc/%s/cgroup'
                                         % out.strip(), shell=True)
        cgroup = cgroup.split(":")[-1].strip()
        placement = []
        for i in range(vcpu):
            cpus, _ = processutils.execute('cgget -n -v -r cpuset.cpus %s'
                                           % (cgroup.replace('\\', '\\\\') +
                                              '/vcpu' + str(i)), shell=True)
            placement.append(cpus.strip())
        return placement

    def get_numa_nodes(self):
        cpu_per_soc = self._get_cores()
        ret = [str(x * cpu_per_soc) + '-' + str(x * cpu_per_soc + cpu_per_soc -
                                                1) + ',' + str(
            x * cpu_per_soc + 2 * cpu_per_soc) + '-' +
               str(x * cpu_per_soc + 3 * cpu_per_soc - 1) for x in range(2)]
        return ret

    def _get_cores(self):
        # get number of real CPUs per socket, assuming a dual-socket,
        # HT-enabled board (2 * 2)
        cores = multiprocessing.cpu_count() / (2 * 2)
        return cores


class TestServerNumaTopo(TestServerNumaBase):
    """
    This smoke test case follows this basic set of operations:

     * Create a keypair for use in launching an instance
     * Create a security group to control network access in instance
     * Add simple permissive rules to the security group
     * Launch an instance with numa topology defined
     * Perform ssh to instance
     * Get numa topology from VM, check correctness
     * Get numa placement info for VM from HOST
     * Check if placement is correct
     * Terminate the instance
    """

    def get_numa_topology(self, rmt):
        topo = {'nodes': []}
        nodes = int(rmt.exec_command("ls /sys/devices/system/node"
                                     " | grep node | wc -l"))
        for i in range(nodes):
            node = {}
            node['cpu'] = rmt.exec_command("cat /sys/devices/system/node/"
                                           "node%s/cpulist" % i)
            node['mem'] = rmt.exec_command("cat /sys/devices/system/node/"
                                           "node%s/meminfo" % i)
            topo["nodes"].append(node)
        return topo

    @test.services('compute', 'network')
    def test_server_numa(self):
        self.security_group = self._create_security_group(
            tenant_id=self.tenant_id)
        self.boot_instance()
        rmt_client = self.verify_ssh()
        topo = self.get_numa_topology(rmt_client)
        self.assertEqual(2, len(topo['nodes']))
        self.assertNotEqual(None, rmt_client)
        placement = self.get_placement(4)
        self.assertEqual(placement[0], placement[1])
        self.assertNotEqual(placement[1], placement[2])
        self.assertEqual(placement[2], placement[3])
        self.servers_client.delete_server(self.instance['id'])


class TestServerNumaPCI(TestServerNumaBase):
    """
    Tests in this class check if pci device
    assigned to the VM is affinitized to the same
    numa node as the VM itself.
    """

    def get_pci_numa_node(self, addr):
        out, _ = processutils.execute('cat /sys/bus/pci/devices/%s/numa_node'
                                      % addr, shell=True)
        return out.strip()

    @test.services('compute', 'network')
    def test_server_numa_pci(self):
        self.security_group = self._create_security_group(
            tenant_id=self.tenant_id)
        self.boot_instance(self.create_flavor_with_numa(1, 1024, 2, 0,
                                                    {"pci_passthrough:alias":
                                                    "niantic_vf:1"}))

        placement = self.get_placement(1)
        host_nodes = self.get_numa_nodes()
        guest_numa = [host_nodes.index(x) for x in placement]
        pci_node = 1
        self.assertIn(int(pci_node), guest_numa)

        self.servers_client.delete_server(self.instance['id'])
