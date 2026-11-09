import os
import sys
import ctypes
from ctypes import wintypes
import winreg
from typing import Optional, Set
from PySide6.QtCore import QRect
import win32gui
import win32con
from enhanced_cursor.logger import get_logger

logger = get_logger()
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

_mutex_handle = None
MUTEX_NAME = "EnhancedCursor_SingleInstance_Mutex_v2"


def acquire_single_instance_mutex(name: str = MUTEX_NAME) -> bool:
    """Acquires a named mutex to ensure only one instance of the app runs."""
    global _mutex_handle
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD

    handle = kernel32.CreateMutexW(None, False, name)
    last_error = kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            kernel32.CloseHandle(handle)
        logger.warning("Another instance of EnhancedCursor is already running.")
        return False

    _mutex_handle = handle
    return True


def release_single_instance_mutex():
    global _mutex_handle
    if _mutex_handle:
        try:
            kernel32.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None


def get_virtual_desktop_rect() -> QRect:
    """Returns the QRect bounding all attached monitors (virtual screen)."""
    try:
        # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
        # SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79
        x = user32.GetSystemMetrics(76)
        y = user32.GetSystemMetrics(77)
        w = user32.GetSystemMetrics(78)
        h = user32.GetSystemMetrics(79)
        if w > 0 and h > 0:
            return QRect(x, y, w, h)
    except Exception as e:
        logger.error(f"Error fetching virtual desktop metrics: {e}")
    # Fallback to standard primary screen metrics (SM_CXSCREEN = 0, SM_CYSCREEN = 1)
    return QRect(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def get_app_executable_path() -> str:
    """Returns the executable command path for Windows autostart."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    else:
        # Running via Python
        py_exe = sys.executable
        # Use pythonw if available to avoid opening console window
        pythonw = os.path.join(os.path.dirname(py_exe), "pythonw.exe")
        if os.path.exists(pythonw):
            py_exe = pythonw
        script = os.path.abspath(sys.argv[0])
        return f'"{py_exe}" "{script}"'


def set_autostart(enable: bool, app_name: str = "EnhancedCursor") -> bool:
    """Adds or removes the application from Windows CurrentVersion/Run."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
            if enable:
                cmd = get_app_executable_path()
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                logger.info(f"Startup enabled: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info("Startup disabled")
                except FileNotFoundError:
                    pass
            return True
    except Exception as e:
        logger.error(f"Error updating autostart in registry: {e}")
        return False


def is_autostart_enabled(app_name: str = "EnhancedCursor") -> bool:
    """Checks if app is registered in Windows CurrentVersion/Run."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"Error checking autostart status: {e}")
        return False


def register_global_hotkey(hwnd: int, hotkey_id: int = 1, mod_keys: int = 0x0001 | 0x0002, vk_code: int = 0x48) -> bool:
    """
    Registers a global hotkey with user32.
    Default: Ctrl (0x0002) + Alt (0x0001) + 'H' (0x48).
    MOD_NOREPEAT (0x4000) prevents key repeat spamming.
    """
    try:
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        mod = mod_keys | 0x4000  # MOD_NOREPEAT
        res = user32.RegisterHotKey(hwnd, hotkey_id, mod, vk_code)
        if res:
            logger.info(f"Global hotkey registered: id={hotkey_id}, mod={hex(mod)}, vk={hex(vk_code)}")
            return True
        else:
            logger.warning(f"Failed to register global hotkey (code {kernel32.GetLastError()})")
    except Exception as e:
        logger.error(f"Exception registering global hotkey: {e}")
    return False


def unregister_global_hotkey(hwnd: int, hotkey_id: int = 1) -> bool:
    try:
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        return bool(user32.UnregisterHotKey(hwnd, hotkey_id))
    except Exception:
        return False


# Fullscreen & Game Detection
IGNORED_WINDOW_CLASSES: Set[str] = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
}


def is_fullscreen_window_active(ignore_hwnds: Optional[Set[int]] = None) -> bool:
    """
    Checks if active foreground window is occupying the entire monitor in fullscreen mode
    (such as a game, full-screen video, or presentation).
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or (ignore_hwnds and hwnd in ignore_hwnds):
            return False

        class_name = win32gui.GetClassName(hwnd)
        if class_name in IGNORED_WINDOW_CLASSES:
            return False

        # Get window rect
        rect = win32gui.GetWindowRect(hwnd)
        win_w = rect[2] - rect[0]
        win_h = rect[3] - rect[1]

        # Get monitor info for this window
        h_monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not h_monitor:
            return False

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi)):
            mon_rect = mi.rcMonitor
            mon_w = mon_rect.right - mon_rect.left
            mon_h = mon_rect.bottom - mon_rect.top
            # If foreground window spans the monitor dimensions or larger
            if rect[0] <= mon_rect.left and rect[1] <= mon_rect.top and win_w >= mon_w and win_h >= mon_h:
                return True
    except Exception:
        pass
    return False


class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HICON),
        ("ptScreenPos", wintypes.POINT),
    ]


_user32_GetCursorInfo = user32.GetCursorInfo
_user32_GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
_user32_GetCursorInfo.restype = wintypes.BOOL
_idc_ibeam = None


def is_ibeam_cursor_active() -> bool:
    """Checks whether the system cursor is currently an I-Beam (text edit) cursor."""
    global _idc_ibeam
    try:
        if _idc_ibeam is None:
            # IDC_IBEAM = 32513
            _idc_ibeam = user32.LoadCursorW(None, 32513)

        ci = _CURSORINFO()
        ci.cbSize = ctypes.sizeof(_CURSORINFO)
        if _user32_GetCursorInfo(ctypes.byref(ci)):
            if ci.flags & 1:  # CURSOR_SHOWING
                return ci.hCursor == _idc_ibeam
    except Exception:
        pass
    return False

