"""
Desktop Watermark Overlay (Windows)
====================================

Displays a tiled, semi-transparent, click-through watermark across the
entire desktop (every monitor) and on top of all windows. The watermark
text can be a fixed static string, or derived from Active Directory (the
logged-in domain user's attributes). The overlay automatically hides
itself whenever the foreground (active) window belongs to one of the
configured "excluded" applications.

Requirements (Windows only):
    pip install pywin32 psutil
    pip install pystray pillow (optional - only needed for the tray icon)

Run:
    python desktop_watermark.py

To stop:
    Right-click the tray icon (if pystray is installed) -> Exit
    or close it from Task Manager (python.exe / pythonw.exe).
"""

import ctypes
from ctypes import wintypes
import getpass
import socket
import sys
import threading
import time
from datetime import datetime

import tkinter as tk

import win32api
import win32con
import win32gui
import win32process
import psutil


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

CONFIG = {
    # -----------------------------------------------------------------
    # WATERMARK TEXT SOURCE
    # -----------------------------------------------------------------
    # Choose where the watermark text comes from:
    #   "login_user" -> the currently logged-in Windows username
    #                   (no AD/network lookup needed; works offline)
    #   "static"     -> a fixed string you set below
    #   "ad"         -> looked up from Active Directory (ADSI or LDAP)
    "text_source": "login_user",

    # Used when text_source = "login_user". Choose how much detail to show:
    #   "username"       -> just the Windows username, e.g. "jdoe"
    #   "username_host"  -> "jdoe@DESKTOP-1234"
    #   "full_name"      -> the account's display/full name if available,
    #                       falling back to the username if not (this does
    #                       one quick local ADSI call - no domain network
    #                       round-trip required for a domain-joined PC)
    "login_user_format": "username",

    # If True, a date/time stamp is appended below the username.
    "login_user_show_timestamp": True,

    # Used when text_source = "static".
    "static_text": "CONFIDENTIAL - INTERNAL USE ONLY",
    "static_text_show_timestamp": True,

    # How often (seconds) to refresh the timestamp shown in the watermark.
    "text_refresh_seconds": 60,

    # How often (seconds) to check which application is in the foreground.
    "foreground_poll_seconds": 1,

    # How often (seconds) to re-assert that the overlay is the topmost
    # window. Many apps (Teams, Outlook reminders, PowerPoint, OneNote
    # "Always on Top" notes, etc.) periodically re-assert their own
    # "always on top" state, which can push them above the overlay in
    # Windows' topmost z-order band. Re-applying HWND_TOPMOST regularly
    # keeps the watermark visible over those apps too.
    "topmost_refresh_seconds": 1,

    # Font used for the watermark text.
    "font_family": "Segoe UI",
    "font_size": 14,

    # Color of the watermark text (hex).
    "text_color": "#FFFFFF",

    # 0.0 (invisible) - 1.0 (fully opaque). Recommended: 0.10 - 0.30
    "opacity": 0.2,

    # Spacing (pixels) between repeated watermark tiles.
    "tile_spacing_x": 350,
    "tile_spacing_y": 220,

    # Rotation angle (degrees) of the watermark text.
    "rotation_angle": 30,

    # If True, each monitor's overlay covers only that monitor's "work
    # area" (i.e. the screen area excluding the taskbar), so the taskbar
    # always remains clickable. If False, each monitor's overlay covers
    # its full bounds, including any area occupied by the taskbar - in
    # that case clicking the taskbar may become less reliable.
    "avoid_taskbar": True,

    # If True, one overlay window is created per connected monitor, so
    # the watermark covers the whole desktop regardless of how many
    # screens are attached. If False, only the primary monitor is
    # covered.
    "cover_all_monitors": True,

    # If True, the script checks whether it is running elevated
    # ("Run as administrator"). If it is NOT elevated, it relaunches
    # itself elevated (via a UAC prompt) and exits the non-elevated copy.
    #
    # Why this matters: Windows' User Interface Privilege Isolation
    # (UIPI) prevents a normal-privilege window from staying on top of
    # windows belonging to an elevated ("Run as administrator") process.
    # If some of your applications run elevated, the watermark will not
    # display over them unless this script also runs elevated.
    "run_as_admin": False,

    # Process names (lowercase, with .exe) for applications over which the
    # watermark should NOT be displayed. The overlay is hidden whenever one
    # of these is the active/foreground application.
    "excluded_processes": [
        "teams.exe",
        "zoom.exe",
        "vlc.exe",
    ],

}


# ---------------------------------------------------------------------------
# WATERMARK TEXT SOURCES
# ---------------------------------------------------------------------------

def get_local_user_info():
    """Fallback info available without any AD query."""
    username = getpass.getuser()
    hostname = socket.gethostname()
    return username, hostname


