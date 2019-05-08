

#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.nxos.nxos import load_config, nxos_argument_spec, run_commands
from ansible.module_utils import common_utils
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = '''
module: nxos_vsan
extends_documentation_fragment: nxos
version_added: "??"
short_description: Configuration of vsan.
description:
    - Configuration of vsan for Cisco MDS NXOS.
author:
    - Suhas Bharadwaj (@srbharadwaj) (subharad@cisco.com)
options:
    vsan:
        description:
            - List of vsan details to be added or removed
        suboptions:
            id:
                description:
                    - vsan id
                required:
                    True
            name:
                description:
                    - Name of the vsan
            suspend:
                description:
                    - suspend the vsan if True
                type: bool
                default: False
            remove:
                description:
                    - Removes the vsan if True
                type: bool
                default: False
            interface:
                description:
                    - List of vsan's interfaces to be added
                type: str


'''

EXAMPLES = '''
- name: Test that vsan module works
      nxos_vsan:
        provider: "{{ creds }}"
        vsan:
           - id: 922
             name: vsan-SAN-A
             suspend: False
             interface:
                - fc1/1
                - fc1/2
                - port-channel 1
             remove: False
           - id: 923
             name: vsan-SAN-B
             suspend: True
             interface:
                - fc1/11
                - fc1/21
                - port-channel 2
             remove: False
           - id: 1923
             name: vsan-SAN-Old
             remove: True
      register: result
'''


class showDeviceAliasStatus(object):
    """docstring for showDeviceAliasStatus"""

    def __init__(self, module):
        self.module = module
        self.distribute = ""
        self.mode = ""
        self.locked = False
        self.update()

    def update(self):
        command = 'show device-alias status'
        output = execute_show_command(command, self.module)[0].split("\n")
        for o in output:
            if "Fabric Distribution" in o:
                self.distribute = o.split(":")[1].strip().lower()
            if "Mode" in o:
                self.mode = o.split("Mode:")[1].strip().lower()
            if "Locked" in o:
                self.locked = True

    def isLocked(self):
        return self.locked

    def getDistribute(self):
        return self.distribute

    def getMode(self):
        return self.mode


class showDeviceAliasDatabase(object):
    """docstring for showDeviceAliasDatabase"""

    def __init__(self, module):
        self.module = module
        self.update()

    def update(self):
        command = 'show device-alias database'
        output = execute_show_command(command, self.module)
        self.da_list = output[0].split("\n")
        # self.module.fail_json(msg=self.da_list)

    def isNameInDaDatabase(self, name):
        newname = " " + name + " "
        return newname in str(self.da_list)

    def isPwwnInDaDatabase(self, pwwn):
        newpwwn = ':'.join(["0" + str(ep) if len(ep) == 1 else ep for ep in pwwn.split(":")])
        return newpwwn in str(self.da_list)


def execute_show_command(command, module, command_type='cli_show'):
    output = 'text'
    commands = [{
        'command': command,
        'output': output,
    }]
    return run_commands(module, commands)


def flatten_list(command_lists):
    flat_command_list = []
    for command in command_lists:
        if isinstance(command, list):
            flat_command_list.extend(command)
        else:
            flat_command_list.append(command)
    return flat_command_list


def main():
    vsan_element_spec = dict(
        id=dict(required=True, type='str'),
        name=dict(type='str'),
        remove=dict(type='bool', default=False),
        suspend=dict(type='bool', default=False),
        interface=dict(type='list', elements='str')
    )

    argument_spec = dict(
        vsan=dict(type='list', elements='dict', options=vsan_element_spec)
    )

    argument_spec.update(nxos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    warnings = list()
    messages = list()
    commands_executed = list()
    result = {'changed': False}

    commands = []
    vsan_list = module.params['vsan']

    commands.append("terminal dont-ask")

    for eachvsan in vsan_list:
        commands.append("vsan database")
        vsanid = eachvsan['id']
        vsanname = eachvsan['name']
        vsanremove = eachvsan['remove']
        vsansuspend = eachvsan['suspend']
        vsaninterface_list = eachvsan['interface']

        if vsanremove:
            commands.append("no vsan " + str(vsanid))
            messages.append("deleting the vsan " + str(vsanid))
            continue
        else:
            commands.append("vsan " + str(vsanid))
            messages.append("creating vsan " + str(vsanid))

        if vsanname is not None:
            commands.append("vsan " + str(vsanid) + " name " + vsanname)
            messages.append("setting vsan name to " + vsanname + " for vsan " + str(vsanid))

        if vsansuspend:
            commands.append("vsan " + str(vsanid) + " suspend")
            messages.append("suspending the vsan " + str(vsanid))
        else:
            commands.append("no vsan " + str(vsanid) + " suspend")
            messages.append("no suspending the vsan " + str(vsanid))

        if vsaninterface_list is not None:
            commands.append("vsan database")
            for each_interface_name in vsaninterface_list:
                commands.append("vsan " + str(vsanid) + " interface " + each_interface_name)
                messages.append("adding interface " + each_interface_name + " to vsan " + str(vsanid))

    commands.append("no terminal dont-ask")

    cmds = flatten_list(commands)
    commands_executed = cmds

    if commands_executed:
        if module.check_mode:
            module.exit_json(changed=False, commands=commands_executed, msg="Check Mode: No cmds issued to the hosts")
        else:
            result['changed'] = True
            load_config(module, commands_executed)

    result['messages'] = messages
    result['cmds'] = commands_executed
    result['warnings'] = warnings
    module.exit_json(**result)


if __name__ == '__main__':
    main()
