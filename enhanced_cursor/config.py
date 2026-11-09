import os
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal
from enhanced_cursor.logger import get_app_dir, get_logger


@dataclass
class CursorConfig:
    # Sizes
    cursor_size: int = 7
    outline_size: int = 22
    cursor_border_width: int = 1

    # Colors & Opacities
    cursor_color: str = "#7373cc"
    cursor_opacity: int = 140
    outline_color: str = "#a9a9de"
    outline_opacity: int = 45
    cursor_border_color: str = "#ffffff"
    cursor_border_opacity: int = 60

    # Physics & Animation
    speed: float = 0.25  # 0.01 - 1.0 (smooth trailing factor)
    animation_duration: int = 220  # ms
    squash_and_stretch: bool = True
    click_ripple: bool = True

    # Behavior
    enabled: bool = True
    start_on_login: bool = False
    idle_fade: bool = True
    idle_timeout_sec: float = 2.5
    hide_while_typing: bool = True
    game_detection: bool = True

    # System & UX
    language: str = "ru"  # "ru" or "en"
    active_preset: str = "iPad Classic"
    hotkey: str = "Ctrl+Alt+H"


BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "iPad Classic": {
        "cursor_size": 7,
        "outline_size": 22,
        "cursor_border_width": 1,
        "cursor_color": "#7373cc",
        "cursor_opacity": 140,
        "outline_color": "#a9a9de",
        "outline_opacity": 45,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 60,
        "speed": 0.25,
        "animation_duration": 220,
        "squash_and_stretch": True,
        "click_ripple": True,
    },
    "Neon Cyan": {
        "cursor_size": 8,
        "outline_size": 26,
        "cursor_border_width": 2,
        "cursor_color": "#00f0ff",
        "cursor_opacity": 180,
        "outline_color": "#ff007f",
        "outline_opacity": 60,
        "cursor_border_color": "#00ffff",
        "cursor_border_opacity": 140,
        "speed": 0.35,
        "animation_duration": 180,
        "squash_and_stretch": True,
        "click_ripple": True,
    },
    "Highlighter Yellow": {
        "cursor_size": 14,
        "outline_size": 32,
        "cursor_border_width": 1,
        "cursor_color": "#ffea00",
        "cursor_opacity": 130,
        "outline_color": "#ffd600",
        "outline_opacity": 50,
        "cursor_border_color": "#ff9100",
        "cursor_border_opacity": 80,
        "speed": 0.35,
        "animation_duration": 200,
        "squash_and_stretch": False,
        "click_ripple": True,
    },
    "Minimalist White": {
        "cursor_size": 6,
        "outline_size": 14,
        "cursor_border_width": 1,
        "cursor_color": "#ffffff",
        "cursor_opacity": 210,
        "outline_color": "#ffffff",
        "outline_opacity": 35,
        "cursor_border_color": "#000000",
        "cursor_border_opacity": 180,
        "speed": 0.45,
        "animation_duration": 150,
        "squash_and_stretch": False,
        "click_ripple": False,
    },
    "Stealth Dark": {
        "cursor_size": 6,
        "outline_size": 18,
        "cursor_border_width": 1,
        "cursor_color": "#2a2a2a",
        "cursor_opacity": 100,
        "outline_color": "#505050",
        "outline_opacity": 35,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 50,
        "speed": 0.25,
        "animation_duration": 220,
        "squash_and_stretch": True,
        "click_ripple": False,
    },
}


TRANSLATIONS = {
    "ru": {
        "app_title": "EnhancedCursor: Настройки",
        "tab_appearance": "Вид курсора",
        "tab_animation": "Анимация и эффекты",
        "tab_behavior": "Поведение",
        "tab_presets": "Пресеты и система",
        
        "cursor_size": "Размер курсора:",
        "outline_size": "Размер аутлайна:",
        "border_width": "Толщина границы:",
        
        "cursor_color": "Цвет курсора:",
        "cursor_opacity": "Прозрачность курсора:",
        "outline_color": "Цвет аутлайна:",
        "outline_opacity": "Прозрачность аутлайна:",
        "border_color": "Цвет границы:",
        "border_opacity": "Прозрачность границы:",
        
        "speed": "Скорость следования:",
        "speed_hint": "(Меньше — больше инерции, больше — острее отклик)",
        "animation_duration": "Длительность клика:",
        "squash_and_stretch": "Эластичная деформация при движении (iPadOS)",
        "click_ripple": "Эффект расходящейся волны при клике (Ripple)",
        
        "idle_fade": "Скрывать при бездействии",
        "idle_timeout": "Время до скрытия:",
        "hide_while_typing": "Скрывать при наборе текста (I-Beam)",
        "game_detection": "Игровой режим (пауза в полноэкранных играх)",
        "start_on_login": "Запускать вместе с Windows",
        "hotkey": "Горячая клавиша вкл/выкл:",
        "language": "Язык интерфейса:",
        
        "presets": "Готовые пресеты:",
        "apply_preset": "Применить пресет",
        "save_preset": "Сохранить как новый пресет...",
        "delete_preset": "Удалить пресет",
        "set_defaults": "Сбросить к умолчанию",
        "show_logs": "Открыть лог-файл",
        
        "interactive_preview": "Интерактивный тест (подвигайте и покликайте мышь здесь):",
        "zoom": "Масштаб предпросмотра:",
        
        "save": "Сохранить",
        "apply": "Применить",
        "close": "Закрыть",
        
        # Tray Menu
        "tray_enabled": "Включен",
        "tray_disabled": "Приостановлен",
        "tray_toggle": "Включить / Выключить (Ctrl+Alt+H)",
        "tray_presets": "Пресеты",
        "tray_settings": "Настройки...",
        "tray_logs": "Открыть журнал...",
        "tray_exit": "Выход",
    },
    "en": {
        "app_title": "EnhancedCursor: Settings",
        "tab_appearance": "Appearance",
        "tab_animation": "Animation & Effects",
        "tab_behavior": "Behavior",
        "tab_presets": "Presets & System",
        
        "cursor_size": "Cursor Size:",
        "outline_size": "Outline Size:",
        "border_width": "Border Width:",
        
        "cursor_color": "Cursor Color:",
        "cursor_opacity": "Cursor Opacity:",
        "outline_color": "Outline Color:",
        "outline_opacity": "Outline Opacity:",
        "border_color": "Border Color:",
        "border_opacity": "Border Opacity:",
        
        "speed": "Follow Speed:",
        "speed_hint": "(Lower = more inertia, higher = sharper tracking)",
        "animation_duration": "Click Duration:",
        "squash_and_stretch": "Elastic Squash & Stretch (iPadOS style)",
        "click_ripple": "Click Ripple Wave Effect",
        
        "idle_fade": "Fade out when idle",
        "idle_timeout": "Idle Timeout:",
        "hide_while_typing": "Hide while typing (I-Beam text cursor)",
        "game_detection": "Game Mode (auto-pause in fullscreen games)",
        "start_on_login": "Start with Windows",
        "hotkey": "Toggle Hotkey:",
        "language": "Language:",
        
        "presets": "Preset:",
        "apply_preset": "Apply Preset",
        "save_preset": "Save as New Preset...",
        "delete_preset": "Delete Preset",
        "set_defaults": "Restore Defaults",
        "show_logs": "Open Log File",
        
        "interactive_preview": "Interactive Preview (move & click mouse here):",
        "zoom": "Preview Zoom:",
        
        "save": "Save",
        "apply": "Apply",
        "close": "Close",
        
        # Tray Menu
        "tray_enabled": "Enabled",
        "tray_disabled": "Disabled",
        "tray_toggle": "Toggle On/Off (Ctrl+Alt+H)",
        "tray_presets": "Presets",
        "tray_settings": "Settings...",
        "tray_logs": "Open Logs...",
        "tray_exit": "Exit",
    }
}


