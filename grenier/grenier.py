#!/usr/env/python
import os
import time
import sys
import argparse
import shutil
from pathlib import Path

# grenier modules
from grenier.checks import *
from grenier.logger import *
from grenier.repository import *
from grenier.crypto import *

# 3rd party modules
import yaml
import xdg.BaseDirectory

# ---CONFIG---------------------------
CONFIG_FILE = "grenier.yaml"
ENCRYPTION_FLAG = ".encrypted"


# ---GRENIER---------------------------
class Grenier(object):
    def __init__(self, config_file, toggle_encryption=False):
        self.config_file = config_file
        self.toggle_encryption = toggle_encryption
        self.repositories = []
        self.originally_encrypted = False
        self.encrypted_file_flag = Path(self.config_file.parent,
                                        ENCRYPTION_FLAG)
        self.cipher = None
        self.reencrypted = False

    def is_config_file_encrypted(self):
        first_check = (type(yaml.load(open(self.config_file.as_posix(),
                                           'r'))) == str)
        second_check = Path(self.config_file.parent, ENCRYPTION_FLAG).exists()
        return first_check and second_check

    def __enter__(self):
        if self.is_config_file_encrypted():
            self.originally_encrypted = True
            print("Decrypting config file.")
            # sauvegarde du crypté
            shutil.copyfile(self.config_file.as_posix(),
                            "%s_backup" % self.config_file.as_posix())
            self.cipher = AESCipher()
            self.cipher.decrypt_file(self.config_file.as_posix())
            if self.encrypted_file_flag.exists():
                os.remove(self.encrypted_file_flag.as_posix())
        else:
            self.originally_encrypted = False
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            print("\nGot interrupted. Trying to clean up.")
            self.encrypt_if_necessary()

    def encrypt_if_necessary(self):
        if not self.reencrypted:
            # encrypt config if necessary
            if (not self.originally_encrypted and self.toggle_encryption) or \
               (self.originally_encrypted and not self.toggle_encryption):
                logger.info("Encrypting config file.")
                if self.cipher is None:
                    self.cipher = AESCipher()
                self.cipher.encrypt_file(self.config_file.as_posix())
                open(self.encrypted_file_flag.as_posix(), 'a').close()
                self.reencrypted = True

    def open_config(self):
        if self.config_file.exists():
            try:
                config = yaml.load(open(self.config_file.as_posix(), 'r'))
                for p in list(config.keys()):
                    bp = GrenierRepository(p,
                                           config[p]["backup_dir"],
                                           config[p].get("passphrase", None))
                    sources_dict = config[p]["sources"]
                    for s in list(sources_dict.keys()):
                        bp.add_source(s,
                                      sources_dict[s]["dir"],
                                      sources_dict[s].get("excluded", []))
                    remotes = config[p]["backups"]
                    if "googledrive" in list(remotes.keys()):
                        bp.add_google_drive_backend(remotes["googledrive"])
                    if "hubic" in list(remotes.keys()):
                        bp.add_hubic_backend()
                    if "disks" in list(remotes.keys()):
                        bp.add_disks(remotes["disks"])
                    self.repositories.append(bp)
                self.encrypt_if_necessary()
                return True
            except Exception as err:
                print("Invalid configuration file!!")
                print(err)
                return False
        else:
            print("No configuration file found!")
            return False


