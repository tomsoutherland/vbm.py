#
# configuration file for the vbm.py script
#
# Directory for your ISOs
isodir = "/Volumes/Sabrent Rocket/iso"
# Location of your VMs
vbbasedir = "/Volumes/Sabrent Rocket/VirtualBox VMs"
# Where you would like to save shared disks
vbdiskdir = vbbasedir + "/VMdisks"
# Path to VirtualBox VBoxHeadless
vbheadless = "/usr/local/bin/VBoxHeadless"
# Any args you want to pass to VBoxHeadless
vbheadlessargs = "--vrde off"
# Path to VBoxManage
vbmanage = "/usr/local/bin/VBoxManage"
# Path to socat
socat = "/usr/local/bin/socat"
# Any arguments for socat
socatargs = "-,raw,echo=0,escape=0x1d"
# Time to wait after running a virtualbox command.
sleeptime = 1
# Path to the lockfile
lockfoo = "/var/tmp/vbm"