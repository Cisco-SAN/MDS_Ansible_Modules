#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.nxos.nxos import load_config, nxos_argument_spec, run_commands


__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = '''
module: nxos_zone_zoneset
extends_documentation_fragment: nxos
version_added: ??
short_description: Configuration of zone/zoneset.
description:
    - Configuration of zone/zoneset for Cisco MDS NXOS.
author:
    - Suhas Bharadwaj (@srbharadwaj) (subharad@cisco.com)
options:
    zone_zoneset_details:
        description:
            - List of zone/zoneset details to be added or removed
        suboptions:
            vsan:
                description:
                    - vsan id
                required:
                    True
            mode:
                description:
                    - mode of the zone for the vsan
                choices: ['enhanced', 'basic']
                default: 'basic'
            default_zone:
                description:
                    - default zone behaviour for the vsan
                choices: ['permit', 'deny']
                default: 'deny'
            smart_zoning:
                description:
                    - Removes the vsan if True
                type: bool
                default: False
            zone:
                description:
                    - List of zone options for that vsan
                suboptions:
                    name:
                        description:
                            - name of the zone
                        required:
                            True
                    remove:
                        description:
                            - Deletes the zone if True
                        type: bool
                        default: False
                    members:
                        description:
                            - Members of the zone that needs to be removed or added
                        suboptions:
                            pwwn:
                                description:
                                    - pwwn member of the zone, use alias 'device-alias' as option for device-alias member
                                aliases=['device-alias']
                                required=True
                            remove:
                                description:
                                    - Removes member from the zone if True
                                type: bool
                                    default: False
                            devtype:
                                description:
                                    - devtype of the zone member used along with Smart zoning config
                                choices: ['initiator', 'target', 'both']


            zoneset:
                description:
                    - List of zoneset options for the vsan
                suboptions:
                    name:
                        description:
                            - name of the zoneset
                        required:
                            True
                    remove:
                        description:
                            - Removes zoneset if True
                        type: bool
                        default: False
                    action:
                        description:
                            - activates/de-activates the zoneset
                        choices: ['activate', 'deactivate']
                        default: 'deactivate'
                    members:
                        description:
                            - Members of the zoneset that needs to be removed or added
                        suboptions:
                            name:
                                description:
                                    - name of the zone that needs to be added to the zoneset or removed from the zoneset
                                required=True
                            remove:
                                description:
                                    - Removes zone member from the zoneset
                                type: bool
                                    default: False

---
'''

EXAMPLES = '''
- name: Test that zone/zoneset module works
      nxos_zone_zoneset:
        provider: "{{ creds }}"
        zone_zoneset_details:
           - vsan: 22
             mode: enhanced
             zone:
                - name: zoneA
                  members:
                     - {pwwn: '11:11:11:11:11:11:11:11'}
                     - {device-alias: 'test123'}
                     - {pwwn: '61:61:62:62:12:12:12:12', remove: True}
                - name: zoneB
                  members:
                     - {pwwn: '10:11:11:11:11:11:11:11'}
                     - {pwwn: '62:62:62:62:21:21:21:21'}
                - name: zoneC
                  remove: True
             zoneset:
                 - name: zsetname1
                   members:
                      - {name: zoneA}
                      - {name: zoneB}
                      - {name: zoneC, remove: True}
                   action: activate
                 - name: zsetTestExtra
                   remove: True
                   action: deactivate
           - vsan: 21
             mode: basic
             smart_zoning: True
             zone:
                - name: zone21A
                  members:
                     - {pwwn: '11:11:11:11:11:11:11:11',devtype: 'both'}
                     - {pwwn: '62:62:62:62:12:12:12:12'}
                     - {pwwn: '92:62:62:62:12:12:1a:1a',devtype: 'both', remove: True}
                - name: zone21B
                  members:
                     - {pwwn: '10:11:11:11:11:11:11:11'}
                     - {pwwn: '62:62:62:62:21:21:21:21'}
             zoneset:
                 - name: zsetname21
                   members:
                      - {name: zone21A}
                      - {name: zone21B}
                   action: activate
      register: result
'''


"""
Questions
1) Should we name it as nxos_zone or nxos_zone_zoneset?
2) Should zone_details be renamed as zone_zoneset_details?
"""


