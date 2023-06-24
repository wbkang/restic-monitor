import win32api

def get_idle_time():
    return (win32api.GetTickCount()-win32api.GetLastInputInfo())/1000
