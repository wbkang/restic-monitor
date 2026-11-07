import os
import subprocess

def openshell(directory, restic_exe=None, env=None):
    """Open an interactive cmd set up for restic troubleshooting:
    env.json variables applied and restic's directory prepended to PATH.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    if restic_exe:
        restic_dir = os.path.dirname(restic_exe)
        if restic_dir:
            full_env["PATH"] = restic_dir + os.pathsep + full_env.get("PATH", "")
    subprocess.Popen(
        ["cmd.exe", "/k"],
        cwd=directory,
        env=full_env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
