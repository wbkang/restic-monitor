import subprocess
from subprocess import Popen
import threading
import logging
import os
import time
import asyncio
from pathlib import Path
from .lastline import get_last_line

class ResticMonitor:
    def __init__(self, app_dir, restic_exe, args, env):
        self.app_dir = app_dir
        self.restic_exe = restic_exe
        self.args = args
        self.env = env
        self.cancel_requested = False
        self.restic_proc: subprocess.Popen = None
        self.lock = threading.RLock()
        self.logger = logging.getLogger("ResticMonitor")
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(f"ResticMonitor initialized with restic_exe:{restic_exe}, args={args}")
        # don't print sensitive values
        self.logger.info(f"The following env vars are specified: {env.keys()}")
        self._last_run_code = None
        self._last_run_cancelled = False

    def _restic_log_filename(self):
        return os.path.join(self.app_dir, "logs", "restic-last.log")
    
    def _restic_successul_marker_filename(self):
        return os.path.join(self.app_dir, "restic-last-successful.marker")

    def seconds_since_last_successful_run(self):
        if not os.path.exists(self._restic_successul_marker_filename()):
            return None
        else:
            return time.time() - os.path.getmtime(self._restic_successul_marker_filename())
    
    def last_run_code(self):
        with self.lock:
            return self._last_run_code

    def is_restic_running(self):
        " thread safe "
        with self.lock:
            return self.restic_proc is not None

    def cancel_run(self):
        # " must be called from event loop"
        with self.lock:
            self.cancel_requested = True
            if self.restic_proc is not None:
                self.restic_proc.kill()
    
    def is_last_run_cancelled(self):
        with self.lock:
            return self._last_run_cancelled

    def get_restic_last_lines(self, lines=1):
        return get_last_line(self._restic_log_filename(), lines)


    async def run_backup(self, onprogress):
        args = [self.restic_exe] + self.args
        environ_copy = os.environ.copy()
        environ_copy.update(self.env)
        
        self.logger.info(f"run_backup starting")
        self.restic_logfile = open(self._restic_log_filename(), "w")
        with self.lock:
            self.restic_proc = Popen(args, 
                                     env=environ_copy, 
                                     stdout=self.restic_logfile, 
                                     stderr=self.restic_logfile, 
                                     stdin=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)

        while self.restic_proc.poll() is None:
            self.logger.debug(f"run_backup: Waiting for restic to be done")
            onprogress()
            await asyncio.sleep(1)
        
        self.restic_logfile.close()
        
        self.logger.info(f"run_backup: restic returned {self.restic_proc.returncode}")

        if self.restic_proc.returncode == 0:
            Path(self._restic_successul_marker_filename()).touch()
        with self.lock:
            cancelled = self.cancel_requested
            self._last_run_cancelled = cancelled
            self.cancel_requested = False
            retval = self.restic_proc.returncode
            self._last_run_code = self.restic_proc.returncode
            self.restic_proc = None
        return (retval, cancelled)
