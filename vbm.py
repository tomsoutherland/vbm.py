#!/usr/bin/env python3


from vbmconfig import isodir, vbbasedir, vbdiskdir, vbheadless, vbheadlessargs, vbmanage, socat, socatargs, sleeptime
import re, datetime, sys, argparse
from subprocess import Popen, PIPE, STDOUT
from time import sleep
from os import execv, listdir
from os.path import isfile, join

class VMS:
    def __init__(self):
        self.VM_max_len = 1
        self.vmlist = {}
        self.VMSlist = {}
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
        pfoo = "/tmp/vb-" + VMc.name + "-console"
        if self.is_vm_running(i):
            return pfoo
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
                vargs = "--vrde on --vrdeproperty TCP/Ports=3389-3400".split(' ')
            else:
                vargs = vbheadlessargs.split(' ')
            Popen([vbheadless] + vargs + ["-s", uuid], close_fds=True, shell=False)
            sleep(sleeptime)
        return pfoo
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
        pipe = Popen([vbmanage, "unregistervm", uuid, "--delete"], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
        print(pipe.stdout.read())
        sleep(sleeptime)
        del VMc
        del V.VMSlist[uuid]
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
    def vm_disk_menu(self, i, detach, D):
        uuid, VMc = self.locate_vm_menu_selection(i)
        i = 1
        for k, v in VMc.conf.items():
            match = re.search(r'\S+\s\(\d,\s\d\)', k)
            if match:
                if detach and detach == i:
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
                elif detach == 0:
                    print(i,"  ", k, v)
                i += 1
    def show_vm_menu(self):
        i = 1
        for uuid, VMc in self.VMSlist.items():
            mystr = VMc.conf["State"]
            print('{0:2d}'.format(i), '{:<{l}}'.format(self.vmlist[uuid], l=self.VM_max_len), mystr)
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
    def vm_attach_disk(self, i, controller, disk_uuid):
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
                        print("Attaching disk to " + controller + " (" + str(port) + ", " + str(device) + ")")
                        pipe = Popen(
                            [vbmanage, 'storageattach', uuid, '--storagectl', 'IDE', '--port', str(port), '--device',
                             str(device), '--type', 'hdd', '--medium', disk_uuid], stdout=PIPE, stderr=STDOUT,
                            encoding='utf-8')
                        print(pipe.stdout.read())
                        sleep(sleeptime)
                        VMc.populate()
                        return
                    else:
                        device += 1
                port += 1
        else:
            maxp = maxports[controller]
            port = 0
            while port < maxp:
                if not controller + " (" + str(port) + ", 0)" in VMc.conf:
                    print("Attaching disk to " + controller + " (" + str(port) + ", 0)")
                    pipe = Popen(
                        [vbmanage, 'storageattach', uuid, '--storagectl', controller, '--port', str(port), '--type',
                         'hdd', '--medium', disk_uuid], stdout=PIPE, stderr=STDOUT, encoding='utf-8')
                    print(pipe.stdout.read())
                    sleep(sleeptime)
                    VMc.populate()
                    return
                port += 1
        print("Unable to attach", disk_uuid, "to", controller)
        exit(1)
    def create_and_attach_disks(self, D, vms, howmany, whatsize, controller):
        if len(vms) > 1:
            shared = 1
            ddir = vbdiskdir
        else:
            shared = 0
            uuid, VMc = self.locate_vm_menu_selection(vms[0])
            ddir = vbbasedir + "/" + VMc.name
        j = 0
        while j < howmany:
            uuid = D.disk_create(whatsize, shared, ddir)
            for i in vms:
                self.vm_attach_disk(i, controller, uuid)
            j += 1
    def show_attachable_disks(self, D, i, attach, controller):
        uuid, VMc = self.locate_vm_menu_selection(i)
        Duuid = D.show_attachable_disks(uuid, attach)
        if Duuid and attach:
            self.vm_attach_disk(i, controller, Duuid)
            VMc.populate()
            D.populate()
    def is_no_such_vm(self,i):
        uuid, VMc = self.locate_vm_menu_selection(i)
        if uuid:
            return 0
        else:
            return 1
class VM:
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid
        self.conf = {}
        self.VMParms = ["Guest OS", "Memory size", "Number of CPUs", "State", "Storage Controller Name.*", "UUID",
                        "Boot Device \d", "Storage Controller Type.*", "\w+\s\(\d*,\s\d*\)", "NIC \d", "UART \d",
                        "Firmware", "Graphics Controller", "VRAM size"]
    def display(self):
        print('Name  -> ', self.name)
        for k, v in self.conf.items():
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
                        self.conf.update({k: v})
class DISKS:
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
    def show_disk(self, uuid):
        self.disks[uuid].show_disk()
    def show_all(self, how):
        for disk, D in self.disks.items():
            if how == 'full':
                D.show_disk()
            if how == 'brief':
                D.show_disk_brief()
    def disk_create(self, size, shared, ddir):
        foo = ddir + '/' + datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f") + '.vdi'
        print(foo)
        if shared:
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
            if D.props['Type'] == "shareable" or len(D.conns) == 0:
                if attach == 0:
                    print(i, "  ", D.props['Capacity'], D.props['Location'])
                if attach == i:
                    return disk
                i += 1
        return ''
class DISK:
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
        if V.is_no_such_vm(user_input):
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
    if V.is_no_such_vm(user_input):
        print("No such VM:", str(user_input))
        return
    user_selection = user_input
    cs = {1: "IDE", 2: "SATA", 3: "SCSI", 4: "SAS"}
    while user_input != "Q":
        V.show_vm_menu_selection(user_selection)
        print("\n"
              "(O) OS  (N) NICs  (C) CPUs  (M) Memory  (S) Add Storage Controller  (D) Delete Storage Controller\n"
              "(E) Eject CD/DVD  (I) Insert CD/DVD  (A) Attach Disk  (U) Detach Disk\n"
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
                print(i, " - ", join(isodir, f))
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
                V.run_with_args(user_selection, 'storagectl', ['--add', c, '--name', C])
        elif user_input == "D":
            if V.is_vm_running(user_selection):
                continue
            user_input = get_int("Delete  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
            if user_input and user_input < 5:
                V.run_with_args(user_selection, 'storagectl', ['--remove', '--name', cs[user_input]])
                V.populate()
                D.populate()
        elif user_input == "N":
            #if V.is_vm_running(user_selection):
            #    continue
            nicn = input("NIC Number? ")
            nictype = vm_select_nictype()
            if nictype == "bridged":
                nicnet = vm_select_nicnet("bridgedifs")
                V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--bridgeadapter' + nicn, nicnet])
            elif nictype == "hostonly":
                nicnet = vm_select_nicnet("hostonlyifs")
                V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--hostonlyadapter' + nicn, nicnet])
            elif nictype == "natnetwork":
                nicnet = vm_select_nicnet("natnets")
                V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--nat-network' + nicn, nicnet])
            elif nictype == "nat":
                nicnet = vm_select_nicnet("natnets")
                V.run_with_args(user_selection, 'modifyvm',
                                ['--nic' + nicn, nictype, '--natnet' + nicn, nicnet])
            elif nictype == "none":
                V.run_with_args(user_selection, 'modifyvm', ['--nic' + nicn, 'none'])
        elif user_input == "U":
            if V.is_vm_running(user_selection):
                continue
            V.vm_disk_menu(user_selection, 0, D)
            user_input = get_int("\n Select Disk Number to Detach: ")
            if user_input:
                V.vm_disk_menu(user_selection, user_input, D)
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
    edit_vms(V, D)
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
        if V.is_no_such_vm(user_input):
            if user_input:
                print("No such VM:", str(user_input))
            continue
        if user_input:
            vms.append(user_input)
    if len(vms) == 0:
        return
    cs = {1: "IDE", 2: "SATA", 3: "SCSI", 4: "SAS"}
    user_input = get_int("Add  (1) IDE  (2) SATA  (3) SCSI  (4) SAS ")
    if user_input and user_input < 5:
        V.create_and_attach_disks(D, vms, howmany, whatsize, cs[user_input])
        D.populate()
def delete_vm(V, D):
    user_input = 99
    while user_input != 0:
        print("\n=============== Select VM to Delete ===============\n")
        V.show_vm_menu()
        user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
        if V.is_no_such_vm(user_input):
            print("No such VM:", str(user_input))
            return
        if user_input != 0:
            V.delete_vm(V, D, user_input)
def poweroff_vm(V, D):
    user_input = 99
    while user_input != 0:
        print("\n=============== Select VM to Power Off ===============\n")
        V.show_vm_menu()
        user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
        if user_input != 0:
            if V.is_no_such_vm(user_input):
                print("No such VM:", str(user_input))
                return
            V.poweroff_vm(V, D, user_input)
def boot_vm(V, D):
    user_input = 99
    while user_input != 0:
        print("\n=============== Select VM to Boot ===============\n")
        V.show_vm_menu()
        user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
        if user_input != 0:
            if V.is_no_such_vm(user_input):
                print("No such VM:", str(user_input))
                return 0
            if V.is_vm_running(user_input):
                return 1
            pfoo = V.boot_vm(V, D, user_input, vrde=0)
            if pfoo:
                vm_console(pfoo)
def clone_vm(V, D):
    print("\n=============== Select VM to Clone ===============\n")
    V.show_vm_menu()
    user_input = get_int("\n 0 Return to previous menu\n\nCommand Me: ")
    if V.is_no_such_vm(user_input):
        print("No such VM:", str(user_input))
        return
    newvm = input("\nEnter Clone Name: ")
    if user_input != 0:
        V.clone_vm(V, D, user_input, newvm)
def top_menu(V, D):
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
              "(R) Remove Orphaned Disks\n"
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
            boot_vm(V, D)
        elif user_input == "P":
            poweroff_vm(V, D)
def vm_console(pfoo):
    pipe = Popen(['ps', 'ax'], stdin=None, stderr=None, stdout=PIPE, universal_newlines=True, encoding='utf-8')
    for line in pipe.stdout:
        match = re.search(fr'(^\d+).*{pfoo}', line)
        if match:
            print(" console in use by", match.group(1), "\n")
            return
    print("Connected to", pfoo)
    execv(socat, ["socat", socatargs, pfoo])
def main():
    parser = argparse.ArgumentParser(description='Manage your VirtualBox VMs.')
    parser.add_argument('-l', action='store_true', help='List the VirtualBox VMs.')
    parser.add_argument('-b', type=int, help='Boot VM B')
    parser.add_argument('-p', type=int, help='Power Off VM P')
    parser.add_argument('-e', type=int, help='Edit VM E')
    parser.add_argument('-d', type=int, help='Delete VM D')
    clone = parser.add_argument_group('clone')
    clone.add_argument('-c', type=int, help="Number of machine to clone.")
    clone.add_argument('--clone', help="Name to use for the new clone.")
    parser.add_argument('-i', action='store_true', help='Interactive Interface')
    results = parser.parse_args()
    if results.c and results.clone is None:
        parser.error("-c C requires --clone CLONE_NAME")
    V = VMS()
    V.populate()
    D = DISKS()
    D.populate()
    if results.l:
        V.show_vm_menu()
    elif results.b:
        pfoo = V.boot_vm(V, D, results.b, 0)
        if pfoo:
            vm_console(pfoo)
    elif results.p:
        V.poweroff_vm(V, D, results.p)
    elif results.e:
        edit_vm(V, D, results.e)
    elif results.d:
        if V.is_no_such_vm(results.d):
            print("No such VM:", str(results.d))
            return
        V.delete_vm(V, D, results.d)
    elif results.i:
        top_menu(V, D)
    elif results.c:
        if V.is_no_such_vm(results.c):
            print("No such VM:", str(results.c))
            return
        V.clone_vm(V, D, results.c, results.clone)
    else:
        top_menu(V, D)

if __name__ == '__main__':
    main()
