import subprocess
from pathlib import Path

from logger import *
from checks import *

def duplicity_command(cmd, passphrase):
    logger.debug(cmd)
    if passphrase:
        env_dict = {"PASSPHRASE": passphrase}
    else:
        env_dict = {}
    p = subprocess.Popen(["duplicity", "-v8"] + cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=1,
                        env=env_dict)
    cpt = 0
    for line in iter(p.stdout.readline, b''):
        line = line.decode("utf8").rstrip()
        logger.debug(line)
        if line.startswith("Processed"):
            logger.info("Processed file %s"%cpt)
            cpt += 1
    for line in iter(p.stderr.readline, b''):
        line = line.decode("utf8").rstrip()
        logger.debug(line)
        if "warning" not in line.lower():
            logger.warning("\t !!! " + line)
    p.communicate()

def attic_command(cmd, passphrase, quiet=False):
    logger.debug(cmd)
    if passphrase:
        env_dict = {"ATTIC_PASSPHRASE": passphrase}
    else:
        env_dict = {}
    p = subprocess.Popen(["attic"] + cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=1,
                        env=env_dict)
    output = []
    for line in iter(p.stdout.readline, b''):
        if not quiet:
            logger.info(line.decode("utf8").rstrip())
        output.append(line.decode("utf8").rstrip())
    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
        output.append("\t !!! " + line.decode("utf8").rstrip())
    p.communicate()
    return output

def rsync_command(cmd, quiet=False):
    logger.debug(cmd)
    p = subprocess.Popen(["rsync", "-va", "--delete", "--progress", "--force"] + cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=1)
    for line in iter(p.stdout.readline, b''):
        if not quiet:
            logger.info(line.decode("utf8").rstrip())
    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
    p.communicate()

def create_or_check_if_empty(target):
    t = Path(target)
    if not t.exists():
        t.mkdir(parents=True)
        return True
    else:
        return (list(t.glob('*')) == [])

def list_fuse_mounts():
    p = subprocess.Popen(["mount"],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         bufsize=1)
    mounts = []
    for line in iter(p.stdout.readline, b''):
        line = line.decode("utf8").strip()
        if "atticfs" in line:
            mounts.append(line.split(" ")[2])
    return mounts

def is_fuse_mounted(directory):
    if directory.endswith("/"):
        directory = directory[:-1]
    return directory in list_fuse_mounts()

def notify_this(text):
    notify2.init("grenier")
    n = notify2.Notification("Grenier",
                             text,
                             "drive-removable-media")
    n.set_timeout(2000)
    n.show()
