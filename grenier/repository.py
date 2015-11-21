import os
import time
import sys
import getpass
from pathlib import Path
import xdg.BaseDirectory

from grenier.logger import *
from grenier.helpers import *


class GrenierSource(object):
    def __init__(self, name, target_dir, format_list=None):
        self.name = name
        self.target_dir = Path(target_dir)
        if format_list:
            self.excluded_extensions = format_list
        else:
            self.excluded_extensions = []


class GrenierRemote(object):
    def __init__(self, name):
        self.name = name
        self.is_directory = False
        self.is_disk = False
        self.is_cloud = False
        self.is_cloud_configured = False

        if Path(name).is_absolute():
            self.full_path = Path(name)
            self.is_directory = True
        elif Path("/run/media/%s/%s" % (getpass.getuser(), name)).exists():
            self.full_path = Path("/run/media/%s/%s" % (getpass.getuser(), name))
            self.is_disk = True
        else:  # out of options...
            self.is_cloud = True
            # TODO: parse rclone ini file to see if defined
            # TODO: if not, call rclone config

    def __str__(self):
        if self.is_directory:
            return "%s (dir)" % self.name
        elif self.is_disk:
            return "%s (disk)" % self.name
        elif self.is_cloud:
            return "%s (cloud)" % self.name
        else:
            return "%s (unknown)" % self.name


