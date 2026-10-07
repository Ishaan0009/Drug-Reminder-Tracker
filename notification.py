# notification.py
import platform
import sys

# toast for Windows
try:
    from win10toast import ToastNotifier
    TOASTER = ToastNotifier()
except Exception:
    TOASTER = None

# winsound for Windows beep; fallback bell for others
try:
    import winsound
except Exception:
    winsound = None

def toast_notify(title: str, msg: str):
    """Show Windows toast if possible; otherwise print."""
    if TOASTER and platform.system() == "Windows":
        try:
            TOASTER.show_toast(title, msg, duration=6, threaded=True)
        except Exception:
            print("Toast failed:", title, msg)
    else:
        print("NOTIFY:", title, msg)

def play_sound():
    try:
        if winsound and platform.system() == "Windows":
            # short system exclamation
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        else:
            # fallback terminal bell
            print('\a', end='', flush=True)
    except Exception:
        pass
