import os
import json
from PySide6.QtCore import QStandardPaths, QObject, Signal
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication # For QApplication.screens()
from typing import Optional, List, Dict, Any

SETTINGS_FILE_PATH_CONFIG = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation), "app_settings.json")
RECENT_FILES_FILE_PATH_CONFIG = os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation), "recent_files.json")
MAX_RECENT_FILES_CONFIG = 10

class ApplicationConfigManager(QObject):
    recent_files_updated = Signal()
    output_screen_setting_changed = Signal(QScreen) # Emits the new screen

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._app_settings: Dict[str, Any] = {}
        self._recent_files_list: List[str] = []
        self._target_output_screen: Optional[QScreen] = None

        self._load_app_settings()
        self._load_recent_files()

    def _load_app_settings(self):
        print(f"ConfigManager: Attempting to load app settings from {SETTINGS_FILE_PATH_CONFIG}")
        if os.path.exists(SETTINGS_FILE_PATH_CONFIG):
            try:
                with open(SETTINGS_FILE_PATH_CONFIG, 'r') as f:
                    settings = json.load(f)
                if not isinstance(settings, dict):
                    print(f"ConfigManager: Error - Settings file {SETTINGS_FILE_PATH_CONFIG} is not a dict.")
                    settings = {}
                self._app_settings = settings
            except (IOError, json.JSONDecodeError) as e:
                print(f"ConfigManager: Error loading app settings: {e}")
                self._app_settings = {}
        else:
            print(f"ConfigManager: App settings file not found. Using defaults.")
            self._app_settings = {}
        self._resolve_target_output_screen_from_settings()

    def _save_app_settings(self):
        current_settings_to_save = dict(self._app_settings) # Start with a copy of existing settings

        if self._target_output_screen:
            try:
                current_settings_to_save["output_screen_index"] = QApplication.screens().index(self._target_output_screen)
            except ValueError:
                current_settings_to_save["output_screen_index"] = -1
        else:
            current_settings_to_save["output_screen_index"] = -1

        try:
            settings_dir = os.path.dirname(SETTINGS_FILE_PATH_CONFIG)
            os.makedirs(settings_dir, exist_ok=True)
            with open(SETTINGS_FILE_PATH_CONFIG, 'w') as f:
                json.dump(current_settings_to_save, f, indent=4)
            print(f"ConfigManager: Saved app settings to {SETTINGS_FILE_PATH_CONFIG}")
        except IOError as e:
            print(f"ConfigManager: Error saving app settings: {e}")

    def _resolve_target_output_screen_from_settings(self):
        output_screen_index = self._app_settings.get("output_screen_index")
        screens = QApplication.screens()
        selected_screen: Optional[QScreen] = None
        if screens and isinstance(output_screen_index, int) and 0 <= output_screen_index < len(screens):
            selected_screen = screens[output_screen_index]
            print(f"ConfigManager: Loaded target output screen: {selected_screen.name()} (Index {output_screen_index})")
        else:
            print(f"ConfigManager: Invalid or missing 'output_screen_index' in settings. Defaulting.")
            selected_screen = self._get_default_output_screen()

        if self._target_output_screen != selected_screen:
            self._target_output_screen = selected_screen
            # Don't emit signal here during initial load, MainWindow can query after init

    def _get_default_output_screen(self) -> Optional[QScreen]:
        screens = QApplication.screens()
        if screens:
            primary_screen = QApplication.primaryScreen()
            if primary_screen and primary_screen in screens:
                return primary_screen
            return screens[0]
        return None

    def get_target_output_screen(self) -> Optional[QScreen]:
        if self._target_output_screen is None: # Ensure it's resolved if not already
             self._resolve_target_output_screen_from_settings()
        return self._target_output_screen

    def set_target_output_screen(self, screen: Optional[QScreen]):
        if self._target_output_screen != screen:
            self._target_output_screen = screen
            self._save_app_settings() # Save when changed
            if screen: # Only emit if a valid screen is set
                self.output_screen_setting_changed.emit(screen)
            print(f"ConfigManager: Target output screen set to {screen.name() if screen else 'None'}")

    def _load_recent_files(self):
        if os.path.exists(RECENT_FILES_FILE_PATH_CONFIG):
            try:
                with open(RECENT_FILES_FILE_PATH_CONFIG, 'r') as f:
                    recent_files = json.load(f)
                if isinstance(recent_files, list):
                    self._recent_files_list = [f for f in recent_files if isinstance(f, str)][:MAX_RECENT_FILES_CONFIG]
                else: self._recent_files_list = []
            except (IOError, json.JSONDecodeError):
                self._recent_files_list = []
        else:
            self._recent_files_list = []
        # self.recent_files_updated.emit() # MainWindow can query after init

    def _save_recent_files(self):
        try:
            recent_dir = os.path.dirname(RECENT_FILES_FILE_PATH_CONFIG)
            os.makedirs(recent_dir, exist_ok=True)
            with open(RECENT_FILES_FILE_PATH_CONFIG, 'w') as f:
                json.dump(self._recent_files_list, f, indent=4)
        except IOError as e:
            print(f"ConfigManager: Error saving recent files: {e}")

    def get_recent_files(self) -> List[str]:
        return list(self._recent_files_list) # Return a copy

    def add_recent_file(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if filepath in self._recent_files_list:
            self._recent_files_list.remove(filepath)
        self._recent_files_list.insert(0, filepath)
        if len(self._recent_files_list) > MAX_RECENT_FILES_CONFIG:
            self._recent_files_list = self._recent_files_list[:MAX_RECENT_FILES_CONFIG]
        self._save_recent_files()
        self.recent_files_updated.emit()

    def get_app_setting(self, key: str, default_value: Any = None) -> Any:
        return self._app_settings.get(key, default_value)

    def set_app_setting(self, key: str, value: Any):
        self._app_settings[key] = value
        self._save_app_settings() # Save when any app setting changes

    def save_all_configs(self): # Explicit save if needed, e.g. on app close
        self._save_app_settings()
        self._save_recent_files()