#!/usr/env/python
import os, time, subprocess, sys, datetime, argparse
from pathlib import Path

# CHECKS
from checks import *
from logger import *
from grenierrepo import *

#---CONFIG---------------------------

# config is located next to this script
script_dir = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = Path(script_dir, "grenier.yaml")

#TODO: faire bcp mieux
PASSPHRASE = "courgettebleue!"

#---GRENIER---------------------------

class Grenier(object):
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = None
        self.repositories = []

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        pass
        #print( exc_type+ exc_value+ traceback)

    def open_config(self):
        if self.config_file.exists():
            self.config = yaml.load(open(self.config_file.as_posix(), 'r'))
            for p in list(self.config.keys()):
                bp = GrenierGrenier(p, self.config[p]["backup_dir"])
                sources_dict = self.config[p]["sources"]
                for s in list(sources_dict.keys()):
                    bp.add_source(s,
                                  sources_dict[s]["dir"],
                                  sources_dict[s].get("excluded", []))
                backups_dict = self.config[p]["backups"]
                if "googledrive" in list(backups_dict.keys()):
                    bp.add_google_drive_backend(backups_dict["googledrive"])
                if "hubic" in list(backups_dict.keys()):
                    bp.add_hubic_backend()
                if "disks" in list(backups_dict.keys()):
                    bp.add_disks(backups_dict["disks"])
                self.repositories.append(bp)
        else:
            raise Exception("Invalid configuration file!!")

if __name__ == "__main__":
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

    group_projects = parser.add_argument_group('Backups', 'Manage backups.')
    group_projects.add_argument('-n',
                                '--name',
                                dest='names',
                                action='store',
                                nargs ="+",
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
                                nargs ="+",
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

    if args.names is None:
        print("No project selected. Nothing can be done.")
        sys.exit(-1)

    if args.config and Path(args.config[0]).exists():
        configuration_file = args.config[0]
    else:
        configuration_file = CONFIG_FILE

    if args.fuse:
        try:
            assert Path(args.fuse[0]).exists()
            assert len(args.names) == 1
        except AssertionError as err:
            print("One project (and one only) must be specified with --name,"
               " and the mountpoint must be an existing directory.")
            sys.exit(-1)

    if args.restore:
        try:
            assert len(args.names) == 1
        except AssertionError as err:
            print("One project (and one only) must be specified with --name")
            sys.exit(-1)

    # This is where stuff actually gets done.
    overall_start = time.time()
    with Grenier(configuration_file) as g:
        g.open_config()
        for p in g.repositories:
            if p.name in args.names or args.names == ["all"]:
                logger.info("  == Grenier %s == \n"%p.name)
                logger.debug(p)
                if args.check:
                    p.check_and_repair()
                if args.backup:
                    p.backup()
                if args.backup_target:
                    if "google" in args.backup_target or args.backup_target == ["all"]:
                        p.save_to_google_drive()
                    if "hubic" in args.backup_target or args.backup_target == ["all"]:
                        p.save_to_hubic()
                    for drive in [el for el in args.backup_target if el not in ["google", "hubic", "all"]]:
                        p.save_to_disk(drive)
                if args.fuse:
                    #TODO tester si déjà monté, et alors unfuse
                    p.fuse(args.fuse[0])
                if args.restore:
                    p.restore(args.restore[0])

                # p.save_to_folder("/home/barsanuphe/aubergine/sauvegarde/test/")
                # p.restore_from_google_drive("/home/barsanuphe/aubergine/sauvegarde/test/")

    logger.info("\n+ Everything was done in %.2fs."%(time.time() - overall_start))
