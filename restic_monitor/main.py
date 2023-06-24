# avoid import here until we fix the sys.path

APP_NAME = 'restic-monitor'

PAUSE_UNTIL_FILENAME = "pause_until.txt"
LOG_FILENAME = "restic-monitor.log"

LOCKFILE_NAME = "lock"
SETTINGS_FILENAME = "settings.json"
ENV_FILENAME = "env.json"

RESTIC_EXE_SETTING = "restic_exe"
ARGS_SETTING = "args"
MIN_IDLE_SECONDS_SETTING = 'min_idle_seconds'
IGNORE_EXIT_CODE_3_SETTING = 'ignore_exit_code_3'
NO_BACKUP_WARNING_SETTING = 'no_backup_warning_seconds'
MIN_SECONDS_BETWEEN_BACKUPS_SETTING = 'min_seconds_between_backups'

def elevate_if_needed(debug):
    ''' Not used if it's started w/ pyinstaller, since it does its own thing '''
    import ctypes, sys

    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    if is_admin():
        return True
    else:
        # Re-run the program with admin rights
        import os
        
        new_args = [sys.executable,
                    os.path.join(os.path.dirname(__file__), "..", "main.py"),
                    "--pythonpath",
                    os.pathsep.join(sys.path),
                    "--cwd",
                    os.getcwd()]
        if debug:
            new_args = ["cmd.exe", "/k"] + new_args
        processed_args = []
        # the proper way is to use shlex.quote equivalent for windows
        for a in new_args[1:]:
            if " " in a:
                processed_args.append('"' + a + '"')
            else:
                processed_args.append(a)
        args= " ".join(processed_args)
        print(f"Running {args}")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", new_args[0], " ".join(processed_args), None, 1)
        return False

def run():

    import argparse
    import sys
    import os
    import subprocess

    parser = argparse.ArgumentParser()
    parser.add_argument("--pythonpath", help="PYTHONPATH")
    parser.add_argument("--cwd", help="cwd")
    parser.add_argument("--debug", help="cwd", action="store_true")
    args = parser.parse_args()
    if args.pythonpath:
        for p in args.pythonpath.split(";"):
            sys.path.append(p)
    if args.cwd:
        os.chdir(args.cwd)

    from .messagebox import messagebox
    from .appdir import get_appdir
    rootappdir = get_appdir(APP_NAME)
    os.makedirs(rootappdir, exist_ok=True)
    os.makedirs(os.path.join(rootappdir, "logs"), exist_ok=True)
    settings_json = os.path.join(rootappdir, SETTINGS_FILENAME)
    env_json = os.path.join(rootappdir, ENV_FILENAME)
    if not os.path.exists(settings_json) or not os.path.exists(env_json):
        messagebox(f"Please create {SETTINGS_FILENAME} and {ENV_FILENAME} in {rootappdir}. Opening the directory now.")
        os.startfile(rootappdir)
        return 1


    if not elevate_if_needed(args.debug):
        # print("not an admin, relaunching")
        return
    
    import json
    import logging
    import os
    import asyncio
    from .logutils import LogConfigurator
    from .monitor import ResticMonitor
    from .tray import ResticTray
    import filelock

    logger = logging.getLogger("main")
    logconf = LogConfigurator(APP_NAME)
    logconf.setup_console_logger()

    logconf.setup_file_logger(os.path.join(rootappdir, "logs"))

    logging.info(f"Loading settings from {settings_json}")
    with open(settings_json) as f:
        settings = json.loads(f.read())
    logging.info(f"Loading settings from {env_json}")
    with open(env_json) as f:
        env = json.loads(f.read())
    
    os.environ.update(env)

    logger.info("Checking lockfile")
    lockfile_path = os.path.join(rootappdir, LOCKFILE_NAME)
    
    lock = filelock.FileLock(lockfile_path)
    restart_requested = False
    try:
        lock.acquire(timeout=0)

        logger.info(f"Launched with {sys.executable} {sys.argv}")

        if args.debug:
            import aiodebug.log_slow_callbacks
            aiodebug.log_slow_callbacks.enable(0.05)

        monitor = ResticMonitor(app_dir=rootappdir, restic_exe=settings[RESTIC_EXE_SETTING], args=settings[ARGS_SETTING], env=env)
        
        tray = ResticTray(
            monitor=monitor,
            min_idle_seconds=int(settings[MIN_IDLE_SECONDS_SETTING]),
            no_backup_warning_seconds=int(settings[NO_BACKUP_WARNING_SETTING]),
            min_seconds_between_backups=int(settings[MIN_SECONDS_BETWEEN_BACKUPS_SETTING]),
            pause_until_filename=os.path.join(rootappdir, PAUSE_UNTIL_FILENAME),
            ignore_exit_code_3=bool(settings.get(IGNORE_EXIT_CODE_3_SETTING, False)),
            app_log=os.path.join(rootappdir, "logs", "restic-monitor.log")
        )
        
        asyncio.run(tray.run_async())
        logger.info(f"Done event loop waiting - restart: {tray.restart}")

        restart_requested = tray.restart
    except KeyboardInterrupt:
        tray.tray_shutdown()
    except filelock.Timeout:
        logger.exception("Another instance running?")
        messagebox("Another instance of ResticMonitor is running! Close that one first.")
        return
    finally:
        lock.release()
    
    if restart_requested:
        if os.path.basename(sys.executable) == "restic-monitor.exe":
            # launched from the pyinstaller exe
            args = [sys.executable]
        else:
            args = [sys.executable,
                    os.path.join(os.path.dirname(__file__), "..", "main.py"),
                    "--pythonpath",
                    os.pathsep.join(sys.path),
                    "--cwd",
                    os.getcwd()]
        logger.debug(f"Restarting with args:{args}")
        subprocess.Popen(args, start_new_session=True)


