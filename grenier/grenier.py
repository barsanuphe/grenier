#!/usr/env/python
import getpass
import argparse

from grenier.checks import check_third_party_modules
check_third_party_modules()
# 3rd party modules
import yaml
import xdg.BaseDirectory

# grenier modules
from grenier.logger import *
from grenier.repository import *
from grenier.helpers import *


# ---CONFIG---------------------------
CONFIG_FILE = "grenier.yaml"


# ---GRENIER---------------------------
class Grenier(object):
    def __init__(self, config_file):
        self.config_file = config_file
        self.repositories = []
        # dict to keep the keepassx kdb passwords, in case several repositories
        # use the same file. Hide your RAM from prying eyes.
        self.master_passwords = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            print("\nGot interrupted. Trying to clean up.")

    def open_config(self):
        if self.config_file.exists():
            try:
                with open(str(self.config_file), 'r') as f:
                    config = yaml.load(f)
                    for p in config:
                        backend = config[p]["backend"]
                        repository_path = Path(config[p]["repository_path"], "grenier_%s" % p)
                        temp_dir = Path(config[p].get("temp_dir", "/tmp/grenier_%s" % p))
                        default_rclone_config_file = "/home/%s/.rclone.conf" % getpass.getuser()
                        rclone_config_file = Path(config[p].get("rclone_config_file",
                                                                default_rclone_config_file))

                        kdb_file = config[p].get("kdb_file", None)
                        if kdb_file:
                            kdb_file = Path(kdb_file)
                            assert kdb_file.exists()
                            if kdb_file in self.master_passwords:
                                passphrase = self.master_passwords[kdb_file]
                            else:
                                master_password, repository_password = find_password(kdb_file, p)
                                if master_password and repository_password:
                                    self.master_passwords[kdb_file] = master_password
                                    passphrase = repository_password
                        else:
                            passphrase = config[p].get("passphrase", None)
                        # we really should have the password by now
                        assert passphrase

                        assert rclone_config_file.exists()
                        bp = GrenierRepository(p,
                                               backend,
                                               repository_path,
                                               temp_dir,
                                               rclone_config_file,
                                               passphrase)
                        sources_dict = config[p]["sources"]
                        for s in sources_dict:
                            bp.add_source(s,
                                          sources_dict[s]["dir"],
                                          sources_dict[s].get("excluded", []))

                        bp.add_remotes(config[p].get("remotes", []))
                        self.repositories.append(bp)
                return True
            except Exception as err:
                print("Invalid configuration file!!")
                print(err)
                return False
        else:
            print("No configuration file found!")
            return False

    def export_last_sync(self):
        data_path = xdg.BaseDirectory.save_data_path("grenier")
        path = Path(data_path, "last_synced.yml")
        if path.exists():
            last_synced = yaml.load(open(path.as_posix(), 'r'))
        else:
            last_synced = {}

        for r in self.repositories:
            if r.just_synced:
                if r.name not in last_synced:
                    last_synced[r.name] = {}
                for sync in r.just_synced:
                    last_synced[r.name].update(sync)
        yaml.dump(last_synced,
                  open(path.as_posix(), 'w'),
                  default_flow_style=False)

    @staticmethod
    def show_last_synced():
        data_path = xdg.BaseDirectory.save_data_path("grenier")
        path = Path(data_path, "last_synced.yml")
        if path.exists():
            last_synced = yaml.load(open(path.as_posix(), 'r'))
        else:
            last_synced = {}

        for r in last_synced:
            logger.info("%s:" % r)
            for dest in last_synced[r]:
                logger.info("\t%s:\n\t\t%s\n" % (dest, last_synced[r][dest]))


