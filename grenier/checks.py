import sys
from subprocess import call, DEVNULL

# --CHECKS----------------------------
if sys.version_info < (3, 4, 0):
    print("You need python 3.4 or later to run this script.")
    sys.exit(-1)


# -- Python modules
def check_third_party_modules():
    # install: python-yaml, python-xdg, python-notify2, python-progressbar, python-keepassx
    modules = ["yaml", "xdg.BaseDirectory", "progressbar", "notify2", "keepassx"]
    for module in modules:
        try:
            __import__(module)
        except ImportError:
            print("%s must be installed!" % module)
            sys.exit(-1)


# -- External binaries
# install: rclone, encfs, rsync, bup, restic
def external_binaries_available(p):
    try:
        assert call([p, "--version"], stdout=DEVNULL, stderr=DEVNULL) == 0 \
            or call([p, "version"], stdout=DEVNULL, stderr=DEVNULL) == 0
        return True
    except FileNotFoundError:
        print("%s must be installed!" % p)
        return False
