import copy
from typing import Optional, Dict

from PySide6.QtCore import QObject, Slot # type: ignore
from PySide6.QtWidgets import QDialog, QMessageBox # type: ignore

# Assuming these imports are correct relative to the new file's location
from data_models.slide_data import SlideData
from core.presentation_manager import PresentationManager
from dialogs.edit_slide_content_dialog import EditSlideContentDialog
from commands.slide_commands import EditLyricsCommand

class SlideEditHandler(QObject):
    """
    Handles the logic for editing slide content using the EditSlideContentDialog.
    """
    def __init__(self, presentation_manager: PresentationManager, parent_widget: QObject):
        """
        Args:
            presentation_manager: The PresentationManager instance to interact with.
            parent_widget: The parent widget (usually MainWindow) for dialogs.
        """
        super().__init__(parent_widget)
        self.presentation_manager = presentation_manager
        self.parent_widget = parent_widget # Store parent for dialogs

    @Slot(int)
    def handle_edit_slide_requested(self, slide_index: int):
        """
        Opens the EditSlideContentDialog for the specified slide index,
        processes the result, and executes an undoable command if changes were made.
        """
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            # Use parent_widget to show message box
            QMessageBox.critical(self.parent_widget, "Error", f"Cannot edit slide: Index {slide_index} is invalid.")
            return

        slide_data = slides[slide_index]

        # Get current text content from template_settings or fallback to legacy lyrics
        old_text_content: Dict[str, str] = {}
        old_legacy_lyrics: Optional[str] = None

        if slide_data.template_settings and isinstance(slide_data.template_settings.get("text_content"), dict):
            old_text_content = copy.deepcopy(slide_data.template_settings["text_content"])

        # The dialog will handle the case where text_boxes are not defined and use slide_data.lyrics
        # So, we also need to capture the old legacy lyrics for the command.
        old_legacy_lyrics = slide_data.lyrics

        # Pass parent_widget to the dialog
        dialog = EditSlideContentDialog(slide_data, self.parent_widget)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text_content_from_dialog = dialog.get_updated_content()

            # Determine if actual changes were made
            content_changed = False
            new_legacy_lyrics_from_dialog: Optional[str] = None
            new_text_content_for_command: Dict[str, str | None] = {} # Use Dict[str, str | None] to allow None for legacy_lyrics key if not present

            if "legacy_lyrics" in new_text_content_from_dialog: # Dialog was in legacy mode
                new_legacy_lyrics_from_dialog = new_text_content_from_dialog["legacy_lyrics"]
                if new_legacy_lyrics_from_dialog != old_legacy_lyrics:
                    content_changed = True
                # For the command, pass only the legacy part if that's what was edited
                new_text_content_for_command = {"legacy_lyrics": new_legacy_lyrics_from_dialog}
            else: # Dialog was in template mode
                # Compare the dictionaries directly
                if new_text_content_from_dialog != old_text_content:
                    content_changed = True
                new_text_content_for_command = new_text_content_from_dialog
                # Ensure legacy_lyrics is explicitly None in the command data if not in dialog result
                new_legacy_lyrics_from_dialog = None # Not applicable in template mode

            if not content_changed:
                return # No actual changes made

            cmd = EditLyricsCommand(self.presentation_manager, slide_index,
                                    old_text_content, new_text_content_for_command,
                                    old_legacy_lyrics, new_legacy_lyrics_from_dialog)
            self.presentation_manager.do_command(cmd)