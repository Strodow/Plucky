from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any, Optional
import copy # For deep copying dictionaries

if TYPE_CHECKING:
    from core.presentation_manager import PresentationManager
    from data_models.slide_data import SlideData


class Command(ABC):
    """Abstract base class for commands."""
    @abstractmethod
    def execute(self):
        pass


    @abstractmethod
    def undo(self):
        pass


class AddSlideCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_data: 'SlideData', at_index: Optional[int] = None):
        self.manager = manager
        self.slide_data = slide_data
        self.at_index = at_index if at_index is not None else len(manager.get_slides())

    def execute(self):
        # This command inherently changes the structure, so it should use the general signal.
        # PresentationManager.add_slide handles this.
        self.manager.add_slide(self.slide_data, self.at_index, _execute_command=False) # _execute_command=False to prevent double signal from PM.do_command

    def undo(self):
        # This command inherently changes the structure, so it should use the general signal.
        # PresentationManager.remove_slide handles this.
        self.manager.remove_slide(self.at_index, _execute_command=False)


class DeleteSlideCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int):
        self.manager = manager
        self.slide_index = slide_index
        self.deleted_slide_data: Optional['SlideData'] = None

    def execute(self):
        slides = self.manager.get_slides()
        if 0 <= self.slide_index < len(slides):
            self.deleted_slide_data = slides[self.slide_index]
            # This command inherently changes the structure, so it should use the general signal.
            self.manager.remove_slide(self.slide_index, _execute_command=False)

    def undo(self):
        if self.deleted_slide_data:
            # This command inherently changes the structure, so it should use the general signal.
            self.manager.add_slide(self.deleted_slide_data, self.slide_index, _execute_command=False)


class EditLyricsCommand(Command):
    """Command to edit the text content of a slide, supporting multiple text boxes."""
    def __init__(self, manager: 'PresentationManager', slide_index: int,
                 old_text_content: Dict[str, str], new_text_content: Dict[str, str],
                 old_legacy_lyrics: Optional[str] = None, new_legacy_lyrics: Optional[str] = None):
        self.manager = manager
        self.slide_index = slide_index
        self.old_text_content = copy.deepcopy(old_text_content)
        self.new_text_content = copy.deepcopy(new_text_content)
        self.old_legacy_lyrics = old_legacy_lyrics
        self.new_legacy_lyrics = new_legacy_lyrics

    def execute(self):
        if not (0 <= self.slide_index < len(self.manager.slides)):
            return

        slide = self.manager.slides[self.slide_index]

        # Update template_settings.text_content
        if slide.template_settings is None: # Ensure template_settings dictionary exists
            slide.template_settings = {}
        slide.template_settings["text_content"] = copy.deepcopy(self.new_text_content)

        # Update legacy slide.lyrics
        # Priority: 1. Explicit new_legacy_lyrics (if dialog was in legacy mode)
        #           2. Content of the first text_box (if template defines text_boxes)
        #           3. First value from new_text_content (if no specific first_tb_id)
        #           4. Empty string as a last resort
        if self.new_legacy_lyrics is not None:
            slide.lyrics = self.new_legacy_lyrics
        elif self.new_text_content:
            first_tb_id = None
            text_boxes_config = slide.template_settings.get("text_boxes")
            if isinstance(text_boxes_config, list) and text_boxes_config:
                first_tb_id = text_boxes_config[0].get("id")
            
            if first_tb_id and first_tb_id in self.new_text_content:
                slide.lyrics = self.new_text_content[first_tb_id]
            else: # Fallback to the first available text content or empty
                slide.lyrics = next(iter(self.new_text_content.values()), "")
        else: # No new text content provided at all
            slide.lyrics = ""
            
        self.manager.slide_visual_property_changed.emit([self.slide_index])

    def undo(self):
        if not (0 <= self.slide_index < len(self.manager.slides)):
            return
            
        slide = self.manager.slides[self.slide_index]

        if slide.template_settings is None:
            slide.template_settings = {}
        slide.template_settings["text_content"] = copy.deepcopy(self.old_text_content)

        if self.old_legacy_lyrics is not None: # If we explicitly stored old legacy lyrics, restore it
            slide.lyrics = self.old_legacy_lyrics
        elif self.old_text_content: # Otherwise, derive from old_text_content like in execute
            first_tb_id = None
            text_boxes_config = slide.template_settings.get("text_boxes")
            if isinstance(text_boxes_config, list) and text_boxes_config:
                first_tb_id = text_boxes_config[0].get("id")
            
            if first_tb_id and first_tb_id in self.old_text_content:
                slide.lyrics = self.old_text_content[first_tb_id]
            else:
                slide.lyrics = next(iter(self.old_text_content.values()), "")
        else:
            slide.lyrics = ""

        self.manager.slide_visual_property_changed.emit([self.slide_index])


class ApplyTemplateCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int, old_settings: Optional[Dict[str, Any]], new_settings: Dict[str, Any]):
        self.manager = manager
        self.slide_index = slide_index
        self.old_settings = old_settings if old_settings is not None else {} # Ensure old_settings is a dict
        self.new_settings = new_settings

    def execute(self):
        self.manager.set_slide_template_settings(self.slide_index, self.new_settings, _suppress_signal=True)

    def undo(self):
        self.manager.set_slide_template_settings(self.slide_index, self.old_settings, _suppress_signal=True)


class ChangeOverlayLabelCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_index: int, old_label: str, new_label: str):
        self.manager = manager
        self.slide_index = slide_index
        self.old_label = old_label
        self.new_label = new_label

    def execute(self):
        self.manager.slides[self.slide_index].overlay_label = self.new_label
        self.manager.slide_visual_property_changed.emit([self.slide_index]) # Directly emit specific signal

    def undo(self):
        self.manager.slides[self.slide_index].overlay_label = self.old_label
        self.manager.slide_visual_property_changed.emit([self.slide_index]) # Directly emit specific signal