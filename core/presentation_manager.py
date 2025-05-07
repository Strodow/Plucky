# Optional: Class to manage presentation state, orchestrate slide transitions,
# and coordinate save/load operations.

from typing import List, Optional, Dict, Any # Added Dict, Any
from PySide6.QtCore import QObject, Signal as pyqtSignal # Or from PySide6.QtCorefrom typing import Dict, Any # Added Dict, Any

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
        
    def update_slide_content(self, index: int, new_lyrics: str):
        """Updates the lyrics of a specific slide."""
        if 0 <= index < len(self.slides):
            self.slides[index].lyrics = new_lyrics
            self.is_dirty = True
            self.presentation_changed.emit() # Or a more specific signal if needed
        else:
            self.error_occurred.emit(f"Cannot update slide: Index {index} out of bounds.")

    def remove_slide(self, index: int):
        """Removes a specific slide by its index."""
        if 0 <= index < len(self.slides):
            del self.slides[index]
            self.is_dirty = True
            self.presentation_changed.emit()
        else:
            self.error_occurred.emit(f"Cannot remove slide: Index {index} out of bounds.")
            
    def update_entire_song(self, original_song_title: str, new_song_title: str, new_lyrics_stanzas: List[str]):
        """
        Replaces all slides of a song identified by original_song_title
        with new slides based on new_song_title and new_lyrics_stanzas.
        If new_lyrics_stanzas is empty, the song is effectively deleted.
        """
        # Sanitize new_song_title: if empty, it means the song becomes untitled
        processed_new_song_title = new_song_title.strip() if new_song_title.strip() else None

        new_slides_for_song = [
            SlideData(lyrics=stanza, song_title=processed_new_song_title) 
            for stanza in new_lyrics_stanzas if stanza.strip() # Ensure stanzas are not empty
        ]

        updated_slide_list = []
        song_block_replaced = False

        for slide in self.slides:
            if slide.song_title == original_song_title:
                if not song_block_replaced:
                    # This is the first slide of the song block to be replaced.
                    # Add all new slides for the (potentially renamed) song here.
                    updated_slide_list.extend(new_slides_for_song)
                    song_block_replaced = True
                # Skip this old slide (and subsequent old slides of the same song title)
            else:
                # This slide is not part of the song being replaced, keep it.
                updated_slide_list.append(slide)
        
        self.slides = updated_slide_list
        self.is_dirty = True
        self.presentation_changed.emit()
    
    def set_slide_template_settings(self, slide_index: int, new_template_settings: Dict[str, Any]):
        """Updates the template_settings of a specific slide."""
        if 0 <= slide_index < len(self.slides):
            self.slides[slide_index].template_settings = new_template_settings # Assign a copy if mutation is a concern
            self.is_dirty = True
            self.presentation_changed.emit() # To refresh preview and mark as dirty
        else:
            self.error_occurred.emit(f"Cannot set template for slide: Index {slide_index} out of bounds.")

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