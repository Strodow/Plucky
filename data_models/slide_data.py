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
    background_color: str = "#000000" # Default black background if no image
    template_settings: Dict[str, Any] = field(default_factory=lambda: DEFAULT_TEMPLATE.copy())

    # Optional info bar details (could be derived or stored separately too)
    slide_number: Optional[int] = None
    section_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the SlideData instance to a dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> 'SlideData':
        """Creates a SlideData instance from a dictionary (e.g., loaded from JSON)."""
        # Ensure all fields expected by the dataclass are present or have defaults
        # This basic implementation assumes data_dict keys match dataclass fields.
        # For more robustness, you might want to handle missing keys or type conversions.
        
        # If 'id' is not in the loaded data, it will get a new default UUID.
        # If 'template_settings' is not in data_dict, it will get DEFAULT_TEMPLATE.
        # This is generally fine, but be aware if you need stricter loading.
        
        return cls(**data_dict)

if __name__ == "__main__":
    # Example Usage
    slide1 = SlideData(lyrics="This is the first line\nAnd the second line.")
    slide2 = SlideData(lyrics="Single line.", background_color="#FF0000", template_settings={"color": "#FFFF00"}) # Red bg, yellow text
    slide3 = SlideData(lyrics="With Background", background_image_path="c:/path/to/your/image.png")

    print("Slide 1:", slide1)
    print("Slide 1 ID:", slide1.id)
    print("\nSlide 2:", slide2)
    print("\nSlide 3:", slide3)
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