class ConfigManager(QObject):
    config_changed = Signal(CursorConfig)

    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.config_file = os.path.join(get_app_dir(), "config.json")
        self.custom_presets_file = os.path.join(get_app_dir(), "custom_presets.json")
        self.config = CursorConfig()
        self.custom_presets: Dict[str, Dict[str, Any]] = {}
        self.load()

    def tr(self, key: str) -> str:
        lang = self.config.language if self.config.language in TRANSLATIONS else "ru"
        return TRANSLATIONS[lang].get(key, key)

    def load(self):
        # Load custom presets
        if os.path.exists(self.custom_presets_file):
            try:
                with open(self.custom_presets_file, "r", encoding="utf-8") as f:
                    self.custom_presets = json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading custom presets: {e}")

        # Load main config
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_fields = set(CursorConfig.__dataclass_fields__.keys())
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                self.config = CursorConfig(**filtered_data)
                self.logger.info("Configuration loaded from file.")
                return
            except Exception as e:
                self.logger.error(f"Error loading config.json: {e}")

        # Default configuration
        self.config = CursorConfig()
        self.save()

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
            self.logger.info("Configuration saved successfully.")
        except Exception as e:
            self.logger.error(f"Error saving config.json: {e}")

    def update_config(self, new_config: CursorConfig, save: bool = True):
        self.config = new_config
        if save:
            self.save()
        self.config_changed.emit(self.config)

    def get_all_presets(self) -> Dict[str, Dict[str, Any]]:
        combined = dict(BUILTIN_PRESETS)
        combined.update(self.custom_presets)
        return combined

    def apply_preset(self, preset_name: str) -> bool:
        presets = self.get_all_presets()
        if preset_name in presets:
            preset_data = presets[preset_name]
            for key, val in preset_data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, val)
            self.config.active_preset = preset_name
            self.save()
            self.config_changed.emit(self.config)
            self.logger.info(f"Preset applied: {preset_name}")
            return True
        return False

    def save_custom_preset(self, name: str) -> bool:
        if not name or name in BUILTIN_PRESETS:
            return False
        preset_data = {
            "cursor_size": self.config.cursor_size,
            "outline_size": self.config.outline_size,
            "cursor_border_width": self.config.cursor_border_width,
            "cursor_color": self.config.cursor_color,
            "cursor_opacity": self.config.cursor_opacity,
            "outline_color": self.config.outline_color,
            "outline_opacity": self.config.outline_opacity,
            "cursor_border_color": self.config.cursor_border_color,
            "cursor_border_opacity": self.config.cursor_border_opacity,
            "speed": self.config.speed,
            "animation_duration": self.config.animation_duration,
            "squash_and_stretch": self.config.squash_and_stretch,
            "click_ripple": self.config.click_ripple,
        }
        self.custom_presets[name] = preset_data
        try:
            with open(self.custom_presets_file, "w", encoding="utf-8") as f:
                json.dump(self.custom_presets, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Custom preset '{name}' saved.")
            return True
        except Exception as e:
            self.logger.error(f"Error saving custom preset: {e}")
            return False

    def delete_custom_preset(self, name: str) -> bool:
        if name in self.custom_presets:
            del self.custom_presets[name]
            try:
                with open(self.custom_presets_file, "w", encoding="utf-8") as f:
                    json.dump(self.custom_presets, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Custom preset '{name}' deleted.")
                return True
            except Exception as e:
                self.logger.error(f"Error deleting custom preset: {e}")
        return False

