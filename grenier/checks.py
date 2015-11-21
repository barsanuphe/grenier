import sys
import subprocess

# --CHECKS----------------------------
if sys.version_info < (3, 4, 0):
    print("You need python 3.4 or later to run this script.")
    sys.exit(-1)

# -- Python modules
# install: python-yaml, python-xdg, python-notify2, python-progressbar
modules = ["yaml", "xdg.BaseDirectory", "progressbar", "notify2"]
for module in modules:
    try:
        __import__(module)
    except ImportError:
        print("%s must be installed!" % module)
        sys.exit(-1)

# -- External binaries
# install: rclone, encfs, rsync, bup
externals = ["rclone", "encfs", "rsync", "bup"]
for external in externals:
    try:
        assert subprocess.call([external, "--version"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0
    except FileNotFoundError:
        print("%s must be installed!" % external)
        sys.exit(-1)