def main():
    log("\n# # # G R E N I E R # # #", color="boldwhite")

    parser = argparse.ArgumentParser(description='Grenier.\nA wrapper around '
                                                 'bup, rclone, rsync, encfs to back stuff up.')

    group_config = parser.add_argument_group('Configuration',
                                             'Manage configuration files.')
    group_config.add_argument('--config',
                              dest='config',
                              action='store',
                              metavar="CONFIG_FILE",
                              nargs=1,
                              help='Use an alternative configuration file.')
    group_config.add_argument('-l',
                              '--list',
                              dest='list_repositories',
                              action='store_true',
                              default=False,
                              help='List defined repositories.')

    group_projects = parser.add_argument_group('Repositories', 'Manage repositories.')
    group_projects.add_argument('-n',
                                '--name',
                                dest='names',
                                action='store',
                                nargs="+",
                                metavar="BACKUP_NAME",
                                help='specify backup names, or "all".')
    group_projects.add_argument('-b',
                                '--backup',
                                dest='backup',
                                action='store_true',
                                default=False,
                                help='backup selected repositories.')
    group_projects.add_argument('-s',
                                '--sync',
                                dest='backup_target',
                                action='store',
                                nargs="+",
                                metavar="REMOTE",
                                help='backup selected repositories to the cloud'
                                     ' or usb drives, or to "all".')
    group_projects.add_argument('-c',
                                '--check',
                                dest='check',
                                action='store_true',
                                default=False,
                                help='check and repair selected repositories.')
    group_projects.add_argument('-f',
                                '--fuse',
                                dest='fuse',
                                action='store',
                                metavar="MOUNT_POINT",
                                nargs=1,
                                help='Mount/unmount a specified repository '
                                     'to a mountpoint.')
    group_projects.add_argument('-r',
                                '--restore',
                                dest='restore',
                                action='store',
                                metavar="RESTORE_DIRECTORY",
                                nargs=1,
                                help='Restore latest to this directory.')
    group_projects.add_argument('--last-synced',
                                dest='last_synced',
                                action='store_true',
                                default=False,
                                help='list when you last backed up repositories.')
    group_projects.add_argument('--recover',
                                dest='recover',
                                action='store',
                                nargs=2,
                                metavar=("REMOTE", "TARGET"),
                                help='recover repository from remote to target.')
    args = parser.parse_args()
    logger.debug(args)

    if args.names is None and args.last_synced is False and args.list_repositories is False:
        log("No project selected. Nothing can be done.", color="red", save=False)
        sys.exit(-1)

    if args.config and Path(args.config[0]).exists():
        configuration_file = Path(args.config[0])
    else:
        config_path = xdg.BaseDirectory.save_config_path("grenier")
        configuration_file = Path(config_path, CONFIG_FILE)
        try:
            assert configuration_file.exists()
        except AssertionError:
            log("No configuration file found at %s" % configuration_file, color="red", save=False)
            sys.exit(-1)

    if args.fuse:
        try:
            assert Path(args.fuse[0]).exists()
            assert len(args.names) == 1
        except AssertionError:
            log("One project (and one only) must be specified with --name,"
                " and the mountpoint must be an existing directory.", color="red", save=False)
            sys.exit(-1)

    if args.restore:
        try:
            assert len(args.names) == 1
        except AssertionError:
            log("One project (and one only) must be specified with --name", color="red", save=False)
            sys.exit(-1)

    # This is where stuff actually gets done.
    overall_start = time.time()
    try:
        with Grenier(configuration_file) as g:
            if not g.open_config():
                log("Invalid configuration. Exiting.", color="red", save=False)
                sys.exit(-1)
            for p in g.repositories:

                if args.list_repositories:
                    print(p)

                if args.names is not None and p.name in args.names or args.names == ["all"]:
                    log("\n+ %s +\n" % p.name, color="boldblue")
                    log(p, display=False)

                    if args.check:
                        p.check_and_repair()

                    if args.backup:
                        p.save()

                    if args.backup_target:
                        # finding what remotes to back up
                        if args.backup_target == ["all"]:
                            remotes_to_backup = p.remotes
                        else:
                            remote_names = [el.name for el in p.remotes]
                            remotes_to_backup = [d for d in args.backup_target
                                                 if d in remote_names]
                        for remote in remotes_to_backup:
                            p.sync_remote(remote)
                        g.export_last_sync()

                    if args.fuse:
                        target = Path(args.fuse[0])
                        if is_fuse_mounted(target):
                            p.unfuse(target)
                        else:
                            p.fuse(target)

                    if args.restore:
                        p.restore(Path(args.restore[0]))

                    if args.recover:
                        p.recover(args.recover[0], args.recover[1])

            if args.last_synced:
                g.show_last_synced()

        overall_time = time.time() - overall_start
        log("\nEverything was done in %.2fs." % overall_time, color="boldgreen")
        notify_this("Everything was done in %.2fs." % overall_time)

    except KeyboardInterrupt:
        overall_time = time.time() - overall_start
        red("\n!! Got interrupted after %.2fs." % overall_time)
        notify_this("!! Grenier was killed after %.2fs." % overall_time)
        sys.exit(-1)


if __name__ == "__main__":
    main()