class showZoneStatus(object):
    """docstring for showDeviceAliasStatus"""

    def __init__(self, module, vsan):
        self.vsan = vsan
        self.module = module
        self.default_zone = ""
        self.mode = ""
        self.session = ""
        self.sz = ""
        self.locked = False
        self.update()

    def update(self):
        command = 'show zone status vsan ' + str(self.vsan)
        output = execute_show_command(command, self.module)[0].split("\n")

        patfordefzone = "VSAN: " + str(self.vsan) + " default-zone:\s+(\S+).*"
        patformode = ".*mode:\s+(\S+).*"
        patforsession = ".*session:\s+(\S+).*"
        patforsz = ".*smart-zoning:\s+(\S+).*"
        for line in output:
            mdefz = re.match(patfordefzone, line.strip())
            mmode = re.match(patformode, line.strip())
            msession = re.match(patforsession, line.strip())
            msz = re.match(patforsz, line.strip())

            if mdefz:
                self.default_zone = mdefz.group(1)
            if mmode:
                self.mode = mmode.group(1)
            if msession:
                self.session = msession.group(1)
                if self.session != "none":
                    self.locked = True
            if msz:
                self.sz = msz.group(1)

    def isLocked(self):
        return self.locked

    def getDefaultZone(self):
        return self.default_zone

    def getMode(self):
        return self.mode

    def getSmartZoningStatus(self):
        return self.sz


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

    supported_choices = ['pwwn', 'device-alias']
    zone_member_spec = dict(
        pwwn=dict(required=True, type='str', aliases=['device-alias']),
        devtype=dict(type='str', choices=['initiator', 'target', 'both']),
        remove=dict(type='bool', default=False)
    )

    zone_spec = dict(
        name=dict(required=True, type='str'),
        members=dict(type='list', elements='dict', options=zone_member_spec),
        remove=dict(type='bool', default=False)
    )

    zoneset_member_spec = dict(
        name=dict(required=True, type='str'),
        remove=dict(type='bool', default=False)
    )

    zoneset_spec = dict(
        name=dict(type='str', required=True),
        members=dict(type='list', elements='dict', options=zoneset_member_spec),
        remove=dict(type='bool', default=False),
        action=dict(type='str', choices=['activate', 'deactivate'], default='deactivate')
    )

    # zoneset_act_spec = dict(
    #     name=dict(type='str', required=True),
    #     action=dict(type='str', choices=['activate', 'deactivate'], default='deactivate')
    # )

    zonedetails_spec = dict(
        vsan=dict(required=True, type='int'),
        mode=dict(type='str', choices=['enhanced', 'basic'], default='basic'),
        default_zone=dict(type='str', choices=['permit', 'deny'], default='deny'),
        smart_zoning=dict(type='bool', default=False),
        zone=dict(type='list', elements='dict', options=zone_spec),
        zoneset=dict(type='list', elements='dict', options=zoneset_spec),
        # zoneset_activate=dict(type='list', elements='dict', options=zoneset_act_spec)

    )

    argument_spec = dict(
        zone_zoneset_details=dict(type='list', elements='dict', options=zonedetails_spec)
    )

    argument_spec.update(nxos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    warnings = list()
    messages = list()
    commands = list()
    result = {'changed': False}

    commands_executed = []
    listOfZoneDetails = module.params['zone_zoneset_details']
    for eachZoneZonesetDetail in listOfZoneDetails:
        vsan = eachZoneZonesetDetail['vsan']
        op_mode = eachZoneZonesetDetail['mode']
        op_default_zone = eachZoneZonesetDetail['default_zone']
        op_smart_zoning = eachZoneZonesetDetail['smart_zoning']
        op_zone = eachZoneZonesetDetail['zone']
        op_zoneset = eachZoneZonesetDetail['zoneset']
        # messages.append(vsan)
        # messages.append(mode)
        # messages.append(default_zone)
        # messages.append(smart_zoning)
        # messages.append(zone_remove)
        # messages.append(zone_add)
        # messages.append(zoneset_remove)
        # messages.append(zoneset_add)

        # Step1: execute show zone status and get
        shZoneStatusObj = showZoneStatus(module, vsan)
        sw_default_zone = shZoneStatusObj.getDefaultZone()
        sw_mode = shZoneStatusObj.getMode()
        sw_smart_zoning = shZoneStatusObj.getSmartZoningStatus()
        if (sw_default_zone == ""):
            module.fail_json(msg='Could not get default zone status from the switch for vsan ' + str(vsan) + '. Hence cannot procced.')
        else:
            messages.append("default zone status on switch for vsan " + str(vsan) + " is " + sw_default_zone)

        if (sw_mode == ""):
            module.fail_json(msg='Could not get zone mode from the switch for vsan ' + str(vsan) + '. Hence cannot procced.')
        else:
            messages.append("zone mode on switch for vsan " + str(vsan) + " is " + sw_mode)

        if (sw_smart_zoning == ""):
            module.fail_json(msg='Could not get smart-zoning status from the switch for vsan ' + str(vsan) + '. Hence cannot procced.')
        else:
            messages.append("smart-zoning status on switch for vsan " + str(vsan) + " is " + sw_smart_zoning)
            if sw_smart_zoning.lower() == "Enabled".lower():
                sw_smart_zoning_bool = True
            else:
                sw_smart_zoning_bool = False

        if shZoneStatusObj.isLocked():
            module.fail_json(msg='zone has acquired lock on the switch for vsan ' + str(vsan) + '. Hence cannot procced.')

        commands_executed.append("terminal dont-ask")

        # Process zone default zone options
        if op_default_zone != sw_default_zone:
            if op_default_zone == "permit":
                commands_executed.append("zone default-zone permit vsan " + str(vsan))
                messages.append("default zone configuration changed from deny to permit for vsan " + str(vsan))
            else:
                commands_executed.append("no zone default-zone permit vsan " + str(vsan))
                messages.append("default zone configuration changed from permit to deny for vsan " + str(vsan))
        else:
            messages.append("no change in default zone configuration for vsan " + str(vsan))

        # Process zone mode options
        if op_mode != sw_mode:
            if op_mode == "enhanced":
                commands_executed.append("zone mode enhanced vsan " + str(vsan))
                messages.append("zone mode configuration changed from basic to enhanced for vsan " + str(vsan))
            else:
                commands_executed.append("no zone mode enhanced vsan " + str(vsan))
                messages.append("zone mode configuration changed from enhanced to basic for vsan " + str(vsan))
        else:
            messages.append("no change in zone mode configuration for vsan " + str(vsan))

        # Process zone smart-zone options
        if op_smart_zoning != sw_smart_zoning_bool:
            if op_smart_zoning:
                commands_executed.append("zone smart-zoning enable vsan " + str(vsan))
                messages.append("smart-zoning enabled for vsan " + str(vsan))
            else:
                commands_executed.append("no zone smart-zoning enable vsan " + str(vsan))
                messages.append("smart-zoning disabled for vsan " + str(vsan))
        else:
            messages.append("no change in smart-zoning configuration for vsan " + str(vsan))

        # Process zone  options
        if op_zone is not None:
            for eachzone in op_zone:
                zname = eachzone['name']
                zmembers = eachzone['members']
                removeflag = eachzone['remove']
                if removeflag:
                    messages.append("zone '" + zname + "' is removed from vsan " + str(vsan))
                    commands_executed.append("no zone name " + zname + " vsan " + str(vsan))
                else:
                    commands_executed.append("zone name " + zname + " vsan " + str(vsan))
                    for eachmem in zmembers:
                        memtype = list(set(supported_choices).intersection(eachmem.keys()))
                        cmd = "member " + memtype[0] + " " + eachmem[memtype[0]]
                        if op_smart_zoning:
                            if eachmem['devtype'] is not None:
                                cmd = cmd + " " + eachmem['devtype']

                        if eachmem["remove"]:
                            cmd = "no " + cmd
                            messages.append("removing zone member '" + eachmem[memtype[0]] + "' from zone '" + zname + "' in vsan " + str(vsan))
                        else:
                            messages.append("adding zone member '" + eachmem[memtype[0]] + "' to zone '" + zname + "' in vsan " + str(vsan))
                        commands_executed.append(cmd)

        # Process zoneset options
        if op_zoneset is not None:
            for eachzoneset in op_zoneset:
                zsetname = eachzoneset['name']
                zsetmembers = eachzoneset['members']
                removeflag = eachzoneset['remove']
                actionflag = eachzoneset['action']
                if removeflag:
                    messages.append("zoneset '" + zsetname + "' is removed from vsan " + str(vsan))
                    commands_executed.append("no zoneset name " + zsetname + " vsan " + str(vsan))
                else:
                    commands_executed.append("zoneset name " + zsetname + " vsan " + str(vsan))
                    for eachzsmem in zsetmembers:
                        zsetmem_name = eachzsmem['name']
                        zsetmem_removeflag = eachzsmem['remove']
                        cmd = "member " + zsetmem_name
                        if zsetmem_removeflag:
                            cmd = "no " + cmd
                            messages.append("removing zoneset member '" + zsetmem_name + "' from zoneset '" + zsetname + "' in vsan " + str(vsan))
                        else:
                            messages.append("adding zoneset member '" + zsetmem_name + "' to zoneset '" + zsetname + "' in vsan " + str(vsan))
                        commands_executed.append(cmd)

                if actionflag == 'deactivate':
                    messages.append("deactivating zoneset '" + zsetname + "' in vsan " + str(vsan))
                    commands_executed.append("no zoneset activate name " + zsetname + " vsan " + str(vsan))
                else:
                    messages.append("activating zoneset '" + zsetname + "' in vsan " + str(vsan))
                    commands_executed.append("zoneset activate name " + zsetname + " vsan " + str(vsan))

        if op_mode == "enhanced":
            commands_executed.append("zone commit vsan " + str(vsan))

    commands_executed.append("no terminal dont-ask")

    cmds = flatten_list(commands_executed)
    if cmds:
        if module.check_mode:
            module.exit_json(changed=False, commands=cmds, msg="Check Mode: No cmds issued to the hosts")
        else:
            result['changed'] = True
            commands = commands + cmds
            load_config(module, cmds)

    result['messages'] = messages
    result['cmds'] = commands_executed
    result['warnings'] = warnings
    module.exit_json(**result)


if __name__ == '__main__':
    main()