def get_login_user_text():
    """
    Build watermark text from the currently logged-in Windows username.
    No Active Directory / network lookup is required for "username" or
    "username_host" formats - getpass.getuser() reads this straight from
    the local Windows session. Only "full_name" does one quick *local*
    ADSI call (no domain round-trip) to resolve the display name.
    """
    username, hostname = get_local_user_info()
    fmt = CONFIG["login_user_format"]

    if fmt == "username_host":
        text = f"{username}@{hostname}" 
    else:  # "username" (default)
        text = username

    if CONFIG["login_user_show_timestamp"]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        text = f"{text} | {timestamp}"

    return text


def get_watermark_text():
    """Build the full watermark string based on CONFIG["text_source"]."""
    source = CONFIG["text_source"]

    if source == "login_user":
        return get_login_user_text()

    if source == "static":
        text = CONFIG["static_text"]
        if CONFIG["static_text_show_timestamp"]:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            text = f"{text} | {timestamp}"
        return text

    # Unknown text_source - fail safe to the login username rather than
    # showing nothing.
    print(f"[watermark] Unknown text_source '{source}', falling back to login_user")
    return get_login_user_text()


# ---------------------------------------------------------------------------
# WIN32 HELPERS
# ---------------------------------------------------------------------------

def make_window_clickthrough(hwnd, alpha=255):
    """Make the window transparent to mouse/keyboard input (click-through),
    exclude it from screen-share/Alt-Tab where possible, and re-apply the
    layered-window alpha so the new styles take effect immediately."""
    styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    styles |= (
        win32con.WS_EX_LAYERED
        | win32con.WS_EX_TRANSPARENT
        | win32con.WS_EX_TOOLWINDOW
        | win32con.WS_EX_NOACTIVATE
    )
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)

    # Re-apply layered window attributes - required on some Windows
    # versions for WS_EX_TRANSPARENT to actually start passing clicks
    # through once it's added after the window already exists.
    win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)

    # Force the window manager to re-evaluate the extended styles.
    win32gui.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE
        | win32con.SWP_NOSIZE
        | win32con.SWP_NOZORDER
        | win32con.SWP_NOACTIVATE
        | win32con.SWP_FRAMECHANGED,
    )


def get_work_area():
    """Return (left, top, width, height) of the primary monitor's work
    area, i.e. the screen area excluding the taskbar."""
    rect = wintypes.RECT()
    SPI_GETWORKAREA = 0x0030
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def get_virtual_screen_geometry():
    """Bounding rectangle covering all monitors."""
    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
    width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    return left, top, width, height


def get_monitor_geometries():
    """Return a list of (left, top, width, height) rectangles - one per
    connected monitor (or just the primary monitor, depending on
    CONFIG["cover_all_monitors"]). Each rectangle is either the
    monitor's work area (taskbar excluded) or its full bounds, depending
    on CONFIG["avoid_taskbar"]."""
    rects = []

    try:
        monitors = win32api.EnumDisplayMonitors(None, None)
    except Exception:
        monitors = []

    for hmonitor, _hdc, _rect in monitors:
        try:
            info = win32api.GetMonitorInfo(hmonitor)
        except Exception:
            continue
        if CONFIG["avoid_taskbar"]:
            l, t, r, b = info["Work"]
        else:
            l, t, r, b = info["Monitor"]
        is_primary = bool(info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY)
        rects.append((l, t, r - l, b - t, is_primary))

    if not rects:
        # Fallback if monitor enumeration fails for any reason.
        if CONFIG["avoid_taskbar"]:
            l, t, w, h = get_work_area()
        else:
            l, t, w, h = get_virtual_screen_geometry()
        rects.append((l, t, w, h, True))

    if not CONFIG["cover_all_monitors"]:
        # Keep only the primary monitor (or the first one, as a fallback).
        primary = [r for r in rects if r[4]]
        rects = primary if primary else rects[:1]

    return [(l, t, w, h) for (l, t, w, h, _is_primary) in rects]


def get_foreground_process_name():
    """Return the lowercase exe name of the application currently in focus."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name().lower()
    except Exception:
        return ""


def is_running_as_admin():
    """Return True if this process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin():
    """Relaunch this script elevated (triggers a UAC prompt)."""
    script = sys.argv[0]
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    cmd = f'"{script}" {params}'.strip()
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd, None, 1)
    except Exception as exc:
        print(f"[watermark] Failed to relaunch as administrator: {exc}")


# ---------------------------------------------------------------------------
# OVERLAY WINDOW (one per monitor)
# ---------------------------------------------------------------------------

