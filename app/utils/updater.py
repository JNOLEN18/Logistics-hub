import sys
import subprocess
import tempfile
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox

from app.utils.config import APP_VERSION, getsharednetworkpath


def _versiontuple(v: str):
    """Convert "1.2.3" → (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.strip().split('.'))
    except (ValueError, AttributeError):
        return (0,)


def checkforupdate(parent=None) -> bool:
    """
    Check the shared drive for a newer build.
    Returns True if the user accepted an update (caller should exit the app).
    """
    if not getattr(sys, 'frozen', False):
        # Running from source — never auto-update
        return False

    try:
        network_version_file = getsharednetworkpath() / "updates" / "version.txt"
        if not network_version_file.exists():
            return False

        network_version = network_version_file.read_text().strip()
        if _versiontuple(network_version) <= _versiontuple(APP_VERSION):
            return False

        reply = QMessageBox.question(
            parent,
            "Update Available",
            f"A new version of MP&L Hub is available.\n\n"
            f"  Installed:  {APP_VERSION}\n"
            f"  Available:  {network_version}\n\n"
            f"Update now?  The app will close and restart automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            return _applyupdate(parent)

    except Exception as e:
        print(f"[Updater] Check failed: {e}")

    return False


def manualcheck(parent=None):
    """Triggered by the 'Check for Updates' button — shows a result either way."""
    if not getattr(sys, 'frozen', False):
        QMessageBox.information(parent, "Updates", "Update checking is only available in the installed build.")
        return

    try:
        network_version_file = getsharednetworkpath() / "updates" / "version.txt"
        if not network_version_file.exists():
            QMessageBox.information(parent, "Updates", "No update file found on the shared drive.")
            return

        network_version = network_version_file.read_text().strip()
        if _versiontuple(network_version) <= _versiontuple(APP_VERSION):
            QMessageBox.information(
                parent, "Up to Date",
                f"You are on the latest version ({APP_VERSION})."
            )
            return

        # Newer version found — reuse the same prompt
        reply = QMessageBox.question(
            parent,
            "Update Available",
            f"A new version of MP&L Hub is available.\n\n"
            f"  Installed:  {APP_VERSION}\n"
            f"  Available:  {network_version}\n\n"
            f"Update now?  The app will close and restart automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            if _applyupdate(parent):
                parent.close() if parent else None

    except Exception as e:
        QMessageBox.warning(parent, "Update Check Failed", f"Could not reach the shared drive:\n{e}")


def _applyupdate(parent=None) -> bool:
    """
    Write an updater batch script to %TEMP%, launch it detached, and return
    True so the caller knows to exit the application.
    """
    try:
        app_dir = Path(sys.executable).resolve().parent
        exe_path = Path(sys.executable).resolve()
        source_dir = getsharednetworkpath() / "updates" / "MPL_Hub"

        bat_lines = [
            "@echo off",
            "echo MP^&L Hub is updating, please wait...",
            "timeout /t 4 /nobreak > nul",
            f'robocopy "{source_dir}" "{app_dir}" /E /IS /IT /COPY:DAT /R:5 /W:3 > nul',
            "if errorlevel 8 (",
            "    echo Update failed. Please copy the new version manually from:",
            f'    echo {source_dir}',
            "    pause",
            "    exit /b 1",
            ")",
            f'start "" "{exe_path}"',
            'del "%~f0"',
        ]

        bat_path = Path(tempfile.gettempdir()) / "_mplhub_update.bat"
        bat_path.write_text("\r\n".join(bat_lines), encoding="utf-8")

        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        return True

    except Exception as e:
        QMessageBox.critical(
            parent,
            "Update Failed",
            f"Could not launch the updater:\n{e}\n\n"
            f"Please update manually by copying the new build from:\n"
            f"{getsharednetworkpath() / 'updates' / 'MPL_Hub'}",
        )
        print(f"[Updater] Apply failed: {e}")
        return False
