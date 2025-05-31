# Optional: Class to manage presentation state, orchestrate slide transitions,
# and coordinate save/load operations.
import shutil # For copying files in save_presentation_as
import uuid # For generating unique SlideData IDs
import os
import sys # Import the sys module
from PySide6.QtCore import QObject, Signal

from data_models.slide_data import SlideData
from .presentation_io import PresentationIO # Revert to direct class import
from collections import deque
from PySide6.QtGui import QColor

try:
    from core.plucky_standards import PluckyStandards
    from typing import List, Optional, Dict, Any, TYPE_CHECKING # Import TYPE_CHECKING here
except ImportError:
    from plucky_standards import PluckyStandards # Fallback

if TYPE_CHECKING: # Keep existing TYPE_CHECKING imports
    from commands.base_command import Command # Forward declaration for type hinting
    from .template_manager import TemplateManager # For type hinting
from .template_manager import SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME # Import the constant
# For isinstance checks in do_command, we need actual imports
from commands.slide_commands import ApplyTemplateCommand, ChangeOverlayLabelCommand, EditLyricsCommand

MAX_UNDO_HISTORY = 30 # Configurable limit for undo steps

class PresentationManager(QObject):
    """
    Manages the presentation's state, including its slides,
    and handles saving and loading operations.
    """
    # Emits list of global indices of slides whose visual property changed
    slide_visual_property_changed = Signal(list) 
    presentation_changed = Signal() # Emitted when slides are loaded or significantly changed.
    error_occurred = Signal(str) # Emitted when an error occurs.

    def __init__(self, template_manager: 'TemplateManager'): # Add template_manager parameter
        super().__init__()
        self.template_manager = template_manager # Store the instance
        # Old state:
        # self.slides: List[SlideData] = []
        # self.current_filepath: Optional[str] = None
        # self.is_dirty: bool = False

        # New state for modular presentation structure:
        self.presentation_manifest_data: Optional[Dict[str, Any]] = None
        # Stores the parsed content of the *.plucky_pres file.
        # Example: {"version": "1.0.0", "presentation_title": "...", "sections": [{"id": "uuid", "path": "...", "active_arrangement_name": "..."}]}

        self.loaded_sections: Dict[str, Dict[str, Any]] = {}
        # Key: section_id from the manifest (e.g., "pres_sec_uuid_1")
        # Value: {"manifest_entry_data": {...}, "section_content_data": {...parsed section file...}, "is_dirty": False}

        self.current_manifest_filepath: Optional[str] = None
        self.presentation_manifest_is_dirty: bool = False

        self.io_handler = PresentationIO() # Instantiate the class directly
        
        self.undo_stack: deque['Command'] = deque(maxlen=MAX_UNDO_HISTORY)
        self.redo_stack: deque['Command'] = deque(maxlen=MAX_UNDO_HISTORY)

        # Map to quickly find section/arrangement details from a SlideData instance ID
        # Populated by get_slides()
        self._instance_id_to_arrangement_info_map: Dict[str, Dict[str, Any]] = {}

    def add_slide(self, slide_data: SlideData, at_index: Optional[int] = None, _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides.
        New functionality should use section-specific methods like `add_slide_block_to_section`.
        """
        print("PM: add_slide is deprecated. Use section-specific methods.")
        # if _execute_command:
        #     self.presentation_manifest_is_dirty = True # Or section specific dirty
        #     self.presentation_changed.emit()
        
    def add_slides(self, new_slides: List[SlideData], _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides.
        New functionality should use section-specific methods.
        """
        print("PM: add_slides is deprecated. Use section-specific methods.")
        # if _execute_command:
        #     self.presentation_manifest_is_dirty = True # Or section specific
        #     self.presentation_changed.emit()

    def insert_slides(self, slides_to_insert: List[SlideData], at_index: int, _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides.
        New functionality should use section-specific methods.
        """
        print("PM: insert_slides is deprecated. Use section-specific methods.")
        # if _execute_command:
        #     self.presentation_manifest_is_dirty = True # Or section specific
        #     self.presentation_changed.emit()
        
    def update_slide_content(self, index: int, new_lyrics: str, _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides.
        New functionality should use section-specific methods like `update_slide_block_in_section`.
        """
        print("PM: update_slide_content is deprecated. Use section-specific methods.")
        # if 0 <= index < len(self.slides):
        #     self.slides[index].lyrics = new_lyrics
        #     if _execute_command:
        #         self.is_dirty = True
        #         self.presentation_changed.emit()
        # else:
        #     self.error_occurred.emit(f"Cannot update slide: Index {index} out of bounds.")

    def remove_slide(self, index: int, _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides.
        New functionality should use section-specific methods like `delete_slide_block_from_section`.
        """
        # TODO: Refactor for new structure. This will involve finding the correct section and modifying its arrangement/slide_blocks.
        # if 0 <= index < len(self.slides):
        #     del self.slides[index]
        #     if _execute_command:
        #         self.is_dirty = True
        #         self.presentation_changed.emit()
        # else:
        #     self.error_occurred.emit(f"Cannot remove slide: Index {index} out of bounds.")
        print("PM: remove_slide is deprecated. Use section-specific methods.")
            
    def update_entire_song(self, original_song_title: Optional[str], new_song_title: str, new_lyrics_stanzas: List[str], _execute_command: bool = True):
        """
        DEPRECATED/REFACTOR: This method operated on a flat list of slides by song_title.
        New functionality will involve finding the correct section file (which represents a song/section)
        and modifying its 'title' and 'slide_blocks'/'arrangements'.

        If new_lyrics_stanzas is empty (and it's not a title-only change), the song is effectively deleted.
        """
        # Sanitize new_song_title: if empty, it means the song becomes untitled
        # TODO: Refactor for new structure. This will involve finding the correct section file and modifying it.
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
            # self.is_dirty = True # TODO: Refactor for new structure
            self.presentation_manifest_is_dirty = True # Or section specific
            self.presentation_changed.emit()
        print("PM: update_entire_song is deprecated/needs refactor. Use section-specific methods.")
    
    def set_slide_template_settings(self, slide_index: int, new_template_settings: Dict[str, Any], _suppress_signal: bool = False):
        """
        DEPRECATED/REFACTOR: Operates on flat list.
        New: `update_slide_block_in_section` should handle template changes within a slide_block.
        """
        if 0 <= slide_index < len(self.get_slides()): # Use get_slides() for dynamic list
            self.is_dirty = True # Always mark dirty
            if _suppress_signal:
                # This command will trigger a specific UI update
                self.slide_visual_property_changed.emit([slide_index])
            else: # Default behavior, emit general change
                self.presentation_changed.emit()
        else:
            self.error_occurred.emit(f"Cannot set template for slide: Index {slide_index} out of bounds.")
        print("PM: set_slide_template_settings is deprecated/needs refactor.")

    def set_slide_banner_color(self, slide_index: int, color: Optional[QColor], _suppress_signal: bool = False):
        """
        Sets the banner color for a slide. The color is stored in the
        slide_block data as 'ui_banner_color'.

        If color is None, resets to the default color.
        _suppress_signal: If True, indicates a batch update, and update_slide_block_in_section
                          will handle emitting slide_visual_property_changed without a full
                          presentation_changed signal from its own _execute_command logic.
        """
        all_slides = self.get_slides()
        if not (0 <= slide_index < len(all_slides)):
            self.error_occurred.emit(f"Cannot set banner color: Index {slide_index} out of bounds.")
            return

        slide_data_instance = all_slides[slide_index]
        section_id = slide_data_instance.section_id_in_manifest
        block_id = slide_data_instance.slide_block_id

        if section_id is None or block_id is None:
            self.error_occurred.emit(f"Cannot set banner color: Slide at index {slide_index} has missing section or block ID.")
            return

        # Store color as hex string (e.g., "#RRGGBBAA" or "#RRGGBB")
        # If color is provided but invalid (e.g. default QColor()), treat as None
        color_hex = None
        if color and color.isValid():
            color_hex = color.name(QColor.HexArgb)

        # _execute_command for update_slide_block_in_section should be True for single updates (emit presentation_changed)
        # and False for batch updates (rely on slide_visual_property_changed).
        self.update_slide_block_in_section(section_id, block_id, {"ui_banner_color": color_hex}, _execute_command=not _suppress_signal)

    # Each modification should set self.is_dirty = True and emit presentation_changed

    def get_slides(self) -> List[SlideData]:
        """
        Dynamically generates a flat list of SlideData objects from the loaded
        presentation manifest and section data.
        """
        flat_slides_list: List[SlideData] = []
        self._instance_id_to_arrangement_info_map.clear() # Clear map before rebuilding
        # This map helps commands find the exact location of a slide instance
        # Example entry: {"instance_slide_id_xyz": {"section_id_in_manifest": "pres_sec_abc", "slide_block_id": "slide_123", "arrangement_name": "Default", "index_in_arrangement": 0}}

        if not self.presentation_manifest_data or not self.loaded_sections:
            return flat_slides_list # No presentation loaded or no sections

        manifest_sections = self.presentation_manifest_data.get("sections", [])

        for section_manifest_entry in manifest_sections:
            section_id_in_manifest = section_manifest_entry.get("id")
            if not section_id_in_manifest or section_id_in_manifest not in self.loaded_sections:
                print(f"PM: Warning - Section ID '{section_id_in_manifest}' from manifest not found in loaded_sections. Skipping.")
                continue

            loaded_section_wrapper = self.loaded_sections[section_id_in_manifest]
            section_content_data = loaded_section_wrapper.get("section_content_data")
            if not section_content_data:
                print(f"PM: Warning - No content_data for section '{section_id_in_manifest}'. Skipping.")
                continue

            section_title = section_content_data.get("title")
            slide_blocks_map = {sb["slide_id"]: sb for sb in section_content_data.get("slide_blocks", []) if "slide_id" in sb}
            arrangements_map = section_content_data.get("arrangements", {})

            active_arrangement_name = section_manifest_entry.get("active_arrangement_name")
            current_arrangement_slides = []

            if active_arrangement_name and active_arrangement_name in arrangements_map:
                current_arrangement_slides = arrangements_map[active_arrangement_name]
            elif arrangements_map: # Fallback to the first arrangement if active_arrangement_name is not specified or not found
                first_arrangement_name = next(iter(arrangements_map), None)
                if first_arrangement_name:
                    current_arrangement_slides = arrangements_map[first_arrangement_name]
                    print(f"PM: Warning - Active arrangement '{active_arrangement_name}' not found for section '{section_title}'. Using first available: '{first_arrangement_name}'.")
                else: # No arrangements defined in the section
                    print(f"PM: Warning - No arrangements defined for section '{section_title}'. Skipping slide generation for this section.")
                    continue
            else: # No arrangements defined
                print(f"PM: Warning - No arrangements defined for section '{section_title}'. Skipping slide generation for this section.")
                continue

            for arr_item_idx, arrangement_item in enumerate(current_arrangement_slides):
                slide_id_ref = arrangement_item.get("slide_id_ref")
                if not slide_id_ref or slide_id_ref not in slide_blocks_map:
                    print(f"PM: Warning - slide_id_ref '{slide_id_ref}' in arrangement for section '{section_title}' not found in slide_blocks. Skipping.")
                    continue

                slide_block_data = slide_blocks_map[slide_id_ref]
                
                # Resolve the template settings using TemplateManager
                # This will return the layout structure, including text box definitions.
                resolved_template_settings_from_tm = self.template_manager.resolve_slide_template_for_block(
                    slide_block_data,
                    section_content_data # Pass full section data for context if needed by TM
                )

                # Ensure resolved_template_settings_from_tm is a dictionary
                if resolved_template_settings_from_tm is None:
                    resolved_template_settings_from_tm = {} # Default to empty if resolution failed

                # The actual text content comes from slide_block_data["content"]
                # This content should already be mapped to the correct text box IDs
                # by EditLyricsCommand or ApplyTemplateCommand.
                block_content_source = slide_block_data.get('content', {}) # No copy needed here, just reading
                final_text_content_for_slidedata = {} # This will be populated

                if resolved_template_settings_from_tm and "text_boxes" in resolved_template_settings_from_tm:
                    for tb_def in resolved_template_settings_from_tm["text_boxes"]:
                        tb_id_from_template = tb_def.get("id")
                        if tb_id_from_template:
                            # Prioritize content directly matching the template's text box ID
                            if tb_id_from_template in block_content_source:
                                final_text_content_for_slidedata[tb_id_from_template] = block_content_source[tb_id_from_template]
                            # Fallback for "System Default Fallback" if its box is "main_text_fallback"
                            # and the source content has "main_text" (e.g., from initial section creation)
                            elif tb_id_from_template == "main_text_fallback" and "main_text" in block_content_source:
                                final_text_content_for_slidedata["main_text_fallback"] = block_content_source["main_text"]
                            else:
                                final_text_content_for_slidedata[tb_id_from_template] = "" # Default to empty if no match
                elif isinstance(block_content_source, dict): # No template text boxes, but content is a dict
                    final_text_content_for_slidedata = block_content_source.copy()
                elif isinstance(block_content_source, str): # Legacy string content, no template
                    # This case is less likely now with System Default Fallback, but as a safety
                    if resolved_template_settings_from_tm and resolved_template_settings_from_tm.get("text_boxes"):
                        for tb_def in resolved_template_settings_from_tm["text_boxes"]:
                            # Try to put legacy string into the first text box
                            first_tb_id = tb_def.get("id")
                            if first_tb_id:
                                final_text_content_for_slidedata[first_tb_id] = block_content_source
                                break
                resolved_template_settings_from_tm["text_content"] = final_text_content_for_slidedata

                # The 'lyrics' field in SlideData is somewhat legacy.
                # For consistency, we can try to populate it from the 'text_content'
                # if a primary text box is identifiable, or leave it based on 'main_text' if present.
                lyrics = final_text_content_for_slidedata.get('main_text', '') # Use the mapped content
                if not lyrics and final_text_content_for_slidedata: # If main_text not found, try first text box from mapped content
                    lyrics = next(iter(final_text_content_for_slidedata.values()), '')

                overlay_label = slide_block_data.get('label', '') # This could be the song part (Verse 1, Chorus)
                background_source = slide_block_data.get('background_source')
                bg_image_path = background_source if background_source and not background_source.startswith('#') else None
                bg_color = background_source if background_source and background_source.startswith('#') else None
                notes = slide_block_data.get('notes')
                is_enabled = arrangement_item.get('enabled', True)
                
                banner_color_hex = slide_block_data.get('ui_banner_color')
                banner_qcolor = QColor(banner_color_hex) if banner_color_hex else None

                # Determine if this slide block should be treated as a background-setter
                is_background_setter_slide = False
                has_defined_background = bool(bg_image_path or (bg_color and bg_color.lower() != "#00000000"))

                # A slide is a background setter if it has a defined background AND
                # its own specific text content (final_text_content_for_slidedata) is empty or whitespace only.
                # This means even if its template *could* show text, this particular slide instance doesn't use it for main content.
                actual_content_is_empty = not final_text_content_for_slidedata or \
                                   all(not text_val or not str(text_val).strip() for text_val in final_text_content_for_slidedata.values())

                if has_defined_background and actual_content_is_empty:
                    is_background_setter_slide = True

                # Create a unique ID for this instance of the slide in the presentation
                # This helps distinguish if the same slide_block is used multiple times.
                # Removed UUID to make instance_id deterministic based on structure for stable drag-drop.
                instance_slide_id = f"{section_id_in_manifest}_{slide_id_ref}_{arr_item_idx}"

                # --- DEBUG PRINTS for get_slides ---
                # print(f"DEBUG_PM_GET_SLIDES: For slide_block_id '{slide_block_data.get('slide_id')}', template_id '{slide_block_data.get('template_id')}'")
                # print(f"  slide_block_data['content'] (source for text): {slide_block_data.get('content')}")
                # print(f"  resolved_template_settings_from_tm['text_boxes'] (structure): {resolved_template_settings_from_tm.get('text_boxes')}")
                # print(f"  resolved_template_settings_from_tm['text_content'] (merged text): {resolved_template_settings_from_tm.get('text_content')}")
                # sys.stdout.flush()
                # --- END DEBUG PRINTS ---

                slide_data_obj = SlideData(
                    id=instance_slide_id, # Unique ID for this instance in the flattened list
                    lyrics=lyrics,
                    song_title=section_title,
                    overlay_label=overlay_label, # This is the slide's label (e.g., "Verse 1")
                    # Pass the fully resolved settings, which now includes the text_content
                    template_settings=resolved_template_settings_from_tm,
                    background_image_path=bg_image_path,
                    background_color=bg_color,
                    notes=notes,
                    is_enabled_in_arrangement=is_enabled,
                    banner_color=banner_qcolor, # Pass the loaded banner color
                    # New fields:
                    section_id_in_manifest=section_id_in_manifest, # ID of section in manifest
                    slide_block_id=slide_id_ref,                   # ID of the slide_block in the section file                    
                    is_background_slide=is_background_setter_slide, # Set based on heuristic
                    active_arrangement_name_for_section=active_arrangement_name # The arrangement name being used
                )
                flat_slides_list.append(slide_data_obj)

                # Populate the instance ID map
                self._instance_id_to_arrangement_info_map[instance_slide_id] = {
                    "section_id_in_manifest": section_id_in_manifest,
                    "slide_block_id": slide_id_ref, # This is the ID of the slide_block
                    "arrangement_name": active_arrangement_name,
                    "index_in_arrangement": arr_item_idx
                }

        return flat_slides_list

    def save_presentation_as(self, new_manifest_filepath: str) -> bool:
        """
        Saves the current presentation to a new manifest file.
        Sections not already in the central store are copied there,
        and manifest paths are updated to reference the central store.
        """
        if not self.presentation_manifest_data:
            self.error_occurred.emit("Cannot 'Save As': No presentation data loaded.")
            return False

        original_manifest_filepath = self.current_manifest_filepath
        self.current_manifest_filepath = new_manifest_filepath # Update to the new path

        # Update presentation_title in manifest data based on the new filename
        new_title_from_filename = os.path.splitext(os.path.basename(new_manifest_filepath))[0]
        self.presentation_manifest_data["presentation_title"] = new_title_from_filename

        # Ensure PluckyStandards is available
        if TYPE_CHECKING: from core.plucky_standards import PluckyStandards # type: ignore
        else: from core.plucky_standards import PluckyStandards

        central_sections_dir = PluckyStandards.get_sections_dir()

        for section_entry in self.presentation_manifest_data.get("sections", []):
            section_id_in_manifest = section_entry.get("id")
            if not section_id_in_manifest or section_id_in_manifest not in self.loaded_sections:
                continue

            section_wrapper = self.loaded_sections[section_id_in_manifest]
            current_abs_section_path = section_wrapper.get("resolved_filepath")
            section_content_data = section_wrapper.get("section_content_data")

            if not current_abs_section_path or not section_content_data:
                print(f"PM: Warning (Save As) - Skipping section '{section_id_in_manifest}', missing path or content.")
                continue

            section_filename = os.path.basename(current_abs_section_path)
            target_central_store_path = os.path.join(central_sections_dir, section_filename)

            # Normalize paths for reliable comparison
            if os.path.normpath(current_abs_section_path) != os.path.normpath(target_central_store_path):
                print(f"PM: (Save As) Copying section '{section_filename}' from '{current_abs_section_path}' to central store '{target_central_store_path}'")
                PluckyStandards.ensure_directory_exists(central_sections_dir) # Ensure central sections dir exists
                shutil.copy2(current_abs_section_path, target_central_store_path)
                section_wrapper["resolved_filepath"] = target_central_store_path # Update resolved path
                section_wrapper["is_dirty"] = True # Mark as dirty to save to new central location
            
            # Update path in manifest to be simple filename (implies central store)
            section_entry["path"] = section_filename
        
        self.presentation_manifest_is_dirty = True # Manifest paths have changed
        return self.save_presentation() # Call the regular save to handle saving manifest and dirty sections

    def save_presentation(self, filepath: Optional[str] = None) -> bool:
        """
        Saves the current presentation.
        If filepath is provided, it becomes the new current_manifest_filepath.
        Saves the manifest file if dirty, and any dirty section files.
        """
        if filepath:
            self.current_manifest_filepath = filepath

        if not self.current_manifest_filepath:
            self.error_occurred.emit("Cannot save: No file path specified.")
            return False

        try:
            # 1. Save the presentation manifest file if it's dirty
            if self.presentation_manifest_data and self.presentation_manifest_is_dirty:
                print(f"PM: Saving presentation manifest to {self.current_manifest_filepath}")
                self.io_handler.save_json_file(self.presentation_manifest_data, self.current_manifest_filepath)
                self.presentation_manifest_is_dirty = False

            # 2. Iterate through loaded sections and save any that are dirty
            for section_id_in_manifest, section_wrapper in self.loaded_sections.items():
                if section_wrapper.get("is_dirty"):
                    section_content_data = section_wrapper.get("section_content_data")
                    section_resolved_filepath = section_wrapper.get("resolved_filepath")

                    if section_content_data and section_resolved_filepath:
                        print(f"PM: Saving dirty section '{section_id_in_manifest}' to {section_resolved_filepath}")
                        self.io_handler.save_json_file(section_content_data, section_resolved_filepath)
                        section_wrapper["is_dirty"] = False
                    else:
                        print(f"PM: Warning - Cannot save section '{section_id_in_manifest}', missing content or resolved path.")

            self.undo_stack.clear() # Clear undo/redo history on successful save
            self.redo_stack.clear()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to save presentation: {e}")
            return False

    def load_presentation(self, filepath: str) -> bool:
        """
        Loads a presentation from a manifest file (*.plucky_pres).
        Reads the manifest, then loads each referenced section file.
        """
        try:
            # 1. Clear existing presentation data
            self.clear_presentation() # Use the existing clear method

            # 2. Read and parse the presentation manifest JSON
            print(f"PM: Loading presentation manifest from {filepath}")
            manifest_data = self.io_handler.load_json_file(filepath)
            if not isinstance(manifest_data, dict):
                 raise ValueError("Manifest file does not contain a valid JSON object.")
            if "sections" not in manifest_data or not isinstance(manifest_data["sections"], list):
                 raise ValueError("Manifest file is missing the 'sections' array.")

            # Store manifest data and path
            self.presentation_manifest_data = manifest_data
            self.current_manifest_filepath = filepath
            self.presentation_manifest_is_dirty = False
            manifest_dir = os.path.dirname(filepath)
            
            # 3. Iterate through sections and load each one
            for i, section_entry in enumerate(self.presentation_manifest_data.get("sections", [])):
                if not isinstance(section_entry, dict) or "id" not in section_entry or "path" not in section_entry:
                    print(f"PM: Warning - Skipping invalid section entry at index {i} in manifest: {section_entry}")
                    continue # Skip invalid entries

                section_id_in_manifest = section_entry["id"]
                section_relative_or_simple_path = section_entry["path"]
                
                # Resolve the absolute path to the section file
                section_abs_filepath = self._resolve_section_filepath(manifest_dir, section_relative_or_simple_path)

                if section_abs_filepath is None:
                    self.error_occurred.emit(f"Section file not found for path: {section_relative_or_simple_path} (referenced in manifest {filepath})")
                    print(f"PM: Error - Section file not found for path: {section_relative_or_simple_path}")
                    # TODO: Handle missing sections more gracefully in the UI (e.g., placeholder)
                    continue # Skip loading this section

                try:
                    print(f"PM: Loading section file from {section_abs_filepath}")
                    section_content_data = self.io_handler.load_json_file(section_abs_filepath)
                    if not isinstance(section_content_data, dict):
                         raise ValueError("Section file does not contain a valid JSON object.")

                    # Store the loaded section data
                    self.loaded_sections[section_id_in_manifest] = {
                        "manifest_entry_data": section_entry,
                        "section_content_data": section_content_data,
                        "is_dirty": False, # Newly loaded sections are not dirty
                        "resolved_filepath": section_abs_filepath # Store the resolved absolute path
                    }
                except Exception as e:
                    self.error_occurred.emit(f"Failed to load section file {section_abs_filepath}: {e}")
                    print(f"PM: Error loading section file {section_abs_filepath}: {e}")
                    # TODO: Handle corrupt sections more gracefully
                    continue # Skip loading this section
            self.undo_stack.clear() # Clear undo/redo history on successful load
            self.redo_stack.clear()
            self.presentation_changed.emit() # Emit signal AFTER successful loading of manifest and all sections
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to load presentation: {e}")
            return False
    
    def _resolve_section_filepath(self, manifest_dir: str, section_path: str) -> Optional[str]:
        """
        Resolves the absolute path for a section file based on the path stored in the manifest.
        Checks relative to manifest, then in the central sections store, then as absolute.
        Returns the absolute path if found, otherwise None.
        """
        # 1. Check if the path is already absolute
        if os.path.isabs(section_path):
            if os.path.exists(section_path):
                return section_path

        # 2. Check relative to the manifest file's directory
        relative_path = os.path.join(manifest_dir, section_path)
        if os.path.exists(relative_path):
            return os.path.abspath(relative_path) # Return absolute path

        # 3. Check relative to the central sections store
        central_store_path = os.path.join(PluckyStandards.get_sections_dir(), section_path)
        if os.path.exists(central_store_path):
            return os.path.abspath(central_store_path) # Return absolute path

        # Path not found in any standard location
        return None

    def do_command(self, command: 'Command'):
        """Executes a command and adds it to the undo stack."""
        try:
            command.execute()
            self.undo_stack.append(command)
            self.redo_stack.clear() # New action clears redo history
            self.presentation_manifest_is_dirty = True # Or section specific

            # Determine if the generic presentation_changed signal should be emitted.
            # If a command handles its own specific UI update (e.g., via slide_visual_property_changed),
            # we don't want to also trigger a full UI rebuild from here.
            commands_with_specific_updates = (
                ApplyTemplateCommand,
                ChangeOverlayLabelCommand,
                # EditLyricsCommand # Add EditLyricsCommand here once it's also optimized
                EditLyricsCommand
            )
            if isinstance(command, commands_with_specific_updates):
                # These commands are expected to trigger slide_visual_property_changed
                # through their execution path (e.g., by calling a PM method with _suppress_signal=True).
                # So, do_command itself should not emit presentation_changed for these.
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
        self.presentation_manifest_is_dirty = True # Or section specific
        self.presentation_changed.emit()
        print(f"PM: Undid command {command.__class__.__name__}. Redo stack size: {len(self.redo_stack)}")

    def redo(self):
        if not self.redo_stack:
            print("PM: Redo stack empty.")
            return
        command = self.redo_stack.pop()
        command.execute() # Or command.redo() if it has specific redo logic
        self.undo_stack.append(command)
        self.presentation_manifest_is_dirty = True # Or section specific
        self.presentation_changed.emit()
        print(f"PM: Redid command {command.__class__.__name__}. Undo stack size: {len(self.undo_stack)}")
    
    def move_slide(self, source_index: int, target_index: int, new_song_title: Optional[str], _execute_command: bool = True) -> bool:
        """
        Moves a slide from a source index to a target index.
        The target_index is the index *before* the source slide is removed if source_index < target_index,
        or the direct index if source_index > target_index.
        The SlideDragDropHandler should pass the 'actual_target_index' here.
        The new_song_title will be applied to the moved slide. If None, the slide becomes untitled
        or retains its current title if the logic in the caller doesn't provide a new one.
        """
        print("PM: move_slide needs complete refactor for new structure (manifest reorder or slide reorder within section arrangement).")
        # num_slides = len(self.slides)
        # if not (0 <= source_index < num_slides):
        #     self.error_occurred.emit(f"Error moving slide: Invalid source index ({source_index}).")
        #     return False
        # target_index is the final insertion point in the list *after* the pop.
        # It can range from 0 to num_slides - 1 (if num_slides > 0).
        # If num_slides is 0, this method shouldn't be callable with valid source_index.
        # if not (0 <= target_index < num_slides if num_slides > 0 else target_index == 0):
        #      self.error_occurred.emit(f"Error moving slide: Invalid target index ({target_index}) for {num_slides} slides.")
        #      return False

        if _execute_command:
            # This would set self.presentation_manifest_is_dirty = True if reordering sections in manifest,
            # or self.loaded_sections[section_id]["is_dirty"] = True if reordering slides within a section's arrangement.
            self.presentation_manifest_is_dirty = True # Placeholder
            self.presentation_changed.emit()
        return True

    def clear_presentation(self):
        """Clears all slides and resets the presentation to a new, empty state."""
        self.presentation_manifest_data = None
        self.loaded_sections.clear()
        self.current_manifest_filepath = None
        self.presentation_manifest_is_dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.presentation_changed.emit()

    # --- New Modification Methods (Stubs for Phase 2, Step 3) ---

    def add_section_to_presentation(self, section_filepath: str, insert_at_index: int, desired_arrangement_name: Optional[str] = None, _execute_command: bool = True) -> bool:
        """
        Adds a section (from a *.plucky_section file) to the current presentation manifest.
        - section_filepath: Path to the section file (absolute or relative to central store).
        - insert_at_index: Index where to insert in the presentation's list of sections.
        - desired_arrangement_name: Which arrangement from the section file to use.
        Returns True if successful, False otherwise.
        """
        print(f"PM: add_section_to_presentation(filename='{section_filepath}', index={insert_at_index}, arr='{desired_arrangement_name}')")

        # 1. Initialize manifest_data if it's a brand new (empty) presentation
        if self.presentation_manifest_data is None:
            self.presentation_manifest_data = {
                "version": "1.0.0",
                "presentation_title": "Untitled Presentation", # Default title for new presentations
                "sections": []
            }
            # self.current_manifest_filepath remains None until first save/save_as
            self.presentation_manifest_is_dirty = True # New presentation is inherently dirty until saved

        # Ensure PluckyStandards is available for path resolution
        if TYPE_CHECKING: from core.plucky_standards import PluckyStandards # type: ignore
        else: from core.plucky_standards import PluckyStandards

        # 2. Resolve section_filepath (assuming it's a simple filename in central store)
        #    and load its content.
        full_resolved_path = os.path.join(PluckyStandards.get_sections_dir(), section_filepath)
        
        try:
            section_content_data = self.io_handler.load_json_file(full_resolved_path)
            if not isinstance(section_content_data, dict):
                raise ValueError("Section file does not contain a valid JSON object.")
        except Exception as e:
            self.error_occurred.emit(f"Failed to load section file '{section_filepath}': {e}")
            return False

        # 3. Create a new unique ID for this section's instance in the manifest
        manifest_section_id = f"pres_sec_{uuid.uuid4().hex}"

        # 4. Create the new section entry for the manifest
        manifest_entry = {
            "id": manifest_section_id,
            "path": section_filepath, # Store the simple filename, implying central store
            "active_arrangement_name": desired_arrangement_name or section_content_data.get("arrangements", {}).get("Default") or next(iter(section_content_data.get("arrangements", {})), "Default")
        }

        # 5. Insert into self.presentation_manifest_data['sections']
        self.presentation_manifest_data.setdefault("sections", []).insert(insert_at_index, manifest_entry)

        # 6. Add to self.loaded_sections
        self.loaded_sections[manifest_section_id] = {
            "manifest_entry_data": manifest_entry,
            "section_content_data": section_content_data,
            "is_dirty": False, # Not dirty as it was just loaded/created
            "resolved_filepath": full_resolved_path
        }

        if _execute_command:
            self.presentation_manifest_is_dirty = True
            self.presentation_changed.emit()
        return True

    def remove_section_from_presentation(self, section_id_in_manifest: str, _execute_command: bool = True) -> bool:
        """Removes a section reference from the presentation manifest."""
        print(f"PM STUB: remove_section_from_presentation(id='{section_id_in_manifest}')")
        # 1. Find and remove the entry from self.presentation_manifest_data['sections'] by id.
        # 2. Optionally, consider if the section_content_data in self.loaded_sections should be removed
        #    if no other manifest entry refers to its file (complex to track, maybe leave for now).
        if _execute_command:
            self.presentation_manifest_is_dirty = True
            self.presentation_changed.emit()
        return True # Placeholder

    def reorder_sections_in_manifest(self, section_id_in_manifest: str, new_index: int, _execute_command: bool = True) -> bool:
        """Reorders a section within the presentation manifest."""
        if not self.presentation_manifest_data or "sections" not in self.presentation_manifest_data:
            self.error_occurred.emit("Cannot reorder section: Presentation manifest data is missing or invalid.")
            return False

        manifest_sections = self.presentation_manifest_data["sections"]
        current_index = -1
        section_to_move = None

        for i, sec_entry in enumerate(manifest_sections):
            if sec_entry.get("id") == section_id_in_manifest:
                current_index = i
                section_to_move = sec_entry
                break

        if section_to_move is None:
            self.error_occurred.emit(f"Cannot reorder section: Section ID '{section_id_in_manifest}' not found in manifest.")
            return False

        # Remove the section from its current position and insert it at the new index
        manifest_sections.pop(current_index)
        manifest_sections.insert(new_index, section_to_move)
        print(f"PM: Reordered section '{section_id_in_manifest}' to new index {new_index}.")

        if _execute_command:
            self.presentation_manifest_is_dirty = True
            self.presentation_changed.emit()
        return True # Placeholder

    def set_active_arrangement_for_section_in_presentation(self, section_id_in_manifest: str, arrangement_name: str, _execute_command: bool = True) -> bool:
        """Sets the active arrangement for a section instance in the presentation manifest."""
        print(f"PM STUB: set_active_arrangement_for_section_in_presentation(id='{section_id_in_manifest}', arr='{arrangement_name}')")
        # 1. Find the section entry in self.presentation_manifest_data['sections'].
        # 2. Update its 'active_arrangement_name' field.
        # 3. Validate that arrangement_name exists in the loaded section's content.
        if _execute_command:
            self.presentation_manifest_is_dirty = True
            self.presentation_changed.emit() # UI needs to re-render slides for this section
        return True # Placeholder
    
    # --- Helper method to map instance ID back to section/arrangement info ---
    def _get_arrangement_info_from_instance_id(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Looks up section/arrangement info using the unique slide instance ID."""
        # Ensure get_slides() has been called recently enough for the map to be valid.
        # This map is rebuilt every time get_slides() is called.
        return self._instance_id_to_arrangement_info_map.get(instance_id)

    def add_slide_block_to_section(self, section_id_in_manifest: str, new_slide_block_data: Dict[str, Any], arrangement_name: str, at_index_in_arrangement: Optional[int] = None, _execute_command: bool = True) -> bool:
        """
        Adds a new slide_block to a section and a reference to it in one of its arrangements.
        - new_slide_block_data: The dict for the new slide_block (must include a unique 'slide_id' for that section).
        """
        print(f"PM: add_slide_block_to_section(section_id='{section_id_in_manifest}', arr='{arrangement_name}', index={at_index_in_arrangement})")

        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper:
            self.error_occurred.emit(f"Section '{section_id_in_manifest}' or its content not found for adding slide block.")
            return False

        section_content = section_wrapper["section_content_data"]
        
        # 1. Add new_slide_block_data to slide_blocks list
        slide_blocks_list = section_content.setdefault("slide_blocks", [])
        # Ensure slide_id is unique within this section
        new_block_id = new_slide_block_data.get("slide_id")
        if not new_block_id:
            self.error_occurred.emit("New slide block data is missing 'slide_id'.")
            return False
        if any(sb.get("slide_id") == new_block_id for sb in slide_blocks_list):
            self.error_occurred.emit(f"Slide block ID '{new_block_id}' already exists in section '{section_id_in_manifest}'.")
            # Potentially auto-generate a new one if this happens, or let command handle it.
            return False
        slide_blocks_list.append(new_slide_block_data)

        # 2. Add reference to the specified arrangement
        arrangements = section_content.setdefault("arrangements", {})
        arrangement_list = arrangements.setdefault(arrangement_name, [])
        
        arrangement_item_to_add = {"slide_id_ref": new_block_id, "enabled": True}

        if at_index_in_arrangement is None or at_index_in_arrangement >= len(arrangement_list):
            arrangement_list.append(arrangement_item_to_add)
        else:
            arrangement_list.insert(at_index_in_arrangement, arrangement_item_to_add)

        section_wrapper["is_dirty"] = True
        if _execute_command:
            self.presentation_changed.emit()
        # Rebuild instance map as structure changed
        self.get_slides()
        return True

    def update_slide_block_in_section(self, section_id_in_manifest: str, slide_block_id: str, updated_fields: Dict[str, Any], _execute_command: bool = True) -> bool:
        """Updates an existing slide_block within a section."""
        print(f"PM: update_slide_block_in_section(section_id='{section_id_in_manifest}', slide_block_id='{slide_block_id}', fields_to_update={list(updated_fields.keys())})")
        
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper:
            self.error_occurred.emit(f"Section '{section_id_in_manifest}' not found for updating slide block.")
            return False

        section_content = section_wrapper["section_content_data"]
        slide_blocks = section_content.get("slide_blocks", [])
        
        block_found_and_updated = False
        for i, block in enumerate(slide_blocks):
            if block.get("slide_id") == slide_block_id:
                # Update specified fields
                for key, value in updated_fields.items():
                    block[key] = value # Directly update the block's dictionary
                # slide_blocks[i] = block # Not strictly necessary as block is a mutable dict, but good for clarity if block was copied
                block_found_and_updated = True
                print(f"  Updated block '{slide_block_id}' in section '{section_id_in_manifest}'.")
                break
        
        if not block_found_and_updated:
            self.error_occurred.emit(f"Slide block '{slide_block_id}' not found in section '{section_id_in_manifest}'.")
            return False

        section_wrapper["is_dirty"] = True
        
        # Always attempt to emit the specific signal if visual properties were updated.
        affected_global_indices = []
        # Get the current slide list to map block_id to global indices.
        # Calling get_slides() here also ensures the instance_id map is up-to-date
        # and SlideData objects will reflect the change we just made to slide_block_data.
        all_current_slides = self.get_slides() 

        for global_idx, slide_data_instance in enumerate(all_current_slides):
            if slide_data_instance.section_id_in_manifest == section_id_in_manifest and \
               slide_data_instance.slide_block_id == slide_block_id:
                affected_global_indices.append(global_idx)
        
        if affected_global_indices:
            print(f"PM: Emitting slide_visual_property_changed for indices: {affected_global_indices} (update_slide_block)")
            self.slide_visual_property_changed.emit(affected_global_indices)
        
        # If _execute_command is true, it means this change was a direct modification
        # that should update the overall presentation state (like dirty status).
        if _execute_command:
            self.presentation_manifest_is_dirty = self.is_overall_dirty() # Ensure top-level dirty flag reflects section changes
            print(f"PM: update_slide_block_in_section with _execute_command=True. Emitting presentation_changed. Overall dirty: {self.presentation_manifest_is_dirty}")
            self.presentation_changed.emit()
        return True

    def delete_slide_reference_from_arrangement(self, instance_slide_id: str, _execute_command: bool = True) -> Optional[tuple[Dict[str, Any], int, str, str]]:
        """
        Removes a specific slide instance from its arrangement using its unique instance_slide_id.
        Returns the deleted arrangement item and its original index if successful, otherwise None.
        This method is called by a Command's execute().
        """
        print(f"PM: delete_slide_reference_from_arrangement(instance_slide_id='{instance_slide_id}')")

        arrangement_info = self._get_arrangement_info_from_instance_id(instance_slide_id)
        if not arrangement_info:
            self.error_occurred.emit(f"Could not find slide instance '{instance_slide_id}' for deletion.")
            return None

        section_id_in_manifest = arrangement_info["section_id_in_manifest"]
        arrangement_name = arrangement_info["arrangement_name"]
        index_in_arrangement = arrangement_info["index_in_arrangement"]
        
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper:
            self.error_occurred.emit(f"Section '{section_id_in_manifest}' (from instance map) not found.")
            return None

        section_content_data = section_wrapper.get("section_content_data")
        if not section_content_data:
            self.error_occurred.emit(f"No content data for section '{section_id_in_manifest}'.")
            return None

        arrangements = section_content_data.get("arrangements")
        if not arrangements or arrangement_name not in arrangements:
            self.error_occurred.emit(f"Arrangement '{arrangement_name}' not found in section '{section_id_in_manifest}'.")
            return None

        arrangement_list: List[Dict[str, Any]] = arrangements[arrangement_name]

        if 0 <= index_in_arrangement < len(arrangement_list):
            deleted_item = arrangement_list.pop(index_in_arrangement)
            section_wrapper["is_dirty"] = True
            if _execute_command: # Typically true when called from a command's execute
                self.presentation_changed.emit()
            # Rebuild the map as indices have shifted
            self.get_slides() # This rebuilds the map
            return deleted_item, index_in_arrangement, section_id_in_manifest, arrangement_name
        else:
            self.error_occurred.emit(f"Invalid index '{index_in_arrangement}' for arrangement '{arrangement_name}' in section '{section_id_in_manifest}'.")
            return None

    def insert_slide_reference_into_arrangement(self, section_id_in_manifest: str, arrangement_name: str, arrangement_item: Dict[str, Any], index_in_arrangement: int, _execute_command: bool = True) -> bool:
        """
        Inserts a slide_block reference back into a specific arrangement.
        This method is called by a Command's undo().
        """
        print(f"PM: insert_slide_reference_into_arrangement(section_id='{section_id_in_manifest}', arr='{arrangement_name}', item={arrangement_item}, index={index_in_arrangement})")
        
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper:
            self.error_occurred.emit(f"Section '{section_id_in_manifest}' or its content not found for insert.")
            return False
        
        arrangements = section_wrapper["section_content_data"].get("arrangements")
        if not arrangements or arrangement_name not in arrangements:
            self.error_occurred.emit(f"Arrangement '{arrangement_name}' not found in section '{section_id_in_manifest}' for insert.")
            return False
            
        arrangement_list: List[Dict[str, Any]] = arrangements[arrangement_name]
        arrangement_list.insert(index_in_arrangement, arrangement_item)
        
        section_wrapper["is_dirty"] = True
        if _execute_command: # Typically true when called from a command's undo
            self.presentation_changed.emit()
        return True # Placeholder

    def delete_slide_reference_from_arrangement_by_block_id(self, section_id_in_manifest: str, arrangement_name: str, slide_block_id: str, _execute_command: bool = True) -> bool:
        """
        Helper for undoing AddSlideBlockToSectionCommand. Removes the last added reference
        to a slide_block_id from an arrangement.
        Also removes the slide_block itself if it's no longer referenced in any arrangement.
        This is a simplified version for undo. A full delete operation would be more complex.
        """
        print(f"PM: delete_slide_reference_from_arrangement_by_block_id for undo (section='{section_id_in_manifest}', arr='{arrangement_name}', block_id='{slide_block_id}')")
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper: return False
        section_content = section_wrapper["section_content_data"]
        arrangements = section_content.get("arrangements", {})
        arrangement_list = arrangements.get(arrangement_name)

        if arrangement_list:
            # Find and remove the last occurrence of the slide_block_id reference
            # This assumes the 'add' command added it to the end or a specific known index.
            # For a more robust undo, the command should store the exact index.
            for i in range(len(arrangement_list) - 1, -1, -1):
                if arrangement_list[i].get("slide_id_ref") == slide_block_id:
                    arrangement_list.pop(i)
                    break # Remove only one instance (the one that was added)

        # Remove the slide_block itself (assuming it was newly added and only referenced once)
        slide_blocks_list = section_content.get("slide_blocks", [])
        section_content["slide_blocks"] = [sb for sb in slide_blocks_list if sb.get("slide_id") != slide_block_id]

        section_wrapper["is_dirty"] = True
        if _execute_command: self.presentation_changed.emit()
        self.get_slides() # Rebuild map
        return True

    def modify_arrangement_in_section(self, section_id_in_manifest: str, arrangement_name: str, new_arrangement_list: List[Dict[str, Any]], _execute_command: bool = True) -> bool:
        """Replaces an entire arrangement list for a given arrangement name within a section."""
        print(f"PM STUB: modify_arrangement_in_section(section_id='{section_id_in_manifest}', arr_name='{arrangement_name}')")
        # 1. Get section_wrapper.
        # 2. Update section_wrapper['section_content_data']['arrangements'][arrangement_name] = new_arrangement_list.
        #    (Handle creation if arrangement_name is new).
        if _execute_command:
            if section_id_in_manifest in self.loaded_sections:
                self.loaded_sections[section_id_in_manifest]["is_dirty"] = True
            self.presentation_changed.emit()
        return True # Placeholder

    def is_overall_dirty(self) -> bool:
        """Checks if the manifest or any loaded section is dirty."""
        if self.presentation_manifest_is_dirty:
            return True
        for section_wrapper in self.loaded_sections.values():
            if section_wrapper.get("is_dirty", False):
                return True
        return False

    def get_presentation_title(self) -> Optional[str]:
        """Returns the title of the currently loaded presentation manifest."""
        if self.presentation_manifest_data:
            return self.presentation_manifest_data.get("presentation_title")
        return None

    # --- Helper Methods for Slide Block Data Management within Sections ---

    def _get_slide_block_data(self, section_id_in_manifest: str, slide_block_id: str) -> Optional[Dict[str, Any]]:
        """Helper to retrieve a specific slide_block_data from a loaded section."""
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if section_wrapper and "section_content_data" in section_wrapper:
            slide_blocks = section_wrapper["section_content_data"].get("slide_blocks", [])
            for block in slide_blocks:
                if block.get("slide_id") == slide_block_id:
                    return block
        return None

    def _add_slide_block_to_section_data_only(self, section_id_in_manifest: str, slide_block_data_to_add: Dict[str, Any]) -> bool:
        """
        Helper to add slide_block_data directly to a section's slide_blocks list.
        Marks the section as dirty. Does not affect arrangements or emit presentation_changed.
        Used by commands like MoveSlideInstanceCommand when copying a block between sections.
        """
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper:
            print(f"PM Helper: Section '{section_id_in_manifest}' not found for adding block data.")
            return False
        
        section_content = section_wrapper["section_content_data"]
        slide_blocks_list = section_content.setdefault("slide_blocks", [])
        
        # Check for ID collision (though for a copy, this might be intentional if IDs are reused across sections)
        # For a true "move" where the block is unique, this check is less critical if source is deleted.
        # However, if we are copying, we should ensure the ID is unique or handle it.
        # For now, assume the command ensures the block_id is appropriate for the target.
        # if any(sb.get("slide_id") == slide_block_data_to_add.get("slide_id") for sb in slide_blocks_list):
        #     print(f"PM Helper: Slide block ID '{slide_block_data_to_add.get('slide_id')}' already exists in target section.")
        #     return False # Or handle ID renaming

        slide_blocks_list.append(slide_block_data_to_add)
        section_wrapper["is_dirty"] = True
        print(f"PM Helper: Added slide_block '{slide_block_data_to_add.get('slide_id')}' to section '{section_id_in_manifest}' data.")
        return True

    def _remove_slide_block_from_section_data_only(self, section_id_in_manifest: str, slide_block_id_to_remove: str) -> bool:
        """
        Helper to remove slide_block_data directly from a section's slide_blocks list.
        Marks the section as dirty. Does not affect arrangements or emit presentation_changed.
        Used for undoing a block copy (e.g., in MoveSlideInstanceCommand's undo).
        """
        section_wrapper = self.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper or "section_content_data" not in section_wrapper:
            print(f"PM Helper: Section '{section_id_in_manifest}' not found for removing block data.")
            return False
        
        section_content = section_wrapper["section_content_data"]
        slide_blocks_list = section_content.get("slide_blocks", [])
        
        original_len = len(slide_blocks_list)
        section_content["slide_blocks"] = [sb for sb in slide_blocks_list if sb.get("slide_id") != slide_block_id_to_remove]
        
        if len(section_content["slide_blocks"]) < original_len:
            section_wrapper["is_dirty"] = True
            print(f"PM Helper: Removed slide_block '{slide_block_id_to_remove}' from section '{section_id_in_manifest}' data.")
            return True
        else:
            print(f"PM Helper: Slide_block '{slide_block_id_to_remove}' not found in section '{section_id_in_manifest}' data for removal.")
            return False

    # --- End Helper Methods ---

    def update_manifest_section_order(self, new_ordered_section_ids: List[str], _execute_command: bool = True):
        """
        Updates the order of sections in the presentation manifest based on a new list of ordered IDs.
        """
        if not self.presentation_manifest_data or "sections" not in self.presentation_manifest_data:
            self.error_occurred.emit("Cannot reorder sections: Presentation manifest data is missing or invalid.")
            return False

        current_manifest_sections_map = {
            sec_entry.get("id"): sec_entry 
            for sec_entry in self.presentation_manifest_data.get("sections", []) 
            if sec_entry.get("id")
        }
        
        reordered_manifest_sections = []
        all_ids_found = True
        for section_id in new_ordered_section_ids:
            if section_id in current_manifest_sections_map:
                reordered_manifest_sections.append(current_manifest_sections_map[section_id])
            else:
                print(f"PM: Warning - Section ID '{section_id}' from drag reorder not found in current manifest. Manifest may be out of sync.")
                all_ids_found = False
        
        if not all_ids_found and len(reordered_manifest_sections) != len(current_manifest_sections_map.keys()):
            print(f"PM: Discrepancy during section reorder by drag. Original count: {len(current_manifest_sections_map.keys())}, New count based on widget: {len(new_ordered_section_ids)}, Found in manifest: {len(reordered_manifest_sections)}")
            # Potentially, you might want to handle this more gracefully, e.g., by not changing if counts mismatch significantly.
            # For now, we proceed with the order of IDs found in the manifest.

        self.presentation_manifest_data["sections"] = reordered_manifest_sections
        
        if _execute_command:
            self.presentation_manifest_is_dirty = True
            self.presentation_changed.emit() # This will trigger UI refresh, including SectionManagementPanel
        print(f"PM: Updated manifest section order based on drag-and-drop. New order has {len(reordered_manifest_sections)} sections.")
        return True
        return True # Placeholder