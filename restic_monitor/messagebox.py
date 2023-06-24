import ctypes

def messagebox(msg, title="Restic Monitor"):
    ctypes.windll.user32.MessageBoxW(0, msg, title, 0)