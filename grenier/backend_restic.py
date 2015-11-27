from datetime import datetime

from grenier.helpers import *
from grenier.backend_default import Backend


def restic_command(cmd, repository_path, passphrase):
    log_cmd(cmd)
    output = ""
    env_dict = {"RESTIC_REPOSITORY": str(repository_path),
                "RESTIC_PASSWORD": passphrase}
    if cmd[0] == "backup":
        redirect = None
    else:
        redirect = PIPE
    with Popen(["restic"] + cmd, stdout=redirect, stderr=redirect, env=env_dict) as p:
        stdout, stderr = p.communicate()
        if stdout:
            output = stdout.decode("utf8")
        if stderr:
            output += stderr.decode("utf8")
        if p.returncode == 0:
            return True, output
        else:
            return False, output


class ResticBackend(Backend):
    def __init__(self, repository_path, passphrase):
        super().__init__("restic", repository_path)
        self.passphrase = passphrase

    def init(self, quiet=True):
        return restic_command(["init"], self.repository_path, self.passphrase)

    def check(self, display=True):
        return restic_command(["check"], self.repository_path, self.passphrase)

    def _save_source(self, source, display=True):
        yellow("+ Saving %s to %s" % (source.target_dir, self.repository_path), display)
        if source.excluded_extensions:
            excluded = ""
            for ext in source.excluded_extensions:
                excluded += "-e=*.{ext} ".format(ext=ext)
            cmd = ["backup", excluded, str(source.target_dir)]
        else:
            cmd = ["backup", str(source.target_dir)]

        success, output = restic_command(cmd, self.repository_path, self.passphrase)
        if success:
            # optimize
            optimize_success, optimize_output = restic_command(["optimize"],
                                                               self.repository_path,
                                                               self.passphrase)
            success = success and optimize_success
            output += optimize_output

        return success, output

    def _restore_source(self, source, target, display=True):
        success, output = self.list(display)
        if not success:
            return False, "Unable to list snapshots!!!"

        snapshot_hash = "XXXXX"
        snapshots = output.split("\n")[2:-1]
        latest_date = datetime.fromtimestamp(0)
        for snap in snapshots:
            snap_hash, date, hour, machine, folder = [el for el in snap.split(" ") if el != '']
            if Path(folder) == source.target_dir or Path(folder).samefile(source.target_dir):
                # keep latest hash
                snapshot_date = datetime.strptime(date+hour, "%Y-%m-%d%H:%M:%S")
                if snapshot_date > latest_date:
                    latest_date = snapshot_date
                    snapshot_hash = snap_hash

        yellow("Restoring %s from snapshot %s [saved on %s]." % (source.name,
                                                                 snapshot_hash,
                                                                 latest_date.strftime("%Y-%m-%d %H:%M:%S")))
        return restic_command(["restore", snapshot_hash, "--target", str(target)],
                              self.repository_path, self.passphrase)

    def fuse(self, mount_path, display=True):
        # TODO: restic only mounts the repo while active, quitting the command unmounts.
        # TODO: see what can be done about that.
        if create_or_check_if_empty(mount_path):
            return restic_command(["mount", str(mount_path)], self.repository_path, self.passphrase)
        else:
            return False, "!!! Could not mount %s. Mount path exists and is not empty." % mount_path

    def list(self, display=True):
        return restic_command(["snapshots"], self.repository_path, self.passphrase)

