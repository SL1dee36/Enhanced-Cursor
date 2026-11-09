import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QActionGroup

from enhanced_cursor.config import ConfigManager, CursorConfig
from enhanced_cursor.logger import open_log_file, get_logger
from enhanced_cursor.win32_utils import is_running_as_admin, restart_as_admin

logger = get_logger()


class TrayManager:
    def __init__(self, config_manager: ConfigManager, icon_path: str, on_open_settings, on_exit):
        self.config_manager = config_manager
        self.icon_path = icon_path
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit

        self.tray_icon = QSystemTrayIcon()
        if os.path.exists(self.icon_path):
            self.tray_icon.setIcon(QIcon(self.icon_path))

        self.menu = QMenu()
        self.presets_menu = QMenu(self.tr_text("tray_presets"))
        self.build_menu()

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        self.config_manager.config_changed.connect(self.on_config_changed)
        self.update_tray_tooltip()

    def tr_text(self, key: str) -> str:
        return self.config_manager.tr(key)

    def build_menu(self):
        self.menu.clear()

        # 1. Toggle Enabled Action
        self.act_toggle = QAction(self.tr_text("tray_toggle"), self.menu)
        self.act_toggle.setCheckable(True)
        self.act_toggle.setChecked(self.config_manager.config.enabled)
        self.act_toggle.triggered.connect(self.toggle_enabled)
        self.menu.addAction(self.act_toggle)

        # 2. Presets submenu
        self.build_presets_submenu()
        self.menu.addMenu(self.presets_menu)

        self.menu.addSeparator()

        # 3. Settings action
        act_settings = QAction(self.tr_text("tray_settings"), self.menu)
        act_settings.triggered.connect(self.on_open_settings)
        self.menu.addAction(act_settings)

        # 4. Logs action
        act_logs = QAction(self.tr_text("tray_logs"), self.menu)
        act_logs.triggered.connect(open_log_file)
        self.menu.addAction(act_logs)

        # 5. Admin elevation action if not currently elevated
        if not is_running_as_admin():
            act_admin = QAction("🛡️ Запустить от имени Администратора", self.menu)
            act_admin.triggered.connect(restart_as_admin)
            self.menu.addAction(act_admin)

        self.menu.addSeparator()

        # 6. Exit action
        act_exit = QAction(self.tr_text("tray_exit"), self.menu)
        act_exit.triggered.connect(self.on_exit)
        self.menu.addAction(act_exit)

    def build_presets_submenu(self):
        self.presets_menu.clear()
        presets = self.config_manager.get_all_presets()
        active = self.config_manager.config.active_preset

        group = QActionGroup(self.presets_menu)
        group.setExclusive(True)

        for name in presets.keys():
            action = QAction(name, self.presets_menu)
            action.setCheckable(True)
            if name == active:
                action.setChecked(True)
            action.triggered.connect(lambda checked, p=name: self.apply_preset(p))
            group.addAction(action)
            self.presets_menu.addAction(action)

    def apply_preset(self, preset_name: str):
        self.config_manager.apply_preset(preset_name)

    def toggle_enabled(self):
        cfg = self.config_manager.config
        cfg.enabled = not cfg.enabled
        self.config_manager.update_config(cfg, save=True)

    def on_config_changed(self, cfg: CursorConfig):
        self.act_toggle.setChecked(cfg.enabled)
        self.build_presets_submenu()
        self.update_tray_tooltip()

    def update_tray_tooltip(self):
        status = self.tr_text("tray_enabled") if self.config_manager.config.enabled else self.tr_text("tray_disabled")
        self.tray_icon.setToolTip(f"EnhancedCursor — {status} ({self.config_manager.config.active_preset})")

    def on_tray_activated(self, reason):
        # Trigger on single click or double click to open settings
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.on_open_settings()

    def hide(self):
        self.tray_icon.hide()

