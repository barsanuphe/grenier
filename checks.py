import sys, subprocess

#--CHECKS----------------------------
if sys.version_info < (3,0,0):
  print("You need python 3.0 or later to run this script.")
  sys.exit(-1)
try:
    import yaml
except Exception as err:
    print("pyyaml (for python3) must be installed!")
    sys.exit(-1)
try:
    # installer: duplicity
    assert subprocess.call(["duplicity","--version"],
                           stdout=subprocess.DEVNULL) == 0
except Exception as err:
    print("duplicity must be installed!")
    sys.exit(-1)
try:
    assert subprocess.call(["python2","-c", "'import pyrax'"],
                           stdout=subprocess.DEVNULL) == 0
except Exception as err:
    print("pyrax (for python2) must be installed!: sudo pip install pyrax.")
    sys.exit(-1)
try:
    # installer: bup
    assert subprocess.call(["bup","--version"], stdout=subprocess.DEVNULL) == 0
except Exception as err:
    print("bup must be installed!")
    sys.exit(-1)

try:
    # installer: attic
    import attic
except Exception as err:
    print("attic must be installed!")
    sys.exit(-1)

try:
    # install: python-notify2
    import notify2
except Exception as err:
    print("python-notify2 must be installed!")
    sys.exit(-1)
