import sys
import subprocess

# --CHECKS----------------------------
if sys.version_info < (3, 4, 0):
    print("You need python 3.4 or later to run this script.")
    sys.exit(-1)

# -- Python modules

# install: python-yaml, python-xdg, python-notify2, python-crypto, attic, python-progressbar
modules = ["yaml", "xdg.BaseDirectory", "notify2", "Crypto", "attic", "progressbar"]
for module in modules:
    try:
        __import__(module)
    except ImportError:
        print("%s must be installed!" % module)
        sys.exit(-1)

# python2 module
try:
    # sudo pip2 install pyrax
    # python2-oslo-config must be installed from AUR before that
    assert subprocess.call(["python2", "-c", "'import pyrax'"],
                           stdout=subprocess.DEVNULL) == 0
except Exception as err:
    print("pyrax (for python2) must be installed!: sudo pip install pyrax.")
    sys.exit(-1)

# -- External binaries

# install: duplicity, rsync, bup
# attic detected as python3 module already
externals = ["duplicity", "rsync", "bup"]
for external in externals:
    try:
        assert subprocess.call([external, "--version"],
                               stdout=subprocess.DEVNULL) == 0
    except Exception:
        print("%s must be installed!" % external)
        sys.exit(-1)
