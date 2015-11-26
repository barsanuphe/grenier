from pathlib import Path


class GrenierSource(object):
    def __init__(self, name, target_dir, format_list=None):
        self.name = name
        self.target_dir = Path(target_dir)
        if format_list:
            self.excluded_extensions = format_list
        else:
            self.excluded_extensions = []

    def __str__(self):
        return "Source %s: \n\tPath: %s\n\tExluded extensions: %s" % (self.name,
                                                                      self.target_dir,
                                                                      " ".join(self.excluded_extensions))

    # TODO : get when last synced, etc
