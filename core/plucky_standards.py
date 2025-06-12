import os
import sys
from PySide6.QtCore import QStandardPaths

# Table of Contents
# 1. File Paths and Directory Management
# 2. File Extensions and MIME Types
# 3. Default Names and Identifiers
# 4. Core Data Structure Keys (for Scene Rendering)
# 5. Configuration and Settings Keys
# 6. UI and Theming Constants
# 7. Application and Company Metadata
# 8. Timing and Animation Constants
# 9. Default State and Fallback Values
# 10. Resource Handling Constants
# 11. Keyboard Shortcut Definitions
# 12. Application Limits

class PluckyStandards:
    """
    Provides standardized paths, constants, and keys for the Plucky application.
    This class is the single source of truth for application-wide standards
    to prevent "magic strings" and improve maintainability.
    """

    # --- 1. File Paths and Directory Management ---

    @staticmethod
    def get_user_store_root() -> str:
        """Returns the root directory for Plucky user-facing documents."""
        documents_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return os.path.join(documents_location, "Plucky", "UserStore")

    @staticmethod
    def get_presentations_dir() -> str:
        """Returns the directory for storing presentation manifest files."""
        return os.path.join(PluckyStandards.get_user_store_root(), "Presentations")

    @staticmethod
    def get_sections_dir() -> str:
        """Returns the default directory for storing individual section files."""
        return os.path.join(PluckyStandards.get_user_store_root(), "Sections")

    @staticmethod
    def get_templates_dir() -> str:
        """Returns the directory for storing user-defined template files."""
        return os.path.join(PluckyStandards.get_user_store_root(), "Templates")

    @staticmethod
    def get_templates_styles_dir() -> str:
        """Directory for user-defined style templates."""
        return os.path.join(PluckyStandards.get_templates_dir(), "Styles")

    @staticmethod
    def get_templates_layouts_dir() -> str:
        """Directory for user-defined layout templates."""
        return os.path.join(PluckyStandards.get_templates_dir(), "Layouts")

    @staticmethod
    def get_image_cache_dir() -> str:
        """Returns the directory for storing cached image files."""
        return os.path.join(PluckyStandards.get_user_store_root(), "image_cache")

    @staticmethod
    def get_app_name() -> str:
        """Returns the application's name, used for path generation."""
        return "Plucky"

    @staticmethod
    def get_user_data_dir() -> str:
        """Returns a user-specific directory for application data like databases."""
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if not path:
            home = os.path.expanduser("~")
            app_name_dir = PluckyStandards.get_app_name()
            if sys.platform == "win32":
                path = os.path.join(home, "AppData", "Local", app_name_dir)
            elif sys.platform == "darwin":
                path = os.path.join(home, "Library", "Application Support", app_name_dir)
            else:
                path = os.path.join(home, ".local", "share", app_name_dir)
        PluckyStandards.ensure_directory_exists(path)
        return path

    @staticmethod
    def get_resource_db_path() -> str:
        """Returns the full path to the resource tracking SQLite database."""
        return os.path.join(PluckyStandards.get_user_data_dir(), "plucky_resources.db")

    @staticmethod
    def ensure_directory_exists(path: str) -> None:
        """Ensures that the specified directory path exists."""
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                print(f"PluckyStandards: Created directory {path}")
            except OSError as e:
                print(f"PluckyStandards: Error creating directory {path}: {e}")

    @staticmethod
    def initialize_user_store() -> None:
        """Initializes all standard Plucky user directories."""
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_presentations_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_sections_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_styles_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_layouts_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_image_cache_dir())

    # --- 2. File Extensions and MIME Types ---

    @staticmethod
    def presentation_extension() -> str:
        return ".plucky_pres"

    @staticmethod
    def section_extension() -> str:
        return ".plucky_section"

    @staticmethod
    def template_extension() -> str:
        return ".plucky_template"

    @staticmethod
    def slide_mime_type() -> str:
        """Custom MIME type for drag-and-drop of slides."""
        return "application/x-plucky-slide"

    # --- 3. Default Names and Identifiers ---

    @staticmethod
    def default_layout_name() -> str:
        return "Default Layout"

    @staticmethod
    def default_style_name() -> str:
        return "Default Style"

    @staticmethod
    def untitled_presentation_name() -> str:
        return "Untitled Presentation"

    # --- 4. Core Data Structure Keys (for Scene Rendering) ---

    SCENE_KEY_WIDTH = "width"
    SCENE_KEY_HEIGHT = "height"
    SCENE_KEY_LAYERS = "layers"

    LAYER_KEY_ID = "id"
    LAYER_KEY_TYPE = "type"
    LAYER_KEY_POSITION = "position"
    LAYER_KEY_PROPERTIES = "properties"

    LAYER_TYPE_SOLID_COLOR = "solid_color"
    LAYER_TYPE_IMAGE = "image"
    LAYER_TYPE_VIDEO = "video"
    LAYER_TYPE_TEXT = "text"

    # --- 5. Configuration and Settings Keys ---

    SETTING_TARGET_MONITOR = "target_output_monitor_name"
    SETTING_DECKLINK_FILL_IDX = "decklink_fill_device_index"
    SETTING_DECKLINK_KEY_IDX = "decklink_key_device_index"
    SETTING_DECKLINK_MODE = "decklink_video_mode_details"
    SETTING_PREVIEW_SIZE = "preview_size"
    SETTING_RECENT_FILES = "recent_files"
    SETTING_WINDOW_STATE = "main_window_state"

    # --- 6. UI and Theming Constants ---

    PREVIEW_BASE_WIDTH = 160
    PREVIEW_BASE_HEIGHT = 90

    # --- 7. Application and Company Metadata ---

    APP_VERSION = "2.0.0-beta"
    ORGANIZATION_NAME = "PluckyAV"
    ORGANIZATION_DOMAIN = "pluckyav.com"

    # --- 8. Timing and Animation Constants ---

    DEBOUNCE_INTERVAL_MS = 250  # Standard delay for text input before triggering updates

    # --- 9. Default State and Fallback Values ---

    DEFAULT_OUTPUT_WIDTH = 1920
    DEFAULT_OUTPUT_HEIGHT = 1080
    DEFAULT_OUTPUT_BG_COLOR = "#000000"  # Black
    DEFAULT_RENDER_FONT = "Arial"

    # --- 10. Resource Handling Constants ---

    SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
    SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")

    # --- 11. Keyboard Shortcut Definitions ---

    KEY_SEQUENCE_NEXT_SLIDE = "Right"
    KEY_SEQUENCE_PREV_SLIDE = "Left"

    # --- 12. Application Limits ---

    MAX_RECENT_FILES = 10
