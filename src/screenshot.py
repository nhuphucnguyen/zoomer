import os
import subprocess
import tempfile

from PIL import Image


def take_screenshot() -> Image.Image:
    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        return _capture(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _capture(path: str) -> Image.Image:
    # GNOME Shell DBus — works on both X11 and Wayland GNOME sessions
    try:
        import dbus
        bus = dbus.SessionBus()
        shell = bus.get_object('org.gnome.Shell', '/org/gnome/Shell')
        iface = dbus.Interface(shell, 'org.gnome.Shell.Screenshot')
        success, _ = iface.Screenshot(False, False, path)
        if success and os.path.getsize(path) > 0:
            return Image.open(path).copy()
    except Exception:
        pass

    # grim — native Wayland compositor screenshot tool
    if os.environ.get('WAYLAND_DISPLAY'):
        try:
            result = subprocess.run(['grim', path], capture_output=True, timeout=10)
            if result.returncode == 0 and os.path.getsize(path) > 0:
                return Image.open(path).copy()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # scrot — X11 screenshot tool
    try:
        result = subprocess.run(['scrot', path], capture_output=True, timeout=10)
        if result.returncode == 0 and os.path.getsize(path) > 0:
            return Image.open(path).copy()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # PIL ImageGrab — last resort, requires scrot or similar on Linux
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if img:
            return img
    except Exception:
        pass

    raise RuntimeError(
        "Could not capture screenshot.\n"
        "Install one of: gnome-shell (GNOME), grim (Wayland), scrot (X11)"
    )
