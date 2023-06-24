import subprocess

def get_last_line(filename, lines):
    """ Windows-only atm 
        NOT platform independent but couldn't find a faster way
    """

    return subprocess.check_output(
        ["powershell", "-windowstyle", "hidden", "-command", f'get-content -tail {lines} "{filename}"'],
        universal_newlines=True,
        errors='ignore',
        creationflags=subprocess.CREATE_NO_WINDOW).strip()
