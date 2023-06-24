from pystray import Icon, Menu as menu, MenuItem as item
import pystray
import logging
import datetime
from PIL import Image
import threading
import asyncio
from .monitor import ResticMonitor
from .idle import get_idle_time
import os
from .pystray_patch import patch_on_notify
from .openshell import openshell

class ResticTray:
    MAIN_ICON = "main.ico"
    GOOD_ICON = "good.ico"
    FAILED_ICON = "failed.ico"
    WARNING_ICON = "warning.ico"
    RUNNING_ICON = "wip.ico"
    PAUSED_ICON = "paused.ico"

    def __init__(self, 
                 monitor: ResticMonitor, 
                 min_idle_seconds: int,
                 min_seconds_between_backups: int,
                 no_backup_warning_seconds: int,
                 pause_until_filename: str,
                 ignore_exit_code_3: bool,
                 app_log:str) -> None:
        self.logger = logging.getLogger("ResticTray")
        self.logger.setLevel(logging.DEBUG)
        # extracted during run_async()
        self.loop : asyncio.AbstractEventLoop = None
        # set to True if restart was requested on shutdown.
        self.restart = False
        self.update_menu_queued = False
        self.app_log = app_log
        self.min_seconds_between_backups = min_seconds_between_backups
        self.ignore_exit_code_3 = ignore_exit_code_3
        self.last_old_backup_warn_time:datetime.datetime = None
        m = menu(
            item(lambda _: self.tray_get_info_line1_text(),
                 action=lambda: None),
            item(lambda _: self.tray_get_info_line2_text(),
                 action=lambda: None),
            menu.SEPARATOR,
            item(
                '▶️ Run now',
                lambda: self.tray_request_run(),
                enabled=lambda _: self.tray_is_runnable()
                ),
            item(
                '⏹️ Stop',
                lambda: self.tray_request_stop_run(),
                enabled=lambda _: self.tray_is_stoppable()
                ),
            item(
                '⏸️ Pause for 8 hours',
                lambda: self.tray_toggle_pause(),
                checked=lambda _:self.tray_is_paused()
                ),
            menu.SEPARATOR,
            item(
                '📜 Open the most recent Restic log',
                lambda: self.tray_open_log(),
                enabled=lambda _: self.tray_can_open_log()
            ),
            item(
                '📂 Open App Directory',
                lambda: self.tray_open_app_dir(),
                default=True
            ),
            item(
                '📂 Open App Log',
                lambda: self.tray_open_app_log(),
            ),
            item(
                '🔧 Open Rustic Shell',
                lambda: self.tray_open_shell()
            ),
            menu.SEPARATOR,
            item(
                '🔃 Reload',
                lambda: self.tray_shutdown(restart=True)),
            item(
                '👋 Quit',
                lambda: self.tray_shutdown()),
        )
        self.no_backup_warning_seconds = no_backup_warning_seconds
        self.icon_images = self._load_resources()
        self.icon = pystray.Icon(
            'restic-monitor',
            title="Loading",
            menu=m,
            icon=self.icon_images[ResticTray.MAIN_ICON])
        patch_on_notify(self.icon)
        self.monitor : ResticMonitor = monitor
        
        self.min_idle_seconds = min_idle_seconds
        self.run_requested = False
        self.pause_until_filename = pause_until_filename
        self.pause_until: datetime.datetime = self._load_pause_until_from_file()

        # to signal to the watcher to re-evaluate the next action now.
        self.wakeup_watcher_event = asyncio.Event()
        # to signal that the os-thread of the tray is about to exit.
        self.shutdown_event = asyncio.Event()
        self.quit = False
        self.lock = threading.RLock()
        self.tasks = set()
        self.tray_title = "default_title"

    def _load_pause_until_from_file(self):
        try:
            if os.path.exists(self.pause_until_filename):
                with open(self.pause_until_filename, "r") as f:
                    return datetime.datetime.fromisoformat(f.read())
        except:
            self.logger.warn(f"Failed to read {self.pause_until_filename}", exc_info=1)
        return None
    
    def _save_pause_until(self, value:datetime.datetime):
        try:
            self.pause_until = value
            if self.pause_until:
                with open(self.pause_until_filename, "w") as f:
                    f.write(self.pause_until.isoformat())
            else:
                os.remove(self.pause_until_filename)
        except:
            self.logger.warn(f"Failed to persist pause until to {self.pause_until_filename}", exc_info=1)

    def _load_resources(self):
        self.logger.debug("_load_resources")
        icons = dict()
        resource_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))

        for dirpath, dirnames, filenames in os.walk(resource_root):
            for f in filenames:
                self.logger.debug(f"Resource found: {os.path.join(resource_root,dirpath, f)}")
        with open(os.path.join(resource_root, ResticTray.MAIN_ICON), "rb") as f:
            im = Image.open(f)
            im.resize((32, 32), Image.Resampling.BICUBIC)
            icons[ResticTray.MAIN_ICON] = im
        for overlay in [ResticTray.GOOD_ICON, 
                        ResticTray.WARNING_ICON, 
                        ResticTray.PAUSED_ICON, 
                        ResticTray.RUNNING_ICON,
                        ResticTray.FAILED_ICON]:
            with open(os.path.join(resource_root, overlay), "rb") as f:
                to_overlay = Image.open(f)
                copied = icons[ResticTray.MAIN_ICON].copy()
                copied.paste(to_overlay, (0,0), to_overlay)
                to_overlay.close()
                icons[overlay] = copied

        return icons

    def tray_request_run(self):
        " from event handler " 
        logging.info("request_run outside")
        async def work():
            logging.info("request_run work line 1")
            with self.lock:
                logging.info("request_run work run_requested")
                self.run_requested = True
                self.wakeup_watcher_event.set()
        self._fire_in_async(work())

    def tray_request_stop_run(self):
        logging.info("tray_request_stop_run outside")
        async def work():
            with self.lock:
                self.monitor.cancel_run()
        self._fire_in_async(work())

    def tray_is_stoppable(self):
        with self.lock:
            return self.monitor.is_restic_running()

    def _format_timedelta_minutes(self, td: datetime.timedelta):
        minutes = td.total_seconds() / 60
        seconds = td.seconds % 60
        return f"{minutes:.0f}m {seconds}s"

    def _format_timedelta_days(self, td: datetime.timedelta):
        s = []
        hours = int(td.seconds / 3600)
        min = int((td.seconds % 3600)/60)
        if td.days > 0:
            s.append(f"{td.days} days")
        if hours > 0:
            s.append(f"{hours} hours")
        if min > 0:
            s.append(f"{min} minutes")
        if len(s) > 0:
            return " ".join(s)
        return "Less than a minute"

    def sync_tray(self):
        '''
        Must be in the event loop

        Syncs the current world state into the tray icon state.
        '''
        self.logger.debug("sync_tray is running")
        asyncio.get_running_loop()
        # reflect the latest state into the tray icon

        def upgrade_icon_to_warning():
            if self.icon.icon != self.icon_images[ResticTray.WARNING_ICON] and \
                self.icon.icon != self.icon_images[ResticTray.FAILED_ICON]:
                self.icon.icon = self.icon_images[ResticTray.WARNING_ICON]

        with self.lock:
            if self.monitor.is_restic_running():
                self.icon.icon = self.icon_images[ResticTray.RUNNING_ICON]
                last_line = self.monitor.get_restic_last_lines(1)[0:64]
                self.icon.title = f"In progress: {last_line}"
            elif self.is_paused():
                self.icon.icon = self.icon_images[ResticTray.PAUSED_ICON]
                pause_until_formatted = self.pause_until.strftime("%Y-%m-%d %I:%m %p")
                self.icon.title = f"Paused until {pause_until_formatted}"
            else: # idle state
                last_code = self.monitor.last_run_code()
                if last_code == 0 or (last_code == 3 and self.ignore_exit_code_3):
                    self.icon.icon = self.icon_images[ResticTray.GOOD_ICON]
                    self.icon.title = self.get_last_ran_text()
                elif last_code is not None and last_code != 0:
                    last_run_cancelled = self.monitor.is_last_run_cancelled()
                    self.logger.debug(f"sync_tray: last_run_cancelled={last_run_cancelled}")
                    if self.monitor.is_last_run_cancelled():
                        self.icon.icon = self.icon_images[ResticTray.WARNING_ICON]
                        self.icon.title = "Last run cancelled by user"
                    elif last_code == 3:
                        self.icon.icon = self.icon_images[ResticTray.WARNING_ICON]
                        self.icon.title = "Some files were not backed up. Check the logs."
                    else:
                        self.icon.icon = self.icon_images[ResticTray.FAILED_ICON]
                        self.icon.title = f"Last back up failed with code {last_code}. Check the logs."
                else:
                    self.icon.title = ""
                
                # additional warnings
                if self.monitor.seconds_since_last_successful_run() is None:
                    upgrade_icon_to_warning()
                    self.icon.title = self.get_last_ran_text() + " " + self.icon.title
                elif self.monitor.seconds_since_last_successful_run() > self.no_backup_warning_seconds:
                    self.icon.title = f"It's been a while since the last successful backup! {self.icon.title}"
                    upgrade_icon_to_warning()
                self.warn_once_an_hour()

        def try_update():
            self.update_menu_queued = False
            if self.quit:
                self.logger.debug("Skip menu update since we are shutting down")
                return
            if not getattr(self.icon, "menu_visible", None):
                self.logger.debug("Calling icon.update_menu()")
                self.icon.update_menu()
            else:
                # sketchy busy loop - because pystray gives no way to be
                # notified when the menu is closed.
                if not self.update_menu_queued:
                    self.update_menu_queued = True
                    self.loop.call_later(0.1, try_update)
                    
        try_update()
        

    def tray_get_info_line1_text(self):
        """ This is the first informational line that shows up in the context menu
        """
        with self.lock:
            idle_period_str = self._format_timedelta_minutes(datetime.timedelta(seconds=self.min_idle_seconds))
            if not self.monitor.is_restic_running():
                return f"Wait for idle for {idle_period_str}"
            else:
                short_summary = self.monitor.get_restic_last_lines(1)[:32]
                return f"Running: {short_summary}"
    
    def tray_get_info_line2_text(self):
        """ This is the second informational line that shows up in the context menu
        """
        with self.lock:
            return self.get_last_ran_text()

    def get_last_ran_text(self):
        """
        Produces a user-friendly message about how long it's been since the last successful backup.
        """
        secs = self.monitor.seconds_since_last_successful_run()
        if secs is not None:
            td = datetime.timedelta(seconds=secs)
            idle_period_str = self._format_timedelta_days(td)
            return f"{idle_period_str} since the last successful backup"
        else:
            return "⚠️ Never ran a successful backup yet."

    def tray_open_log(self):
        self.logger.debug("Opening the log file")
        os.startfile(self.monitor._restic_log_filename())

    def tray_open_app_dir(self):
        self.logger.debug("Opening the app dir")
        os.startfile(self.monitor.app_dir)

    def tray_open_app_log(self):
        self.logger.debug("Opening the app log")
        os.startfile(self.app_log)

    def tray_open_shell(self):
        self.logger.debug("Opening the shell")
        openshell(self.monitor.app_dir)

    def tray_can_open_log(self):
        with self.lock:
            return os.path.exists(self.monitor._restic_log_filename())

    def _fire_in_async(self, coro, onexception=None):
        """
        This is a function to fire off a co-routine inside the main app event loop 
        (as opposed to the pystray event loop)
        """
        logging.info("_fire_in_async outside")
        def work():
            self.logger.debug("_fire_in_async running")
            t = asyncio.create_task(coro)
            self.tasks.add(t)
            def done_cb(t:asyncio.Task):
                exc = t.exception()
                if exc is not None:
                    self.logger.info("Exception in the future", exc_info=exc)
                    if onexception:
                        onexception(exc)
                    else:
                        self.logger.error("Exception from a task", exc_info=exc)
                self.tasks.discard(t)
            t.add_done_callback(done_cb)
        self.loop.call_soon_threadsafe(work)

    def tray_toggle_pause(self):
        " from event handler, resume backup OR to interrupt any existing process & invoke a pause " 
        async def do_pause():
            with self.lock:
                if not self.tray_is_paused():
                    self.logger.info("Enabling pause")
                    if self.monitor.is_restic_running():
                        self.monitor.cancel_run()
                    self._save_pause_until(datetime.datetime.now() + datetime.timedelta(hours=8))
                    self.wakeup_watcher_event.clear()
                else:
                    self.logger.info("Clearing pause")
                    self._save_pause_until(None)
                    self.wakeup_watcher_event.set()
                self.sync_tray()
        self._fire_in_async(do_pause())


    def tray_is_runnable(self):
        """
        Returns true if a new backup job can be started.
        """
        with self.lock:
            if self.monitor.is_restic_running():
                return False
            else:
                paused = self.tray_is_paused()
                return not paused

    def is_paused(self):
        if self.pause_until is None:
            logging.debug("currently not paused because pause_until is None")
            return False
        else:
            logging.debug(f"now <= pause until {datetime.datetime.now() <= self.pause_until}")
            return datetime.datetime.now() <= self.pause_until

    def tray_is_paused(self):
        " from the external tray thread only "
        with self.lock:
            return self.is_paused()
            
    
    async def run_backup_async(self):
        """
        Wrapper around actually triggering a new backup job.

        If there is already a job running, that request is ignored.
        """
        if self.monitor.is_restic_running():
            self.logger.debug("ResticTray:on_run_backup - already runnning!")
            return
        def onprogress():
            self.sync_tray()
            self.logger.debug(f"onprogress callback")
        retcode, cancelled = await self.monitor.run_backup(onprogress)
        self.icon.title = f"Return code is {retcode}"
        if cancelled:
            self.icon.notify(self.monitor.get_restic_last_lines(3), title=f"User cancelled backup. code {retcode}")
        elif retcode != 0:
            self.icon.notify(self.monitor.get_restic_last_lines(3), title=f"Restic failed with code {retcode}")
        self.sync_tray()
        await asyncio.sleep(0)

    def warn_once_an_hour(self):
        secs = self.monitor.seconds_since_last_successful_run()
        if secs is None  or secs > self.no_backup_warning_seconds:
            if self.last_old_backup_warn_time is not None and (datetime.datetime.now() - self.last_old_backup_warn_time) < datetime.timedelta(hours=1):
                self.logger.debug(f"Skipping old backup warning. Last warning:{self.last_old_backup_warn_time}")
                return
            self.logger.debug("Showing old backup warning")
            def notify():
                if not self.quit:
                    self.icon.notify(f"⚠️ It's been a long time since the last backup. {self.get_last_ran_text()}", "ResticMonitor")
            self.loop.call_later(1, notify)
            self.last_old_backup_warn_time = datetime.datetime.now()

    async def run_async(self):
        self.loop = asyncio.get_event_loop()
        self.logger.info("Starting up")
        
        self.icon.run_detached()

        asyncio.create_task(self.main_tray_loop())

        await asyncio.wait([
            asyncio.create_task(self.shutdown_event.wait()), 
            asyncio.create_task(self.main_tray_loop())
        ])

    async def main_tray_loop(self):
        self.logger.info("main_tray_loop is running")
        self.sync_tray()
        while not self.quit:
            # this loop is very important, and should continue to run.
            try:
                waiter = None
                idle_time = get_idle_time()
                if self.tray_is_paused():
                    # wait until the un-pause time for 1 hour (just in case), whichever is less 
                    wait_time = min((self.pause_until - datetime.datetime.now()).total_seconds(), 3600)
                    self.logger.debug(f"it's paused, nothing to do for {wait_time} seconds")
                    waiter = asyncio.sleep(wait_time)
                elif idle_time > self.min_idle_seconds or self.run_requested:
                    self.run_requested = False
                    if self.monitor.is_restic_running():
                        self.logger.error("Already running... not possible check again in 10sec")
                        waiter = asyncio.sleep(10)
                    else:
                        self.logger.debug("Running the job!!")
                        await self.run_backup_async()
                        waiter = asyncio.sleep(self.min_seconds_between_backups)
                        self.logger.debug(f"after run, watcher will sleep for {self.min_seconds_between_backups}s")
                else:
                    remaining_idle = max(0, self.min_idle_seconds - idle_time)
                    waiter = asyncio.sleep(remaining_idle)
                    self.logger.debug(f"watcher will sleep for {remaining_idle}s for idle")
                
                # wait until the waiting time, or until a wake up event.
                await asyncio.wait([
                    asyncio.create_task(waiter),
                    asyncio.create_task(self.wakeup_watcher_event.wait())
                ], return_when=asyncio.FIRST_COMPLETED)

                with self.lock:
                    # clear pause event only if there is no other pause scheduled
                    self.wakeup_watcher_event.clear()
            except:
                self.logger.error("Exception in main_tray_loop", exc_info=1)
            finally:
                self.logger.debug("main_tray_loop loop iteration over")
        self.logger.info("main_tray_loop quit")
        await asyncio.sleep(0)

    def tray_shutdown(self, restart=False):
        self.logger.info("Shutdown requested, stopping icon")
        self.icon.stop()
        async def inner_shutdown():
            with self.lock:
                self.logger.info("Shutting down from event loop side")
                self.monitor.cancel_run()
                self.quit = True
                self.restart = restart
                self.wakeup_watcher_event.set()
                self.shutdown_event.set()
        self._fire_in_async(inner_shutdown())
        