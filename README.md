# vbm.py
python3 program to manage your VirtualBox machines

% vbm -h
usage:

  vbm [-h] 
  vbm [-l] 
  vbm [-b B] 
  vbm [-p P] 
  vbm [-e E] 
  vbm [-d D] 
  vbm [ -i ]
  vbm [-c C] [--clone CLONE]

Manage your VirtualBox VMs.

optional arguments:
  -h, --help     show this help message and exit
  -l             List the VirtualBox VMs
  -b B           Boot VM B
  -p P           Power Off VM P
  -e E           Edit VM E
  -d D           Delete VM D
  -i             Interactive Interface

clone:
  -c C           Number of machine to clone.
  --clone CLONE  Name to use for the new clone.

ABOUT

vbm.py is a python3 program for management of VirtualBox VMs. I frequently
need to create multiple VMs and attach shared storage which is very
cumbersome in the GUI. This is the primary reason for writing the program (plus
I get to sharpen my phython skills)

The design of the program assumes you intend to run your VMs with a serial port
console. 'socat' will need to be installed in order for this to work. The VMs will
also have to be configured to support a serial port console. The serial port is added
to the VM when it is booted. It then launches 'socat' and connects to the serial port
PIPE for console communications.

INSTALL

The program is a single python script with an additional configuration file.

You will need to configure the variables in vbmconfig.py to reflect your environment.

You can just check out the project then crete a symbolic link to the 'vbm.py' file in the
project.