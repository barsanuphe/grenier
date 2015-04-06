import logging, os, time
from pathlib import Path

def set_up_logger(program):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    log_path = Path(script_dir, "log")
    if not log_path.exists():
        log_path.mkdir(parents=True)
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    fh = logging.FileHandler("log/%s_%s.log" % (time.strftime("%Y-%m-%d_%Hh%M"), 
                                              program))
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger

logger = set_up_logger("grenier")