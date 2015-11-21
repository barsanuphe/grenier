import sys
import getpass
from configparser import ConfigParser

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
    def __init__(self, name, rclone_config_file):
        self.name = name
        self.is_directory = False
        self.is_disk = False
        self.is_cloud = False

        self.rclone_config_file = rclone_config_file

        if Path(name).is_absolute():
            self.full_path = Path(name)
            self.is_directory = True
        elif Path("/run/media/%s/%s" % (getpass.getuser(), name)).exists():
            self.full_path = Path("/run/media/%s/%s" % (getpass.getuser(), name))
            self.is_disk = True
        else:  # out of options...
            # check if known
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
            logger.info("+ Creating folder %s" % self.temp_dir)
            self.temp_dir.mkdir(parents=True)
        self.backup_dir = backup_dir
        if not self.backup_dir.exists():
            logger.info("+ Creating folder %s" % self.backup_dir)
            self.backup_dir.mkdir(parents=True)
        self.fuse_dir = None

        self.sources = []
        self.remotes = []

        # TODO remove
        self.google_configured = None
        self.hubic_configured = None

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
            bup_command(["init"], self.backup_dir, quiet=True)

    def check_and_repair(self, display=True):
        log("+ Checking and repairing repository.", color="yellow", display=display)
        return self._fsck(generate=False, display=display)

    def backup(self, check_before=False, display=True):
        starting_time = time.time()
        self.init(display)
        if check_before:
            self.check_and_repair(display)
        total_number_of_files = self.save(display)
        log("+ Backup done in %.2fs." % (time.time() - starting_time),
            color="green", display=display)
        return total_number_of_files

    def _find_remote(self, remote_name):
        for remote in self.remotes:
            if remote.name == remote_name:
                return True, remote
        return False, None

    def sync_remote(self, remote_name, display=False):
        remote_found, remote = self._find_remote(remote_name)
        if remote_found:
            if not remote.is_known:
                print("Create cloud config for %s?" % remote.name)
                # TODO: if not, call rclone config


            if remote.is_cloud:
                self.save_to_cloud(remote, display)
            elif remote.is_disk or remote.is_directory:
                self.save_to_folder(remote, display)
            else:
                log("Unknown remote %s, maybe unmounted disk. "
                    "Not doing anything." % remote.name, color="red", display=display)
        else:
            log("Remote %s not found!!!" % remote_name, color="red", display=display)
        return remote_found  # TODO and save success

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

    def fuse(self, folder, display=True):
        if create_or_check_if_empty(folder):
            self.fuse_dir = folder
            log("+ Mounting repository to %s." % folder, color="yellow", display=display)
            bup_command(["fuse", folder], self.backup_dir, quiet=True)

    def unfuse(self, folder=None, display=True):
        if folder is not None:
            self.fuse_dir = folder
        if self.fuse_dir is not None:
            log("+ Unmounting repository from {folder}.".format(folder=self.fuse_dir),
                color="yellow", display=display)
            umount(self.fuse_dir)

    def save_to_folder(self, grenier_remote, display=True):
        log("+ Syncing with %s." % grenier_remote.name, color="yellow", display=display)
        if not grenier_remote.full_path.exists():
            grenier_remote.full_path.mkdir(parents=True)
        start = time.time()
        rsync_command([str(self.backup_dir), str(grenier_remote.full_path)])
        update_or_create_sync_file(Path(grenier_remote.full_path, "last_synced.yaml"),
                                   self.name)
        log("+ Synced in %.2fs." % (time.time() - start), color="green", display=display)
        self.just_synced.append({grenier_remote.name: time.strftime("%Y-%m-%d_%Hh%M")})
        # TODO return rsync success
        return True

    def save_to_cloud(self, grenier_remote, display=True):
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
            return success

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

    def _index(self, source, display=True):
        log("+ Indexing.", color="yellow", display=display)
        cmd = ["index", "-vv"]
        if source.excluded_extensions:
            cmd.append(r"--exclude-rx=^.*\.(%s)$" % r"|".join(source.excluded_extensions))
        cmd.append(str(source.target_dir))
        output = bup_command(cmd, self.backup_dir, quiet=True)
        return len(output)

    def _fsck(self, generate=False, display=True):
        if generate:
            log("+ Generating redundancy files.", color="yellow", display=display)
        # get number of .pack files
        # each .pack has its own par2 files
        repository_objects = Path(self.backup_dir, "objects", "pack")
        packs = [el for el in repository_objects.iterdir()
                 if el.suffix == ".pack"]
        cmd = ["fsck", "-v", "-j8"]
        if generate:
            cmd.append("-g")
            title = "Generating: "
        else:
            cmd.append("-r")
            title = "Checking: "
        return bup_command(cmd, self.backup_dir, quiet=not display,
                           number_of_items=len(packs),
                           pbar_title=title,
                           save_output=False)

    def save(self, display=True):
        original_size = get_folder_size(self.backup_dir)
        total_number_of_files = 0
        for source in self.sources:
            total_number_of_files += self._save(source, display)
        new_size = get_folder_size(self.backup_dir)
        delta = new_size - original_size
        log("+ Backed up %s files." % total_number_of_files, color="green", display=display)
        log("+ Final repository size: %s (+%s)." % (readable_size(new_size),
                                                    readable_size(delta)),
            color="green", display=display)
        return total_number_of_files

    def _save(self, source, display=True):
        log(">> %s -> %s." % (source.target_dir, self.backup_dir), color="blue", display=display)
        number_of_files = self._index(source, display)
        log("+ Saving.", color="yellow", display=display)
        bup_command(["save", "-vv",
                     source.target_dir.as_posix(),
                     "-n", source.name,
                     '--strip-path=%s' % source.target_dir.as_posix(),
                     '-9'],
                    self.backup_dir,
                    quiet=not display,
                    number_of_items=number_of_files,
                    pbar_title="Saving: ",
                    save_output=False)
        self._fsck(generate=True, display=display)
        return number_of_files
