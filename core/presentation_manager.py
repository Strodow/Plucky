# Optional: Class to manage presentation state, orchestrate slide transitions,
# and coordinate save/load operations.

from typing import List, Optional
from PySide6.QtCore import QObject, Signal as pyqtSignal # Or from PySide6.QtCore

from data_models.slide_data import SlideData
from core import presentation_io # This relies on __init__.py in core

class PresentationManager(QObject):
    """
    Manages the presentation's state, including its slides,
    and handles saving and loading operations.
    """
    presentation_changed = pyqtSignal() # Emitted when slides are loaded or significantly changed. In PySide6, pyqtSignal is an alias for Signal.
    error_occurred = pyqtSignal(str)    # Emitted when an error occurs during save/load.

    def __init__(self):
        super().__init__()
        self.slides: List[SlideData] = []
        self.current_filepath: Optional[str] = None
        self.is_dirty: bool = False # Tracks unsaved changes

    def add_slide(self, slide: SlideData):
        self.slides.append(slide)
        self.is_dirty = True
        self.presentation_changed.emit()
        
    def add_slides(self, new_slides: List[SlideData]):
        if not new_slides:
            return
        self.slides.extend(new_slides)
        self.is_dirty = True
        self.presentation_changed.emit()

    # Add other methods to modify slides (remove, reorder, update)
    # Each modification should set self.is_dirty = True and emit presentation_changed

    def get_slides(self) -> List[SlideData]:
        return self.slides

    def save_presentation(self, filepath: Optional[str] = None) -> bool:
        if filepath:
            self.current_filepath = filepath
        
        if not self.current_filepath:
            self.error_occurred.emit("Cannot save: No file path specified.")
            return False
        
        try:
            presentation_io.save_presentation(self.slides, self.current_filepath)
            self.is_dirty = False
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to save presentation: {e}")
            return False

    def load_presentation(self, filepath: str) -> bool:
        try:
            self.slides = presentation_io.load_presentation(filepath)
            self.current_filepath = filepath
            self.is_dirty = False
            self.presentation_changed.emit()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to load presentation: {e}")
            return False