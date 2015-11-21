import logging
import time
from pathlib import Path
import xdg.BaseDirectory


def set_up_logger(program):
    data_path = xdg.BaseDirectory.save_data_path(program)
    log_path = Path(data_path,
                    "log",
                    "{date}_{program}.log".format(date=time.strftime("%Y-%m-%d_%Hh%M"),
                                                  program=program))
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True)
    program_logger = logging.getLogger(program)
    program_logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    program_logger.addHandler(ch)

    fh = logging.FileHandler(log_path.as_posix())
    fh.setLevel(logging.DEBUG)
    program_logger.addHandler(fh)
    return program_logger

logger = set_up_logger("grenier")
