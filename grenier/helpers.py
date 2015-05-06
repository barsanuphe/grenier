from subprocess import PIPE, Popen, STDOUT
import time
from pathlib import Path

import notify2
import yaml
from progressbar import Bar, Counter, ETA, Percentage, ProgressBar


from grenier.logger import *


def duplicity_command(cmd, passphrase):
    logger.debug(cmd)
    if passphrase:
        env_dict = {"PASSPHRASE": passphrase}
    else:
        env_dict = {}
    p = Popen(["duplicity", "-v8"] + cmd,
                         stdout=PIPE,
                         stderr=PIPE,
                         bufsize=1,
                         env=env_dict)
    cpt = 0
    for line in iter(p.stdout.readline, b''):
        line = line.decode("utf8").rstrip()
        logger.debug(line)
        if line.startswith("Processed"):
            print(".", end="", flush=True)
            logger.debug("Processed file %s" % cpt)
            cpt += 1
    for line in iter(p.stderr.readline, b''):
        line = line.decode("utf8").rstrip()
        logger.debug(line)
        if "warning" not in line.lower():
            logger.warning("\t !!! " + line)
    p.communicate()
    print(".", flush=True)


def attic_command(cmd, passphrase, quiet=False):
    logger.debug(cmd)
    if passphrase:
        env_dict = {"ATTIC_PASSPHRASE": passphrase}
    else:
        env_dict = {}
    p = Popen(["attic"] + cmd,
              stdout=PIPE,
              stderr=PIPE,
              bufsize=1,
              env=env_dict)
    output = []
    for line in iter(p.stdout.readline, b''):
        if not quiet:
            logger.info("\t"+line.decode("utf8").rstrip())
        output.append(line.decode("utf8").rstrip())
    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
        output.append("\t !!! " + line.decode("utf8").rstrip())
    p.communicate()
    return output

def generate_pbar(title, number_of_elements):
    widgets = [title,
               Counter(),
               '/%s '%number_of_elements,
               Percentage(),
               ' ',
               Bar(left='[',right=']', fill='-'),
               ' ',
               ETA()]
    return ProgressBar(widgets = widgets, maxval = number_of_elements).start()


def bup_command(cmd, backup_directory, quiet=False, number_of_items=None, pbar_title="", save_output=True):
    logger.debug(cmd)
    env_dict = {"BUP_DIR": backup_directory.as_posix()}
    output = []

    if number_of_items:
        cpt = 0
        pbar = generate_pbar(pbar_title, number_of_items).start()

    with Popen(["bup"] + cmd,
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1,
               env=env_dict) as p:
        for line in p.stdout:
            if number_of_items:
                cpt += 1
                if cpt < number_of_items:
                    pbar.update(cpt)
            elif not quiet:
                logger.info("\t"+line.rstrip())
            if save_output:
                output.append(line.rstrip())
    if number_of_items:
        pbar.finish()
    return output


def rsync_command(cmd, quiet=False):
    logger.debug(cmd)
    p = Popen(["rsync", "-a", "--delete", "--human-readable",
                          "--info=progress2", "--force"] + cmd,
                         stderr=PIPE,
                         bufsize=1)
    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
    p.communicate()

def readable_size(num):
    for unit in ['b','Kb','Mb','Gb','Tb']:
        if abs(num) < 1024.0:
            return "%3.1f%s" % (num, unit)
        num /= 1024.0
    return num

def get_folder_size(path, excluded_extensions=[]):
    cmd = ["du", "-b", path.as_posix()]
    for ext in excluded_extensions:
        cmd.append("--exclude=*.%s"%ext)
    with Popen(cmd,
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1) as p:
        for line in p.stdout:
            size = line.split()[0].decode("utf8")
    return int(size)


def create_or_check_if_empty(target):
    t = Path(target)
    if not t.exists():
        t.mkdir(parents=True)
        return True
    else:
        return (list(t.glob('*')) == [])


def list_fuse_mounts():
    mounts = []
    with Popen(["mount"],
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1) as p:
        for line in p.stdout:
            if "atticfs" in line or "fuse.bup-fuse" in line:
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


def update_or_create_sync_file(path, backup_name):
    if not path.exists():
        synced = {}
    else:
        synced = yaml.load(open(path.as_posix(), 'r'))
    synced[backup_name] = time.strftime("%Y-%m-%d_%Hh%M")
    yaml.dump(synced, open(path.as_posix(), 'w'), default_flow_style=False)


try:
    # colored input is optionnal
    from colorama import init
    init(autoreset=True)
    from colorama import Fore, Style

    colors = {
                "red": Fore.RED + Style.BRIGHT,
                "green": Fore.GREEN + Style.NORMAL,
                "boldgreen": Fore.GREEN + Style.BRIGHT,
                "blue": Fore.BLUE + Style.NORMAL,
                "boldblue": Fore.BLUE + Style.BRIGHT,
                "yellow": Fore.YELLOW + Style.NORMAL,
                "boldwhite": Fore.WHITE + Style.BRIGHT
             }

    def log(text, display=True, save=True, color=None):
        if display:
            if color in colors:
                print(colors[color]  + text + Style.RESET_ALL)
            else:
                print(text)
        if save:
            logger.debug(text)
except:
    def log(text, display=True, save=True, color=None):
        if display:
            print(text)
        if save:
            logger.debug(text)
