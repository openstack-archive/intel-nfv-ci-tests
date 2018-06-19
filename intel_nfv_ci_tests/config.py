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


from oslo_config import cfg

group = cfg.OptGroup(
    name='intel_nfv_ci',
    title='Intel NFV CI plugin config options')

opts = [
    cfg.StrOpt(
        'qemu_ssh_user',
        help='Username to use when connecting to libvirt on every host in '
             'the deployment. The URL will look like '
             'qemu+ssh://<qemu_ssh_user>@<host IP address>/system'),
    cfg.StrOpt(
        'qemu_ssh_private_key_path',
        help='Path to the SSH private key to use when connecting to libvirt. '
             'Every host in the deployment needs to allow qemu_ssh_user to '
             'connect with this private key.'),
]
