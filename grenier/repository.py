import sys
from grenier.logger import logger
from grenier.checks import external_binaries_available
from grenier.helpers import *
from grenier.remote import GrenierRemote
from grenier.source import GrenierSource
from grenier.backend_bup import BupBackend
from grenier.backend_restic import ResticBackend


class GrenierRepository(object):
    def __init__(self, name, backend, repository_path, temp_dir, rclone_config_file, passphrase=None):
        self.name = name
        self.rclone_config_file = rclone_config_file
        self.temp_dir = temp_dir
        if not self.temp_dir.exists():
            logger.debug("+ Creating folder %s" % self.temp_dir)
            self.temp_dir.mkdir(parents=True)
        self.repository_path = repository_path
        if not self.repository_path.exists():
            logger.debug("+ Creating folder %s" % self.repository_path)
            self.repository_path.mkdir(parents=True)
        self.fuse_dir = None
        self.sources = []
        self.remotes = []
        self.passphrase = passphrase
        self.just_synced = []

        # check that the backend is available...
        if backend == "bup" and external_binaries_available("bup") and external_binaries_available("encfs"):
            self.backend = BupBackend(self.repository_path)
        elif backend == "restic" and external_binaries_available("restic"):
            self.backend = ResticBackend(self.repository_path, self.passphrase)
        else:
            raise Exception("Unknown backend %s, or missing dependancies." % backend)

    def add_source(self, name, target_dir, excluded=None):
        self.sources.append(GrenierSource(name, target_dir, excluded))

    def add_remotes(self, remote_list):
        for remote in remote_list:
            self.remotes.append(GrenierRemote(remote, self.rclone_config_file))

    def init(self, display=True):
        if create_or_check_if_empty(self.repository_path):
            yellow("+ Initializing repository.", display)
            return self.backend.init(quiet=True)
        else:
            return True, "Repository already exists."

    def check_and_repair(self, display=True):
        yellow("+ Checking and repairing repository.", display)
        return self.backend.check(display=display)

    def save(self, check_before=False, display=True):
        starting_time = time.time()
        init_success, errlog = self.init(display)
        if not init_success:
            red("!!! %s " % errlog, display)
            return False, 0
        else:
            if check_before:
                self.check_and_repair(display)
            original_size = get_folder_size(self.repository_path)
            success, errlog = self.backend.save(self.sources, display)
            if success:
                new_size = get_folder_size(self.repository_path)
                delta = new_size - original_size
                green("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                              readable_size(delta)), display)
                green("+ Backup done in %.2fs." % (time.time() - starting_time), display)
            else:
                red("!!! Error saving repository, stopping.", display)
            return success, errlog

    def sync_remote(self, remote_name, display=False):
        remote = self._find_remote_by_name(remote_name)
        save_success = False
        err_log = ""
        if remote and remote.is_known:
            yellow("+ Syncing with %s." % remote.name, display)
            start = time.time()

            if remote.is_cloud:
                save_success, err_log = self.backend.sync_to_cloud(self.name, remote,
                                                                   self.rclone_config_file,
                                                                   encfs_mount=self.temp_dir,
                                                                   password=self.passphrase,
                                                                   display=display)
            elif remote.is_disk or remote.is_directory:
                save_success, err_log = self.backend.sync_to_folder(self.name, remote,
                                                                    display=display)
            else:
                red("Unknown remote %s, maybe unmounted disk. Not doing anything." % remote.name,
                    display)

            if save_success:
                self.just_synced.append({remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
                green("+ Synced in %.2fs." % (time.time() - start), display)
            else:
                red("!! Error! %s" % err_log, display)

        elif remote and not remote.is_known:
            red("Rclone config for remote %s not found!!!" % remote_name, display)
        else:
            red("Remote %s not found!!!" % remote_name, display)

        return remote and remote.is_known and save_success

    def restore(self, target, display=True):
        if not create_or_check_if_empty(target):
            red("Directory %s is not empty, not doing anything." % target, display)
            return False, "Could not restore!"
        return self.backend.restore(self.sources, target, display)

    def fuse(self, mount_path, display=True):
        success, err_log = self.backend.fuse(mount_path, display)
        if success:
            yellow("+ Mounted repository to %s." % mount_path, display)
        else:
            red(err_log)
        return success

    def unfuse(self, mount_path, display=True):
        yellow("+ Unmounting repository from {folder}.".format(folder=mount_path), display)
        self.backend.unfuse(mount_path)

    def recover(self, remote_info, target, display=True):
        start = time.time()
        remote = self._find_remote_by_name(remote_info)
        if remote:
            if remote.is_cloud:
                yellow("+ Recovering from cloud (%s) to %s." % (remote.name, target), display)
                success, err_log = self.backend.recover_from_cloud(self.name,
                                                                   remote,
                                                                   target,
                                                                   self.rclone_config_file,
                                                                   encfs_path=self.temp_dir,
                                                                   password=self.passphrase,
                                                                   display=display)
            elif remote.is_disk:
                yellow("+ Recovering files from disk %s to %s." % (remote.name, target), display)
                success, err_log = self.backend.recover_from_folder(remote, target, display=display)
            else:
                return False, "Unknown remote!"
        else:
            remote = self._find_remote_by_path(remote_info)
            if remote:
                yellow("+ Recovering files from %s to %s." % (remote.full_path, target), display)
                success, err_log = self.backend.recover_from_folder(remote, target, display=display)
            else:
                return False, "No such remote!"

        if success:
            green("+ Downloaded from %s in %.2fs." % (remote.name, time.time() - start), display)
        else:
            red("!! Error! %s" % err_log, display)
        return success, err_log

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

    def __str__(self):
        txt = "++ Repository %s\n" % self.name
        txt += "\tRepository path: %s\n" % self.repository_path
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
