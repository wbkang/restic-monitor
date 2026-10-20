import subprocess
from subprocess import Popen
import threading
import logging
import os
import glob
import time
import datetime
import asyncio
from pathlib import Path
from .lastline import get_last_line

class ResticMonitor:
    def __init__(self, app_dir, restic_exe, args, env,
                 name="restic", ignore_exit_code_3=False, log_retention_days=180):
        self.app_dir = app_dir
        self.restic_exe = restic_exe
        self.args = args
        self.env = env
        self.name = name
        self.ignore_exit_code_3 = ignore_exit_code_3
        self.log_retention_days = log_retention_days
        self.cancel_requested = False
        self.restic_proc: subprocess.Popen = None
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"ResticMonitor[{name}]")
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(f"ResticMonitor '{name}' initialized with restic_exe:{restic_exe}, args={args}")
        # don't print sensitive values
        self.logger.info(f"The following env vars are specified: {list(env.keys())}")
        self._last_run_code = None
        self._last_run_cancelled = False
        self._current_logfile = None
        os.makedirs(self._log_dir(), exist_ok=True)

    # --- log file management ------------------------------------------------
    def _log_dir(self):
        return os.path.join(self.app_dir, "logs", self.name)

    def _new_run_logfile(self):
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return os.path.join(self._log_dir(), f"{self.name}-{ts}.log")

    def _restic_log_filename(self):
        """Current run's log while running/just-ran, else the most recent one."""
        if self._current_logfile and os.path.exists(self._current_logfile):
            return self._current_logfile
        files = sorted(glob.glob(os.path.join(self._log_dir(), f"{self.name}-*.log")))
        if files:
            return files[-1]
        # nothing yet; return a non-existent path in the log dir
        return os.path.join(self._log_dir(), f"{self.name}-none.log")

    def prune_old_logs(self):
        """Delete this target's run logs older than log_retention_days."""
        cutoff = time.time() - self.log_retention_days * 86400
        for f in glob.glob(os.path.join(self._log_dir(), f"{self.name}-*.log")):
            try:
                if os.path.getmtime(f) < cutoff:
                    os.remove(f)
            except OSError:
                self.logger.warning(f"Could not prune old log {f}", exc_info=1)

    def _restic_successul_marker_filename(self):
        return os.path.join(self.app_dir, f"{self.name}-last-successful.marker")

    # --- status helpers -----------------------------------------------------
    def seconds_since_last_successful_run(self):
        if not os.path.exists(self._restic_successul_marker_filename()):
            return None
        else:
            return time.time() - os.path.getmtime(self._restic_successul_marker_filename())

    def last_run_code(self):
        with self.lock:
            return self._last_run_code

    def is_ok(self):
        """True if the last run counts as success (0, or 3 when ignored)."""
        with self.lock:
            c = self._last_run_code
        return c == 0 or (c == 3 and self.ignore_exit_code_3)

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

    # --- the run ------------------------------------------------------------
    async def run_backup(self, onprogress):
        args = [self.restic_exe] + self.args
        environ_copy = os.environ.copy()
        environ_copy.update(self.env)

        os.makedirs(self._log_dir(), exist_ok=True)
        self._current_logfile = self._new_run_logfile()
        self.logger.info(f"run_backup '{self.name}' starting -> {self._current_logfile}")
        self.restic_logfile = open(self._current_logfile, "w")
        with self.lock:
            self.restic_proc = Popen(args,
                                     env=environ_copy,
                                     stdout=self.restic_logfile,
                                     stderr=self.restic_logfile,
                                     stdin=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)

        while self.restic_proc.poll() is None:
            self.logger.debug(f"run_backup[{self.name}]: Waiting for restic to be done")
            onprogress()
            await asyncio.sleep(1)

        self.restic_logfile.close()

        self.logger.info(f"run_backup[{self.name}]: restic returned {self.restic_proc.returncode}")

        rc = self.restic_proc.returncode
        if rc == 0 or (rc == 3 and self.ignore_exit_code_3):
            Path(self._restic_successul_marker_filename()).touch()
        with self.lock:
            cancelled = self.cancel_requested
            self._last_run_cancelled = cancelled
            self.cancel_requested = False
            retval = self.restic_proc.returncode
            self._last_run_code = self.restic_proc.returncode
            self.restic_proc = None

        self.prune_old_logs()
        return (retval, cancelled)
