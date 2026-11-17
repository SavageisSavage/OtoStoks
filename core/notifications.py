"""
core/notifications.py - Native Desktop Notifications for OtoStoksBot.
Dispatches native Windows notifications without external heavy dependencies.
"""
import sys
import subprocess
import threading


def show_native_notification(title: str, message: str):
    """Fires native OS desktop notification in a non-blocking daemon thread."""
    def _worker():
        try:
            if sys.platform == "win32":
                # PowerShell System.Windows.Forms balloon notification
                script = (
                    f"[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
                    f"$n = New-Object System.Windows.Forms.NotifyIcon;"
                    f"$n.Icon = [System.Drawing.SystemIcons]::Information;"
                    f"$n.BalloonTipTitle = '{title}';"
                    f"$n.BalloonTipText = '{message}';"
                    f"$n.Visible = $True;"
                    f"$n.ShowBalloonTip(4500);"
                    f"Start-Sleep -Milliseconds 800;"
                    f"$n.Dispose();"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            elif sys.platform == "darwin":
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(["osascript", "-e", script], capture_output=True)
            elif sys.platform.startswith("linux"):
                subprocess.run(["notify-send", title, message], capture_output=True)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
