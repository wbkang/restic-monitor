from __future__ import unicode_literals
import logging.handlers
import os
from datetime import datetime
from dateutil.tz import tzutc


class LogConfigurator(object):
    def __init__(self, name):
        self.formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(name)s): %(message)s")
        self.console_setup = False
        self.file_setup = False
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.name = name

    def setup_file_logger(self, logfile_dir):
        if self.file_setup:
            raise Exception("File logger already setup")
        if not os.path.exists(logfile_dir):
            os.makedirs(logfile_dir)
        logfile_path = os.path.join(logfile_dir, ("%s.log" % (self.name)))
        file_handler = logging.handlers.TimedRotatingFileHandler(
            logfile_path, when="H", interval=1, backupCount=100, encoding=None, delay=False, utc=False
        )
        file_handler.setFormatter(self.formatter)
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.file_setup = True

    def setup_console_logger(self):
        if self.console_setup:
            raise Exception("Console logger already setup")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)
        self.console_setup = True


def normalize_isoformat(iso_datetime):
    """Append milliseconds to iso datetime if it does not exist"""
    if "." in iso_datetime:
        return iso_datetime
    else:
        return iso_datetime + ".000"


def timestr_now():
    return normalize_isoformat(datetime.utcnow().isoformat())


def timestr(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(tzutc()).replace(tzinfo=None)
    return normalize_isoformat(dt.isoformat())