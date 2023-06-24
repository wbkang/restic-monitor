import os

def get_appdir(appname):
    return os.path.join(os.environ['LOCALAPPDATA'], appname)