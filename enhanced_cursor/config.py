import os
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal
from enhanced_cursor.logger import get_app_dir, get_logger


@dataclass
class CursorConfig:
    # Mode & Style
    shape_mode: str = "fluid_drop"  # "fluid_drop" (капля с хвостиком) or "classic_circle" (iPadOS)
    render_mode: str = "custom"     # "custom" (скрыть стрелку Windows) or "aura" (шлейф поверх стрелки)
    use_system_accent: bool = True  # подхватывать системный цвет Windows

    # Sizes
    cursor_size: int = 8
    outline_enabled: bool = True    # включение/выключение внешнего круга (ореола)
    outline_size: int = 22
    cursor_border_width: int = 1

    # Colors & Opacities
    cursor_color: str = "#00b7c3"
    cursor_opacity: int = 200
    outline_color: str = "#00e5ff"
    outline_opacity: int = 50
    cursor_border_color: str = "#ffffff"
    cursor_border_opacity: int = 120
    right_click_color: str = "#ff7043"

    # Fluid Physics & Tail
    tail_length: float = 1.0        # 0.2 - 2.5 (множитель длины хвостика)
    viscosity: float = 0.55         # 0.1 - 1.0 (вязкость и поверхностное натяжение)
    speed: float = 0.28             # 0.01 - 1.0 (smooth trailing factor)
    animation_duration: int = 220   # ms
    squash_and_stretch: bool = True # эластичное растяжение головы при скорости
    
    # Interactive Effects
    click_ripple: bool = True       # расходящаяся волна при клике
    click_splash: bool = True       # микро-всплеск капелек при клике
    shake_to_find: bool = True      # увеличение капли при быстром покачивании мыши
    color_mode_per_click: bool = True # раздельный цвет для ЛКМ / ПКМ

    # Behavior
    enabled: bool = True
    start_on_login: bool = False
    idle_fade: bool = True
    idle_timeout_sec: float = 2.5
    hide_while_typing: bool = True
    game_detection: bool = True

    # System & UX
    language: str = "ru"            # "ru" or "en"
    active_preset: str = "Системный акцент (Капля)"
    hotkey: str = "Ctrl+Alt+H"


BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "Системный акцент (Капля)": {
        "shape_mode": "fluid_drop",
        "render_mode": "custom",
        "use_system_accent": True,
        "cursor_size": 8,
        "outline_size": 22,
        "cursor_border_width": 1,
        "cursor_opacity": 200,
        "outline_opacity": 50,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 130,
        "tail_length": 1.0,
        "viscosity": 0.55,
        "speed": 0.30,
        "squash_and_stretch": True,
        "click_ripple": True,
        "click_splash": True,
        "shake_to_find": True,
    },
    "Жидкая ртуть (Mercury)": {
        "shape_mode": "fluid_drop",
        "render_mode": "custom",
        "use_system_accent": False,
        "cursor_size": 8,
        "outline_size": 24,
        "cursor_border_width": 1,
        "cursor_color": "#e0e5ea",
        "cursor_opacity": 230,
        "outline_color": "#90a4ae",
        "outline_opacity": 60,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 180,
        "tail_length": 1.15,
        "viscosity": 0.70,
        "speed": 0.28,
        "squash_and_stretch": True,
        "click_ripple": True,
        "click_splash": True,
        "shake_to_find": True,
    },
    "Неоновая комета (Cyberpunk)": {
        "shape_mode": "fluid_drop",
        "render_mode": "custom",
        "use_system_accent": False,
        "cursor_size": 8,
        "outline_size": 26,
        "cursor_border_width": 2,
        "cursor_color": "#00f0ff",
        "cursor_opacity": 220,
        "outline_color": "#ff007f",
        "outline_opacity": 80,
        "cursor_border_color": "#00ffff",
        "cursor_border_opacity": 160,
        "tail_length": 1.4,
        "viscosity": 0.45,
        "speed": 0.35,
        "squash_and_stretch": True,
        "click_ripple": True,
        "click_splash": True,
        "shake_to_find": True,
    },
    "Капля воды (Water Drop)": {
        "shape_mode": "fluid_drop",
        "render_mode": "custom",
        "use_system_accent": False,
        "cursor_size": 8,
        "outline_size": 22,
        "cursor_border_width": 1,
        "cursor_color": "#4fc3f7",
        "cursor_opacity": 190,
        "outline_color": "#81d4fa",
        "outline_opacity": 60,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 150,
        "tail_length": 1.0,
        "viscosity": 0.50,
        "speed": 0.32,
        "squash_and_stretch": True,
        "click_ripple": True,
        "click_splash": True,
        "shake_to_find": True,
    },
    "iPad Classic (Аура)": {
        "shape_mode": "classic_circle",
        "render_mode": "aura",
        "use_system_accent": False,
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
        "click_splash": False,
        "shake_to_find": False,
    },
    "Highlighter Yellow": {
        "shape_mode": "classic_circle",
        "render_mode": "aura",
        "use_system_accent": False,
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
        "click_splash": False,
        "shake_to_find": False,
    },
    "Stealth Dark": {
        "shape_mode": "fluid_drop",
        "render_mode": "custom",
        "use_system_accent": False,
        "cursor_size": 7,
        "outline_size": 18,
        "cursor_border_width": 1,
        "cursor_color": "#2c2c34",
        "cursor_opacity": 220,
        "outline_color": "#555566",
        "outline_opacity": 55,
        "cursor_border_color": "#ffffff",
        "cursor_border_opacity": 80,
        "tail_length": 0.9,
        "viscosity": 0.60,
        "speed": 0.26,
        "squash_and_stretch": True,
        "click_ripple": False,
        "click_splash": False,
        "shake_to_find": True,
    },
}


