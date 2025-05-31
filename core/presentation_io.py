# Optional: Handles serialization/deserialization of presentation data for file storage.
import json
import os # For directory creation
from typing import Dict, Any # No longer directly deals with SlideData List

class PresentationIO:
    """
    Handles generic JSON serialization and deserialization for presentation manifest
    and section files.
    """
    def save_json_file(self, data: Dict[str, Any], filepath: str) -> bool:
        """
        Saves dictionary data to a JSON file.
        Returns True on success, False on failure.
        """
        try:
            # Ensure the directory exists
            directory = os.path.dirname(filepath)
            if directory: # Check if directory is not empty (e.g. for relative paths in current dir)
                os.makedirs(directory, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4) # Use indent for readability
            print(f"IO Success: Saved JSON data to {filepath}")
            return True # Indicate success
        except IOError as e: # More specific exception for file I/O issues
            print(f"IO Error: Could not write JSON to {filepath}: {e}")
            # raise # Re-raise for the caller to handle (e.g., PresentationManager or MainWindow)
            return False # Indicate failure
        except Exception as e:
            print(f"IO Error: An unexpected error occurred saving JSON to {filepath}: {e}")
            # raise
            return False # Indicate failure

    def load_json_file(self, filepath: str) -> Dict[str, Any]: # Return type is now Dict
        """
        Loads data from a JSON file and returns it as a dictionary.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data_loaded = json.load(f)
            if not isinstance(data_loaded, dict): # Basic validation
                raise ValueError(f"File {filepath} does not contain a valid JSON object at the root.")
            print(f"IO Success: Loaded JSON data from {filepath}")
            return data_loaded
        except FileNotFoundError:
            print(f"IO Error: File not found at {filepath}")
            raise
        except json.JSONDecodeError as e:
            print(f"IO Error: Could not decode JSON from {filepath}: {e}")
            raise
        except Exception as e:
            print(f"IO Error: An unexpected error occurred loading {filepath}: {e}")
            raise
        
    def load_manifest_data_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        Loads manifest data from a presentation file (which is expected to be JSON).
        This method is specifically for compatibility with ResourceTracker.
        """
        print(f"PresentationIO: Delegating load_manifest_data_from_file for {filepath} to load_json_file.")
        # Assuming presentation manifest files are JSON files.
        return self.load_json_file(filepath)