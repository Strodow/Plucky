from typing import Dict, Any, Optional, TYPE_CHECKING
from commands.base_command import Command
from data_models.slide_data import SlideData

if TYPE_CHECKING:
    from core.presentation_manager import PresentationManager # Forward declaration


class ChangeOverlayLabelCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int, old_label: str, new_label: str):
        super().__init__(manager)
        self.slide_index = slide_index
        self.old_label = old_label
        self.new_label = new_label

    def execute(self):
        slide = self.manager.slides[self.slide_index]
        slide.overlay_label = self.new_label
        # The manager's do_command will handle dirty flag and presentation_changed signal

    def undo(self):
        slide = self.manager.slides[self.slide_index]
        slide.overlay_label = self.old_label


class EditLyricsCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int, old_lyrics: str, new_lyrics: str):
        super().__init__(manager)
        self.slide_index = slide_index
        self.old_lyrics = old_lyrics
        self.new_lyrics = new_lyrics

    def execute(self):
        # Directly modify, PresentationManager's update_slide_content is more for external calls
        self.manager.slides[self.slide_index].lyrics = self.new_lyrics

    def undo(self):
        self.manager.slides[self.slide_index].lyrics = self.old_lyrics


class AddSlideCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_data: SlideData, index: Optional[int] = None):
        super().__init__(manager)
        self.slide_data = slide_data
        # If index is None, it will be appended. Store the index where it's actually added.
        self.added_at_index = index if index is not None else len(manager.slides)

    def execute(self):
        # The manager's add_slide method will handle appending or inserting
        self.manager.add_slide(self.slide_data, at_index=self.added_at_index, _execute_command=False)
        # Ensure the index is correctly captured if it was appended
        if self.added_at_index >= len(self.manager.slides): # It was appended
             self.added_at_index = len(self.manager.slides) -1

    def undo(self):
        self.manager.remove_slide(self.added_at_index, _execute_command=False)


class DeleteSlideCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int):
        super().__init__(manager)
        self.slide_index = slide_index
        self.deleted_slide_data: Optional[SlideData] = None

    def execute(self):
        # Store the data before deleting
        self.deleted_slide_data = self.manager.slides[self.slide_index]
        self.manager.remove_slide(self.slide_index, _execute_command=False)

    def undo(self):
        if self.deleted_slide_data:
            self.manager.add_slide(self.deleted_slide_data, at_index=self.slide_index, _execute_command=False)


class ApplyTemplateCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int,
                 old_template_settings: Dict[str, Any], new_template_settings: Dict[str, Any]):
        super().__init__(manager)
        self.slide_index = slide_index
        self.old_template_settings = old_template_settings
        self.new_template_settings = new_template_settings

    def execute(self):
        self.manager.set_slide_template_settings(self.slide_index, self.new_template_settings, _execute_command=False)

    def undo(self):
        self.manager.set_slide_template_settings(self.slide_index, self.old_template_settings, _execute_command=False)

# Example for a more complex operation like AddSong (conceptual)
# class AddSongCommand(Command):
#     def __init__(self, manager: 'PresentationManager', slides_data: List[SlideData]):
#         super().__init__(manager)
#         self.slides_data = slides_data
#         self.added_indices: List[int] = []

#     def execute(self):
#         # This would need careful handling of indices if add_slides appends
#         start_index = len(self.manager.slides)
#         self.manager.add_slides(self.slides_data, _execute_command=False)
#         self.added_indices = list(range(start_index, start_index + len(self.slides_data)))

#     def undo(self):
#         # Remove slides in reverse order of addition
#         for index in sorted(self.added_indices, reverse=True):
#             self.manager.remove_slide(index, _execute_command=False)