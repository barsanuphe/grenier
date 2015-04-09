import os, time, subprocess, sys, datetime, argparse, re, getpass
from pathlib import Path

from attic.archiver import Archiver

from logger import *
from helpers import *

class GrenierSource(object):
    def __init__(self, name, target_dir, format_list=[]):
        self.name = name
        self.target_dir = target_dir
        self.excluded_extensions = format_list


class GrenierRepo(object):
    def __init__(self, name, backup_dir, passphrase=None):
        self.name = name
        self.backup_dir = Path(backup_dir)
        if not self.backup_dir.exists():
            logger.info("+ Creating folder %s" % self.backup_dir)
            self.backup_dir.mkdir(parents=True)
        self.fuse_dir = None
        self.sources = []
        self.google_address = None
        self.hubic_credentials = None
        self.backup_disks = []
        self.passphrase = passphrase

    def add_source(self, name, target_dir, excluded=[]):
        self.sources.append(GrenierSource(name, target_dir, excluded))

    def init(self):
        if create_or_check_if_empty(self.backup_dir):
            logger.info("+ Initializing repository.")
            self.do_init()

    def save(self):
        for source in self.sources:
            self.do_save(source)

    def check_and_repair(self):
        logger.info("+ Checking and repairing repository.")
        self.do_check()

    def backup(self, check_before=False):
        starting_time = time.time()
        self.init()
        if check_before:
            self.check_and_repair()
        self.save()
        logger.info("+ Backup done in %.2fs."%(time.time() - starting_time))

    def restore(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty, not doing anything."%target)
            sys.exit(-1)
        for source in self.sources:
            logger.info("+ Restoring %s to %s."%(source.name, target))
            self.do_restore(source, target)

    def fuse(self, folder):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            logger.info("+ Mounting repository to %s."%(folder))
            self.do_fuse(folder)
    def unfuse(self, folder=None):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            logger.info("+ Unmounting repository from %s."%(folder))
            os.system("fusermount -u %s"%self.fuse_dir)

    def add_google_drive_backend(self, address):
        # check address
        if re.match("[^@]+@gmail.com", address):
            self.google_address = address
    @property
    def has_valid_google_address(self):
        return self.google_address is not None
    def save_to_google_drive(self):
        if self.has_valid_google_address:
            start = time.time()
            logger.info("+ Syncing with google drive.")
            duplicity_command([self.backup_dir.as_posix(), "gdocs://%s/bupdup/%s"%(self.google_address, self.name)], self.passphrase)
            logger.info("+ Synced in %.2fs."%(time.time() - start))
    def restore_from_google_drive(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty, not doing anything."%target)
            sys.exit(-1)
        if self.has_valid_google_address:
            logger.info("+ Restoring from google drive.")
            duplicity_command(["gdocs://%s/bupdup/%s" % (self.google_address, self.name), target], self.passphrase)

    def add_hubic_backend(self):
        # TODO: manage credentials
        self.hubic_credentials = True
    def save_to_hubic(self):
        # TODO aller chercher credentials dans config
        if self.hubic_credentials:
            start = time.time()
            logger.info("+ Syncing with hubic.")
            duplicity_command([self.backup_dir.as_posix(), "cf+hubic://%s"%self.name], self.passphrase)
            logger.info("+ Synced in %.2fs."%(time.time() - start))
    def restore_from_hubic(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty, not doing anything."%target)
            sys.exit(-1)
        # TODO aller chercher credentials dans config
        logger.info("+ Restoring from hubic.")
        duplicity_command(["cf+hubic://%s"%self.name, target], self.passphrase)

    def add_disks(self, disks_list):
        self.backup_disks = disks_list
    def save_to_disk(self, disk_name):
        if self.backup_disks and disk_name in self.backup_disks:
            mount_point = "/run/media/%s/%s"%(getpass.getuser(), disk_name)
            if not Path(mount_point).exists():
                logger.error("Drive %s is not mounted."%disk_name)
                sys.exit(-1)
            else:
                self.save_to_folder(Path(mount_point, self.name))

    def save_to_folder(self, target):
        path = Path(target)
        if not path.is_absolute():
            logger.error("Directory %s is not an absolute path,"
                         "nothing will be done." % path)
        else:
            logger.info("+ Syncing with %s."%path)
            if not path.exists():
                path.mkdir(parents=True)
            duplicity_command([self.backup_dir.as_posix(), path.as_uri()],
                              self.passphrase)
    def restore_from_folder(self, folder, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty, not doing anything."%target)
            sys.exit(-1)
        if not Path(target).is_absolute():
            logger.error("Directory %s is not an absolute path, nothing will be done."%target)
            sys.exit(-1)
        else:
            logger.info("+ Restoring from %s to %s."%(folder, target))
            duplicity_command([Path(folder).as_uri(), target], self.passphrase)

    def __str__(self):
        txt = "++ Project %s\n"%self.name
        txt += "\tBup Dir: %s\n"%self.backup_dir
        txt += "\tSources:\n"
        for source in self.sources:
            txt += "\t\t%s (%s) [exluded: %s]\n" % (source.name,
                                                    source.target_dir,
                                                    source.excluded_extensions)
        txt += "\tBackups:\n"
        if self.has_valid_google_address:
            txt += "\t\tGoogle Drive (%s)\n"%(self.google_address)
        if self.hubic_credentials is not None:
            txt += "\t\tHubic\n"
        for d in self.backup_disks:
            txt += "\t\tDisk (%s)\n"%d
        return txt

class GrenierBup(GrenierRepo):
    def __init__(self, name, backup_dir):
        super().__init__(name, backup_dir)
        self.bup = "bup -d %s"%self.backup_dir

    def do_init(self):
        os.system("%s init"%self.bup)

    def do_save(self, source):
        logger.info("+ Indexing source directory %s."%source.target_dir)
        if source.excluded_extensions != []:
            os.system('%s index %s --exclude-rx="^.*\.(%s)$"'%(self.bup, source.target_dir, "|".join(source.excluded_extensions)))
        else:
            os.system('%s index %s'%(self.bup, source.target_dir))
        logger.info("+ Saving source directory %s to %s."%(source.target_dir, self.backup_dir))
        os.system('%s save %s -n %s --strip-path=%s -9'%(self.bup, source.target_dir, source.name, source.target_dir))
        logger.info("+ Generating par2 files for repository.")
        os.system("%s fsck -g -j9"%self.bup)

    def do_check(self):
        os.system("%s fsck -r -j9"%self.bup)

    def do_restore(self, source, target):
        os.system("%s restore -C %s /%s/latest/." % (self.bup, target, source.name))

    def do_fuse(self, folder):
        os.system("%s fuse %s"%(self.bup, folder))


class GrenierGrenier(GrenierRepo):

    def __init__(self, name, backup_dir, passphrase):
        super().__init__(name, backup_dir, passphrase)
        self.attic = Archiver()

    def do_init(self):
        #TODO mettre les bonnes options
        attic_command(["init", self.backup_dir.as_posix(), "--encryption=passphrase"], self.passphrase)

    def do_save(self, source):
        logger.info("+ Saving source directory %s to %s."%(source.target_dir, self.backup_dir))
        excluded = []
        for excl in source.excluded_extensions:
            excluded.extend(["--exclude", "*.%s"%excl])

        attic_command(["create", '--do-not-cross-mountpoints', "--stats", "%s::%s_%s"%(self.backup_dir, time.strftime("%Y-%m-%d_%Hh%M"), source.name), source.target_dir] + excluded, self.passphrase)

    def do_check(self):
        #TODO repair is experimental?  "--repair",
        attic_command(["check", "-v", "--repository-only", self.backup_dir.as_posix()], self.passphrase)

    def do_restore(self, source, target):
        origin = os.getcwd()

        # get latest archive name for source.name
        archives = attic_command(["list", self.backup_dir.as_posix()], self.passphrase, quiet=True)
        archives = [el.split(" ")[0].strip() for el in archives if el.split(" ")[0].strip().split("_")[-1] == source.name]
        archives.sort()
        latest_archive_name = archives[-1]

        # create target/source.name
        p = Path(target, latest_archive_name)
        if not create_or_check_if_empty(p):
            logger.error("Target %s cannot be created or is not empty. Not doing anything."%p)
            sys.exit(-1)
        # cd to this
        os.chdir(p.as_posix())
        attic_command(["extract", "-v", "%s::%s"%(self.backup_dir, latest_archive_name)], self.passphrase)
        os.chdir(origin)

    def do_fuse(self, folder):
        attic_command(["mount", "-v", self.backup_dir.as_posix(), folder], self.passphrase)
