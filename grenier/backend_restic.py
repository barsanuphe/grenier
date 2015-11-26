from grenier.helpers import *
from grenier.backend_default import Backend
from subprocess import Popen


def restic_command(cmd, repository_path, passphrase):
    log_cmd(cmd)
    output = ""
    env_dict = {"RESTIC_REPOSITORY": str(repository_path),
                "RESTIC_PASSWORD": passphrase}
    with Popen(["restic"] + cmd, env=env_dict) as p:
        p.communicate()
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
        # TODO verif que check fail == return != 0
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

        # TODO: apres save, faire optimize direct? et check?

        return success, output

    def _restore_source(self, source, target, display=True):
        sub_target = Path(target, source.name)

        success, output = self.list(display)
        # TODO: get list of snapshots, extract latest hash
        snapshot_hash = "XXXXX"

        return restic_command(["restore", snapshot_hash, "--target", str(sub_target)],
                              self.repository_path, self.passphrase)

    def fuse(self, mount_path, display=True):
        # TODO: restic only mounts the repo while active, quitting the command unmounts.
        # TODO: see what can be done about that.
        if create_or_check_if_empty(mount_path):
            return restic_command(["mount", str(mount_path)], self.repository_path, self.passphrase)
        else:
            return False, "!!! Could not mount %s. Mount path exists and is not empty." % mount_path

    def list(self, display=True):
        # TODO pb: output is now empty: cmd output to stdout
        success, output = restic_command(["snapshots"], self.repository_path, self.passphrase)
        print(success)
        print(output)
        # TODO parse snapshots output

        return success, output
