import os
import time
import sys
import re
import getpass
from pathlib import Path
import xdg.BaseDirectory

from grenier.logger import *
from grenier.helpers import *


class GrenierSource(object):
    def __init__(self, name, target_dir, format_list=[]):
        self.name = name
        self.target_dir = Path(target_dir)
        self.excluded_extensions = format_list


class GrenierRepository(object):
    def __init__(self, name, backup_dir, passphrase=None):
        self.name = name
        self.backup_dir = backup_dir
        if not self.backup_dir.exists():
            logger.info("+ Creating folder %s" % self.backup_dir)
            self.backup_dir.mkdir(parents=True)
        self.fuse_dir = None
        self.sources = []
        self.google_address = None
        self.hubic_credentials = None
        self.backup_disks = []
        self.passphrase = passphrase
        self.just_synced = []

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
        logger.info("+ Backup done in %.2fs." % (time.time() - starting_time))

    def restore(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty,"
                         " not doing anything." % target)
            sys.exit(-1)
        for source in self.sources:
            logger.info("+ Restoring %s to %s." % (source.name, target))
            self.do_restore(source, target)

    def fuse(self, folder):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            logger.info("+ Mounting repository to %s." % (folder))
            self.do_fuse(folder)

    def unfuse(self, folder=None):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            logger.info("+ Unmounting repository from %s." % (folder))
            os.system("fusermount -u %s" % self.fuse_dir)

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
            duplicity_command([self.backup_dir.as_posix(),
                               "gdocs://%s/grenier/%s" % (self.google_address,
                                                          self.name)],
                              self.passphrase)
            self.just_synced.append({"google": time.strftime("%Y-%m-%d_%Hh%M")})
            logger.info("+ Synced in %.2fs." % (time.time() - start))

    def restore_from_google_drive(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty,"
                         " not doing anything." % target)
            sys.exit(-1)
        if self.has_valid_google_address:
            logger.info("+ Restoring from google drive.")
            duplicity_command(["gdocs://%s/grenier/%s" % (self.google_address,
                                                          self.name), target],
                              self.passphrase)

    def add_hubic_backend(self):
        # TODO: manage credentials
        self.hubic_credentials = True

    def save_to_hubic(self):
        # TODO aller chercher credentials dans config
        if self.hubic_credentials:
            start = time.time()
            logger.info("+ Syncing with hubic.")
            duplicity_command([self.backup_dir.as_posix(),
                               "cf+hubic://%s" % self.name],
                              self.passphrase)
            self.just_synced.append({"hubic": time.strftime("%Y-%m-%d_%Hh%M")})
            logger.info("+ Synced in %.2fs." % (time.time() - start))

    def restore_from_hubic(self, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty,"
                         " not doing anything." % target)
            sys.exit(-1)
        # TODO aller chercher credentials dans config
        logger.info("+ Restoring from hubic.")
        duplicity_command(["cf+hubic://%s" % self.name, target],
                          self.passphrase)

    def add_disks(self, disks_list):
        self.backup_disks = disks_list

    def save_to_disk(self, disk_name):
        if self.backup_disks and disk_name in self.backup_disks:
            mount_point = Path("/run/media/%s/%s" % (getpass.getuser(),
                                                     disk_name))
            if not mount_point.exists():
                logger.error("!! Drive %s is not mounted." % disk_name)
            else:
                if self.save_to_folder(mount_point):
                    self.just_synced.append({disk_name: time.strftime("%Y-%m-%d_%Hh%M")})

    def save_to_folder(self, target):
        path = Path(target)
        if not path.is_absolute():
            logger.error("Directory %s is not an absolute path,"
                         "nothing will be done." % path)
            return False
        else:
            logger.info("+ Syncing with %s." % path)
            if not path.exists():
                path.mkdir(parents=True)
            start = time.time()
            rsync_command([self.backup_dir.as_posix(), path.as_posix()])
            update_or_create_sync_file(Path(path, "last_synced.yaml"),
                                       self.name)
            logger.info("+ Synced in %.2fs." % (time.time() - start))
            return True

    def restore_from_folder(self, folder, target):
        if not create_or_check_if_empty(target):
            logger.error("Directory %s is not empty,"
                         " not doing anything." % target)
        elif not Path(target).is_absolute():
            logger.error("!! Directory %s is not an absolute path,"
                         " nothing will be done." % target)
        else:
            logger.info("+ Restoring from %s to %s." % (folder, target))
            duplicity_command([Path(folder).as_uri(), target], self.passphrase)

    def __str__(self):
        txt = "++ Repository %s\n" % self.name
        txt += "\tBup Dir: %s (%s)\n" % (self.backup_dir,
                                         get_folder_size(self.backup_dir))
        txt += "\tSources:\n"
        for source in self.sources:
            source_size = get_folder_size(source.target_dir,
                                          source.excluded_extensions)
            if source.excluded_extensions != []:
                txt += "\t\t%s (%s) (%s) [exluded: %s]\n" % (source.name,
                                                    source.target_dir,
                                                    source_size,
                                                    source.excluded_extensions)
            else:
                txt += "\t\t%s (%s) (%s)\n" % (source.name,
                                               source.target_dir,
                                               source_size)
        txt += "\tBackups:\n"
        if self.has_valid_google_address:
            txt += "\t\tGoogle Drive\n"
        if self.hubic_credentials is not None:
            txt += "\t\tHubic\n"
        if self.backup_disks != []:
            txt += "\t\tDisks: %s" % (" ".join(self.backup_disks))
        return txt

    def do_init(self):
        # TODO add options when/if merge-all becomes official
        attic_command(["init", self.backup_dir.as_posix(),
                       "--encryption=passphrase"],
                      self.passphrase)

    def do_save(self, source):
        logger.info("+ Saving source directory %s to %s." % (source.target_dir,
                                                             self.backup_dir))
        excluded = []
        for excl in source.excluded_extensions:
            excluded.extend(["--exclude", "*.%s" % excl])

        attic_command(["create", '--do-not-cross-mountpoints', "--stats",
                       "%s::%s_%s" % (self.backup_dir,
                                      time.strftime("%Y-%m-%d_%Hh%M"),
                                      source.name),
                       source.target_dir.as_posix()] + excluded,
                      self.passphrase)

    def do_check(self):
        attic_command(["check", "-v", self.backup_dir.as_posix()],
                      self.passphrase)

    def do_restore(self, source, target):
        origin = os.getcwd()

        # get latest archive name for source.name
        archives = attic_command(["list", self.backup_dir.as_posix()],
                                 self.passphrase, quiet=True)
        archives = [el.split(" ")[0].strip() for el in archives
                    if el.split(" ")[0].strip().split("_")[-1] == source.name]
        archives.sort()
        latest_archive_name = archives[-1]

        # create target/source.name
        p = Path(target, latest_archive_name)
        if not create_or_check_if_empty(p):
            logger.error("Target %s cannot be created or is not empty."
                         "Not doing anything." % p)
            sys.exit(-1)
        # cd to this
        os.chdir(p.as_posix())
        attic_command(["extract", "-v",
                       "%s::%s" % (self.backup_dir, latest_archive_name)],
                      self.passphrase)
        os.chdir(origin)

    def do_fuse(self, folder):
        attic_command(["mount", "-v", self.backup_dir.as_posix(), folder],
                      self.passphrase)


