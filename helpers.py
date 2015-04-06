import subprocess
from pathlib import Path

from logger import *

def duplicity_command(cmd, passphrase):
    p = subprocess.Popen(["duplicity", "-v8"] + cmd,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         bufsize=1,
                         env={"PASSPHRASE": passphrase})
    for line in iter(p.stdout.readline, b''):
        line = line.decode("utf8").strip()
        if line.startswith("Processed"):
            logger.info(".", end="", flush=True)
    for line in iter(p.stderr.readline, b''):
        line = line.decode("utf8").strip()
        if "warning" not in line.lower():
            logger.info("\t !!! " + line, flush=True)
    p.communicate()
    logger.info(".")

def create_or_check_if_empty(target):
    t = Path(target)
    if not t.exists():
        t.mkdir(parents=True)
        return True
    else:
        return (list(t.rglob('*')) == [])

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
