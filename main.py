# actual main file to make package import happy
if __name__ == '__main__':
    try:
        from restic_monitor.main import run
        import sys
        run()
    except Exception as e:
        import traceback
        tb = traceback.format_exception(e)
        from restic_monitor.messagebox import messagebox
        messagebox(f"Uncaught exception in main {tb}. sys.path: {sys.path}")
