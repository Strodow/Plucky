# Optional: Handles serialization/deserialization of presentation data for file storage.
import json
from typing import List, Dict, Any
from data_models.slide_data import SlideData # Adjust import if necessary based on your project structure

class PresentationIO:
    """
    Handles serialization and deserialization of presentation data.
    """
    def save_presentation(self, slides: List[SlideData], filepath: str) -> None:
        """
        Saves the presentation data (list of slides) to a JSON file.
        """
        try:
            data_to_save = [slide.to_dict() for slide in slides]
            with open(filepath, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Presentation saved to {filepath}")
        except Exception as e:
            print(f"Error saving presentation to {filepath}: {e}")
            raise # Or handle more gracefully, e.g., by returning a status

    def load_presentation(self, filepath: str) -> List[SlideData]:
        """
        Loads presentation data (list of slides) from a JSON file.
        """
        try:
            with open(filepath, 'r') as f:
                data_loaded = json.load(f)
            slides = [SlideData.from_dict(slide_data) for slide_data in data_loaded]
            print(f"Presentation loaded from {filepath}")
            return slides
        except Exception as e:
            print(f"Error loading presentation from {filepath}: {e}")
            raise # Or handle more gracefully