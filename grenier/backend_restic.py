from grenier.helpers import *
from grenier.backend_default import Backend, rclone_command
import pexpect
import re


def restic_command(cmd, repository_path, passphrase, quiet=False, number_of_items=None,
                   pbar_title="", save_output=True, passphrase_twice=False):
    log_cmd(cmd)
    number_of_items = 0
    output = ""

    # if number_of_items and not quiet:
    #     cpt = 0
    #     pbar = generate_pbar(pbar_title, number_of_items).start()
    #
    # if number_of_items and not quiet:
    #     pbar.finish()

    p = pexpect.spawn("restic -r {path} {cmd}".format(path=repository_path, cmd=cmd))
    p.expect(b"password")
    p.sendline(passphrase)
    if passphrase_twice:
        p.expect(b"password")
        p.sendline(passphrase)

    # FIXME: quite ugly
    if cmd.startswith("backup"):
        p.expect("ETA")
        number_of_items = int(re.findall(r'/ (\d) items', p.before.decode("utf8"))[0])

    while not p.eof():
        line = p.readline().strip().decode("utf8")
        if "ETA" in line:
            print("\r{progress}".format(progress=line), end="", flush=True)
        if save_output:
            output += line
        if not quiet:
            print(line)

    # waiting for end
    p.expect(pexpect.EOF)
    p.close()
    if p.exitstatus == 0:
        return True, number_of_items
    else:
        return False, number_of_items


class ResticBackend(Backend):
    def __init__(self, repository_path, passphrase):
        super().__init__("restic", repository_path)
        self.passphrase = passphrase

    def init(self, quiet=True):
        return restic_command("init", self.repository_path, self.passphrase,
                              passphrase_twice=True, quiet=quiet)

    def _save_source(self, source, display=True):
        yellow("+ Saving %s" % source.name, display)
        excluded = ""
        for ext in source.excluded_extensions:
            excluded += "-e=*.{ext} ".format(ext=ext)

        success, output = restic_command("backup {excluded} {source}".format(source=str(source.target_dir),
                                                                             excluded=excluded),
                                         self.repository_path, self.passphrase,
                                         quiet=not display)
        return success, output