class GrenierRepository(object):
    def __init__(self, name, backup_dir, temp_dir, passphrase=None):
        self.name = name
        self.temp_dir = temp_dir
        if not self.temp_dir.exists():
            logger.info("+ Creating folder %s" % self.temp_dir)
            self.temp_dir.mkdir(parents=True)
        self.backup_dir = backup_dir
        if not self.backup_dir.exists():
            logger.info("+ Creating folder %s" % self.backup_dir)
            self.backup_dir.mkdir(parents=True)
        self.fuse_dir = None

        self.sources = []
        self.remotes = []

        self.google_configured = None
        self.hubic_configured = None
        self.backup_disks = []
        self.passphrase = passphrase
        self.just_synced = []

    def add_source(self, name, target_dir, excluded=None):
        self.sources.append(GrenierSource(name, target_dir, excluded))

    def add_remotes(self, remote_list):
        for remote in remote_list:
            self.remotes.append(GrenierRemote(remote))

    def sync_remote(self, remote_name):
        remote_found = False
        for remote in self.remotes:
            if remote.name == remote_name:
                remote_found = True
                # TODO sync according to type !!!!!
                if remote.is_cloud:
                    self.save_to_cloud(remote)
                elif remote.is_disk or remote.is_directory:
                    self.save_to_folder(remote)
                else:
                    log("Unknown remote %s, maybe unmounted disk. "
                        "Not doing anything." % remote.name, color="red")
                break
        if not remote_found:
            print("Remote %s not found!!!" % remote_name)

    def init(self):
        if create_or_check_if_empty(self.backup_dir):
            log("+ Initializing repository.", color="yellow")
            bup_command(["init"], self.backup_dir, quiet=True)

    def check_and_repair(self):
        log("+ Checking and repairing repository.", color="yellow")
        self._fsck(generate=False)

    def backup(self, check_before=False):
        starting_time = time.time()
        self.init()
        if check_before:
            self.check_and_repair()
        self.save()
        log("+ Backup done in %.2fs." % (time.time() - starting_time),
            color="green")

    def restore(self, target):
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red")
            sys.exit(-1)
        for source in self.sources:
            log("+ Restoring %s to %s." % (source.name, target), color="yellow")
            bup_command(["restore", "-C", target, "/%s/latest/." % source.name],
                        self.backup_dir,
                        quiet=False)

    def fuse(self, folder):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            log("+ Mounting repository to %s." % folder, color="yellow")
            bup_command(["fuse", folder], self.backup_dir, quiet=False)

    def unfuse(self, folder=None):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            log("+ Unmounting repository from {folder}.".format(folder=self.fuse_dir),
                color="yellow")
            umount(self.fuse_dir)

    def save_to_folder(self, grenier_remote):
        log("+ Syncing with %s." % grenier_remote.name, color="yellow")
        if not grenier_remote.full_path.exists():
            grenier_remote.full_path.mkdir(parents=True)
        start = time.time()
        rsync_command([str(self.backup_dir), str(grenier_remote.full_path)])
        update_or_create_sync_file(Path(grenier_remote.full_path, "last_synced.yaml"),
                                   self.name)
        log("+ Synced in %.2fs." % (time.time() - start), color="green")
        self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
        # TODO return rsync success
        return True

    def save_to_cloud(self, grenier_remote):
        # check if configured
        if grenier_remote.is_cloud and grenier_remote.is_configured:
            start = time.time()
            log("+ Syncing with %s." % grenier_remote.name, color="yellow")
            # TODO!! dosser xdg
            encfs_xml_dir = "encryption_info_dir"
            success, err_log = save_to_cloud(self.name,
                                             grenier_remote.name,
                                             self.backup_dir,
                                             self.temp_dir,
                                             self.passphrase,
                                             encfs_xml_dir)
            if success:
                self.just_synced.append({grenier_remote.name : time.strftime("%Y-%m-%d_%Hh%M")})
                log("+ Synced in %.2fs." % (time.time() - start), color="green")
            else:
                log("!! Error! %s" % err_log, color="red")

    def restore_from_google_drive(self, target):
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red")
            sys.exit(-1)
        if self.google_configured:
            log("+ Restoring from google drive.", color="yellow")
            # TODO with rclone

    def restore_from_hubic(self, target):
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red")
            sys.exit(-1)
        # TODO aller chercher credentials dans config
        log("+ Restoring from hubic.", color="yellow")
        start = time.time()
        if self.hubic_configured:
            # TODO!! dosser xdg
            encfs_xml_dir = "encryption_info_dir"
            success, err_log = restore_from_cloud(self.name,
                                                  "hubic",
                                                  self.temp_dir,
                                                  target,
                                                  self.passphrase,
                                                  encfs_xml_dir)
            if success:
                log("+ Downloaded from hubic in %.2fs." % (time.time() - start), color="green")
                # TODO: restore bup versions
            else:
                log("!! Error! %s" % err_log, color="red")

    def restore_from_folder(self, folder, target):
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red")
        elif not Path(target).is_absolute():
            log("!! Directory %s is not an absolute path,"
                " nothing will be done." % target, color="red")
        else:
            log("+ Restoring from %s to %s." % (folder, target), color="yellow")
            # TODO with rsync actually!!!
            # duplicity_command([Path(folder).as_uri(), target], self.passphrase)

    def __str__(self):
        txt = "++ Repository %s\n" % self.name
        txt += "\tBup Dir: %s\n" % self.backup_dir
        txt += "\tSources:\n"
        for source in self.sources:
            if source.excluded_extensions:
                txt += "\t\t%s (%s) [exluded: %s]\n" % (source.name,
                                                        source.target_dir,
                                                        source.excluded_extensions)
            else:
                txt += "\t\t%s (%s)\n" % (source.name,
                                          source.target_dir)
        txt += "\tRemotes:\n"
        for remote in self.remotes:
            txt += "\t\t- {remote}\n".format(remote=remote)
        return txt

    def _index(self, source):
        log("+ Indexing.", color="yellow")
        cmd = ["index", "-vv", source.target_dir.as_posix()]
        if source.excluded_extensions:
            cmd.append('--exclude-rx="^.*\.(%s)$"' % "|".join(source.excluded_extensions))
        output = bup_command(cmd, self.backup_dir, quiet=True)
        return len(output)

    def _fsck(self, generate=False):
        if generate:
            log("+ Generating redundancy files.", color="yellow")
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
            total_number_of_files += self._save(source)
        new_size = get_folder_size(self.backup_dir)
        delta = new_size - original_size
        log("+ Backed up %s files." % total_number_of_files, color="green")
        log("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                    readable_size(delta)),
            color="green")

    def _save(self, source):
        log(">> %s -> %s." % (source.target_dir, self.backup_dir), color="blue")
        number_of_files = self._index(source)
        log("+ Saving.", color="yellow")
        bup_command(["save", "-vv",
                     source.target_dir.as_posix(),
                     "-n", source.name,
                     '--strip-path=%s' % source.target_dir.as_posix(),
                     '-9'],
                    self.backup_dir,
                    quiet=False,
                    number_of_items=number_of_files,
                    pbar_title="Saving: ",
                    save_output=False)
        self._fsck(generate=True)
        return number_of_files
