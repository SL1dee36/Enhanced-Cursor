import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from enhanced_cursor.logger import setup_logger, get_logger
from enhanced_cursor.config import ConfigManager
from enhanced_cursor.overlay import CursorOverlayWindow
from enhanced_cursor.settings_dialog import SettingsDialog
from enhanced_cursor.tray_icon import TrayManager
from enhanced_cursor.win32_utils import (
    acquire_single_instance_mutex,
    release_single_instance_mutex,
    restore_system_cursor,
    shutdown_high_resolution_timer
)


def resource_path(relative_path: str) -> str:
    """Gets absolute path to resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class EnhancedCursorApp:
    def __init__(self):
        self.logger = get_logger()
        self.logger.info("Starting EnhancedCursor...")

        # Setup icon paths
        self.icon_ico = resource_path("cursor.ico")
        self.icon_png = resource_path("cursor.png")
        self.best_icon = self.icon_ico if os.path.exists(self.icon_ico) else self.icon_png

        self.config_manager = ConfigManager()
        self.overlay = CursorOverlayWindow(self.config_manager)
        self.settings_dialog = None

        self.tray = TrayManager(
            config_manager=self.config_manager,
            icon_path=self.best_icon,
            on_open_settings=self.open_settings,
            on_exit=self.exit_app
        )

        self.overlay.show()
        self.logger.info("EnhancedCursor is running.")

    def open_settings(self):
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            self.settings_dialog = SettingsDialog(
                config_manager=self.config_manager,
                icon_path=self.best_icon,
                parent=None
            )
            self.settings_dialog.show()
            self.settings_dialog.activateWindow()
            self.settings_dialog.raise_()
        else:
            self.settings_dialog.activateWindow()
            self.settings_dialog.raise_()

    def exit_app(self):
        self.logger.info("Exiting application...")
        restore_system_cursor()
        shutdown_high_resolution_timer()
        if self.overlay:
            self.overlay.unregister_hotkey()
            self.overlay.close()
        if self.tray:
            self.tray.hide()
        release_single_instance_mutex()
        QApplication.quit()


def main():
    logger = setup_logger()

    # Single-instance enforcement
    if not acquire_single_instance_mutex():
        app = QApplication(sys.argv)
        QMessageBox.information(
            None,
            "EnhancedCursor",
            "EnhancedCursor уже запущен и работает в системном трее.\n"
            "EnhancedCursor is already running in the system tray."
        )
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName("EnhancedCursor")
    app.setQuitOnLastWindowClosed(False)

    icon_path = resource_path("cursor.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("cursor.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    try:
        ec_app = EnhancedCursorApp()
        exit_code = app.exec()
    finally:
        restore_system_cursor()
        shutdown_high_resolution_timer()
        release_single_instance_mutex()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
