"""
Multi-client support for CATS.

Two things are needed to drive more than one Elite Dangerous client from the same PC:

1. Only one CATS instance may send keys/mouse input at a time (input is global, not per-window).
   A named Windows mutex is shared by every CATS instance in the same login session.
2. Before sending input, the correct Elite window must be in the foreground.

Both are opt-in: if `game_window` is empty in settings.txt, input_session() does nothing and CATS
behaves exactly as before.

game_window values:
    (empty)     disabled, original behaviour
    1, 2, ...   the Nth running Elite client, ordered by launch time (1 = started first)
    pid:1234    the Elite client with that process ID
"""

import ctypes
import time
from contextlib import contextmanager

import psutil

ELITE_PROCESS_NAMES = ("EliteDangerous64.exe",)
MUTEX_NAME = "Local\\CATS_INPUT_LOCK"

_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080  # previous owner died; we now own the mutex
_INFINITE = 0xFFFFFFFF

_VK_MENU = 0x12
_KEYEVENTF_KEYUP = 0x0002
_SW_RESTORE = 9

_target = ""  # raw game_window setting
_mutex_handle = None


def configure(game_window):
    """Set the target client from the settings value."""
    global _target
    _target = (game_window or "").strip()


def enabled():
    return _target != ""


def _find_elite_pid():
    if _target.lower().startswith("pid:"):
        return int(_target[4:])

    index = int(_target)
    if index < 1:
        raise ValueError("game_window must be 1 or higher, or pid:<number>")

    procs = []
    for proc in psutil.process_iter(["name", "create_time"]):
        if proc.info["name"] in ELITE_PROCESS_NAMES:
            procs.append(proc)
    procs.sort(key=lambda p: p.info["create_time"])

    if index > len(procs):
        raise RuntimeError(
            "game_window=%d but only %d Elite client(s) are running" % (index, len(procs)))
    return procs[index - 1].pid


def _find_window_for_pid(pid):
    user32 = ctypes.windll.user32
    found = []

    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        window_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        # Owner-less, visible top-level window belonging to the client process
        if window_pid.value == pid and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)

    if not found:
        raise RuntimeError("No visible window found for Elite process %d" % pid)
    return found[0]


def focus_game():
    """Bring the configured Elite window to the foreground. Raises on failure."""
    user32 = ctypes.windll.user32
    hwnd = _find_window_for_pid(_find_elite_pid())

    for _ in range(5):
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, _SW_RESTORE)

        # Windows only lets the foreground process hand focus over; a synthetic Alt tap lifts that lock.
        user32.keybd_event(_VK_MENU, 0, 0, 0)
        user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(hwnd)

        time.sleep(0.5)
        if user32.GetForegroundWindow() == hwnd:
            return
    raise RuntimeError("Could not bring the Elite window to the foreground")


def _acquire():
    global _mutex_handle
    kernel32 = ctypes.windll.kernel32
    if _mutex_handle is None:
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not _mutex_handle:
            raise RuntimeError("Could not create the CATS input mutex")

    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    result = kernel32.WaitForSingleObject(_mutex_handle, _INFINITE)
    if result not in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
        raise RuntimeError("Waiting for the CATS input mutex failed (code %d)" % result)


def _release():
    ctypes.windll.kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)


@contextmanager
def input_session():
    """
    Hold the shared input lock and focus this instance's Elite window for the duration of the block.
    The lock is owned by the calling thread, so acquire and release must happen in the same thread.
    """
    if not enabled():
        yield
        return

    _acquire()
    try:
        focus_game()
        yield
    finally:
        _release()
