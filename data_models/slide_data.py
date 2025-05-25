from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import uuid

# Default template settings (can be expanded significantly)
DEFAULT_TEMPLATE = {
    "font": {
        "family": "Arial",
        "size": 58, # Base size for 1080p
        "bold": False,
        "italic": False,
        "underline": False,
        "force_all_caps": False,
    },
    "color": "#FFFFFF", # White text
    "position": {"x": "50%", "y": "80%"}, # Anchor point
    "alignment": "center", # Horizontal text alignment within its box
    "vertical_alignment": "center", # Vertical alignment relative to anchor
    "max_width": "90%", # Max width of the text box relative to screen
    "outline": {"enabled": False, "color": "#000000", "width": 2},
    "shadow": {"enabled": False, "color": "#000000", "offset_x": 3, "offset_y": 3},
    # Info bar specific settings could also go here or be separate
    "info_bar_color": "#0078D7", # Default blue
}

@dataclass
class SlideData:
    """Holds all necessary data to render a single presentation slide."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lyrics: str = ""
    background_image_path: Optional[str] = None
    song_title: Optional[str] = None # New field for the song's title
    overlay_label: str = "" # New field for the overlay label set via context menu
    background_color: str = "#000000" # Default black background if no image
    is_background_slide: bool = False # New field to mark background slides
    template_settings: Dict[str, Any] = field(default_factory=lambda: DEFAULT_TEMPLATE.copy())
    is_enabled_in_arrangement: bool = True # From section's arrangement data
    notes: Optional[str] = None # Operator notes for this slide
    banner_color: Optional[str] = None # Add banner_color as a dataclass field
    
    # New fields for Phase 4 - Identifying target section/block for edits
    section_id_in_manifest: Optional[str] = None # ID of the section entry in the presentation manifest
    slide_block_id: Optional[str] = None         # Original slide_id from the section's slide_blocks
    active_arrangement_name_for_section: Optional[str] = None # Active arrangement for this section


    def __post_init__(self):
        # If this is a background slide, ensure its template_settings
        # reflect that it has no text boxes to render.
        if self.is_background_slide:
            self.template_settings = {"text_boxes": [], "text_content": {}}
            # print(f"DEBUG SLIDEDATA ({self.id}): __post_init__ for BACKGROUND slide. template_settings is now: {self.template_settings}")
        
        # Ensure essential keys in template_settings if not a background slide
        if not self.is_background_slide:
            if "text_content" not in self.template_settings:
                self.template_settings["text_content"] = {}
            if "layout_name" not in self.template_settings: # layout_name is the template_id from slide_block
                self.template_settings["layout_name"] = None
    # Optional info bar details (could be derived or stored separately too)
    slide_number: Optional[int] = None
    section_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the SlideData instance to a dictionary for serialization."""
        # asdict() automatically includes all dataclass fields, including the new banner_color
        return asdict(self)

    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> 'SlideData':
        """Creates a SlideData instance from a dictionary (e.g., loaded from JSON)."""
        # Use .get() for robustness against missing keys, providing defaults.
        return cls(
            id=data_dict.get("id", str(uuid.uuid4())), # Default to new UUID if missing
            lyrics=data_dict.get("lyrics", ""),
            background_image_path=data_dict.get("background_image_path"),
            song_title=data_dict.get("song_title"),
            overlay_label=data_dict.get("overlay_label", ""),
            background_color=data_dict.get("background_color", "#000000"),
            is_background_slide=data_dict.get("is_background_slide", False),
            template_settings=data_dict.get("template_settings", DEFAULT_TEMPLATE.copy()),
            is_enabled_in_arrangement=data_dict.get("is_enabled_in_arrangement", True),
            notes=data_dict.get("notes"),
            banner_color=data_dict.get("banner_color"),
            section_id_in_manifest=data_dict.get("section_id_in_manifest"),
            slide_block_id=data_dict.get("slide_block_id"),
            active_arrangement_name_for_section=data_dict.get("active_arrangement_name_for_section"),
            # slide_number and section_name are not typically part of core data for from_dict
            # but if they were, you'd add them here too.
        )

if __name__ == "__main__":
    # Example Usage
    slide1 = SlideData(lyrics="This is the first line\nAnd the second line.")
    slide2 = SlideData(lyrics="Single line.", background_color="#FF0000", template_settings={"color": "#FFFF00"}) # Red bg, yellow text
    slide3 = SlideData(lyrics="With Background", background_image_path="c:/path/to/your/image.png")
    slide4 = SlideData(lyrics="With Notes", notes="This is an important note.")

    print("Slide 1:", slide1)
    print("Slide 1 ID:", slide1.id)
    print("\nSlide 2:", slide2)
    print("\nSlide 3:", slide3)
    print("\nSlide 4:", slide4)
    print("\nSlide 1 Font Size:", slide1.template_settings.get("font", {}).get("size"))

    # Test serialization and deserialization
    slide1_dict = slide1.to_dict()
    print("\nSlide 1 as dict:", slide1_dict)

    rehydrated_slide1 = SlideData.from_dict(slide1_dict)
    print("\nRehydrated Slide 1:", rehydrated_slide1)
    print("Are original and rehydrated slide1 the same?", slide1 == rehydrated_slide1)

    # Example of loading data that might be missing a new field (like 'id' if loading old data)
    old_data_format = {
        "lyrics": "Old format slide",
        "background_color": "#00FF00",
        # 'id' is missing, 'template_settings' is missing
    }
    slide_from_old_data = SlideData.from_dict(old_data_format)
    print("\nSlide from old data format (new ID and default template assigned):", slide_from_old_data)
