from subprocess import PIPE, Popen, STDOUT
import time
from pathlib import Path
import os

from grenier.logger import *

try:
    import notify2
except ImportError:
    print("No notification framework found.")

import yaml
from progressbar import Bar, Counter, ETA, Percentage, ProgressBar

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


def encfs_command(directory1, directory2, password, reverse=False, quiet=False):
    # TODO: if not reverse, set env for xml path!!!
    # TODO return success, err
    assert directory1 is not None and directory1.exists()
    assert directory2 is not None and directory2.exists()
    cmd = ["encfs", "--standard", "-S", directory1, directory2]
    if reverse:
        cmd.append("--reverse")
    p = Popen(cmd,
              stderr=PIPE,
              bufsize=1)
    p.communicate(password)
    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
    p.communicate()


def backup_encfs_xml(xml_path, repository_name, backup_dir):
    new_path = Path(backup_dir, "%s.xml" % repository_name)
    xml_path.rename(new_path)


def rclone_command(operation, directory=None, container=None, quiet=False):
    # TODO return success, err
    if directory is None and container is None and operation != "config":
        raise Exception("Wrong operation!")
    if operation == "config":
        os.system("rclone config")
    else:
        assert directory is not None and directory.exists()
        assert container is not None
        cmd = ["rclone", operation, "--transfers=16"]
        if operation == "sync":
            cmd.extend([str(directory), container])
        elif operation == "copy":
            cmd.extend([container, str(directory)])
        logger.debug(cmd)
        p = Popen(cmd, stderr=PIPE, bufsize=1)
        for line in iter(p.stderr.readline, b''):
            if not quiet:
                logger.warning("\t !!! " + line.decode("utf8").rstrip())
        p.communicate()


def save_to_cloud(repository_name, backend, directory_path, encfs_mount,
                  password, xml_backup_dir):
    # TODO return success, log
    # reverse encfs mount
    assert create_or_check_if_empty(encfs_mount)
    assert not is_fuse_mounted(encfs_mount)
    encfs_command(directory_path, encfs_mount, password, reverse=True)
    # save xml
    backup_encfs_xml(Path(directory_path, ".encfs6.xml"), repository_name, xml_backup_dir)
    # sync to cloud
    rclone_command("sync", encfs_mount, "%s:%s" % (backend, repository_name))
    # unmount
    umount(encfs_mount)

    return True, "OK"


def restore_from_cloud(repository_name, backend, encfs_path, restore_path,
                       password, xml_backup_dir):
    # TODO return success, log
    # create encfs_path
    encfs_path = Path(encfs_path)
    assert create_or_check_if_empty(encfs_path)
    assert not is_fuse_mounted(encfs_path)
    # rclone copy
    rclone_command("copy", encfs_path, "%s:%s" % (backend, repository_name))
    # find encfs xml
    encfs_xml_path = Path(xml_backup_dir, "%s.xml" % repository_name)
    assert encfs_xml_path.exists()
    # encfs with password to restore_path
    encfs_command(encfs_path, restore_path, password, reverse=False)


def bup_command(cmd, backup_directory, quiet=False, number_of_items=None,
                pbar_title="", save_output=True):
    # TODO return success, err
    logger.debug(cmd)
    env_dict = {"BUP_DIR": str(backup_directory)}
    output = []

    if number_of_items and not quiet:
        cpt = 0
        pbar = generate_pbar(pbar_title, number_of_items).start()

    with Popen(["bup"] + cmd,
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1,
               env=env_dict) as p:
        for line in p.stdout:
            if number_of_items and not quiet:
                cpt += 1
                if cpt < number_of_items:
                    pbar.update(cpt)
            elif not quiet:
                logger.info("\t" + line.decode("utf8").rstrip())
            if save_output:
                output.append(line.decode("utf8").rstrip())
    if number_of_items and not quiet:
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
            size = line.split()[0].decode("utf8")
    return int(size)


def create_or_check_if_empty(target):
    t = Path(target)
    if not t.exists():
        t.mkdir(parents=True)
        return True
    else:
        return list(t.glob('*')) == []


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


def is_fuse_mounted(abs_directory):
    if not abs_directory.is_absolute():
        abs_directory = Path(Path.cwd(), abs_directory)
    return abs_directory in list_fuse_mounts()


def umount(path):
    if not path.is_absolute():
        path = Path(Path.cwd(), path)
    if is_fuse_mounted(path):
        os.system("fusermount -u %s" % path)


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


def update_or_create_sync_file(path, backup_name):
    if not path.exists():
        synced = {}
    else:
        synced = yaml.load(open(path.as_posix(), 'r'))
    synced[backup_name] = time.strftime("%Y-%m-%d_%Hh%M")
    yaml.dump(synced, open(path.as_posix(), 'w'), default_flow_style=False)


