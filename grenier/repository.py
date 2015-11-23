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
            yellow("+ Initializing repository.", display)
            return init_repository(self.backup_dir, display=False)
        else:
            return True, "Repository already exists."

    def check_and_repair(self, display=True):
        yellow("+ Checking and repairing repository.", display)
        return fsck_files(self.backup_dir, generate=False, display=display)

    def save(self, check_before=False, display=True):
        starting_time = time.time()
        init_success, errlog = self.init(display)
        if not init_success:
            red("!!! %s " % errlog, display)
            return False, 0
        else:
            if check_before:
                self.check_and_repair(display)
            success, total_number_of_files = self.save_repository(display)
            if success:
                green("+ Backup done in %.2fs." % (time.time() - starting_time), display)
            return success, total_number_of_files

    def save_repository(self, display=True):
        original_size = get_folder_size(self.backup_dir)
        total_number_of_files = 0
        for source in self.sources:
            success, number_of_files = self._save_source(source, display)
            if success:
                total_number_of_files += number_of_files
            else:
                red("!!! Error saving source %s, stopping." % source.name, display)
                return False, total_number_of_files
        new_size = get_folder_size(self.backup_dir)
        delta = new_size - original_size
        green("+ Backed up %s files." % total_number_of_files, display)
        green("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                      readable_size(delta)), display)
        return True, total_number_of_files

    def _save_source(self, source, display=True):
        blue(">> %s -> %s." % (source.target_dir, self.backup_dir), display)
        yellow("+ Indexing.", display)
        index_success, number_of_files = index_files(source, self.backup_dir)
        yellow("+ Saving.", display)
        save_success, output = save_files(source, self.backup_dir, number_of_files, display=display)
        yellow("+ Generating redundancy files.", display)
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
                red("Unknown remote %s, maybe unmounted disk. Not doing anything." % remote.name,
                    display)
        elif remote and not remote.is_known:
            red("Rclone config for remote %s not found!!!" % remote_name, display)
        else:
            red("Remote %s not found!!!" % remote_name, display)

        return remote and remote.is_known and save_success

    def restore(self, target, display=True):
        overall_success = True
        overall_output = ""
        if not create_or_check_if_empty(target):
            red("Directory %s is not empty, not doing anything." % target, display)
            sys.exit(-1)
        for source in self.sources:
            yellow("+ Restoring %s to %s." % (source.name, target), display)
            success, output = restore_source(self.backup_dir, source.name, target, display=display)
            if not success:
                red("!!! %s" % output, display)
            overall_success = overall_success and success
            overall_output += output
        return overall_success, overall_output

    def fuse(self, folder, display=True):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            yellow("+ Mounting repository to %s." % folder, display)
            bup_command(["fuse", str(folder)], self.backup_dir, quiet=True)

    def unfuse(self, folder=None, display=True):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            yellow("+ Unmounting repository from {folder}.".format(folder=self.fuse_dir), display)
            umount(self.fuse_dir)

    def sync_to_folder(self, grenier_remote, display=True):
        yellow("+ Syncing with %s." % grenier_remote.name, display)
        start = time.time()
        success, err_log = save_to_folder(self.name, self.backup_dir,
                                          grenier_remote, display=display)
        if success:
            self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
            green("+ Synced in %.2fs." % (time.time() - start), display)
        else:
            red("!! Error! %s" % err_log, display)
        return success, err_log

    def sync_to_cloud(self, grenier_remote, display=True):
        # check if configured
        if grenier_remote.is_cloud:
            start = time.time()
            yellow("+ Syncing with %s." % grenier_remote.name, display)
            success, err_log = save_to_cloud(self.name,
                                             grenier_remote.name,
                                             self.backup_dir,
                                             self.temp_dir,
                                             self.rclone_config_file,
                                             self.passphrase)
            if success:
                self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
                green("+ Synced in %.2fs." % (time.time() - start), display)
            else:
                red("!! Error! %s" % err_log, display)
            return success, err_log
        else:
            return False, "!!! %s is not a cloud remote..." % grenier_remote.name

    def recover_from_cloud(self, remote_name, target, display=True):
        remote = self._find_remote_by_name(remote_name)
        if not create_or_check_if_empty(target):
            red("Directory %s is not empty, not doing anything." % target)
            sys.exit(-1)
        if remote and remote.is_cloud:
            yellow("+ Restoring from cloud (%s)." % remote.name, display)
            start = time.time()
            success, err_log = restore_from_cloud(self.name,
                                                  remote.name,
                                                  self.temp_dir,
                                                  target,
                                                  self.rclone_config_file,
                                                  self.passphrase,
                                                  display=display)
            if success:
                green("+ Downloaded from %s in %.2fs." % (remote.name, time.time() - start),
                      display)
            else:
                red("!! Error! %s" % err_log, display)
            return success, err_log
        else:
            return False, "!!! %s is not a cloud remote..." % remote.name

    def recover_from_folder(self, remote_path, target, display=True):
        # find remote by full_path
        remote = self._find_remote_by_path(remote_path)
        if not remote:
            return False, "No such remote!"

        if not create_or_check_if_empty(target):
            red("Directory %s is not empty, not doing anything." % target, display)
            return False, "Target not an empty directory."

        yellow("+ Recovering files from %s to %s." % (remote.full_path, target), display)
        success, err_log = recover_files_from_folder(self.backup_dir, remote, target,
                                                     display=display)
        if not success:
            red("!! Error! %s" % err_log, display)
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
