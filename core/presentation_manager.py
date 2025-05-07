# Optional: Class to manage presentation state, orchestrate slide transitions,
# and coordinate save/load operations.

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal

from data_models.slide_data import SlideData
from .presentation_io import PresentationIO # Revert to direct class import
from collections import deque

if TYPE_CHECKING:
    from commands.base_command import Command # Forward declaration for type hinting

MAX_UNDO_HISTORY = 30 # Configurable limit for undo steps

class PresentationManager(QObject):
    """
    Manages the presentation's state, including its slides,
    and handles saving and loading operations.
    """
    presentation_changed = Signal() # Emitted when slides are loaded or significantly changed.
    error_occurred = Signal(str)    # Emitted when an error occurs.

    def __init__(self):
        super().__init__()
        self.slides: List[SlideData] = []
        self.current_filepath: Optional[str] = None
        self.is_dirty: bool = False # Tracks unsaved changes
        self.io_handler = PresentationIO() # Instantiate the class directly
        
        self.undo_stack: deque['Command'] = deque(maxlen=MAX_UNDO_HISTORY)
        self.redo_stack: deque['Command'] = deque(maxlen=MAX_UNDO_HISTORY)

    def add_slide(self, slide_data: SlideData, at_index: Optional[int] = None, _execute_command: bool = True):
        if at_index is None or at_index >= len(self.slides):
            self.slides.append(slide_data)
        else:
            self.slides.insert(at_index, slide_data)
        
        if _execute_command: # Only mark dirty and emit if not called by an undo/redo operation
            self.is_dirty = True
            self.presentation_changed.emit()
        
    def add_slides(self, new_slides: List[SlideData], _execute_command: bool = True):
        if not new_slides:
            return
        self.slides.extend(new_slides)
        if _execute_command:
            self.is_dirty = True
            self.presentation_changed.emit()
        
    def update_slide_content(self, index: int, new_lyrics: str, _execute_command: bool = True):
        """Updates the lyrics of a specific slide."""
        if 0 <= index < len(self.slides):
            self.slides[index].lyrics = new_lyrics
            if _execute_command:
                self.is_dirty = True
                self.presentation_changed.emit()
        else:
            self.error_occurred.emit(f"Cannot update slide: Index {index} out of bounds.")

    def remove_slide(self, index: int, _execute_command: bool = True):
        """Removes a specific slide by its index."""
        if 0 <= index < len(self.slides):
            del self.slides[index]
            if _execute_command:
                self.is_dirty = True
                self.presentation_changed.emit()
        else:
            self.error_occurred.emit(f"Cannot remove slide: Index {index} out of bounds.")
            
    def update_entire_song(self, original_song_title: str, new_song_title: str, new_lyrics_stanzas: List[str], _execute_command: bool = True):
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
        if _execute_command:
            self.is_dirty = True
            self.presentation_changed.emit()
    
    def set_slide_template_settings(self, slide_index: int, new_template_settings: Dict[str, Any], _execute_command: bool = True):
        """Updates the template_settings of a specific slide."""
        if 0 <= slide_index < len(self.slides):
            self.slides[slide_index].template_settings = new_template_settings.copy() # Assign a copy
            if _execute_command:
                self.is_dirty = True
                self.presentation_changed.emit()
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
            self.io_handler.save_presentation(self.slides, self.current_filepath)
            self.is_dirty = False
            self.undo_stack.clear() # Clear undo/redo history on successful save
            self.redo_stack.clear()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to save presentation: {e}")
            return False

    def load_presentation(self, filepath: str) -> bool:
        try:
            self.slides = self.io_handler.load_presentation(filepath)
            self.current_filepath = filepath
            self.is_dirty = False
            self.undo_stack.clear() # Clear undo/redo history on successful load
            self.redo_stack.clear()
            self.presentation_changed.emit()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to load presentation: {e}")
            return False

    def do_command(self, command: 'Command'):
        """Executes a command and adds it to the undo stack."""
        try:
            command.execute()
            self.undo_stack.append(command)
            self.redo_stack.clear() # New action clears redo history
            self.is_dirty = True
            self.presentation_changed.emit()
            print(f"PM: Executed command {command.__class__.__name__}. Undo stack size: {len(self.undo_stack)}")
        except Exception as e:
            self.error_occurred.emit(f"Error executing command {command.__class__.__name__}: {e}")
            print(f"Error executing command {command.__class__.__name__}: {e}")

    def undo(self):
        if not self.undo_stack:
            print("PM: Undo stack empty.")
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.is_dirty = True # Undoing a change is still a change from the last saved state
        self.presentation_changed.emit()
        print(f"PM: Undid command {command.__class__.__name__}. Redo stack size: {len(self.redo_stack)}")

    def redo(self):
        if not self.redo_stack:
            print("PM: Redo stack empty.")
            return
        command = self.redo_stack.pop()
        command.execute() # Or command.redo() if it has specific redo logic
        self.undo_stack.append(command)
        self.is_dirty = True
        self.presentation_changed.emit()
        print(f"PM: Redid command {command.__class__.__name__}. Undo stack size: {len(self.undo_stack)}")