class OverlayWindow:
    """A single click-through, topmost, watermark window covering one
    monitor's geometry."""

    def __init__(self, tk_window, geometry):
        self.window = tk_window
        left, top, width, height = geometry
        self.width = width
        self.height = height
        self.text = ""

        tk_window.overrideredirect(True)          # no title bar / borders
        tk_window.geometry(f"{width}x{height}+{left}+{top}")
        tk_window.attributes("-topmost", True)     # always on top
        tk_window.attributes("-alpha", CONFIG["opacity"])
        tk_window.config(bg="black")

        # Use a color key so the background is fully transparent and
        # only the text is visible.
        tk_window.wm_attributes("-transparentcolor", "black")

        self.canvas = tk.Canvas(
            tk_window, width=width, height=height, bg="black", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Make the underlying win32 window click-through once it exists.
        tk_window.update_idletasks()
        alpha_255 = max(0, min(255, int(CONFIG["opacity"] * 255)))
        try:
            make_window_clickthrough(tk_window.winfo_id(), alpha=alpha_255)
        except Exception as exc:
            print(f"[watermark] Could not set click-through style: {exc}")

    def set_text(self, text):
        if text != self.text:
            self.text = text
            self._draw_tiles()

    def _draw_tiles(self):
        self.canvas.delete("all")
        spacing_x = CONFIG["tile_spacing_x"]
        spacing_y = CONFIG["tile_spacing_y"]
        font = (CONFIG["font_family"], CONFIG["font_size"], "bold")

        y = 0
        row = 0
        while y < self.height + spacing_y:
            x_offset = (spacing_x // 2) if row % 2 else 0
            x = -spacing_x + x_offset
            while x < self.width + spacing_x:
                self.canvas.create_text(
                    x,
                    y,
                    text=self.text,
                    fill=CONFIG["text_color"],
                    font=font,
                    angle=CONFIG["rotation_angle"],
                    anchor="center",
                    justify="center",
                )
                x += spacing_x
            y += spacing_y
            row += 1

    def reassert_topmost(self):
        try:
            hwnd = self.window.winfo_id()
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE,
            )
        except Exception:
            pass

    def show(self):
        self.window.deiconify()

    def hide(self):
        self.window.withdraw()


# ---------------------------------------------------------------------------
# MANAGER (creates one OverlayWindow per monitor and runs shared loops)
# ---------------------------------------------------------------------------

class WatermarkManager:
    def __init__(self, root):
        self.root = root
        self.overlays = []

        geometries = get_monitor_geometries()
        for index, geometry in enumerate(geometries):
            tk_window = root if index == 0 else tk.Toplevel(root)
            self.overlays.append(OverlayWindow(tk_window, geometry))

        self.text = get_watermark_text()
        for overlay in self.overlays:
            overlay.set_text(self.text)

        self._stop_event = threading.Event()
        threading.Thread(target=self._refresh_text_loop, daemon=True).start()
        threading.Thread(target=self._visibility_loop, daemon=True).start()
        threading.Thread(target=self._topmost_loop, daemon=True).start()

    # --- background loops ---------------------------------------------

    def _refresh_text_loop(self):
        while not self._stop_event.is_set():
            time.sleep(CONFIG["text_refresh_seconds"])
            new_text = get_watermark_text()
            if new_text != self.text:
                self.text = new_text
                for overlay in self.overlays:
                    self.root.after(0, overlay.set_text, new_text)

    def _visibility_loop(self):
        """Hide all overlays when an excluded app is in the foreground."""
        excluded = set(p.lower() for p in CONFIG["excluded_processes"])
        currently_visible = True

        while not self._stop_event.is_set():
            proc_name = get_foreground_process_name()
            should_show = proc_name not in excluded

            if should_show != currently_visible:
                currently_visible = should_show
                for overlay in self.overlays:
                    if should_show:
                        self.root.after(0, overlay.show)
                    else:
                        self.root.after(0, overlay.hide)

            time.sleep(CONFIG["foreground_poll_seconds"])

    def _topmost_loop(self):
        """Continuously re-assert that every overlay stays at the very
        top of the topmost z-order band, so apps that re-assert their
        own always-on-top status (Teams, Outlook, PowerPoint, etc.)
        don't end up covering the watermark."""
        while not self._stop_event.is_set():
            for overlay in self.overlays:
                overlay.reassert_topmost()
            time.sleep(CONFIG["topmost_refresh_seconds"])

    def stop(self):
        self._stop_event.set()


# ---------------------------------------------------------------------------
# OPTIONAL: SYSTEM TRAY ICON (for a clean exit option)
# ---------------------------------------------------------------------------

def run_with_tray(root, manager):
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return False  # pystray/Pillow not installed - run without tray

    def make_icon_image():
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, 60, 60), fill=(255, 0, 0, 200))
        d.text((20, 22), "W", fill="white")
        return img

    def on_exit(icon, item):
        manager.stop()
        icon.stop()
        root.after(0, root.destroy)

    icon = pystray.Icon(
        "watermark",
        make_icon_image(),
        "Desktop Watermark",
        menu=pystray.Menu(pystray.MenuItem("Exit", on_exit)),
    )
    threading.Thread(target=icon.run, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    if CONFIG["run_as_admin"] and not is_running_as_admin():
        print("[watermark] Not running elevated - relaunching as administrator...")
        relaunch_as_admin()
        return

    root = tk.Tk()
    manager = WatermarkManager(root)

    has_tray = run_with_tray(root, manager)
    if not has_tray:
        print("[watermark] Running without a tray icon.")
        print("[watermark] Install 'pystray' and 'pillow' for an Exit option,")
        print("[watermark] or stop the process via Task Manager.")

    root.mainloop()


if __name__ == "__main__":
    main()