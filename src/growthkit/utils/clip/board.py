"""
Clipboard

A cross-platform clipboard module for Python, with copy & paste functions for plain text.
By Al Sweigart al@inventwithpython.com
BSD License

Usage:
  from growthkit.utils.clip import board
  board.copy('The text to be copied to the clipboard.')
  spam = board.paste()

  if not board.is_available():
    print("Copy functionality unavailable!")

On Windows, no additional modules are needed.
On Mac, the pyobjc module is used, falling back to the pbcopy and pbpaste cli
    commands. (These commands should come with OS X.).
On Linux, install xclip, xsel, or wl-clipboard (for "wayland" sessions) via package manager.
For example, in Debian:
    sudo apt-get install xclip
    sudo apt-get install xsel
    sudo apt-get install wl-clipboard

Otherwise on Linux, you will need the qtpy or PyQt5 modules installed.

This module does not work with PyGObject yet.

Cygwin is currently not supported.

Security Note: This module runs programs with these names:
    - which
    - pbcopy
    - pbpaste
    - xclip
    - xsel
    - wl-copy/wl-paste
    - klipper
    - qdbus
A malicious user could rename or add programs with these names, tricking
Clipboard into running them with whatever permissions the Python process has.

"""
__version__ = '1.9.0'

import os
import sys
import time
import base64
import ctypes
import platform
import warnings
import contextlib
import subprocess
from shutil import which

from ctypes import c_size_t, sizeof, c_wchar_p, get_errno, c_wchar


# For paste(): Python 3 uses str.
_PYTHON_STR_TYPE = str

ENCODING = 'utf-8'  # type: str

# Use shutil.which()
def _executable_exists(name):  # type: (str) -> bool
    return bool(which(name))

# Exceptions
class ClipboardException(RuntimeError):
    """Base class for all clipboard-related exceptions in this module."""
    pass

class ClipboardWindowsException(ClipboardException):
    """A Windows-specific clipboard exception."""
    def __init__(self, message):
        message += " (%s)" % ctypes.WinError()
        super(ClipboardWindowsException, self).__init__(message)

class ClipboardTimeoutException(ClipboardException):
    """A timeout occurred while trying to access the clipboard."""
    pass


def init_osx_pbcopy_clipboard():
    """Initializes clipboard functions for macOS using `pbcopy` and `pbpaste` commands.

    Returns:
        A tuple (copy_func, paste_func).
    """
    def copy_osx_pbcopy(text):
        """Copies text to the clipboard using the `pbcopy` command."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        p = subprocess.Popen(['pbcopy', 'w'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_osx_pbcopy():
        """Pastes text from the clipboard using the `pbpaste` command."""
        p = subprocess.Popen(['pbpaste', 'r'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode(ENCODING)

    return copy_osx_pbcopy, paste_osx_pbcopy


def init_osx_pyobjc_clipboard():
    """Initializes clipboard functions for macOS using the PyObjC bridge.

    Returns:
        A tuple (copy_func, paste_func).
    """
    def copy_osx_pyobjc(text):
        """Copies text to the clipboard using PyObjC (AppKit)."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        newStr = Foundation.NSString.stringWithString_(text).nsstring()
        newData = newStr.dataUsingEncoding_(Foundation.NSUTF8StringEncoding)
        board = AppKit.NSPasteboard.generalPasteboard()
        board.declareTypes_owner_([AppKit.NSStringPboardType], None)
        board.setData_forType_(newData, AppKit.NSStringPboardType)

    def paste_osx_pyobjc():
        """Pastes text from the clipboard using PyObjC (AppKit)."""
        board = AppKit.NSPasteboard.generalPasteboard()
        content = board.stringForType_(AppKit.NSStringPboardType)
        return content

    return copy_osx_pyobjc, paste_osx_pyobjc


