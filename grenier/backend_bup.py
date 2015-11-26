from grenier.helpers import *
from grenier.backend_default import Backend, rclone_command


def encfs_command(directory1, directory2, password, encfs_xml_path=None, reverse=False, quiet=False):
    # dirs must be absolute
    directory1 = absolute_path(directory1)
    directory2 = absolute_path(directory2)

    assert directory1 is not None and directory1.exists()
    assert directory2 is not None and directory2.exists()
    cmd = ["encfs", "-S", str(directory1), str(directory2)]
    env = os.environ.copy()
    if reverse:
        cmd.extend(["--standard", "--reverse"])
    else:
        env["ENCFS6_CONFIG"] = str(encfs_xml_path)
    log_cmd(cmd)
    p = Popen(cmd,
              stdin=PIPE,
              stdout=PIPE,
              stderr=PIPE,
              bufsize=1,
              env=env)
    stdout_data, stderr_data = p.communicate(password.encode("utf-8"))
    output = ""
    for line in stderr_data.decode("utf8").strip().split("\n"):
        output += line
        if not quiet:
            logger.warning("\t !!! " + line.rstrip())
        else:
            logger.debug("\t !!! " + line.rstrip())

    if p.returncode == 0:
        return True, output
    else:
        return False, output


def bup_command(cmd, repository_path, quiet=False, number_of_items=None,
                pbar_title="", save_output=True):
    log_cmd(cmd)
    env_dict = {"BUP_DIR": str(repository_path)}
    output = ""

    if number_of_items and not quiet:
        cpt = 0
        pbar = generate_pbar(pbar_title, number_of_items).start()

    with Popen(["bup"] + cmd,
               stdout=PIPE,
               stderr=STDOUT,
               bufsize=1,
               env=env_dict) as p:
        for line in p.stdout:
            if number_of_items and not quiet:
                cpt += 1
                if cpt < number_of_items:
                    pbar.update(cpt)
            elif not quiet:
                logger.info("\t" + line.decode("utf8").rstrip())
            if save_output:
                output += line.decode("utf8")
    if number_of_items and not quiet:
        pbar.finish()
    if p.returncode == 0:
        return True, output
    else:
        return False, output


class BupBackend(Backend):
    def __init__(self, repository_path):
        super().__init__("bup", repository_path)

    def init(self, quiet=True):
        return bup_command(["init"], self.repository_path, quiet=quiet)

    def check(self, generate=False, display=True):
        # get number of .pack files
        # each .pack has its own par2 files
        repository_objects = Path(self.repository_path, "objects", "pack")
        packs = [el for el in repository_objects.iterdir()
                 if el.suffix == ".pack"]
        cmd = ["fsck", "-v", "-j8"]
        if generate:
            cmd.append("-g")
            title = "Generating: "
        else:
            cmd.append("-r")
            title = "Checking: "
        return bup_command(cmd, self.repository_path, quiet=not display,
                           number_of_items=len(packs),
                           pbar_title=title,
                           save_output=False)

    def _save_source(self, source, display=True):
        blue(">> %s -> %s." % (source.target_dir, self.repository_path), display)
        yellow("+ Indexing.", display)
        index_success, number_of_files = self._bup_index(source)
        yellow("+ Saving.", display)
        save_success, output = self._bup_save(source, number_of_files, display=display)
        yellow("+ Generating redundancy files.", display)
        fsck_success, fsck_output = self.check(generate=True, display=display)
        return index_success and save_success and fsck_success, number_of_files

    def _bup_index(self, source):
        cmd = ["index", "-vv"]
        if source.excluded_extensions:
            cmd.append(r"--exclude-rx=^.*\.(%s)$" % r"|".join(source.excluded_extensions))
        cmd.append(str(source.target_dir))
        success, output = bup_command(cmd, self.repository_path, quiet=True)
        # returns succes and number of files/folders
        return success, len(output.strip().split("\n"))

    def _bup_save(self, source, number_of_files, display=True):
        return bup_command(["save", "-vv",
                            str(source.target_dir),
                            "-n", source.name,
                            '--strip-path=%s' % str(source.target_dir),
                            '-9'],
                           self.repository_path,
                           quiet=not display,
                           number_of_items=number_of_files,
                           pbar_title="Saving: ",
                           save_output=False)

    def fuse(self, mount_path, display=True):
        if create_or_check_if_empty(mount_path):
            return bup_command(["fuse", str(mount_path)], self.repository_path, quiet=True)
        else:
            return False, "!!! Could not mount %s. Mount path exists and is not empty." % mount_path

    def sync_to_cloud(self, repository_name, remote, rclone_config_file, encfs_mount=Path(),
                      password="", display=True):

        backup_success = False
        rclone_success = False
        output_rclone = ""
        # reverse encfs mount
        assert create_or_check_if_empty(encfs_mount)
        assert not is_fuse_mounted(encfs_mount)
        success, output_encfs = encfs_command(self.repository_path, encfs_mount,
                                              password, reverse=True, quiet=True)
        if success:
            # save xml
            backup_success = backup_encfs_xml(Path(self.repository_path, ".encfs6.xml"), repository_name)
            # sync to cloud
            rclone_success, output_rclone = rclone_command(rclone_config_file,
                                                           "sync",
                                                           encfs_mount,
                                                           "%s:%s" % (remote.name, repository_name),
                                                           quiet=True)
            # unmount
            umount(encfs_mount)

        return success and backup_success and rclone_success, output_encfs + output_rclone

    def _restore_source(self, source, target, display=True):
        sub_target = Path(target, source.name)
        return bup_command(["restore", "-C", str(sub_target), "/%s/latest/." % source.name],
                           self.repository_path,
                           quiet=not display)

    def recover_from_cloud(self, repository_name, remote, target, rclone_config_file,
                           display=True, encfs_path=None, password=None):
        if not create_or_check_if_empty(target):
            return False, "Directory %s is not empty, not doing anything." % target

        # create encfs_path
        encfs_path = Path(encfs_path)
        assert create_or_check_if_empty(encfs_path)
        assert not is_fuse_mounted(encfs_path)
        # rclone copy
        rclone_success, rclone_log = rclone_command(rclone_config_file, "copy", encfs_path,
                                                    "%s:%s" % (remote.name, repository_name),
                                                    quiet=not display)
        if rclone_success:
            # find encfs xml
            xml_backup_dir = Path(xdg.BaseDirectory.save_data_path("grenier"), "encfs_xml")
            encfs_xml_path = Path(xml_backup_dir, "%s.xml" % repository_name)
            assert encfs_xml_path.exists()
            # encfs with password to restore_path
            encfs_success, encfs_log = encfs_command(encfs_path, target, password,
                                                     encfs_xml_path, reverse=False,
                                                     quiet=not display)
            return encfs_success, encfs_log
        else:
            return False, rclone_log
