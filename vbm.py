#!/usr/bin/env python3

import re, datetime, argparse, ipaddress, json
import xml.etree.ElementTree as ET
from os.path import isfile, join, realpath, dirname
from configparser import RawConfigParser, ExtendedInterpolation
from subprocess import Popen, PIPE, STDOUT
from time import sleep
from os import execv, listdir, remove
from glob import glob
from FileLock import FileLock

class VMS(object):
    def __init__(self):
        self.VM_max_len = 1
        self.vmlist = {}
        self.VMSlist = {}

    def vbox_sync_config(self):
        foodict = {}
        vbdict = {}
        pipe = Popen([vbmanage, "list", "-s", "vms"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        for line in pipe.stdout:
            match = re.search(r'\"(.*)\"\s{(.*)}', line.rstrip())
            if match:
                vbdict.update({match.group(2): match.group(1)})
        foos = glob(join(vbbasedir, "*/*.vbox"))
        for foo in foos:
            f = open(foo)
            for line in f:
                match = re.search(r'Machine uuid="{(\S+)}" name="([A-Za-z0-9 \-]+)"', line)
                if match:
                    foodict.update({match.group(1): foo})
                    f.close
                    break
        for k, v in vbdict.copy().items():
            if v == "<inaccessible>":
                print("Unregistering ", k, v)
                Popen([vbmanage, "unregistervm", k], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                del vbdict[k]
        for k, v in foodict.items():
            if not k in vbdict:
                print("Registering ", k, v)
                pipe = Popen([vbmanage, "registervm", v], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                print(pipe.stdout.read())
    def clone_vm(self, V, D, i, newvm):
        uuid, VMc = self.locate_vm_menu_selection(i)
        pipe = Popen([vbmanage, "clonevm", uuid, "--basefolder=" + vbbasedir, "--name=" + newvm, "--register"],
                     stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        print(pipe.stdout.read())
        V.populate()
        D.populate()
    def is_vm_running(self, i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        VMc.populate()
        if re.search(r'powered off', VMc.conf['State']):
            return(0)
        else:
            print("\n", VMc.name, "is running.\n")
            return(1)
    def boot_vm(self,V,D,i,vrde):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if not uuid:
            print("No such VM:", str(i))
            return 0
        if uc:
            U = Unbound()
            for k, v in VMc.conf.items():
                match = re.search(r'NIC (\d*)', k)
                if match:
                    vm_nic = match.group(1)
                match = re.search(r'MAC:(\S+), .* \'([\S\-]+)\',', v)
                if match:
                    U.unbound_ip(VMc.name, match.group(1), match.group(2), vm_nic, VMc.uuid)
        pfoo = "/tmp/vb-" + VMc.name + "-console"
        if self.is_vm_running(i):
            return pfoo, VMc.name
        else:
            pipe = Popen([vbmanage, "modifyvm", uuid, "--uartmode1", "server", pfoo], stdout=PIPE,
                         stderr=STDOUT, encoding='utf-8')
            print(pipe.stdout.read())
            pipe = Popen([vbmanage, "modifyvm", uuid, "--uart1", "0x3f8", "4"], stdout=PIPE, stderr=STDOUT,
                         encoding='utf-8')
            print(pipe.stdout.read())
            VMc.populate()
            print("booting " + VMc.name)
            if vrde:
                vargs = vrdeargs.split(' ')
            else:
                vargs = vbheadlessargs.split(' ')
            Popen([vbheadless] + vargs + ["-s", uuid], close_fds=True, shell=False)
            if uc:
                U.unbound_control()
            sleep(sleeptime)
        return pfoo, VMc.name
    def poweroff_vm(self, V, D, i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        pipe = Popen([vbmanage, "controlvm", uuid, "poweroff"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        print(pipe.stdout.read())
        VMc.populate()
    def populate(self):
        self.vmlist = {}
        self.VMSlist = {}
        pipe = Popen([vbmanage, "list", "-s", "vms"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        for line in pipe.stdout:
            match = re.search(r'\"(.*)\"\s{(.*)}', line.rstrip())
            if match:
                name = match.group(1)
                uuid = match.group(2)
                l = len(name)
                if l > self.VM_max_len:
                    self.VM_max_len = l
                self.vmlist.update({uuid: name})
                self.VMSlist.update({uuid: VM(name, uuid)})
                self.VMSlist[uuid].populate()
    def delete_vm(self, V, D, i,):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uc:
            U = Unbound()
            for k, v in VMc.conf.items():
                match = re.search(r'NIC (\d*)', k)
                if match:
                    vm_nic = match.group(1)
                match = re.search(r'MAC:(\S+), .* \'([\S\-]+)\',', v)
                if match:
                    U.unbound_rm_ip(VMc.name, match.group(1), match.group(2), vm_nic, VMc.uuid)
            U.unbound_control()
        pipe = Popen([vbmanage, "unregistervm", uuid, "--delete"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        print(pipe.stdout.read())
        sleep(sleeptime)
        del VMc
        del V.VMSlist[uuid]
        V.populate()
        D.populate()
    def remove_controller(self, V, D, i, cname):
        uuid, VMc = self.locate_vm_menu_selection(i)
        for k, v in VMc.conf.items():
            match = re.search(r'' + cname + ' \((\d+), (\d+)\)', k)
            if match:
                p = match.group(1)
                x = match.group(2)
                if cname == 'IDE':
                    print(f"Detach {v} on {cname} ({p}, ({x})")
                    pipe = Popen([vbmanage, 'storageattach', uuid, '--storagectl', cname, '--port', p, '--device', x,
                                  '--medium', 'none'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                else:
                    print(f"detach {v} on {cname} port {p}")
                    pipe = Popen([vbmanage, 'storageattach', uuid, '--storagectl', cname, '--port', p,
                                  '--medium', 'none'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
        print(f"Remove controller {cname}")
        pipe = Popen([vbmanage, 'storagectl', uuid, '--name', cname, '--remove'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        print(pipe.stdout.read())
        V.populate()
        D.populate()
    def eject_iso(self, i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        for k, v in VMc.conf.items():
            if re.search(r'\.iso ', v):
                k = re.sub('[(),]', '', k)
                c, p, x = k.split(' ')
                if c == "IDE":
                    pipe = Popen(
                        [vbmanage, 'storageattach', uuid, '--storagectl', c, '--port', p, '--device', x, '--medium',
                         'emptydrive'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                else:
                    pipe = Popen(
                        [vbmanage, 'storageattach', uuid, '--storagectl', c, '--port', p, '--medium',
                         'emptydrive'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                print(pipe.stdout.read())
                sleep(sleeptime)
                VMc.populate()
    def attach_iso(self, i, iso):
        uuid, VMc = self.locate_vm_menu_selection(i)
        self.eject_iso(i)
        haside = 0
        hassata = 0
        for k, v in VMc.conf.items():
            if v == "IDE":
                haside = 1
            if v == "SATA":
                hassata = 1
            if re.search(r'Empty', v):
                k = re.sub('[(),]', '', k)
                c, p, x = k.split(' ')
                pipe = Popen([vbmanage, 'storageattach', uuid, '--storagectl', c, '--port', p, '--type', 'dvddrive',
                              '--device', x, '--medium', iso], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                print(pipe.stdout.read())
                sleep(sleeptime)
                VMc.populate()
                return
        if haside:
            a = []
            if not 'IDE (0, 0)' in VMc.conf:
                a = ['--port', '0', '--device', '0', '--type', 'dvddrive', '--medium', iso]
            elif not 'IDE (0, 1)' in VMc.conf:
                a = ['--port', '0', '--device', '1', '--type', 'dvddrive', '--medium', iso]
            elif not 'IDE (1, 0)' in VMc.conf:
                a = ['--port', '1', '--device', '0', '--type', 'dvddrive', '--medium', iso]
            elif not 'IDE (1, 1)' in VMc.conf:
                a = ['--port', '1', '--device', '1', '--type', 'dvddrive', '--medium', iso]
            if a:
                pipe = Popen([vbmanage, 'storageattach', uuid, '--storagectl', 'IDE'] + a,
                             stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                print(pipe.stdout.read())
                sleep(sleeptime)
                VMc.populate()
                return
        if hassata:
            a = range(8)
            for n in a:
                k = str(n)
                if not 'SATA (' + k + ', 0)' in VMc.conf:
                    pipe = Popen([vbmanage, 'storageattach', uuid, '--storagectl', 'SATA', '--port', k, '--type',
                                  'dvddrive', '--medium', iso], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                    sleep(sleeptime)
                    VMc.populate()
                    return
    def run_with_args(self, i, f, a):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            pipe = Popen([vbmanage, f, uuid] + a, stdout=PIPE, stderr=STDOUT, encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            VMc.populate()
    def set_vm_memory(self, i, memory):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            memory = memory * 1024
            pipe = Popen([vbmanage, "modifyvm", uuid, "--memory", str(memory)], stdout=PIPE, stderr=STDOUT,
                         encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            VMc.populate()
    def set_vm_cpus(self, i, cpus):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            pipe = Popen([vbmanage, "modifyvm", uuid, "--cpus", str(cpus)], stdout=PIPE, stderr=STDOUT,
                         encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            VMc.populate()
    def set_vm_os(self, i, ostype):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            pipe = Popen([vbmanage, "modifyvm", uuid, "--ostype", ostype], stdout=PIPE, stderr=STDOUT,
                         encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            VMc.populate()
    def vm_disk_menu(self, vmno, diskno, operation, newsize, D):
        uuid, VMc = self.locate_vm_menu_selection(vmno)
        i = 1
        for k, v in VMc.conf.items():
            if re.search(r'\.iso ', v) or v == 'Empty':
                continue
            match = re.search(r'\S+\s\(\d+,\s\d+\)', k)
            if match:
                if operation == 'detach' and diskno == i:
                    k = re.sub('[(),]', '', k)
                    c, p, x = k.split(' ')
                    if c == "IDE":
                        pipe = Popen(
                            [vbmanage, 'storageattach', uuid, '--storagectl', c, '--port', p, '--device', x, '--medium',
                             'none'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    else:
                        pipe = Popen(
                            [vbmanage, 'storageattach', uuid, '--storagectl', c, '--port', p, '--medium',
                             'none', '--device', x], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                    sleep(sleeptime)
                    VMc.populate()
                    D.populate()
                elif operation == 'resize' and diskno == i:
                    match = re.search(r'UUID:(\S+)\)', v)
                    if match:
                        pipe = Popen([vbmanage, 'modifymedium', 'disk', match.group(1), '--resize', str(newsize)],
                                     stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                        print(pipe.stdout.read())
                        sleep(sleeptime)
                        D.populate()
                elif operation == 'list':
                    match = re.search(r'UUID:(\S+)\)', v)
                    if match:
                        cursize = D.show_disk_size(match.group(1))
                        print(i,"  ", k, v, cursize)
                i += 1
    def show_vm_menu(self):
        i = 1
        for uuid, VMc in self.VMSlist.items():
            if not "State" in VMc.conf:
                print("\nERROR: Syncing VirtualBox with on disk configuration\n")
                self.vbox_sync_config()
                exit(1)
            mystr = VMc.conf["State"]
            print('{0:2d}'.format(i), '{:<{l}}'.format(self.vmlist[uuid], l=self.VM_max_len), mystr, VMc.conf['Guest OS'])
            i += 1
    def locate_vm_menu_selection(self, i):
        j = 1
        maxk = len(self.VMSlist)
        for uuid, VMc in self.VMSlist.items():
            if j == i:
                return uuid, VMc
            j += 1
            if j > maxk:
                return 0, 0
    def show_vm_menu_selection(self, i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            VMc.display()
    def vm_attach_disk(self, i, controller, disk_uuid, D):
        maxports = {"SCSI":15, "SATA":30, "SAS":255}
        uuid, VMc = self.locate_vm_menu_selection(i)
        needscontroller = 1
        for k, v in VMc.conf.items():
            if v == controller:
                needscontroller = 0
                break
        if needscontroller:
            print("Adding " + controller + " to " + VMc.name)
            self.run_with_args(i, 'storagectl', ['--add', controller.lower(), '--name', controller])
        if controller == "IDE":
            port = 0
            while port < 2:
                device = 0
                while device < 2:
                    if not controller + " (" + str(port) + ", " + str(device) + ")" in VMc.conf:
                        print("Attaching disk to " + VMc.name, controller + " (" + str(port) + ", " + str(device) + ")")
                        pipe = Popen(
                            [vbmanage, 'storageattach', uuid, '--storagectl', 'IDE', '--port', str(port), '--device',
                             str(device), '--type', 'hdd', '--medium', disk_uuid], stdout=PIPE, stderr=STDOUT,
                            encoding='utf-8')
                        print(pipe.stdout.read())
                        sleep(sleeptime)
                        VMc.populate()
                        D.populate()
                        return
                    else:
                        device += 1
                port += 1
        else:
            maxp = maxports[controller]
            port = 0
            while port < maxp:
                if not controller + " (" + str(port) + ", 0)" in VMc.conf:
                    print("Attaching disk to " + VMc.name, controller + " (" + str(port) + ", 0)")
                    pipe = Popen(
                        [vbmanage, 'storageattach', uuid, '--storagectl', controller, '--port', str(port), '--type',
                         'hdd', '--medium', disk_uuid], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                    sleep(sleeptime)
                    VMc.populate()
                    D.populate()
                    return
                port += 1
        print("Unable to attach", disk_uuid, "to", controller)
        exit(1)
    def create_and_attach_disks(self, D, vms, howmany, whatsize, controller):
        if len(vms) > 1:
            shared = 1
            ddir = vbdiskdir
            vmname = 'shared'
        else:
            shared = 0
            uuid, VMc = self.locate_vm_menu_selection(vms[0])
            ddir = vbbasedir + "/" + VMc.name
            vmname = VMc.name
        j = 0
        while j < howmany:
            uuid = D.disk_create(whatsize, shared, ddir, vmname)
            for i in vms:
                self.vm_attach_disk(i, controller, uuid, D)
            j += 1
    def show_attachable_disks(self, D, i, attach, controller):
        uuid, VMc = self.locate_vm_menu_selection(i)
        Duuid = D.show_attachable_disks(uuid, attach)
        if Duuid and attach:
            self.vm_attach_disk(i, controller, Duuid, D)
            VMc.populate()
            D.populate()
    def is_valid_vm(self,i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            return VMc.name
        else:
            return None
    def get_mac_addr(self, i, nicn):
        uuid, VMc = self.locate_vm_menu_selection(i)
        try:
            match = re.search(r'MAC:(\S+),', VMc.conf["NIC " + nicn])
        except:
            match = re.search(r'(\S+)', '0123456789AB')
        if match:
            mac = match.group(1)
            mac = ":".join(["%s" % (mac[i:i + 2]) for i in range(0, 12, 2)])
            nmac = ' '
            while not re.match("[0-9A-F]{2}([-:]?)[0-9A-F]{2}(\\1[0-9A-F]{2}){4}$", nmac.upper()):
                nmac = input("Enter MAC (" + mac + ") ")
                if nmac == "":
                    nmac = mac
        nmac = re.sub('[.:-]', '', nmac).upper()
        if nmac == '0123456789AB':
            return 'auto'
        return nmac
class VM(object):
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid
        self.conf = {}
        self.VMParms = ["Guest OS", "Memory size", "Number of CPUs", "State", "Storage Controller Name.*", "UUID",
                        "Boot Device \d", "Storage Controller Type.*", "\w+\s\(\d*,\s\d*\)", "NIC \d", "UART \d",
                        "Firmware", "Graphics Controller", "VRAM size"]
    def display(self):
        print('Name  -> ', self.name)
        nicf = ['Attachment', 'Cable', 'Type']
        for k, v in self.conf.items():
            if re.search('NIC', k):
                for field in re.split(',', v):
                    if re.search('MAC', field):
                        nics = field
                    for p in nicf:
                        if re.search(p, field):
                            nics = nics + ',' + field
                v = nics
            print(k, ' -> ', v)

    def populate(self):
        self.conf = {}
        pipe = Popen([vbmanage, "showvminfo", self.uuid], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        for line in pipe.stdout:
            line = re.sub('Memory size ', 'Memory size:', line)
            line = re.sub(':\s+', ':', line)
            line = re.sub('\.\d+\)', ')', line)
            if re.search(':', line):
                [k, v] = line.strip().split(":", 1)
                if v == "disabled":
                    continue
                for r in self.VMParms:
                    if re.search(r, k):
                        if k == "State":
                            v = re.sub("T"," ", v)
                        self.conf.update({k: v})
class DISKS(object):
    def __init__(self):
        self.disks = {}
    def populate(self):
        self.disks = {}
        uuid = ''
        pipe = Popen([vbmanage, "list", "-ls", "hdds"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        for line in pipe.stdout:
            if re.search(':', line):
                [k, v] = line.rstrip().split(':', 1)
                v.lstrip()
                if k == 'UUID':
                    uuid = v.lstrip()
                    self.disks.update({uuid: DISK(uuid)})
                    continue
                if k == 'In use by VMs':
                    match = re.search(r'(.*) \(UUID: (\S+)\)', v.lstrip())
                    if match:
                        self.disks[uuid].add_to_conns(match.group(1), match.group(2))
                        continue
                match = re.search(r'(\S+) \(UUID', k.lstrip())
                if match:
                    self.disks[uuid].add_to_conns(match.group(1), v.lstrip().rstrip(')'))
                    continue
                self.disks[uuid].add_to_props(k, v.lstrip())
    def purge_orphans(self):
        for disk, D in self.disks.copy().items():
            if len(D.conns) == 0:
                print("Destroy ", disk, D.props['Location'])
                pipe = Popen([vbmanage, "closemedium", "disk", disk, "--delete"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                print(pipe.stdout.read())
                sleep(sleeptime)
                del D
                del self.disks[disk]
        self.populate()
        foos = glob(join(vbbasedir, "*/*.vdi"))
        for foo in foos:
            if isfile(foo):
                purge = 1
                for disk, D in self.disks.items():
                    if D.props['Location'] == foo:
                        purge = 0
                        continue
                if purge:
                    try:
                        remove(foo)
                        print("Removed orphaned disk", foo)
                    except:
                        print("Encountered error removing", foo)
    def show_disk(self, uuid):
        self.disks[uuid].show_disk()
    def show_disk_size(self, uuid):
        return self.disks[uuid].show_size()
    def show_all(self, how):
        for disk, D in self.disks.items():
            if how == 'full':
                D.show_disk()
            if how == 'brief':
                D.show_disk_brief()
    def disk_create(self, size, shared, ddir, vmname):
        if shared:
            foo = ddir + '/' + 'shared' + datetime.datetime.now().strftime("_%Y%m%d%H%M%S") + '.vdi'
            pipe = Popen(
                [vbmanage, 'createmedium', 'disk', '--filename', foo, '--size', str(size), '--format', 'VDI', '--variant',
                 'Fixed'], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
            print(pipe.stdout.read())
            pipe = Popen([vbmanage, 'modifymedium', 'disk', foo, '--type', 'shareable'], stdout=PIPE,
                         stderr=STDOUT, encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            self.populate()
        else:
            foo = ddir + '/' + vmname + datetime.datetime.now().strftime("_%Y%m%d%H%M%S") + '.vdi'
            pipe = Popen(
                [vbmanage, "createmedium", "disk", "--filename", foo, "--size", str(size), "--format", "VDI", "--variant",
                 "Standard"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
            print(pipe.stdout.read())
            sleep(sleeptime)
            self.populate()
        for uuid, D in self.disks.items():
            if D.props['Location'] == foo:
                return uuid
    def show_attachable_disks(self, vm, attach):
        i = 1
        for disk, D in self.disks.items():
            if D.props['Type'].lower() == "shareable" or len(D.conns) == 0:
                if attach == 0:
                    print(i, "  ", D.props['Capacity'], D.props['Location'])
                if attach == i:
                    return disk
                i += 1
        return ''
class DISK(object):
    def __init__(self, uuid):
        self.uuid = uuid
        self.props = {}
        self.conns = {}
    def add_to_props(self, key, val):
        self.props.update({key: val})
    def add_to_conns(self, key, val):
        self.conns.update({key: val})
    def show_disk(self):
        print('\nUUID  -> ', self.uuid)
        for key, val in self.props.items():
            print(key, ' -> ', val)
        for key, val in self.conns.items():
            print("Connected to", key, val)
    def show_disk_brief(self):
        print('\nUUID  -> ', self.uuid)
        print('Location ->', self.props['Location'])
        for key, val in self.conns.items():
            print("Connected to", key, val)
    def show_size(self):
        return self.props['Capacity']
class Unbound(object):
    def __init__(self):
        self.natnets = {}
        self.mac_dict = {}
        self.populate()
    def print_natnets(self):
        print('natnets', self.natnets)
    def is_ip_used(self, hostip):
        for m in self.mac_dict:
            if hostip in self.mac_dict[m].values():
                return True
        return False
    def run_command(self, s, verbose=False):
        pipe = Popen(s.split(' '), stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        p = pipe.stdout.read()
        if verbose:
            print(s, '\n', p)
        return p
    def resolv_conf(self):
        ns = []
        try:
            with open('/etc/resolv.conf', 'r') as resolvconf:
                for line in resolvconf.readlines():
                    match = re.search(r'^nameserver\s*(\d*\.\d*\.\d*\.\d*)', line)
                    if match:
                        ns.append(match.group(1))
        except:
            return []
        return ns
    def get_key_natnetdns(self, v):
        for nat, domain in natnetdns.items():
            if v == domain:
                return nat
        return None
    def init_lhosts(self):
        try:
            with open(join(vboxdata, "vbm-lhosts.xml"), 'r') as lhfoo:
                lhdata = json.load(lhfoo)
                lhfoo.close()
        except:
            lhdata = {}
        for k, v in mac_over.items():
            if re.search('DEADBEEF', k):
                p = v.split('.')
                hn = p.pop(0)
                dn = '.'.join(p)
                natnet = self.get_key_natnetdns(dn)
                if not k in lhdata:
                    print(natnetdns)
                    print(natnet)
                    self.unbound_ip(hn, k, natnet, None, None)
                    self.mac_dict[k].update({'netname': natnet})
                else:
                    self.mac_dict[k] = {}
                    self.mac_dict[k].update({'netname': lhdata[k]['netname']})
                    self.mac_dict[k].update({'IP': lhdata[k]['IP']})
                    self.mac_dict[k].update({'name': hn})
        with open(join(vboxdata, "vbm-lhosts.xml"), 'w') as lhfoo:
            json.dump(self.mac_dict, lhfoo, indent=2)
            lhfoo.close()
    def populate(self):
        pipe = self.run_command(vbmanage + " list natnetworks", False)
        for line in pipe.splitlines():
            match = re.search(r'^NetworkName:\s+(\S*)', line)
            if match:
                n = match.group(1)
                self.natnets[n]={}
            match = re.search(r'^Network:\s+(\S*)', line)
            if match:
                self.natnets[n].update({'Network': match.group(1)})
            match = re.search(r'127.0.0.1=(\d*)', line)
            if match:
                self.natnets[n].update({'Loopback': match.group(1)})
        pipe = self.run_command(vbmanage + " list dhcpservers", False)
        for line in pipe.splitlines():
            match = re.search(r'NetworkName:\s+(\S.*)$', line)
            if match:
                netname = match.group(1)
            match = re.search(r' MAC (\S+)', line)
            if match:
                mac = re.sub('[.:-]', '', match.group(1).upper())
                self.mac_dict[mac]={}
                self.mac_dict[mac].update({'netname': netname})
            match = re.search(r'Fixed Address:\s+(\S+)', line)
            if match:
                self.mac_dict[mac].update({'IP': match.group(1)})
        for natnet in self.natnets.keys():
            tree = ET.parse(join(vboxdata, natnet + '-Dhcpd.leases'))
            root = tree.getroot()
            for lease in root.findall('Lease'):
                mac = ip = None
                if lease.get('state') == 'expired': continue
                mac = re.sub('[.:-]', '', lease.get('mac').upper())
                ip = lease.find('Address').get('value')
                if mac and ip:
                    if mac in self.mac_dict:
                        continue
                    else:
                        self.mac_dict[mac] = {}
                        self.mac_dict[mac].update({'IP': ip})
        pipe = self.run_command(vbmanage + " list -l vms", False)
        for line in pipe.splitlines():
            match = re.search(r'^Name:\s+(\S+)', line)
            if match: hname = match.group(1)
            match = re.search(r'MAC: (\S+),', line)
            if match:
                mac = match.group(1)
                if not mac in self.mac_dict:
                    self.mac_dict[mac] = {}
                if mac in mac_over:
                    self.mac_dict[mac].update({'name': mac_over[mac]})
                else:
                    self.mac_dict[mac].update({'name': hname})
        self.init_lhosts()
    def print_dicts(self):
        print('natnets', self.natnets, '\n\n', 'mac_dict', self.mac_dict, '\n\n', 'mac_over', mac_over)
        return
    def unbound_rm_ip(self, vm_name, vm_mac, vm_natnet, vm_nic, vm_uuid):
        s = vbmanage + ' dhcpserver modify --network=' + vm_natnet + ' --vm=' + vm_uuid + ' --nic=' + vm_nic +\
            ' --remove-config'
        self.run_command(s, False)
        self.mac_dict.pop(vm_mac, None)
    def unbound_ip(self, vm_name, vm_mac, vm_natnet, vm_nic, vm_uuid):
        if vm_mac in self.mac_dict:
            if re.search('DEADBEEF', vm_mac): return
            if 'IP' in self.mac_dict[vm_mac]:
                ip = self.mac_dict[vm_mac]["IP"]
                if 'name' in self.mac_dict[vm_mac]:
                    hname = self.mac_dict[vm_mac]["name"]
                    s = vbmanage + ' dhcpserver modify --network=' + vm_natnet + ' --vm=' + vm_uuid + ' --nic=' + \
                        vm_nic + ' --set-opt=12 ' + hname + ' --fixed-address=' + ip
                    self.run_command(s, False)
                return
        else:
            self.mac_dict[vm_mac] = {}
            self.mac_dict[vm_mac].update({'name': vm_name})
            # bug here \/\/
        if vm_natnet in self.natnets:
            dhcpnet = ipaddress.ip_network(self.natnets[vm_natnet]['Network'])
            for hostip in dhcpnet.hosts():
                break_flag = False
                hostip = str(hostip)
                if re.search('\.\d$', hostip): continue
                if self.is_ip_used(hostip): continue
                self.mac_dict[vm_mac].update({'IP': hostip})
                if re.search('DEADBEEF', vm_mac): return
                s = vbmanage + ' dhcpserver modify --network=' + vm_natnet + ' --vm=' + vm_uuid + ' --nic=' + vm_nic +\
                        ' --set-opt=12 ' + vm_name + ' --fixed-address=' + hostip
                self.run_command(s, False)
                return

    def unbound_control(self):
        verbose = False
        self.run_command(uc + " reload", verbose)
        for ns in self.resolv_conf():
            self.run_command(uc + " forward " + ns, verbose)
        for natnet in self.natnets.keys():
            if natnet in natnetdns:
                dnsdom = natnetdns[natnet]
            else:
                continue
            if not re.search('\S+\.$', dnsdom):
                dnsdom = dnsdom + '.'
            nsname = "ns-" + re.sub('[.: ]', '', natnet) + '.' + dnsdom
            self.run_command(uc + " local_zone " + dnsdom + " typetransparent", verbose)
            self.run_command(uc + " local_data " + dnsdom + " 10800 IN SOA " + nsname + \
                             " nobody.invalid. 1 3600 1200 604800 10800", verbose)
            self.run_command(uc + " local_data " + dnsdom + " IN NS " + nsname, verbose)
            ipnet = ipaddress.ip_network(self.natnets[natnet]['Network'])
            ns = (str(ipaddress.ip_address(int(ipnet.network_address) + int((self.natnets[natnet]['Loopback'])))))
            self.run_command(uc + " local_data " + nsname + " IN A " + ns, verbose)
            s = uc + " local_data " + ipaddress.ip_address(ns).reverse_pointer + ". IN PTR " + nsname
            self.run_command(s, verbose)
            for m in self.mac_dict.keys():
                try:
                    if self.mac_dict[m]["netname"] != natnet: continue
                except:
                    continue
                host = self.mac_dict[m]['name'] + '.' + dnsdom
                if 'IP' in self.mac_dict[m]:
                    ip = self.mac_dict[m]['IP']
                    self.run_command(uc + ' local_data ' + host + ' IN A ' + ip, verbose)
                    s = uc + ' local_data ' + ipaddress.ip_address(ip).reverse_pointer + '. IN PTR ' + host
                    self.run_command(s, verbose)
            self.run_command(vbmanage + " dhcpserver modify --network=" + natnet + " --set-opt=6 " + ns, verbose)
            self.run_command(
                vbmanage + " dhcpserver modify --network=" + natnet + " --set-opt=15 " + dnsdom.rstrip('\.'), verbose)
            self.run_command(vbmanage + " dhcpserver restart --network=" + natnet, verbose)
        return

def vm_select_os():
    oslist = {}
    i = 1
    print("\n=============== Select OS ==============\n")
    pipe = Popen([vbmanage, "list", "-s", "ostypes"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
    for line in pipe.stdout:
        match = re.search(r'^ID:\s+(\S+)', line.rstrip())
        if match:
            oslist.update({i: match.group(1)})
            i += 1
    i = 0
    for k, v in oslist.items():
        print(f'{k:<3} {v:<20}', end="   ")
        i += 1
        if i == 4:
            i = 0
            print("")
    user_input = get_int("\nSelct OS: ")
    return oslist[user_input]
def edit_vms(V, D):
    print("\n=============== Select VM ===============\n")
    V.show_vm_menu()
    user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
    if user_input == -1:
        return
    if user_input != 0:
        if V.is_valid_vm(user_input) == None:
            print("No such VM:", str(user_input))
            return
        edit_vm(V, D, user_input)
def get_int(user_prompt):
    user_input = input(user_prompt)
    try:
        tmp = int(user_input)
    except:
        print(user_input, "is not a number.")
        return -1
    return tmp
def edit_vm(V, D, user_input):
    vm_name = V.is_valid_vm(user_input)
    if vm_name == None:
        print("No such VM:", str(user_input))
        return
    user_selection = user_input
    cs = {1: "IDE", 2: "SATA", 3: "SCSI", 4: "SAS"}
    while user_input != "Q":
        V.show_vm_menu_selection(user_selection)
        print("\n"
              "(O) OS  (N) NICs  (C) CPUs  (M) Memory  (S) Add Storage Controller  (D) Delete Storage Controller\n"
              "(E) Eject CD/DVD  (I) Insert CD/DVD  (A) Attach Disk  (U) Detach Disk  (R) Resize Disk\n"
              "(B) Boot Order  (G) Video  (F) Firmware Type  (P) Force NMI      (Q) Return to Previous Menu")
        user_input = input("\nCommand Me: ").upper()
        if user_input == "Q":
            break
        elif user_input == "B":
            if V.is_vm_running(user_selection):
                continue
            border = []
            bmenu = ['none', 'floppy', 'dvd', 'disk', 'net']
            j = 0
            while len(border) < 4:
                i = 0
                while i < len(bmenu):
                    print("(", i, ")", bmenu[i])
                    i += 1
                user_input = get_int("Enter Boot Device " + str(j) + " : ")
                border.append(bmenu[user_input])
                j += 1
            print("\nSetting Boot Order to ",border)
            j = 0
            while j < 4:
                V.run_with_args(user_selection, 'modifyvm', ['--boot' + str(j + 1), border[j]])
                j += 1
        elif user_input == "P":
            V.run_with_args(user_selection, 'debugvm', ['injectnmi'])
        elif user_input == "E":
            V.eject_iso(user_selection)
        elif user_input == "I":
            onlyfiles = [f for f in listdir(isodir) if isfile(join(isodir, f))]
            i = 0
            for f in onlyfiles:
                print('{:>2}'.format(str(i)), " - ", f)
                i += 1
            dvd = input("ISO Number (or Name)? ")
            if dvd.isnumeric():
                dvd = join(isodir, onlyfiles[int(dvd)])
            V.attach_iso(user_selection, dvd)
        elif user_input == "O":
            if V.is_vm_running(user_selection):
                continue
            ostype = vm_select_os()
            V.set_vm_os(user_selection, ostype)
        elif user_input == "C":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("CPUs?: ")
            V.set_vm_cpus(user_selection, user_input)
        elif user_input == "M":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("Memory (GB)?: ")
            V.set_vm_memory(user_selection, user_input)
        elif user_input == "S":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("Add  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
            if user_input and user_input < 5:
                C = cs[user_input]
                c = cs[user_input].lower()
                if c == 'ide':
                    V.run_with_args(user_selection, 'storagectl', ['--add', c, '--name', C, '--controller', 'PIIX3'])
                else:
                    V.run_with_args(user_selection, 'storagectl', ['--add', c, '--name', C])
        elif user_input == "D":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("Delete  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
            if user_input and user_input < 5 and ask_confirm('Delete Controller ' + cs[user_input] + ' ? '):
                V.remove_controller(V, D, user_selection, cs[user_input])
        elif user_input == "N":
            isrunning = V.is_vm_running(user_selection)
            nicn = input("NIC Number? ")
            nicmodels = { 1:'Am79C970A', 2:'Am79C973', 3:'Am79C960', 4:'82540EM', 5:'82543GC', 6:'82545EM', 7:'virtio' }
            nicmodel = get_int("NIC Model " + str(nicmodels) + " ? ")
            nicm = nicmodels[nicmodel]
            nictype = vm_select_nictype()
            mac = V.get_mac_addr(user_selection, nicn)
            if nictype == "bridged":
                nicnet = vm_select_nicnet("bridgedifs")
                if isrunning:
                    V.run_with_args(user_selection, 'controlvm', ['nic' + nicn, nictype, nicnet])
                else:
                    V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--bridgeadapter' + nicn, nicnet, '--nictype' + nicn, nicm,
                                 '--macaddress' + nicn, mac])
            elif nictype == "hostonly":
                nicnet = vm_select_nicnet("hostonlyifs")
                if isrunning:
                    V.run_with_args(user_selection, 'controlvm', ['nic' + nicn, nictype, nicnet])
                else:
                    V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--hostonlyadapter' + nicn, nicnet, '--nictype' + nicn, nicm,
                                 '--macaddress' + nicn, mac])
            elif nictype == "natnetwork":
                nicnet = vm_select_nicnet("natnets")
                if isrunning:
                    V.run_with_args(user_selection, 'controlvm', ['nic' + nicn, nictype, nicnet])
                else:
                    V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--nat-network' + nicn, nicnet, '--nictype' + nicn, nicm,
                                 '--macaddress' + nicn, mac])
            elif nictype == "nat":
                nicnet = vm_select_nicnet("natnets")
                if isrunning:
                    V.run_with_args(user_selection, 'controlvm', ['nic' + nicn, nictype, nicnet])
                else:
                    V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--natnet' + nicn, nicnet, '--nictype' + nicn, nicm,
                                 '--macaddress' + nicn, mac])
            elif nictype == "none":
                if isrunning:
                    print('VM is running. Can only toggle link state')
                    resp = input('Toggle off? [Y/N] ').upper()
                    if resp == 'Y':
                        V.run_with_args(user_selection, 'controlvm', ['setlinkstate' + nicn, 'off'])
                        continue
                    resp = input('Toggle on? [Y/N] ').upper()
                    if resp == 'Y':
                        V.run_with_args(user_selection, 'controlvm', ['setlinkstate' + nicn, 'on'])
                        continue
                else:
                    V.run_with_args(user_selection, 'modifyvm', ['--nic' + nicn, 'none', '--macaddress' + nicn, mac])
        elif user_input == "U":
            if V.is_vm_running(user_selection):
                continue
            V.vm_disk_menu(user_selection, 0, 'list', 0, D)
            diskno = get_int("\n Select Disk Number to Detach: ")
            if diskno:
                V.vm_disk_menu(user_selection, diskno, 'detach', 0, D)
        elif user_input == "R":
            if V.is_vm_running(user_selection):
                continue
            V.vm_disk_menu(user_selection, 0, 'list', 0, D)
            diskno = get_int("\n Select Disk Number to Resize: ")
            newsize = get_int("\n Select New Size in MB: ")
            if diskno and newsize:
                V.vm_disk_menu(user_selection, diskno, 'resize', newsize, D)
        elif user_input == "A":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("Attach to Controller  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
            if user_input and user_input < 5:
                controller = cs[user_input]
            V.show_attachable_disks(D, user_selection, 0, controller)
            user_input = get_int("\n Select Disk Number to Attach: ")
            if user_input:
                V.show_attachable_disks(D, user_selection, user_input, controller)
        elif user_input == "F":
            if V.is_vm_running(user_selection):
                continue
            fopts = {1:"bios", 2:"efi", 3:"efi32", 4:"efi64"}
            for k, v in fopts.items():
                print(str(k), v, end="  ")
            user_input = get_int("\n\nSelect Firmware Type: ")
            if fopts[user_input]:
                V.run_with_args(user_selection, 'modifyvm', ['--firmware',  fopts[user_input]])
        elif user_input == "G":
            if V.is_vm_running(user_selection):
                continue
            vopts = {1: "none", 2: "vboxvga", 3: "vmsvga", 4: "vboxsvga"}
            for k, v in vopts.items():
                print(str(k), v, end="  ")
            user_input = get_int("\n\nSelect Graphics Type: ")
            if vopts[user_input]:
                V.run_with_args(user_selection, 'modifyvm', ['--graphicscontroller',  vopts[user_input]])
            user_input = get_int("\n\nSelect Graphics Memory (MB): ")
            if user_input != -1:
                V.run_with_args(user_selection, 'modifyvm', ['--vram', str(user_input)])
def vm_select_nicnet(iftype):
    nicnets = {}
    nicips = {}
    i = 1
    pipe = Popen([vbmanage, "list", "-s", iftype], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
    for line in pipe.stdout:
        match = re.search(r'(^\S+):\s+(\S+)', line.rstrip())
        if match:
            if match.group(1) == "Name" or match.group(1) == "NetworkName":
                v = match.group(2)
                v = re.sub(r':.*', '', v)
                nicnets.update({i: v})
            elif match.group(1) == "IPAddress" or match.group(1) == "IP":
                nicips.update({i: match.group(2).rstrip()})
                i += 1
    for k, v in nicnets.items():
        y = nicips[k]
        print(f'{k:<3} {v:<10} {y:<15}')
    user_input = get_int("\nSelct Interface: ")
    return nicnets[user_input]
def vm_select_nictype():
    nictypes = {1: "none", 2: "null", 3: "nat", 4: "bridged", 5: "intnet", 6: "hostonly", 7: "generic", 8: "natnetwork"}
    i = 0
    for k, v in nictypes.items():
        print(f'{k:<2} {v:<10}', end="   ")
        i += 1
        if i == 4:
            i = 0
            print("")
    user_input = get_int("\nSelect NIC Type: ")
    return nictypes[user_input]
def create_vm(V, D):
    vmname = input("\n\nEnter VM Name: ")
    ostype = vm_select_os()
    pipe = Popen([vbmanage, "createvm", "--name", vmname, "--ostype", ostype, "--basefolder", vbbasedir, "--register",
                  "--default"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
    print(pipe.stdout.read())
    sleep(sleeptime)
    V.populate()
def create_disks(V, D):
    howmany = get_int("\nHow many disks? ")
    whatsize = get_int("\nSize in MB? ")
    user_input=999
    vms = []
    while user_input:
        print("\n=============== Select VMs to Attach ===============\n")
        V.show_vm_menu()
        print("\nSelected: ", vms)
        user_input = get_int("\n 0 When done\n\nCommand Me: ")
        if V.is_valid_vm(user_input) == None:
            if user_input:
                print("No such VM:", str(user_input))
            continue
        if user_input:
            vms.append(user_input)
    if len(vms) == 0:
        return
    cs = {1: "IDE", 2: "SATA", 3: "SCSI", 4: "SAS"}
    user_input = get_int("Add  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
    if user_input and user_input < 5 and ask_confirm('Create ' + str(howmany) + ' disks and attach? '):
        V.create_and_attach_disks(D, vms, howmany, whatsize, cs[user_input])
        D.populate()
def delete_vm(V, D):
    print("\n=============== Select VM to Delete ===============\n")
    V.show_vm_menu()
    user_input = get_int("\nSelect VM to Delete\n\nCommand Me: ")
    vname = V.is_valid_vm(user_input)
    if vname != None:
        if ask_confirm('Delete ' + vname + ' ? '):
            V.delete_vm(V, D, user_input)
    elif user_input:
        print("\nNo such VM:", str(user_input))
def poweroff_vm(V, D):
    user_input = 99
    while user_input != 0:
        print("\n=============== Select VM to Power Off ===============\n")
        V.show_vm_menu()
        user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
        if user_input != 0:
            if V.is_valid_vm(user_input) == None:
                print("No such VM:", str(user_input))
                return
            V.poweroff_vm(V, D, user_input)
def boot_vm(V, D, L):
    user_input = 99
    while user_input != 0:
        print("\n=============== Select VM to Boot ===============\n")
        V.show_vm_menu()
        user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
        if user_input != 0:
            if V.is_valid_vm(user_input) == None:
                print("No such VM:", str(user_input))
                return 0
            if V.is_vm_running(user_input):
                return 1
            pfoo, vmname = V.boot_vm(V, D, user_input, vrde=0)
            if pfoo:
                vm_console(pfoo, vmname, L)
def clone_vm(V, D):
    print("\n=============== Select VM to Clone ===============\n")
    V.show_vm_menu()
    user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
    vmname = V.is_valid_vm(user_input)
    if vmname == None:
        print("No such VM:", str(user_input))
        return
    newvm = input("\nEnter Clone Name: ")
    if ask_confirm('\nProceed with clone ' + vmname + ' to ' + newvm + '? '):
        V.clone_vm(V, D, user_input, newvm)
def top_menu(V, D, L):
    user_input = ""
    while user_input != "Q":
        print("=============== Top Menu ===============\n"
              "\n"
              "(N) Create New VM\n"
              "(E) Edit VM\n"
              "(L) Clone VM\n"
              "(B) Boot VM\n"
              "(P) Power Off VM\n"
              "(D) Delete VM\n"
              "(C) Create Disks\n"
              "(R) Remove Unattached Disks\n"
              "(Q) Exit Program\n"
              "\n")
        user_input = input("Command Me: ").upper()
        if user_input == "E":
            edit_vms(V, D)
        elif user_input == "N":
            create_vm(V, D)
        elif user_input == "L":
            clone_vm(V, D)
        elif user_input == "C":
            create_disks(V, D)
        elif user_input == "R":
            D.purge_orphans()
        elif user_input == "D":
            delete_vm(V, D)
        elif user_input == "B":
            boot_vm(V, D, L)
        elif user_input == "P":
            poweroff_vm(V, D)
def ask_confirm(prompt):
    user_input = '-'
    while user_input != 'Y' or user_input != 'N':
        user_input = input(prompt).upper()
        if user_input == 'Y':
            return True
        elif user_input == 'N':
            return False
        else:
            print("\nPlease respond (Y or N)\n")
def vm_console(pfoo, vmname, L):
    pipe = Popen(['ps', 'ax'], stdin=None, stderr=None, stdout=PIPE, universal_newlines=True, encoding='utf-8')
    for line in pipe.stdout:
        match = re.search(fr'(^\d+).*{pfoo}', line)
        if match:
            print(" console in use by", match.group(1), "\n")
            return
    print("Connected to", pfoo)
    print("\033]0;%s\007" % (vmname), end=None)
    L.release()
    execv(socat, ["socat", socatargs, pfoo])
def init_config_vars():
    ppath = (dirname(realpath(__file__)))
    config = RawConfigParser(interpolation=ExtendedInterpolation())
    config.optionxform = lambda option: option
    try:
        config.read_file(open(join(ppath, 'vbm.ini'), 'rt', encoding='utf-8'))
    except:
        print('Unable to read configuration file, vbm.ini')
        return
    global isodir
    global vbbasedir
    global vbdiskdir
    global vbheadless
    global vbheadlessargs
    global vrdeargs
    global vbmanage
    global socat
    global socatargs
    global sleeptime
    global lockfoo
    global mac_over
    global natnetdns
    global vboxdata
    global uc
    uc = None
    mac_over = {}
    natnetdns = {}
    for key, val in config.items('vbm'):
        if key == 'isodir': isodir = config['vbm']['isodir']
        if key == 'vbbasedir': vbbasedir = config['vbm']['vbbasedir']
        if key == 'vbdiskdir': vbdiskdir = config['vbm']['vbdiskdir']
        if key == 'vbheadless': vbheadless = config['vbm']['vbheadless']
        if key == 'vbheadlessargs': vbheadlessargs = config['vbm']['vbheadlessargs']
        if key == 'vrdeargs': vrdeargs = config['vbm']['vrdeargs']
        if key == 'vbmanage': vbmanage = config['vbm']['vbmanage']
        if key == 'socat': socat = config['vbm']['socat']
        if key == 'socatargs': socatargs = config['vbm']['socatargs']
        if key == 'sleeptime': sleeptime = int(config['vbm']['sleeptime'])
        if key == 'lockfoo': lockfoo = config['vbm']['lockfoo']
        if key == 'vboxdata': vboxdata = config['vbm']['vboxdata']
        if key == 'uc': uc = config['vbm']['uc']
    for key, val in config.items('name_overrides'):
        mac_over.update({key.upper(): val})
    for key, val in config.items('logical_hosts'):
        mac_over.update({key.upper(): val})
    for key, val in config.items('natnetdns'):
        natnetdns.update({key: val})
    return 0

def main():
    init_config_vars()
    L = FileLock(lockfoo)
    L.acquire()
    parser = argparse.ArgumentParser(description='Manage your VirtualBox VMs.')
    parser.add_argument('-l', action='store_true', help='List the VirtualBox VMs.')
    parser.add_argument('-s', type=int, help='Show configuration of VM N', metavar='N')
    parser.add_argument('-p', type=int, help='Power Off VM N', metavar='N')
    parser.add_argument('-e', type=int, help='Edit VM N', metavar='N')
    parser.add_argument('-d', type=int, help='Delete VM N', metavar='N')
    parser.add_argument('-r', action='store_true', help='Sync on disk config with VirtualBox')
    parser.add_argument('-u', action='store_true', help='Update unbound DNS')

    boot = parser.add_argument_group('boot')
    boot.add_argument('-b', type=int, help='Boot VM N', metavar='N')
    boot.add_argument('-g', action='store_true', default=False, help='Enable VRDE (' + vrdeargs + ')')

    clone = parser.add_argument_group('clone')
    clone.add_argument('-c', type=int, help='Create a clone of VM N', metavar='N')
    clone.add_argument('--clone', help="Name to use for the new clone.")

    disks = parser.add_argument_group('disks')
    disks.add_argument('--disks', action='store_true', help='List All Disks')
    disks_o = disks.add_mutually_exclusive_group()
    disks_o.add_argument('--brief', action='store_true', help='Shorter disk list')
    disks_o.add_argument('--full', action='store_true', help='Include all disk details in list')

    parser.add_argument('-i', action='store_true', help='Interactive Interface')
    parser.add_argument('-y', action='store_true', help='Do not ask, assume YES')
    results = parser.parse_args()
    if results.c and results.clone is None:
        parser.error("-c C requires --clone CLONE_NAME")
    V = VMS()
    V.populate()
    D = DISKS()
    D.populate()
    if results.l:
        V.show_vm_menu()
    elif results.s:
        V.show_vm_menu_selection(results.s)
    elif results.b:
        vmname = V.is_valid_vm(results.b)
        if vmname is not None:
            pfoo, vmname = V.boot_vm(V, D, results.b, results.g)
            if pfoo:
                vm_console(pfoo, vmname, L)
        else:
            print('No such VM', str(results.b))
    elif results.p:
        V.poweroff_vm(V, D, results.p)
    elif results.e:
        edit_vm(V, D, results.e)
    elif results.d:
        vmname = V.is_valid_vm(results.d)
        if vmname == None:
            print("No such VM:", str(results.d))
            return
        if not results.y:
            if not ask_confirm('\nDelete ' + vmname + ' ? '):
                return
        print(f"Delete {vmname}")
        V.delete_vm(V, D, results.d)
    elif results.r:
        V.vbox_sync_config()
    elif results.u:
        if uc:
            U = Unbound()
            U.unbound_control()
        else:
            ppath = (dirname(realpath(__file__)))
            print('Check configuration: ', join(ppath, 'vbm.ini'))
            print('unbound is not configured.')
    elif results.i:
        top_menu(V, D, L)
    elif results.c:
        vmname = V.is_valid_vm(results.c)
        if vmname == None:
            print("No such VM:", str(results.c))
            return
        if not results.y:
            if not ask_confirm('\nClone ' + vmname + ' to ' + results.clone + ' ? '):
                return
        print(f"Clone {vmname} to {results.clone}")
        V.clone_vm(V, D, results.c, results.clone)
    elif results.disks:
        if results.brief:
            D.show_all('brief')
        elif results.full:
            D.show_all('full')
        else:
            D.show_all('full')
    else:
        V.show_vm_menu()
        parser.print_usage()
    L.release()

if __name__ == '__main__':
    main()