def init_qt_clipboard():
    """Initializes clipboard functions using Qt (via qtpy or PyQt5).

    Returns:
        A tuple (copy_func, paste_func).
    """
    global QApplication
    # $DISPLAY should exist

    # Try to import from qtpy, but if that fails try PyQt5
    try:
        from qtpy.QtWidgets import QApplication
    except:
        from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    def copy_qt(text):
        """Copies text to the clipboard using Qt."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        cb = app.clipboard()
        cb.setText(text)

    def paste_qt():
        """Pastes text from the clipboard using Qt."""
        cb = app.clipboard()
        return _PYTHON_STR_TYPE(cb.text())

    return copy_qt, paste_qt


def init_xclip_clipboard():
    """Initializes clipboard functions using the `xclip` command-line tool.

    Returns:
        A tuple (copy_func, paste_func).
    """
    DEFAULT_SELECTION='c'
    PRIMARY_SELECTION='p'

    def copy_xclip(text, primary=False):
        """Copies text to the clipboard using `xclip`."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        selection=DEFAULT_SELECTION
        if primary:
            selection=PRIMARY_SELECTION
        p = subprocess.Popen(['xclip', '-selection', selection],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_xclip(primary=False):
        """Pastes text from the clipboard using `xclip`."""
        selection=DEFAULT_SELECTION
        if primary:
            selection=PRIMARY_SELECTION
        p = subprocess.Popen(['xclip', '-selection', selection, '-o'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             close_fds=True)
        stdout, stderr = p.communicate()
        # Intentionally ignore extraneous output on stderr when clipboard is empty
        return stdout.decode(ENCODING)

    return copy_xclip, paste_xclip


def init_xsel_clipboard():
    """Initializes clipboard functions using the `xsel` command-line tool.

    Returns:
        A tuple (copy_func, paste_func).
    """
    DEFAULT_SELECTION='-b'
    PRIMARY_SELECTION='-p'

    def copy_xsel(text, primary=False):
        """Copies text to the clipboard using `xsel`."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        selection_flag = DEFAULT_SELECTION
        if primary:
            selection_flag = PRIMARY_SELECTION
        p = subprocess.Popen(['xsel', selection_flag, '-i'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_xsel(primary=False):
        """Pastes text from the clipboard using `xsel`."""
        selection_flag = DEFAULT_SELECTION
        if primary:
            selection_flag = PRIMARY_SELECTION
        p = subprocess.Popen(['xsel', selection_flag, '-o'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode(ENCODING)

    return copy_xsel, paste_xsel


def init_wl_clipboard():
    """Initializes clipboard functions using `wl-copy` and `wl-paste` (for Wayland).

    Returns:
        A tuple (copy_func, paste_func).
    """
    PRIMARY_SELECTION = "-p"

    def copy_wl(text, primary=False):
        """Copies text to the clipboard using `wl-copy`."""
        text = _PYTHON_STR_TYPE(text)  # Converts non-str values to str.
        args = ["wl-copy"]
        if primary:
            args.append(PRIMARY_SELECTION)
        if not text:
            args.append("--clear")
            subprocess.check_call(args, close_fds=True)
        else:
            p = subprocess.Popen(args, stdin=subprocess.PIPE, close_fds=True)
            p.communicate(input=text.encode(ENCODING))

    def paste_wl(primary=False):
        """Pastes text from the clipboard using `wl-paste`."""
        args = ["wl-paste", "-n", "-t", "text"]
        if primary:
            args.append(PRIMARY_SELECTION)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, close_fds=True)
        stdout, _stderr = p.communicate()
        return stdout.decode(ENCODING)

    return copy_wl, paste_wl


def init_klipper_clipboard():
    """Initializes clipboard functions for KDE Klipper using `qdbus`.

    Returns:
        A tuple (copy_func, paste_func).
    """
    def copy_klipper(text):
        """Copies text to the Klipper clipboard using `qdbus`."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'setClipboardContents',
             text.encode(ENCODING)],
            stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=None)

    def paste_klipper():
        """Pastes text from the Klipper clipboard using `qdbus`."""
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'getClipboardContents'],
            stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()

        # Workaround for https://bugs.kde.org/show_bug.cgi?id=342874
        # TODO: https://github.com/asweigart/clipboard/issues/43
        clipboardContents = stdout.decode(ENCODING)
        # even if blank, Klipper will append a newline at the end
        assert len(clipboardContents) > 0
        # make sure that newline is there
        assert clipboardContents.endswith('\n')
        if clipboardContents.endswith('\n'):
            clipboardContents = clipboardContents[:-1]
        return clipboardContents

    return copy_klipper, paste_klipper


