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

        if slide_data.template_settings and isinstance(slide_data.template_settings.get("text_content"), dict):
            old_text_content = copy.deepcopy(slide_data.template_settings["text_content"])
        elif slide_data.lyrics: # Fallback if text_content is not structured, use legacy lyrics as main_text
            old_text_content = {"main_text": slide_data.lyrics}

        # Pass parent_widget to the dialog
        dialog = EditSlideContentDialog(slide_data, self.parent_widget)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text_content_from_dialog = dialog.get_updated_content()

            # Compare the new content dictionary with the old one.
            # The EditSlideContentDialog should return a dictionary representing the new 'content'
            # field of a slide_block.
            if new_text_content_from_dialog == old_text_content:
                print("SlideEditHandler: No changes detected in slide content.")
                return # No actual changes made

            # Use slide_data.id as the instance_slide_id
            instance_id_to_edit = slide_data.id

            cmd = EditLyricsCommand(
                self.presentation_manager,
                instance_id_to_edit,
                old_text_content, # The original content dictionary
                new_text_content_from_dialog # The new content dictionary from the dialog
            )
            self.presentation_manager.do_command(cmd)