TRANSLATIONS = {
    "ru": {
        "app_title": "EnhancedCursor: Настройки",
        "tab_appearance": "Вид курсора",
        "tab_animation": "Анимация и эффекты",
        "tab_behavior": "Поведение",
        "tab_presets": "Пресеты и система",
        
        "shape_mode": "Форма курсора:",
        "shape_fluid_drop": "Жидкая капля (Fluid Drop)",
        "shape_classic_circle": "Классический круг (iPadOS)",
        "render_mode": "Режим отображения:",
        "render_custom": "Скрыть стрелку Windows (Замена на каплю)",
        "render_aura": "Аура и шлейф (поверх стрелки Windows)",
        "use_system_accent": "Использовать системный акцентный цвет Windows",
        "outline_enabled": "Включить ореол / ауру (большой круг)",
        
        "cursor_size": "Размер курсора:",
        "outline_size": "Размер аутлайна / ореола:",
        "border_width": "Толщина границы:",
        "tail_length": "Длина хвостика:",
        "viscosity": "Вязкость жидкости:",
        
        "cursor_color": "Цвет курсора:",
        "cursor_opacity": "Прозрачность курсора:",
        "outline_color": "Цвет аутлайна / шлейфа:",
        "outline_opacity": "Прозрачность аутлайна:",
        "border_color": "Цвет границы:",
        "border_opacity": "Прозрачность границы:",
        "right_click_color": "Цвет при клике ПКМ:",
        
        "speed": "Скорость следования:",
        "speed_hint": "(Меньше — больше инерции, больше — острее отклик)",
        "animation_duration": "Длительность клика:",
        "squash_and_stretch": "Эластичная деформация при движении (Squash & Stretch)",
        "click_ripple": "Эффект расходящейся волны при клике (Ripple)",
        "click_splash": "Всплеск микро-капель при клике (Liquid Splash)",
        "shake_to_find": "Встряхнуть для поиска (Shake to Find, как в macOS)",
        
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
        
        "interactive_preview": "Интерактивный тест (подвигайте мышь и покликайте):",
        "zoom": "Масштаб предпросмотра:",
        
        "save": "Сохранить",
        "saved_feedback": "Сохранено! ✓",
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
        
        "shape_mode": "Cursor Shape:",
        "shape_fluid_drop": "Fluid Drop (Liquid Teardrop)",
        "shape_classic_circle": "Classic Circle (iPadOS)",
        "render_mode": "Display Mode:",
        "render_custom": "Hide Windows arrow (Custom Drop)",
        "render_aura": "Aura & trail (over Windows arrow)",
        "use_system_accent": "Use Windows System Accent Color",
        "outline_enabled": "Enable Aura / Glow (Big Circle)",
        
        "cursor_size": "Cursor Size:",
        "outline_size": "Outline / Aura Size:",
        "border_width": "Border Width:",
        "tail_length": "Tail Length:",
        "viscosity": "Fluid Viscosity:",
        
        "cursor_color": "Cursor Color:",
        "cursor_opacity": "Cursor Opacity:",
        "outline_color": "Outline / Trail Color:",
        "outline_opacity": "Outline Opacity:",
        "border_color": "Border Color:",
        "border_opacity": "Border Opacity:",
        "right_click_color": "Right-click Color:",
        
        "speed": "Follow Speed:",
        "speed_hint": "(Lower = more inertia, higher = sharper tracking)",
        "animation_duration": "Click Duration:",
        "squash_and_stretch": "Elastic Squash & Stretch",
        "click_ripple": "Click Ripple Wave Effect",
        "click_splash": "Click Liquid Splash",
        "shake_to_find": "Shake to Find (macOS style locate)",
        
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
        "saved_feedback": "Saved! ✓",
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
            "shape_mode": self.config.shape_mode,
            "render_mode": self.config.render_mode,
            "use_system_accent": self.config.use_system_accent,
            "cursor_size": self.config.cursor_size,
            "outline_enabled": self.config.outline_enabled,
            "outline_size": self.config.outline_size,
            "cursor_border_width": self.config.cursor_border_width,
            "cursor_color": self.config.cursor_color,
            "cursor_opacity": self.config.cursor_opacity,
            "outline_color": self.config.outline_color,
            "outline_opacity": self.config.outline_opacity,
            "cursor_border_color": self.config.cursor_border_color,
            "cursor_border_opacity": self.config.cursor_border_opacity,
            "right_click_color": self.config.right_click_color,
            "tail_length": self.config.tail_length,
            "viscosity": self.config.viscosity,
            "speed": self.config.speed,
            "animation_duration": self.config.animation_duration,
            "squash_and_stretch": self.config.squash_and_stretch,
            "click_ripple": self.config.click_ripple,
            "click_splash": self.config.click_splash,
            "shake_to_find": self.config.shake_to_find,
            "color_mode_per_click": self.config.color_mode_per_click,
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

