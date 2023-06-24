
from ctypes import wintypes
import ctypes

from pystray._util import serialized_image, win32
import pystray


def patch_on_notify(icon:pystray._win32.Icon):
    icon.menu_visible = False
    
    def patched_on_notify(self, wparam, lparam):
        """Handles ``WM_NOTIFY``.

        If this is a left button click, this icon will be activated. If a menu
        is registered and this is a right button click, the popup menu will be
        displayed.
        """
        if lparam == win32.WM_LBUTTONUP:
            self()

        elif self._menu_handle and lparam == win32.WM_RBUTTONUP:
            # TrackPopupMenuEx does not behave unless our systray window is the
            # foreground window
            win32.SetForegroundWindow(self._hwnd)

            # Get the cursor position to determine where to display the menu
            point = wintypes.POINT()
            win32.GetCursorPos(ctypes.byref(point))

            # Display the menu and get the menu item identifier; the identifier
            # is the menu item index
            hmenu, descriptors = self._menu_handle
            self.menu_visible = True
            index = win32.TrackPopupMenuEx(
                hmenu,
                win32.TPM_RIGHTALIGN | win32.TPM_BOTTOMALIGN
                | win32.TPM_RETURNCMD,
                point.x,
                point.y,
                self._menu_hwnd,
                None)
            self.menu_visible = False
            if index > 0:
                descriptors[index - 1](self)
    icon._on_notify = patched_on_notify
    icon._message_handlers[win32.WM_NOTIFY] = lambda w, l: icon._on_notify(icon, w, l)