from subprocess import PIPE, Popen, STDOUT
import os
from grenier.logger import *

import notify2
import yaml
from progressbar import Bar, Counter, ETA, Percentage, ProgressBar


# Logging and notifications
# -------------------


def notify_this(text):
    try:
        notify2.init("grenier")
        n = notify2.Notification("Grenier",
                                 text,
                                 "drive-removable-media")
        n.set_timeout(2000)
        n.show()
    except NameError:
        print(text)

try:
    # colored input is optionnal
    from colorama import init

    init(autoreset=True)
    from colorama import Fore, Style

    colors = {
        "red":       Fore.RED + Style.BRIGHT,
        "green":     Fore.GREEN + Style.NORMAL,
        "boldgreen": Fore.GREEN + Style.BRIGHT,
        "blue":      Fore.BLUE + Style.NORMAL,
        "boldblue":  Fore.BLUE + Style.BRIGHT,
        "yellow":    Fore.YELLOW + Style.NORMAL,
        "boldwhite": Fore.WHITE + Style.BRIGHT
    }


    def log(text, display=True, save=True, color=None):
        if display:
            if color in colors:
                print(colors[color] + text + Style.RESET_ALL)
            else:
                print(text)
        if save:
            logger.debug(text)
except ImportError:
    def log(text, display=True, save=True, color=None):
        if display:
            print(text)
        if save:
            logger.debug(text)


def blue(text, display=True):
    log(text, display=display, color="blue")


def green(text, display=True):
    log(text, display=display, color="green")


def red(text, display=True):
    log(text, display=display, color="red")


def yellow(text, display=True):
    log(text, display=display, color="yellow")


def log_cmd(cmd):
    logger.debug(" ".join(cmd))


def generate_pbar(title, number_of_elements):
    widgets = [title,
               Counter(),
               '/%s ' % number_of_elements,
               Percentage(),
               ' ',
               Bar(left='[', right=']', fill='-'),
               ' ',
               ETA()]
    return ProgressBar(widgets=widgets, maxval=number_of_elements).start()


# Filesystem
# -------------------


def readable_size(num):
    for unit in ['b', 'Kb', 'Mb', 'Gb', 'Tb']:
        if abs(num) < 1024.0:
            return "%3.1f%s" % (num, unit)
        num /= 1024.0
    return num


def get_folder_size(path, excluded_extensions=None):
    if not excluded_extensions:
        excluded_extensions = []
    cmd = ["du", "-b", path.as_posix()]
    for ext in excluded_extensions:
        cmd.append("--exclude=*.%s" % ext)
    with Popen(cmd,
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1) as p:
        for line in p.stdout:
            size = line.decode("utf8").split()[0]
    return int(size)


def create_or_check_if_empty(target):
    if not target.exists():
        target.mkdir(parents=True)
        return True
    else:
        return list(target.glob('*')) == []


def list_fuse_mounts():
    mounts = []
    with Popen(["mount"],
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1) as p:
        for line in p.stdout:
            line = line.decode("utf8")
            if "atticfs" in line or "fuse.bup-fuse" in line or "fuse.encfs" in line:
                mounts.append(Path(line.split(" ")[2]))
    return mounts


def absolute_path(path):
    if not path.is_absolute():
        return Path(Path.cwd(), path)
    else:
        return path


def is_fuse_mounted(abs_directory):
    return absolute_path(abs_directory) in list_fuse_mounts()


def umount(path):
    path = absolute_path(path)
    if is_fuse_mounted(path):
        os.system("fusermount -u %s" % path)


# Other things
# -------------------


def backup_encfs_xml(xml_path, repository_name):
    # defaut xml backup location
    # TODO: document in README
    backup_dir = Path(xdg.BaseDirectory.save_data_path("grenier"), "encfs_xml")
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
    new_path = Path(backup_dir, "%s.xml" % repository_name)
    try:
        new_path.write_bytes(xml_path.read_bytes())
        return True
    except FileNotFoundError as err:
        print(err)
        return False


def update_or_create_sync_file(path, backup_name):
    if not path.exists():
        synced = {}
    else:
        with open(path.as_posix(), 'r') as previous_version:
            synced = yaml.load(previous_version)
    synced[backup_name] = time.strftime("%Y-%m-%d_%Hh%M")
    with open(path.as_posix(), 'w') as last_synced_file:
        yaml.dump(synced, last_synced_file, default_flow_style=False)
