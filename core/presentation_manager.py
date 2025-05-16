# Optional: Class to manage presentation state, orchestrate slide transitions,
# and coordinate save/load operations.

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal

from data_models.slide_data import SlideData
from .presentation_io import PresentationIO # Revert to direct class import
from collections import deque
from PySide6.QtGui import QColor

if TYPE_CHECKING: # Keep existing TYPE_CHECKING imports
    from commands.base_command import Command # Forward declaration for type hinting
# For isinstance checks in do_command, we need actual imports
from commands.slide_commands import ApplyTemplateCommand, ChangeOverlayLabelCommand, EditLyricsCommand

MAX_UNDO_HISTORY = 30 # Configurable limit for undo steps

class PresentationManager(QObject):
    """
    Manages the presentation's state, including its slides,
    and handles saving and loading operations.
    """
    slide_visual_property_changed = Signal(list) # Emits list of indices of slides whose visual property changed
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

    def insert_slides(self, slides_to_insert: List[SlideData], at_index: int, _execute_command: bool = True):
        """Inserts a list of slides at a specific index."""
        if not slides_to_insert:
            return

        # Ensure index is within valid bounds for insertion
        if at_index < 0:
            at_index = 0
        elif at_index > len(self.slides): # Allow inserting at the very end
            at_index = len(self.slides)

        for i, slide_data in enumerate(slides_to_insert):
            self.slides.insert(at_index + i, slide_data)
        
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
            
    def update_entire_song(self, original_song_title: Optional[str], new_song_title: str, new_lyrics_stanzas: List[str], _execute_command: bool = True):
        """
        Updates a song.
        If new_lyrics_stanzas match the original lyrics of an existing song, only the song title is changed
        for the existing slides of that song, leaving all other slide properties untouched.
        Otherwise, replaces all slides of a song identified by original_song_title
        with new slides based on new_song_title and new_lyrics_stanzas. These new slides will have default properties
        except for lyrics and title.
        If new_lyrics_stanzas is empty (and it's not a title-only change), the song is effectively deleted.
        """
        # Sanitize new_song_title: if empty, it means the song becomes untitled
        processed_new_song_title = new_song_title.strip() if new_song_title.strip() else None

        # Find slides belonging to the original song title
        original_song_slide_indices = []
        if original_song_title is not None: # Only search if there's an original title
            original_song_slide_indices = [
                i for i, s in enumerate(self.slides) if s.song_title == original_song_title
            ]

        if not original_song_slide_indices and original_song_title is not None:
            # Song to edit was specified but not found.
            self.error_occurred.emit(f"Song '{original_song_title}' not found for update.")
            return

        # Get the lyrics of these original slides (if any)
        original_stanzas_from_pm = [self.slides[i].lyrics for i in original_song_slide_indices]

        # Check for title-only change:
        is_title_only_change = (
            bool(original_song_slide_indices) and # Must be an existing song
            len(new_lyrics_stanzas) == len(original_stanzas_from_pm) and
            all(new_stanza == old_stanza for new_stanza, old_stanza in zip(new_lyrics_stanzas, original_stanzas_from_pm))
        )

        if is_title_only_change:
            # --- TITLE-ONLY UPDATE ---
            # Modify the song_title of the existing slides in place. All other properties remain.
            changed_anything = False
            for slide_idx in original_song_slide_indices:
                if self.slides[slide_idx].song_title != processed_new_song_title:
                    self.slides[slide_idx].song_title = processed_new_song_title
                    changed_anything = True
            
            if changed_anything and _execute_command:
                self.is_dirty = True
                self.presentation_changed.emit()
            return # Title-only update is complete.

        # --- FULL REPLACE / ADD / DELETE SONG LOGIC ---
        # This part is reached if lyrics are changing, or it's a new song, or a song deletion.
        # New slides created here will have default properties for template, background etc.
        new_slide_objects_for_song = [
            SlideData(lyrics=stanza.strip(), song_title=processed_new_song_title)
            for stanza in new_lyrics_stanzas if stanza.strip() # Ensure stanzas are not empty
        ]

        updated_slide_list = []
        song_block_processed = False
        
        if original_song_title is not None: # Modifying or deleting an existing song
            for slide in self.slides:
                if slide.song_title == original_song_title:
                    if not song_block_processed:
                        updated_slide_list.extend(new_slide_objects_for_song)
                        song_block_processed = True
                else:
                    updated_slide_list.append(slide)
            if not song_block_processed and new_slide_objects_for_song: # Original not found, but new slides exist
                updated_slide_list.extend(new_slide_objects_for_song) # Add as new
            self.slides = updated_slide_list
        else: # Adding a new song (original_song_title is None)
            self.slides.extend(new_slide_objects_for_song)

        if _execute_command:
            self.is_dirty = True
            self.presentation_changed.emit()
    
    def set_slide_template_settings(self, slide_index: int, new_template_settings: Dict[str, Any], _suppress_signal: bool = False):
        """Updates the template_settings of a specific slide."""
        if 0 <= slide_index < len(self.slides):
            self.slides[slide_index].template_settings = new_template_settings.copy() # Assign a copy
            self.is_dirty = True # Always mark dirty
            if _suppress_signal:
                # This command will trigger a specific UI update
                self.slide_visual_property_changed.emit([slide_index])
            else: # Default behavior, emit general change
                self.presentation_changed.emit()
        else:
            self.error_occurred.emit(f"Cannot set template for slide: Index {slide_index} out of bounds.")

    def set_slide_banner_color(self, slide_index: int, color: Optional[QColor], _suppress_signal: bool = False):
        """Sets the banner color for the specified slide.
        If color is None, resets to the default color.
        _suppress_signal: If True, presentation_changed is NOT emitted after the change.
        """
        # Note: _suppress_signal now controls the generic presentation_changed.
        # We will always emit slide_visual_property_changed if not suppressed for batch operations.
        if not 0 <= slide_index < len(self.slides):
            self.error_occurred.emit(f"Cannot set banner color: Index {slide_index} out of bounds.")
            return
        
        # Assuming SlideData has a 'banner_color' attribute that stores a string (like hex) or None, and it's mutable
        self.slides[slide_index].banner_color = color.name() if color is not None else None

        self.is_dirty = True # Always mark dirty when data changes
        if not _suppress_signal: # This controls the generic presentation_changed for single updates
            self.presentation_changed.emit()
        else: # If part of a batch (suppressed generic), emit the specific signal for this slide
            self.slide_visual_property_changed.emit([slide_index])
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

            # Determine if the generic presentation_changed signal should be emitted.
            # If a command handles its own specific UI update (e.g., via slide_visual_property_changed),
            # we don't want to also trigger a full UI rebuild.
            commands_with_specific_updates = (
                ApplyTemplateCommand,
                ChangeOverlayLabelCommand,
                # EditLyricsCommand # Add EditLyricsCommand here once it's also optimized
            )
            if isinstance(command, commands_with_specific_updates):
                # These commands are expected to trigger slide_visual_property_changed
                # through their execution path (e.g., by calling a PM method with _suppress_signal=True).
                pass # Do not emit generic presentation_changed
            else:
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
    
    def move_slide(self, source_index: int, target_index: int, _execute_command: bool = True) -> bool:
        """
        Moves a slide from a source index to a target index.
        The target_index is the index *before* the source slide is removed if source_index < target_index,
        or the direct index if source_index > target_index.
        The SlideDragDropHandler should pass the 'actual_target_index' here.
        """
        num_slides = len(self.slides)
        if not (0 <= source_index < num_slides):
            self.error_occurred.emit(f"Error moving slide: Invalid source index ({source_index}).")
            return False

        # target_index is the final insertion point in the list *after* the pop.
        # It can range from 0 to num_slides - 1 (if num_slides > 0).
        # If num_slides is 0, this method shouldn't be callable with valid source_index.
        if not (0 <= target_index < num_slides if num_slides > 0 else target_index == 0):
             self.error_occurred.emit(f"Error moving slide: Invalid target index ({target_index}) for {num_slides} slides.")
             return False

        slide_to_move = self.slides.pop(source_index)
        self.slides.insert(target_index, slide_to_move)
        
        if _execute_command:
            self.is_dirty = True
            self.presentation_changed.emit()
        return True

    def clear_presentation(self):
        """Clears all slides and resets the presentation to a new, empty state."""
        self.slides.clear()
        self.current_filepath = None
        self.is_dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.presentation_changed.emit()