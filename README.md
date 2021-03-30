# vbm.py
python3 program to manage your VirtualBox machines

<pre>
% vbm -h
usage: vbm [-h] [-l] [-s N] [-p N] [-e N] [-d N] [-r] [-u] [-b N] [-g] [-c N] [--clone CLONE] [--disks] [--brief | --full] [-i] [-y]

Manage your VirtualBox VMs.

optional arguments:
  -h, --help     show this help message and exit
  -l             List the VirtualBox VMs.
  -s N           Show configuration of VM N
  -p N           Power Off VM N
  -e N           Edit VM N
  -d N           Delete VM N
  -r             Sync on disk config with VirtualBox
  -u             Update unbound DNS
  -i             Interactive Interface
  -y             Do not ask, assume YES

boot:
  -b N           Boot VM N
  -g             Enable VRDE (--vrde on --vrdeproperty TCP/Ports=3389-3400)

clone:
  -c N           Create a clone of VM N
  --clone CLONE  Name to use for the new clone.

disks:
  --disks        List All Disks
  --brief        Shorter disk list
  --full         Include all disk details in list
</pre>


ABOUT

vbm.py is a python3 program for management of VirtualBox VMs. I frequently
need to create multiple VMs and attach shared storage which is very
cumbersome in the GUI. This is the primary reason for writing the program (plus
I get to sharpen my python skills)

The design of the program assumes you intend to run your VMs with a serial port
console. 'socat' will need to be installed in order for this to work. The VMs will
also have to be configured to support a serial port console. The serial port is added
to the VM when it is booted. It then launches 'socat' and connects to the serial port
PIPE for console communications.

The program also includes support for running an "unbound" server to provide a DNS
server to the NAT network(s). The DNS is updated when a VM is booted and can also be updated
using the '-u' option.

INSTALL

The easiest way to install the program is to create a directory for the project then run,

<pre>git clone https://github.com/tomsoutherland/vbm.py.git</pre>

inside the target directory.

You will need to configure the variables in vbm.ini to reflect your environment.

I can be contacted at southerland DOT tom AT gmail DOT com.