def main():
    logger.info("\n# # # G R E N I E R # # #\n")

    parser = argparse.ArgumentParser(description='Grenier.\nA wrapper around '
                                     'attic and duplicity to back stuff up.')

    group_config = parser.add_argument_group('Configuration',
                                             'Manage configuration files.')
    group_config.add_argument('--config',
                              dest='config',
                              action='store',
                              metavar="CONFIG_FILE",
                              nargs=1,
                              help='Use an alternative configuration file.')
    group_config.add_argument('--encrypt',
                              dest='encrypt',
                              action='store_true',
                              default=False,
                              help='Toggle encryption on the configuration '
                                   'file.')

    group_projects = parser.add_argument_group('Backups', 'Manage backups.')
    group_projects.add_argument('-n',
                                '--name',
                                dest='names',
                                action='store',
                                nargs="+",
                                metavar="BACKUP_NAME",
                                help='specify backup names, or "all".')
    group_projects.add_argument('-b',
                                '--backup',
                                dest='backup',
                                action='store_true',
                                default=False,
                                help='backup selected projects.')
    group_projects.add_argument('-s',
                                '--sync',
                                dest='backup_target',
                                action='store',
                                nargs="+",
                                metavar="BACKUP_TARGET_NAME",
                                help='backup selected projects to the cloud or'
                                     'usb drives, or to "all".')
    group_projects.add_argument('-c',
                                '--check',
                                dest='check',
                                action='store_true',
                                default=False,
                                help='check and repair selected backups.')
    group_projects.add_argument('-f',
                                '--fuse',
                                dest='fuse',
                                action='store',
                                metavar="MOUNT_POINT",
                                nargs=1,
                                help='Mount/unmount a specified backup '
                                     'to a mountpoint.')
    group_projects.add_argument('-r',
                                '--restore',
                                dest='restore',
                                action='store',
                                metavar="RESTORE_DIRECTORY",
                                nargs=1,
                                help='Restore latest to this directory.')

    args = parser.parse_args()
    logger.debug(args)

    if args.names is None:
        print("No project selected. Nothing can be done.")
        sys.exit(-1)

    if args.config and Path(args.config[0]).exists():
        configuration_file = args.config[0]
    else:
        config_path = xdg.BaseDirectory.save_config_path("grenier")
        configuration_file = Path(config_path, CONFIG_FILE)
        try:
            assert configuration_file.exists()
        except:
            print("No configuration file found at %s" % configuration_file)
            sys.exit(-1)

    if args.fuse:
        try:
            assert Path(args.fuse[0]).exists()
            assert len(args.names) == 1
        except AssertionError:
            print("One project (and one only) must be specified with --name,"
                  " and the mountpoint must be an existing directory.")
            sys.exit(-1)

    if args.restore:
        try:
            assert len(args.names) == 1
        except AssertionError:
            print("One project (and one only) must be specified with --name")
            sys.exit(-1)

    # This is where stuff actually gets done.
    overall_start = time.time()
    try:
        with Grenier(configuration_file, args.encrypt) as g:
            if not g.open_config():
                print("Invalid configuration. Exiting.")
                if g.originally_encrypted:
                    print("Bad encryption passphrase maybe?"
                          "Manually restore the backup.")
                sys.exit(-1)
            for p in g.repositories:
                if p.name in args.names or args.names == ["all"]:
                    logger.info("+++ Working on %s +++\n" % p.name)
                    logger.debug(p)
                    if args.check:
                        p.check_and_repair()
                    if args.backup:
                        p.backup()
                    if args.backup_target:
                        if "google" in args.backup_target or \
                           args.backup_target == ["all"]:
                            p.save_to_google_drive()
                        if "hubic" in args.backup_target or \
                           args.backup_target == ["all"]:
                            p.save_to_hubic()
                        # finding what drives to back up
                        if args.backup_target == ["all"]:
                            drives_to_backup = p.backup_disks
                        else:
                            drives_to_backup = [d for d in args.backup_target
                                                if d in p.backup_disks]
                        for drive in drives_to_backup:
                            p.save_to_disk(drive)
                    if args.fuse:
                        if is_fuse_mounted(args.fuse[0]):
                            p.unfuse(args.fuse[0])
                        else:
                            p.fuse(args.fuse[0])
                    if args.restore:
                        p.restore(args.restore[0])

        overall_time = time.time() - overall_start
        logger.info("\n+ Everything was done in %.2fs." % overall_time)
        notify_this("Everything was done in %.2fs." % overall_time)

    except KeyboardInterrupt:
        overall_time = time.time() - overall_start
        logger.error("\n+ Got interrupted after %.2fs." % overall_time)
        sys.exit()

if __name__ == "__main__":
    main()
