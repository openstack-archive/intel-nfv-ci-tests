# Copyright (C) 2018, Red Hat, Inc.
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


from oslo_log import log as logging
from tempest import config
from tempest.lib.common import ssh

from intel_nfv_ci_tests import exceptions


CONF = config.CONF
LOG = logging.getLogger(__name__)


def _get_hypervisor_ip_for_server_id(hvs_client, servers_admin_client,
                                     server_id):
    hv_hostname = servers_admin_client.show_server(
        server_id)['server']['OS-EXT-SRV-ATTR:hypervisor_hostname']
    for hv in hvs_client.list_hypervisors()['hypervisors']:
        if hv['hypervisor_hostname'] == hv_hostname:
            # Microversion 2.53 replaced id with uuid
            id = hv['id'] if 'id' in hv else hv['uuid']
            return hvs_client.show_hypervisor(id)['hypervisor']['host_ip']
    LOG.info('No hypervisor found with hostname %s', hv_hostname)
    return None


def get_host_libvirt_uri(hvs_client, servers_admin_client, server_id):
    hv_ip = _get_hypervisor_ip_for_server_id(hvs_client, servers_admin_client,
                                             server_id)
    if not hv_ip:
        raise exceptions.HypervisorIPNotFound(server_id=server_id)
    return 'qemu+ssh://%s@%s/system' % (CONF.intel_nfv_ci.qemu_ssh_user, hv_ip)


def get_host_ssh_client(hvs_client, servers_admin_client, server_id):
    hv_ip = _get_hypervisor_ip_for_server_id(hvs_client, servers_admin_client,
                                             server_id)
    if not hv_ip:
        raise exceptions.HypervisorIPNotFound(server_id=server_id)
    return ssh.Client(
        hv_ip, CONF.intel_nfv_ci.qemu_ssh_user,
        key_filename=CONF.intel_nfv_ci.qemu_ssh_private_key_path)
