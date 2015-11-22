import yaml

from grenier.logger import logger
from grenier.helpers import *

# Low-level commands
# -------------------


def encfs_command(directory1, directory2, password, reverse=False, quiet=False):
    # TODO: if not reverse, set env for xml path!!!

    # dirs must be absolute
    directory1 = absolute_path(directory1)
    directory2 = absolute_path(directory2)

    assert directory1 is not None and directory1.exists()
    assert directory2 is not None and directory2.exists()
    cmd = ["encfs", "--standard", "-S", str(directory1), str(directory2)]
    if reverse:
        cmd.append("--reverse")
    p = Popen(cmd,
              stdin=PIPE,
              stdout=PIPE,
              stderr=PIPE,
              bufsize=1)
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
        logger.debug(cmd)
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


def bup_command(cmd, backup_directory, quiet=False, number_of_items=None,
                pbar_title="", save_output=True):
    logger.debug(cmd)
    env_dict = {"BUP_DIR": str(backup_directory)}
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


def rsync_command(cmd, quiet=False, save_output=True):
    complete_cmd = ["rsync", "-a", "--delete", "--human-readable",
                    "--info=progress2", "--force"] + cmd
    logger.debug(complete_cmd)
    output = ""
    # TODO: return success, log
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

# Operations
# -------------------


def index_files(source, backup_dir):
    cmd = ["index", "-vv"]
    if source.excluded_extensions:
        cmd.append(r"--exclude-rx=^.*\.(%s)$" % r"|".join(source.excluded_extensions))
    cmd.append(str(source.target_dir))
    success, output = bup_command(cmd, backup_dir, quiet=True)
    # returns succes and number of files/folders
    return success, len(output.strip().split("\n"))


def save_to_cloud(repository_name, backend, directory_path, encfs_mount,
                  rclone_config_file, password):
    backup_success = False
    rclone_success = False
    output_rclone = ""
    # reverse encfs mount
    assert create_or_check_if_empty(encfs_mount)
    assert not is_fuse_mounted(encfs_mount)
    success, output_encfs = encfs_command(directory_path, encfs_mount,
                                          password, reverse=True, quiet=True)
    if success:
        # save xml
        backup_success = backup_encfs_xml(Path(directory_path, ".encfs6.xml"), repository_name)
        # sync to cloud
        rclone_success, output_rclone = rclone_command(rclone_config_file,
                                                       "sync",
                                                       encfs_mount,
                                                       "%s:%s" % (backend, repository_name),
                                                       quiet=True)
        # unmount
        umount(encfs_mount)

    return success and backup_success and rclone_success, output_encfs + output_rclone


def restore_from_cloud(repository_name, backend, encfs_path, restore_path,
                       rclone_config_file, password):
    # TODO return success, log
    # create encfs_path
    encfs_path = Path(encfs_path)
    assert create_or_check_if_empty(encfs_path)
    assert not is_fuse_mounted(encfs_path)
    # rclone copy
    rclone_command(rclone_config_file, "copy", encfs_path, "%s:%s" % (backend, repository_name))
    # find encfs xml
    xml_backup_dir = Path(xdg.BaseDirectory.save_data_path("grenier"), "encfs_xml")
    encfs_xml_path = Path(xml_backup_dir, "%s.xml" % repository_name)
    assert encfs_xml_path.exists()
    # encfs with password to restore_path
    encfs_command(encfs_path, restore_path, password, reverse=False)


# Other things
# -------------------


def backup_encfs_xml(xml_path, repository_name):
    # defaut xml backup location
    # TODO: document in README
    backup_dir = Path(xdg.BaseDirectory.save_data_path("grenier"), "encfs_xml")
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
    new_path = Path(backup_dir, "%s.xml" % repository_name)
    try:
        new_path.write_bytes(xml_path.read_bytes())
        return True
    except FileNotFoundError as err:
        print(err)
        return False


def update_or_create_sync_file(path, backup_name):
    if not path.exists():
        synced = {}
    else:
        with open(path.as_posix(), 'r') as previous_version:
            synced = yaml.load(previous_version)
    synced[backup_name] = time.strftime("%Y-%m-%d_%Hh%M")
    with open(path.as_posix(), 'w') as last_synced_file:
        yaml.dump(synced, last_synced_file, default_flow_style=False)
