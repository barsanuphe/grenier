from grenier.helpers import *
from grenier.logger import *


def rclone_command(rclone_config_file, operation, directory=None, container=None, quiet=False):
    if directory is None and container is None and operation != "config":
        raise Exception("Wrong operation!")
    if operation == "config":
        os.system("rclone config")
    else:
        assert directory is not None and directory.exists()
        assert container is not None
        cmd = ["rclone", "--config=%s" % str(rclone_config_file),
               operation, "--transfers=16"]
        # TODO add poption "--stats=1s" and parse to make progressbar
        if operation == "sync":
            cmd.extend([str(directory), container])
        elif operation == "copy":
            cmd.extend([container, str(directory)])
        log_cmd(cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, bufsize=1)
        output = ""
        for line in iter(p.stderr.readline, b''):
            output += line.decode("utf8")
            if not quiet:
                logger.warning("\t !!! " + line.decode("utf8").rstrip())
            else:
                logger.debug("\t !!! " + line.decode("utf8").rstrip())
        p.communicate()
        if p.returncode == 0:
            return True, output
        else:
            return False, output


def rsync_command(cmd, quiet=False, save_output=True):
    complete_cmd = ["rsync", "-a", "--delete", "--human-readable",
                    "--info=progress2", "--force"] + cmd
    log_cmd(complete_cmd)
    output = ""
    if quiet:
        p = Popen(complete_cmd, stdout=PIPE, stderr=PIPE, bufsize=1)
    else:
        p = Popen(complete_cmd, stderr=PIPE, bufsize=1)

    for line in iter(p.stderr.readline, b''):
        if not quiet:
            logger.warning("\t !!! " + line.decode("utf8").rstrip())
        if save_output:
            output += line.decode("utf8")
    p.communicate()
    if p.returncode == 0:
        return True, output
    else:
        return False, output


class Backend(object):
    def __init__(self, name, repository_path, *args):
        self.name = name
        self.repository_path = repository_path

    def init(self):
        pass

    def check(self):
        pass

    def save(self, sources, display=True):
        output = ""
        overall_success = True
        for source in sources:
            success, source_output = self._save_source(source, display)
            if not success:
                red("!! Error saving %s!! " % source.name)
            output += source_output
            overall_success = overall_success and success
        return overall_success, output

    def _save_source(self, source, display=True):
        # redefine in subclass
        return True, ""

    def restore(self, sources, target, display=True):
        overall_success = True
        overall_output = ""
        for source in sources:
            yellow("+ Restoring %s to %s." % (source.name, target), display)
            success, output = self._restore_source(source, target, display=display)
            if not success:
                red("!!! %s" % output, display)
            overall_success = overall_success and success
            overall_output += output
        return overall_success, overall_output

    def _restore_source(self, source, target, display=True):
        # redefine in subclass
        return True, "OK"

    def sync_to_folder(self, repository_name, remote, display=True):
        if not remote.full_path.exists():
            remote.full_path.mkdir(parents=True)
        success, err_log = rsync_command([str(self.repository_path), str(remote.full_path)],
                                         quiet=not display)
        if success:
            update_or_create_sync_file(Path(remote.full_path, "last_synced.yaml"),
                                       repository_name)
        return success, err_log

    def sync_to_cloud(self, repository_name, remote, rclone_config_file, encfs_mount=None,
                      password="", display=True):
        # TODO: update sync yaml aussi!!!!!
        return rclone_command(rclone_config_file,
                              "sync",
                              self.repository_path,
                              "%s:%s" % (remote.name, repository_name),
                              quiet=not display)

    def recover_from_folder(self, remote, target, display=True):
        if not create_or_check_if_empty(target):
            return False, "Directory %s is not empty, not doing anything." % target
        remote_path = Path(remote.full_path, self.repository_path.stem)
        if not remote_path.exists():
            return False, "No remote files found."

        return rsync_command([str(remote_path), str(target)], quiet=not display)

    def recover_from_cloud(self, repository_name, remote, target, rclone_config_file,
                           display=True, encfs_path=None, password=None):
        if not create_or_check_if_empty(target):
            return False, "Directory %s is not empty, not doing anything." % target
        return rclone_command(rclone_config_file,
                              "copy",
                              target,
                              "%s:%s" % (remote.name, repository_name),
                              quiet=not display)

    def fuse(self, mount_path):
        pass

    def unfuse(self, mount_path):
        umount(mount_path)

    def list(self, display=True):
        # TODO !!
        pass