def init_dev_clipboard_clipboard():
    """Initializes clipboard functions for Cygwin using /dev/clipboard.

    Returns:
        A tuple (copy_func, paste_func).
    """
    def copy_dev_clipboard(text):
        """Copies text to /dev/clipboard on Cygwin."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        if text == '':
            warnings.warn('Clipboard cannot copy a blank string to the clipboard on Cygwin. This is effectively a no-op.')
        if '\r' in text:
            warnings.warn('Clipboard cannot handle \\r characters on Cygwin.')

        fo = open('/dev/clipboard', 'wt')
        fo.write(text)
        fo.close()

    def paste_dev_clipboard():
        """Pastes text from /dev/clipboard on Cygwin."""
        fo = open('/dev/clipboard', 'rt')
        content = fo.read()
        fo.close()
        return content

    return copy_dev_clipboard, paste_dev_clipboard


def init_no_clipboard():
    """Returns a pair of stub functions that raise an error, for when no clipboard is found.

    Returns:
        A tuple (ClipboardUnavailable_instance, ClipboardUnavailable_instance).
    """
    class ClipboardUnavailable(object):
        """Represents an unavailable clipboard, raising an error when called."""

        def __call__(self, *args, **kwargs):
            additionalInfo = ''
            if sys.platform == 'linux':
                additionalInfo = '\nOn Linux, you can run `sudo apt-get install xclip` or `sudo apt-get install xselect` to install a copy/paste mechanism.'
            raise ClipboardException('Clipboard could not find a copy/paste mechanism for your system. For more information, please visit https://clipboard.readthedocs.io/en/latest/index.html#not-implemented-error' + additionalInfo)

        def __bool__(self):
            return False

    return ClipboardUnavailable(), ClipboardUnavailable()




# Windows-related clipboard functions:
class CheckedCall(object):
    """Wraps a Windows API function, raising an exception if it indicates an error."""
    def __init__(self, f):
        """Initializes with the Windows API function to wrap."""
        super(CheckedCall, self).__setattr__("f", f)

    def __call__(self, *args):
        """Calls the wrapped function and checks for errors."""
        ret = self.f(*args)
        if not ret and get_errno():
            raise ClipboardWindowsException("Error calling " + self.f.__name__)
        return ret

    def __setattr__(self, key, value):
        """Sets attributes on the wrapped function."""
        setattr(self.f, key, value)


def init_windows_clipboard():
    """Initializes clipboard functions for Windows using ctypes.

    Returns:
        A tuple (copy_func, paste_func).
    """
    from ctypes.wintypes import (HGLOBAL, LPVOID, DWORD, LPCSTR, INT, HWND,
                                 HINSTANCE, HMENU, BOOL, UINT, HANDLE)

    windll = ctypes.windll
    msvcrt = ctypes.CDLL('msvcrt')

    safeCreateWindowExA = CheckedCall(windll.user32.CreateWindowExA)
    safeCreateWindowExA.argtypes = [DWORD, LPCSTR, LPCSTR, DWORD, INT, INT,
                                    INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    safeCreateWindowExA.restype = HWND

    safeDestroyWindow = CheckedCall(windll.user32.DestroyWindow)
    safeDestroyWindow.argtypes = [HWND]
    safeDestroyWindow.restype = BOOL

    OpenClipboard = windll.user32.OpenClipboard
    OpenClipboard.argtypes = [HWND]
    OpenClipboard.restype = BOOL

    safeCloseClipboard = CheckedCall(windll.user32.CloseClipboard)
    safeCloseClipboard.argtypes = []
    safeCloseClipboard.restype = BOOL

    safeEmptyClipboard = CheckedCall(windll.user32.EmptyClipboard)
    safeEmptyClipboard.argtypes = []
    safeEmptyClipboard.restype = BOOL

    safeGetClipboardData = CheckedCall(windll.user32.GetClipboardData)
    safeGetClipboardData.argtypes = [UINT]
    safeGetClipboardData.restype = HANDLE

    safeSetClipboardData = CheckedCall(windll.user32.SetClipboardData)
    safeSetClipboardData.argtypes = [UINT, HANDLE]
    safeSetClipboardData.restype = HANDLE

    safeGlobalAlloc = CheckedCall(windll.kernel32.GlobalAlloc)
    safeGlobalAlloc.argtypes = [UINT, c_size_t]
    safeGlobalAlloc.restype = HGLOBAL

    safeGlobalLock = CheckedCall(windll.kernel32.GlobalLock)
    safeGlobalLock.argtypes = [HGLOBAL]
    safeGlobalLock.restype = LPVOID

    safeGlobalUnlock = CheckedCall(windll.kernel32.GlobalUnlock)
    safeGlobalUnlock.argtypes = [HGLOBAL]
    safeGlobalUnlock.restype = BOOL

    wcslen = CheckedCall(msvcrt.wcslen)
    wcslen.argtypes = [c_wchar_p]
    wcslen.restype = UINT

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    @contextlib.contextmanager
    def window():
        """
        Context that provides a valid Windows hwnd.
        """
        # we really just need the hwnd, so setting "STATIC"
        # as predefined lpClass is just fine.
        hwnd = safeCreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0,
                                   None, None, None, None)
        try:
            yield hwnd
        finally:
            safeDestroyWindow(hwnd)

    @contextlib.contextmanager
    def clipboard(hwnd):
        """
        Context manager that opens the clipboard and prevents
        other applications from modifying the clipboard content.
        """
        # We may not get the clipboard handle immediately because
        # some other application is accessing it (?)
        # We try for at least 500ms to get the clipboard.
        t = time.time() + 0.5
        success = False
        while time.time() < t:
            success = OpenClipboard(hwnd)
            if success:
                break
            time.sleep(0.01)
        if not success:
            raise ClipboardWindowsException("Error calling OpenClipboard")

        try:
            yield
        finally:
            safeCloseClipboard()

    def copy_windows(text):
        """Copies text to the Windows clipboard using ctypes."""
        # This function is heavily based on
        # http://msdn.com/ms649016#_win32_Copying_Information_to_the_Clipboard

        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.

        with window() as hwnd:
            # http://msdn.com/ms649048
            # If an application calls OpenClipboard with hwnd set to NULL,
            # EmptyClipboard sets the clipboard owner to NULL;
            # this causes SetClipboardData to fail.
            # => We need a valid hwnd to copy something.
            with clipboard(hwnd):
                safeEmptyClipboard()

                if text:
                    # http://msdn.com/ms649051
                    # If the hMem parameter identifies a memory object,
                    # the object must have been allocated using the
                    # function with the GMEM_MOVEABLE flag.
                    count = wcslen(text) + 1
                    handle = safeGlobalAlloc(GMEM_MOVEABLE,
                                             count * sizeof(c_wchar))
                    locked_handle = safeGlobalLock(handle)

                    ctypes.memmove(c_wchar_p(locked_handle), c_wchar_p(text), count * sizeof(c_wchar))

                    safeGlobalUnlock(handle)
                    safeSetClipboardData(CF_UNICODETEXT, handle)

    def paste_windows():
        """Pastes text from the Windows clipboard using ctypes."""
        with clipboard(None):
            handle = safeGetClipboardData(CF_UNICODETEXT)
            if not handle:
                # GetClipboardData may return NULL with errno == NO_ERROR
                # if the clipboard is empty.
                # (Also, it may return a handle to an empty buffer,
                # but technically that's not empty)
                return ""
            locked_handle = safeGlobalLock(handle)
            return_value = c_wchar_p(locked_handle).value
            safeGlobalUnlock(handle)
            return return_value

    return copy_windows, paste_windows


def init_wsl_clipboard():
    """Initializes clipboard functions for Windows Subsystem for Linux (WSL).

    Uses `clip.exe` for copying and PowerShell `Get-Clipboard` for pasting.

    Returns:
        A tuple (copy_func, paste_func).
    """

    def copy_wsl(text):
        """Copies text to the clipboard in WSL using `clip.exe`."""
        text = _PYTHON_STR_TYPE(text) # Converts non-str values to str.
        p = subprocess.Popen(['clip.exe'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode('utf-16le'))

    def paste_wsl():
        """Pastes text from the clipboard in WSL using PowerShell `Get-Clipboard`."""
        ps_script = '[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Clipboard -Raw)))'

        # '-noprofile' speeds up load time
        p = subprocess.Popen(['powershell.exe', '-noprofile', '-command', ps_script],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             close_fds=True)
        stdout, stderr = p.communicate()

        if stderr:
            raise Exception(f"Error pasting from clipboard: {stderr}")

        try:
            base64_encoded = stdout.decode('utf-8').strip()
            decoded_bytes = base64.b64decode(base64_encoded)
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Decoding error: {e}")

    return copy_wsl, paste_wsl


# Automatic detection of clipboard mechanisms and importing is done in determine_clipboard():
def determine_clipboard():
    """
    Determine the OS/platform and set the copy() and paste() functions
    accordingly.
    """

    global Foundation, AppKit # These are needed as init_osx_pyobjc_clipboard uses them from the module level after this function imports them.

    # Setup for the CYGWIN platform:
    if 'cygwin' in platform.system().lower(): # Cygwin has a variety of values returned by platform.system(), such as 'CYGWIN_NT-6.1'
        # FIXME: clipboard currently does not support Cygwin,
        # see https://github.com/asweigart/clipboard/issues/55
        if os.path.exists('/dev/clipboard'):
            warnings.warn('Clipboard\'s support for Cygwin is not perfect, see https://github.com/asweigart/clipboard/issues/55')
            return init_dev_clipboard_clipboard()

    # Setup for the WINDOWS platform:
    elif os.name == 'nt' or platform.system() == 'Windows':
        return init_windows_clipboard()

    if platform.system() == 'Linux' and os.path.isfile('/proc/version'):
        with open('/proc/version', 'r') as f:
            if "microsoft" in f.read().lower():
                return init_wsl_clipboard()

    # Setup for the MAC OS X platform:
    if os.name == 'mac' or platform.system() == 'Darwin':
        try:
            import Foundation  # check if pyobjc is installed
            import AppKit
        except ImportError:
            return init_osx_pbcopy_clipboard()
        else:
            return init_osx_pyobjc_clipboard()

    # Setup for the LINUX platform:

    if os.getenv("WAYLAND_DISPLAY") and _executable_exists("wl-copy")  and _executable_exists("wl-paste"):
        return init_wl_clipboard()

    # `import PyQt4` sys.exit()s if DISPLAY is not in the environment.
    # Thus, we need to detect the presence of $DISPLAY manually
    # and not load PyQt4 if it is absent.
    elif os.getenv("DISPLAY"):
        if _executable_exists("xclip"):
            # Note: 2024/06/18 Google Trends shows xclip as more popular than xsel.
            return init_xclip_clipboard()
        if _executable_exists("xsel"):
            return init_xsel_clipboard()
        if _executable_exists("klipper") and _executable_exists("qdbus"):
            return init_klipper_clipboard()

        try:
            # qtpy is a small abstraction layer that lets you write
            # applications using a single api call to either PyQt or PySide.
            # https://pypi.python.org/pypi/QtPy
            import qtpy  # check if qtpy is installed
            return init_qt_clipboard()
        except ImportError:
            pass

        # If qtpy isn't installed, fall back on importing PyQt5
        try:
            import PyQt5  # check if PyQt5 is installed
            return init_qt_clipboard()
        except ImportError:
            pass

    return init_no_clipboard()


def set_clipboard(clipboard):
    """Explicitly sets the clipboard mechanism.

    The "clipboard mechanism" is how the copy() and paste() functions interact
    with the operating system to implement the copy/paste feature.
    The clipboard parameter must be one of the keys in `clipboard_types`.

    Args:
        clipboard (str): The name of the clipboard mechanism to use.

    Raises:
        ValueError: If the `clipboard` argument is not a valid mechanism name.
    """
    global copy, paste

    clipboard_types = {
        "pbcopy": init_osx_pbcopy_clipboard,
        "pyobjc": init_osx_pyobjc_clipboard,
        "qt": init_qt_clipboard,  # TODO - split this into 'qtpy' and 'pyqt5'
        "xclip": init_xclip_clipboard,
        "xsel": init_xsel_clipboard,
        "wl-clipboard": init_wl_clipboard,
        "klipper": init_klipper_clipboard,
        "windows": init_windows_clipboard,
        "no": init_no_clipboard,
    }

    if clipboard not in clipboard_types:
        raise ValueError('Argument must be one of %s' % (', '.join([repr(_) for _ in clipboard_types.keys()])))

    # Sets clipboard's copy() and paste() functions:
    copy, paste = clipboard_types[clipboard]()


def lazy_load_stub_copy(text):
    """A stub for copy() that loads the real function on first call.

    This allows users to import the module without immediately running
    `determine_clipboard()`, giving them a chance to call `set_clipboard()` first.
    If not, `determine_clipboard()` runs to select a mechanism.

    Args:
        text (str): The text to be copied.

    Returns:
        Whatever the actual copy function returns (usually None).
    """
    global copy, paste
    copy, paste = determine_clipboard()
    return copy(text)


def lazy_load_stub_paste():
    """A stub for paste() that loads the real function on first call.

    This allows users to import the module without immediately running
    `determine_clipboard()`, giving them a chance to call `set_clipboard()` first.
    If not, `determine_clipboard()` runs to select a mechanism.

    Returns:
        str: The text pasted from the clipboard.
    """
    global copy, paste
    copy, paste = determine_clipboard()
    return paste()


def is_available():
    """Checks if a functional clipboard mechanism is available.

    Returns:
        bool: True if copy/paste functions are not the lazy-load stubs,
              False otherwise.
    """
    return copy != lazy_load_stub_copy and paste != lazy_load_stub_paste


# Initially, copy() and paste() are set to lazy loading wrappers which will
# set `copy` and `paste` to real functions the first time they're used, unless
# set_clipboard() or determine_clipboard() is called first.
copy, paste = lazy_load_stub_copy, lazy_load_stub_paste



__all__ = ['copy', 'paste', 'set_clipboard', 'determine_clipboard']
