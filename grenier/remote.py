from configparser import ConfigParser
from pathlib import Path
import getpass


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

