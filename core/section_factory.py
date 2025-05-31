# core/section_factory.py
import uuid
import os
from typing import Dict, Any
# Assuming PluckyStandards and PresentationManager.io_handler are accessible
# from .plucky_standards import PluckyStandards 
# from .presentation_manager import PresentationManager # For type hinting if needed
from .app_config_manager import ApplicationConfigManager # For reading default template setting


class SectionFactory:
    DEFAULT_SECTION_VERSION = "1.0.0"

    @staticmethod
    def create_new_section_data(title: str, section_file_id: str, section_type: str = "Generic") -> Dict[str, Any]:
        """
        Creates the dictionary structure for a new section.
        This is the single place to define what a 'default' new section looks like.
        """
        default_slide_block_id = f"slide_{uuid.uuid4().hex[:12]}"
        # Read the user-defined default template ID from config
        # This requires ApplicationConfigManager to be accessible, e.g., via a singleton or passed in.
        # For simplicity, let's assume a way to get it.
        config = ApplicationConfigManager() # This might need to be a shared instance
        user_default_template_id_setting = config.get_app_setting("new_slide_default_template_id", None)
        
        # If setting is "None" (string) or Python None, use Python None for template_id
        actual_template_id_for_new_slide = None if user_default_template_id_setting == "None" or user_default_template_id_setting is None else user_default_template_id_setting

        
        # --- THIS IS YOUR CENTRALIZED DEFINITION ---
        section_data = {
            "version": SectionFactory.DEFAULT_SECTION_VERSION,
            "id": section_file_id,
            "title": title,
            "metadata": [], # New generic metadata field
            "slide_blocks": [
                {
                    "slide_id": default_slide_block_id,
                    "label": "Slide 1", 
                    "content": {"main_text": ""}, # Default content
                    "template_id": actual_template_id_for_new_slide,
                    "background_source": None,
                    "notes": None
                }
            ],
            "arrangements": {
                "Default": [
                    {"slide_id_ref": default_slide_block_id, "enabled": True}
                ]
            }
        }
        # -----------------------------------------

        if section_type == "Song":
            # Specific defaults for Song type can be added here
            pass # e.g., section_data["artist"] = "Unknown Artist"
        
        return section_data

    @staticmethod
    def save_new_section_file(section_data: Dict[str, Any], 
                              cleaned_section_title: str, 
                              io_handler, # Pass PresentationManager.io_handler
                              central_sections_dir: str # Pass PluckyStandards.get_sections_dir()
                              ) -> tuple[str | None, str | None]: # full_filepath, simple_filename
        """
        Determines filename, saves the section data to the central store.
        Returns (full_filepath, simple_filename) or (None, None) on failure.
        """
        safe_filename_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in cleaned_section_title)
        if not safe_filename_title:
            safe_filename_title = f"untitled_section_{uuid.uuid4().hex[:8]}"
        
        section_filename = f"{safe_filename_title}.plucky_section"
        full_section_filepath = os.path.join(central_sections_dir, section_filename)

        if os.path.exists(full_section_filepath):
            section_filename = f"{safe_filename_title}_{uuid.uuid4().hex[:4]}.plucky_section"
            full_section_filepath = os.path.join(central_sections_dir, section_filename)
        
        try:
            io_handler.save_json_file(section_data, full_section_filepath)
            return full_section_filepath, section_filename
        except Exception as e:
            print(f"Error in SectionFactory saving new section file: {e}")
            return None, None
