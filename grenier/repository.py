import sys
import getpass
from configparser import ConfigParser
from grenier.logger import *
from grenier.helpers import *
from grenier.commands import *


class GrenierSource(object):
    def __init__(self, name, target_dir, format_list=None):
        self.name = name
        self.target_dir = Path(target_dir)
        if format_list:
            self.excluded_extensions = format_list
        else:
            self.excluded_extensions = []


class GrenierRemote(object):
    def __init__(self, name, rclone_config_file):
        self.name = name
        self.is_directory = False
        self.is_disk = False
        self.is_cloud = False
        self.full_path = None

        if Path(name).is_absolute():
            self.full_path = Path(name)
            self.is_directory = True
        elif Path("/run/media/%s/%s" % (getpass.getuser(), name)).exists():
            self.full_path = Path("/run/media/%s/%s" % (getpass.getuser(), name))
            self.is_disk = True
        else:  # out of options...
            # check if known rclone remote
            conf = ConfigParser()
            conf.read(str(rclone_config_file))
            self.is_cloud = self.name in conf.sections()

    @property
    def is_known(self):
        return self.is_cloud or self.is_directory or self.is_disk

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
    def __init__(self, name, backup_dir, temp_dir, rclone_config_file, passphrase=None):
        self.name = name
        self.rclone_config_file = rclone_config_file
        self.temp_dir = temp_dir
        if not self.temp_dir.exists():
            logger.debug("+ Creating folder %s" % self.temp_dir)
            self.temp_dir.mkdir(parents=True)
        self.backup_dir = backup_dir
        if not self.backup_dir.exists():
            logger.debug("+ Creating folder %s" % self.backup_dir)
            self.backup_dir.mkdir(parents=True)
        self.fuse_dir = None
        self.sources = []
        self.remotes = []
        self.passphrase = passphrase
        self.just_synced = []

    def add_source(self, name, target_dir, excluded=None):
        self.sources.append(GrenierSource(name, target_dir, excluded))

    def add_remotes(self, remote_list):
        for remote in remote_list:
            self.remotes.append(GrenierRemote(remote, self.rclone_config_file))

    def init(self, display=True):
        if create_or_check_if_empty(self.backup_dir):
            log("+ Initializing repository.", color="yellow", display=display)
            return init_repository(self.backup_dir, display=False)
        else:
            return True, "Repository already exists."

    def check_and_repair(self, display=True):
        log("+ Checking and repairing repository.", color="yellow", display=display)
        return fsck_files(self.backup_dir, generate=False, display=display)

    def save(self, check_before=False, display=True):
        starting_time = time.time()
        init_success, errlog = self.init(display)
        if not init_success:
            log("!!! %s " % errlog, color="red", display=display)
            return False, 0
        else:
            if check_before:
                self.check_and_repair(display)
            success, total_number_of_files = self.save_repository(display)
            if success:
                log("+ Backup done in %.2fs." % (time.time() - starting_time),
                    color="green", display=display)
            return success, total_number_of_files

    def save_repository(self, display=True):
        original_size = get_folder_size(self.backup_dir)
        total_number_of_files = 0
        for source in self.sources:
            success, number_of_files = self._save_source(source, display)
            if success:
                total_number_of_files += number_of_files
            else:
                log("!!! Error saving source %s, stopping." % source.name, color="red")
                return False, total_number_of_files
        new_size = get_folder_size(self.backup_dir)
        delta = new_size - original_size
        log("+ Backed up %s files." % total_number_of_files, color="green", display=display)
        log("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                    readable_size(delta)),
            color="green", display=display)
        return True, total_number_of_files

    def _save_source(self, source, display=True):
        log(">> %s -> %s." % (source.target_dir, self.backup_dir), color="blue", display=display)
        log("+ Indexing.", color="yellow", display=display)
        index_success, number_of_files = index_files(source, self.backup_dir)
        log("+ Saving.", color="yellow", display=display)
        save_success, output = save_files(source, self.backup_dir, number_of_files, display=display)
        log("+ Generating redundancy files.", color="yellow", display=display)
        fsck_success, fsck_output = fsck_files(self.backup_dir, generate=True, display=display)
        return index_success and save_success and fsck_success, number_of_files

    def _find_remote_by_name(self, remote_name):
        for remote in self.remotes:
            if remote.name == remote_name:
                return remote
        return None

    def _find_remote_by_path(self, remote_path):
        for remote in self.remotes:
            if remote.full_path == remote_path:
                return remote
        return None

    def sync_remote(self, remote_name, display=False):
        remote = self._find_remote_by_name(remote_name)
        save_success = False
        if remote and remote.is_known:
            if remote.is_cloud:
                save_success, err_log = self.sync_to_cloud(remote, display)
            elif remote.is_disk or remote.is_directory:
                save_success, err_log = self.sync_to_folder(remote, display)
            else:
                log("Unknown remote %s, maybe unmounted disk. "
                    "Not doing anything." % remote.name, color="red", display=display)
        elif remote and not remote.is_known:
            log("Rclone config for remote %s not found!!!" % remote_name,
                color="red", display=display)
        else:
            log("Remote %s not found!!!" % remote_name, color="red", display=display)

        return remote and remote.is_known and save_success

    def restore(self, target, display=True):
        success = False
        output = ""
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red", display=display)
            sys.exit(-1)
        for source in self.sources:
            sub_target = Path(target, source.name)
            log("+ Restoring %s to %s." % (source.name, sub_target), color="yellow",
                display=display)
            success, output = bup_command(
                ["restore", "-C", str(sub_target), "/%s/latest/." % source.name],
                self.backup_dir,
                quiet=False)
        if not success:
            log("!!! %s" % output, color="red", display=display)
        return success, output

    def fuse(self, folder, display=True):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            log("+ Mounting repository to %s." % folder, color="yellow", display=display)
            bup_command(["fuse", str(folder)], self.backup_dir, quiet=True)

    def unfuse(self, folder=None, display=True):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            log("+ Unmounting repository from {folder}.".format(folder=self.fuse_dir),
                color="yellow", display=display)
            umount(self.fuse_dir)

    def sync_to_folder(self, grenier_remote, display=True):
        log("+ Syncing with %s." % grenier_remote.name, color="yellow", display=display)
        start = time.time()
        success, err_log = save_to_folder(self.name, self.backup_dir,
                                          grenier_remote, display=display)
        if success:
            self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
            log("+ Synced in %.2fs." % (time.time() - start), color="green", display=display)
        else:
            log("!! Error! %s" % err_log, color="red", display=display)
        return success, err_log

    def sync_to_cloud(self, grenier_remote, display=True):
        # check if configured
        if grenier_remote.is_cloud:
            start = time.time()
            log("+ Syncing with %s." % grenier_remote.name, color="yellow", display=display)
            success, err_log = save_to_cloud(self.name,
                                             grenier_remote.name,
                                             self.backup_dir,
                                             self.temp_dir,
                                             self.rclone_config_file,
                                             self.passphrase)
            if success:
                self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
                log("+ Synced in %.2fs." % (time.time() - start), color="green", display=display)
            else:
                log("!! Error! %s" % err_log, color="red", display=display)
            return success, err_log
        else:
            return False, "!!! %s is not a cloud remote..." % grenier_remote.name

    def recover_from_cloud(self, remote, target, display=True):
        if not create_or_check_if_empty(target):
            log("Directory %s is not empty,"
                " not doing anything." % target, color="red")
            sys.exit(-1)
        if remote.is_cloud:
            log("+ Restoring from cloud (%s)." % remote.name, color="yellow")
            start = time.time()
            success, err_log = restore_from_cloud(self.name,
                                                  remote.name,
                                                  self.temp_dir,
                                                  target,
                                                  self.rclone_config_file,
                                                  self.passphrase)
            if success:
                log("+ Downloaded from %s in %.2fs." % (remote.name, time.time() - start),
                    color="green")
                # TODO: restore bup versions
            else:
                log("!! Error! %s" % err_log, color="red")
            return success, err_log
        else:
            return False, "!!! %s is not a cloud remote..." % remote.name

    def recover_from_folder(self, remote_path, target, display=True):
        # find remote by full_path
        remote = self._find_remote_by_path(remote_path)
        if not remote:
            return False, "No such remote!"

        if not create_or_check_if_empty(target):
            log("Directory %s is not empty, not doing anything." % target,
                color="red", display=display)
            return False, "Target not an empty directory."

        log("+ Recovering files from %s to %s." % (remote.full_path, target),
            color="yellow", display=display)
        success, err_log = recover_files_from_folder(self.backup_dir, remote, target, display=display)
        if not success:
            log("!! Error! %s" % err_log, color="red", display=display)
        return success, err_log

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
