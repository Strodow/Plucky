import os
from PySide6.QtCore import QStandardPaths

class PluckyStandards:
    """
    Provides standardized paths for the Plucky application.
    Ensures that the necessary directories are created.
    """

    @staticmethod
    def get_user_store_root() -> str:
        """
        Returns the root directory for Plucky user-specific data.
        Example: ~/Documents/Plucky/UserStore
        """
        documents_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return os.path.join(documents_location, "Plucky", "UserStore")

    @staticmethod
    def get_presentations_dir() -> str:
        """
        Returns the directory for storing presentation manifest files (*.plucky_pres).
        Example: ~/Documents/Plucky/UserStore/Presentations
        """
        return os.path.join(PluckyStandards.get_user_store_root(), "Presentations")

    @staticmethod
    def get_sections_dir() -> str:
        """
        Returns the default directory for storing individual section files (*.plucky_section).
        Note: Presentations might store their sections in a relative subfolder.
        Example: ~/Documents/Plucky/UserStore/Sections
        """
        return os.path.join(PluckyStandards.get_user_store_root(), "Sections")

    @staticmethod
    def get_templates_dir() -> str:
        """
        Returns the directory for storing user-defined template files.
        Example: ~/Documents/Plucky/UserStore/Templates
        """
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
    def get_templates_master_templates_dir() -> str:
        """Directory for user-defined master templates."""
        return os.path.join(PluckyStandards.get_templates_dir(), "MasterTemplates")

    @staticmethod
    def ensure_directory_exists(path: str) -> None:
        """
        Ensures that the specified directory path exists. Creates it if it doesn't.
        """
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                print(f"PluckyStandards: Created directory {path}")
            except OSError as e:
                print(f"PluckyStandards: Error creating directory {path}: {e}")
                # Depending on severity, you might want to raise this or handle it

    @staticmethod
    def initialize_user_store() -> None:
        """Initializes all standard Plucky user directories."""
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_user_store_root())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_presentations_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_sections_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_styles_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_layouts_dir())
        PluckyStandards.ensure_directory_exists(PluckyStandards.get_templates_master_templates_dir())
