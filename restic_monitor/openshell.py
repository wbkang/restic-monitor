import ctypes

def openshell(directory):
    ctypes.windll.shell32.ShellExecuteW(None, "open", "cmd.exe", "", directory, 1)