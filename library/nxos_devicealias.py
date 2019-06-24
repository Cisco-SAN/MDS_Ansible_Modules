#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.nxos.nxos import load_config, nxos_argument_spec, run_commands
import string

__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = '''
module: nxos_devicealias
extends_documentation_fragment: nxos
version_added: "??"
short_description: Configuration of device alias.
description:
    - Configuration of device alias for Cisco MDS NXOS.
author:
    - Suhas Bharadwaj (@srbharadwaj) (subharad@cisco.com)
options:
    distribute:
        description:
            - Enable/Disable device-alias distribution
        type: bool
        default: False
    mode:
        description:
            - Mode of devices-alias, basic or enhanced
        choices: ['basic', 'enhanced']
        default: 'basic'
    da:
        description:
            - List of device-alias to be added or removed
        suboptions:
            name:
                description:
                    - Name of the device-alias to be added or removed
                required:
                    True
            pwwn:
                description:
                    - pwwn to which the name needs to be associated with
            remove:
                description:
                    - Removes the device-alias if set to True
                type: bool
                default: False



'''

EXAMPLES = '''
- name: Test that device alias module works
      nxos_devicealias:
          distribute: yes
          mode: enhanced
          da:
              - { name: 'test1_add', pwwn: '56:2:22:11:22:88:11:67'}
              - { name: 'test2_add', pwwn: '65:22:22:11:22:22:11:d'}
              - { name: 'dev1', remove: True}
              - { name: 'dev2', remove: True} 
          provider: "{{ creds }}"
      register: result
    - debug: var=result
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



def isPwwnValid(pwwn):
    pwwnsplit = pwwn.split(":")
    if len(pwwnsplit) != 8:
        return False
    for eachpwwnsplit in pwwnsplit:
        if len(eachpwwnsplit) > 2 or len(eachpwwnsplit) < 1:
            return False
        if not all(c in string.hexdigits for c in eachpwwnsplit):
            return False
    return True


def isNameValid(name):
    if not name[0].isalpha():
        # Illegal first character. Name must start with a letter
        return False
    if len(name) > 64:
        return False
    return True


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
    element_spec = dict(
        name=dict(required=True, type='str'),
        pwwn=dict(type='str'),
        remove=dict(type='bool', default=False)
    )

    argument_spec = dict(
        distribute=dict(type='bool', default=False),
        mode=dict(type='str', choices=['enhanced', 'basic'], default='basic'),
        da=dict(type='list', elements='dict', options=element_spec)
    )

    argument_spec.update(nxos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    warnings = list()
    messages = list()
    commands_executed = list()
    result = {'changed': False}

    distribute = module.params['distribute']
    mode = module.params['mode']
    da = module.params['da']
    # module.fail_json(msg='Dis ' + str(distribute) + ' Mode ' + str(mode))

    ###########################################
    # Step 0.0: Validate syntax of name and pwwn
    ###########################################
    if da is not None:
        for eachdict in da:
            name = eachdict['name']
            pwwn = eachdict['pwwn']
            remove = eachdict['remove']
            if not remove:
                if pwwn is None:
                    module.fail_json(msg='This device alias name ' + str(name) + ' which needs to be added, doenst have pwwn specified . Please specify a valid pwwn')
                if not isNameValid(name):
                    module.fail_json(msg='This pwwn name is invalid : ' + str(name) + '. Note that name cannot be more than 64 chars and it should start with a letter')
                if not isPwwnValid(pwwn):
                    module.fail_json(msg='This pwwn is invalid : ' + str(pwwn) + '. Please check that its a valid pwwn')

    ###########################################
    # Step 0.1: Check DA status
    ###########################################
    shDAStausObj = showDeviceAliasStatus(module)
    d = shDAStausObj.getDistribute()
    m = shDAStausObj.getMode()
    if shDAStausObj.isLocked():
        module.fail_json(msg='device-alias has acquired lock on the switch. Hence cannot procced.')

    ###########################################
    # Step 1: Process distribute
    ###########################################
    commands = []
    if distribute is not None:
        if distribute:
            # playbook has distribute as True(enabled)
            if d == "disabled":
                # but switch distribute is disabled(false), so set it to true(enabled)
                commands.append("device-alias distribute")
                messages.append('device-alias distribute changed from disabled to enabled')
            else:
                messages.append('device-alias distribute remains unchanged. current distribution mode is enabled')
        else:
            # playbook has distribute as False(disabled)
            if d == "enabled":
                # but switch distribute is enabled(true), so set it to false(disabled)
                commands.append("no device-alias distribute")
                messages.append('device-alias distribute changed from enabled to disabled')
            else:
                messages.append('device-alias distribute remains unchanged. current distribution mode is disabled')
    if commands:
        commands.append("device-alias commit")

    cmds = flatten_list(commands)

    if cmds:
        if module.check_mode:
            # Check mode implemented at the da_add/da_remove stage
            pass
        else:
            result['changed'] = True
            commands_executed = commands_executed + cmds
            load_config(module, cmds)

    ###########################################
    # Step 2: Process mode
    ###########################################
    commands = []
    if mode is not None:
        if mode == 'basic':
            # playbook has mode as basic
            if m == 'enhanced':
                # but switch mode is enhanced, so set it to basic
                commands.append("no device-alias mode enhanced")
                messages.append('device-alias mode changed from enhanced to basic')
            else:
                messages.append('device-alias mode remains unchanged. current mode is basic')

        else:
            # playbook has mode as enhanced
            if m == 'basic':
                # but switch mode is basic, so set it to enhanced
                commands.append("device-alias mode enhanced")
                messages.append('device-alias mode changed from basic to enhanced')
            else:
                messages.append('device-alias mode remains unchanged. current mode is enhanced')

    if commands:
        commands.append("device-alias commit")

    cmds = flatten_list(commands)

    if cmds:
        if module.check_mode:
            # Check mode implemented at the end
            pass
        else:
            result['changed'] = True
            commands_executed = commands_executed + cmds
            load_config(module, cmds)

    ###########################################
    # Step 3: Process da
    ###########################################
    commands = []
    shDADatabaseObj = showDeviceAliasDatabase(module)
    if da is not None:
        da_remove_list = []
        da_add_list = []
        commands.append("device-alias database")
        for eachdict in da:
            name = eachdict['name']
            pwwn = eachdict['pwwn']
            remove = eachdict['remove']
            if remove:
                if shDADatabaseObj.isNameInDaDatabase(name):
                    commands.append("no device-alias name " + name)
                    da_remove_list.append(name)
                else:
                    module.fail_json(msg='This device alias name is not in switch device-alias database. hence cant be removed : ' + name)
            else:
                if shDADatabaseObj.isNameInDaDatabase(name):
                    module.fail_json(msg='This device alias name is present in switch device-alias database. hence cant be added : ' + name)
                if shDADatabaseObj.isPwwnInDaDatabase(pwwn):
                    module.fail_json(msg='This device alias pwwn is present in switch device-alias database. hence cant be added : ' + pwwn)
                commands.append("device-alias name " + name + " pwwn " + pwwn)
                da_add_list.append(name)

        commands.append("device-alias commit")
        cmds = flatten_list(commands)
        if cmds:
            if module.check_mode:
                module.exit_json(changed=False, commands=cmds, msg="Check Mode: No cmds issued to the hosts")
            else:
                result['changed'] = True
                commands_executed = commands_executed + cmds
                load_config(module, cmds)
                if da_remove_list:
                    messages.append('the required device-alias were removed. ' + ','.join(da_remove_list))
                if da_add_list:
                    messages.append('the required device-alias were added. ' + ','.join(da_add_list))

    result['messages'] = messages
    result['cmds'] = commands_executed
    result['warnings'] = warnings
    module.exit_json(**result)


if __name__ == '__main__':
    main()