class GrenierBupRepository(GrenierRepository):
    def __init__(self, name, backup_dir, passphrase=None):
        super().__init__(name, backup_dir, passphrase)

    def do_init(self):
        bup_command(["init"], self.backup_dir, quiet=True)

    def do_index(self, source):
        logger.info("+ Indexing.")
        cmd = ["index", "-vv", source.target_dir.as_posix()]
        if source.excluded_extensions != []:
            cmd.append('--exclude-rx="^.*\.(%s)$"' % "|".join(source.excluded_extensions))
        output = bup_command(cmd, self.backup_dir, quiet=True)
        return len(output)

    def do_fsck(self, generate=False):
        if generate:
            logger.info("+ Generating redundancy files.")
        else:
            logger.info("+ Checking (and repairing) repository.")
        # get number of .pack files
        # each .pack has its own par2 files
        repository_objects = Path(self.backup_dir, "objects", "pack")
        packs = [el
                 for el in repository_objects.iterdir()
                 if el.suffix == ".pack"]
        cmd = ["fsck", "-v", "-j8"]
        if generate:
            cmd.append("-g")
            title = "Generating: "
        else:
            cmd.append("-r")
            title = "Checking: "
        bup_command(cmd, self.backup_dir, quiet=True,
                    number_of_items=len(packs),
                    pbar_title=title,
                    save_output=False)

    def save(self):
        original_size = get_folder_size(self.backup_dir)
        total_number_of_files = 0
        for source in self.sources:
            total_number_of_files += self.do_save(source)
        new_size = get_folder_size(self.backup_dir)
        delta = new_size - original_size
        logger.info("+ Backed up %s files." % total_number_of_files)
        logger.info("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                            readable_size(delta)))

    def do_save(self, source):
        logger.info("+ %s -> %s."%(source.target_dir,
                                              self.backup_dir))

        number_of_files = self.do_index(source)
        logger.info("+ Saving.")
        bup_command(["save", "-vv",
                     source.target_dir.as_posix(),
                     "-n", source.name,
                     '--strip-path=%s'%source.target_dir.as_posix(),
                     '-9'],
                    self.backup_dir,
                    quiet=False,
                    number_of_items=number_of_files,
                    pbar_title="Saving: ",
                    save_output=False)
        self.do_fsck(generate=True)
        return number_of_files

    def do_check(self):
        self.do_fsck(generate=False)

    def do_restore(self, source, target):
        bup_command(["restore", "-C", target, "/%s/latest/."%source.name],
                    self.backup_dir,
                    quiet=False)

    def do_fuse(self, folder):
        bup_command(["fuse", folder], self.backup_dir, quiet=False)
