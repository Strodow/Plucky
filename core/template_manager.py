import copy
from typing import Dict, Any, List, Optional
import json # Import the json module
import os # For file path operations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor # For default color values

# --- New Default Definitions for the Structured Template System ---
DEFAULT_STYLE_PROPS: Dict[str, Any] = {
    "font_family": "Arial", "font_size": 48, "font_color": "#FFFFFF",
    "preview_text": "Sample Text", "force_all_caps": False,
    "text_shadow": False, "shadow_x": 1, "shadow_y": 1, "shadow_blur": 2, "shadow_color": QColor(0,0,0,128).name(QColor.NameFormat.HexArgb), # semi-transparent black
    "text_outline": False, "outline_thickness": 1, "outline_color": "#000000"
}

DEFAULT_LAYOUT_PROPS: Dict[str, Any] = {
    "text_boxes": [
        {"id": "main", "x_pc": 10, "y_pc": 10, "width_pc": 80, "height_pc": 80, "h_align": "center", "v_align": "center"}
    ],
    "background_color": "#000000" # Default background for the layout itself
}

DEFAULT_MASTER_TEMPLATE_PROPS: Dict[str, Any] = {
    "layout_name": "Default Layout", # Refers to a layout definition name
    "text_box_styles": { # Maps text_box_id from the layout to a style_definition name
        "main": "Default Style"
    }
}

class TemplateManager(QObject):
    """Manages the collection of named presentation templates."""

    # Emitted when the collection of templates changes (add, remove, rename)
    # or when a specific template's content is updated.
    templates_changed = Signal()

    # Define a path for the template collection file
    CONFIG_DIR = os.path.dirname(os.path.abspath(__file__)) # Core directory
    TEMPLATE_COLLECTION_FILE = os.path.join(CONFIG_DIR, "..", "settings", "templates_collection.json") # Place in a settings folder

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template_collection: Dict[str, Dict[str, Any]] = {
            "styles": {
                "Default Style": copy.deepcopy(DEFAULT_STYLE_PROPS)
            },
            "layouts": {
                "Default Layout": copy.deepcopy(DEFAULT_LAYOUT_PROPS)
            },
            "master_templates": {
                "Default Master": copy.deepcopy(DEFAULT_MASTER_TEMPLATE_PROPS)
            }
        }
        # Note: The old DEFAULT_TEMPLATE from slide_data.py is no longer directly used here.
        # This manager now deals with the structured collection.
        self._ensure_settings_dir_exists()
        self._load_templates_from_file() # Load templates on initialization

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """Returns a deep copy of the entire template collection (styles, layouts, master_templates)."""
        return copy.deepcopy(self._template_collection)

    def update_from_collection(self, new_collection: Dict[str, Dict[str, Any]]):
        """
        Replaces the entire internal collection with a new one.
        Ensures default entries exist if missing.
        Used by TemplateEditorWindow.
        """
        self._template_collection = copy.deepcopy(new_collection)
        self._ensure_default_entries() # Ensure defaults after updating
        self._save_templates_to_file() # Save to file after updating
        self.templates_changed.emit()
        print("TemplateManager: Entire template collection updated.")

    # --- Category-Specific Getters (Optional, but good for other parts of the app) ---
    def get_style_names(self) -> List[str]:
        return list(self._template_collection.get("styles", {}).keys())

    def get_style_definition(self, name: str) -> Optional[Dict[str, Any]]:
        style_def = self._template_collection.get("styles", {}).get(name)
        return copy.deepcopy(style_def) if style_def else None

    def get_layout_names(self) -> List[str]:
        return list(self._template_collection.get("layouts", {}).keys())

    def get_layout_definition(self, name: str) -> Optional[Dict[str, Any]]:
        layout_def = self._template_collection.get("layouts", {}).get(name)
        return copy.deepcopy(layout_def) if layout_def else None

    def get_master_template_names(self) -> List[str]:
        return list(self._template_collection.get("master_templates", {}).keys())

    def get_master_template_definition(self, name: str) -> Optional[Dict[str, Any]]:
        master_def = self._template_collection.get("master_templates", {}).get(name)
        return copy.deepcopy(master_def) if master_def else None

    # --- Deprecated/Replaced Methods (from the old flat template structure) ---
    # These methods are no longer directly applicable to the new structured system
    # in the same way. The TemplateEditorWindow will now work with the full collection.
    # If other parts of your application relied on these, they'll need to be updated
    # to use the new category-specific getters or work with the full collection.

    def get_template_names_old(self) -> List[str]:
        """DEPRECATED: Returns a list of master template names as a stand-in."""
        print("TemplateManager: get_template_names_old() is deprecated. Use get_master_template_names() or similar.")
        return self.get_master_template_names()

    def get_template_settings_old(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Tries to return a master template definition as a stand-in.
        The concept of a single 'template_settings' is replaced by structured data.
        """
        print(f"TemplateManager: get_template_settings_old('{template_name}') is deprecated. Use get_master_template_definition() or resolve styles/layouts.")
        # This is a placeholder. The actual "settings" for a slide will come from resolving
        # a master template, its layout, and the styles for its text boxes.
        # For now, just return the master template definition if it exists.
        master_def = self.get_master_template_definition(template_name)
        if master_def:
            return master_def # This isn't the final "renderable" settings, but it's the stored data.
        return None

    def resolve_layout_template(self, layout_name: str) -> Dict[str, Any]:
        """
        Resolves a layout template by name, including resolving styles for its text boxes.
        Returns a dictionary structure suitable for SlideData.template_settings.
        """
        layout_definitions = self._template_collection.get("layouts", {})
        style_definitions = self._template_collection.get("styles", {})

        if layout_name not in layout_definitions:
            print(f"TemplateManager: Layout '{layout_name}' not found.")
            if layout_name != "Default Layout" and "Default Layout" in layout_definitions:
                print(f"TemplateManager: Falling back to 'Default Layout' for unresolved '{layout_name}'.")
                return self.resolve_layout_template("Default Layout")
            # Ultimate fallback: empty structure
            return {"layout_name": layout_name, "background_color": "#000000", "text_boxes": [], "text_content": {}}

        layout_def = layout_definitions[layout_name]
        resolved_layout = {
            "layout_name": layout_name,
            "background_color": layout_def.get("background_color", "#000000"),
            "text_boxes": [],
            "text_content": {} # This will be populated by MainWindow or lyric editor later
        }

        for tb_def in layout_def.get("text_boxes", []):
            resolved_tb = { # Start with geometry and alignment from layout
                "id": tb_def.get("id", "unknown_tb_id"),
                "x_pc": tb_def.get("x_pc", 0.0), "y_pc": tb_def.get("y_pc", 0.0),
                "width_pc": tb_def.get("width_pc", 100.0), "height_pc": tb_def.get("height_pc", 100.0),
                "h_align": tb_def.get("h_align", "center"), "v_align": tb_def.get("v_align", "center"),
            }

            style_name = tb_def.get("style_name") # Style name assigned in layout editor
            # Get the actual style properties, falling back to "Default Style" or hardcoded defaults
            actual_style_props = style_definitions.get(style_name, style_definitions.get("Default Style", copy.deepcopy(DEFAULT_STYLE_PROPS)))

            # Merge (or rather, add) the resolved style properties into the text box definition
            # These keys should match what SlideRenderer expects
            resolved_tb.update({
                "font_family": actual_style_props.get("font_family"), "font_size": actual_style_props.get("font_size"),
                "font_color": actual_style_props.get("font_color"), "force_all_caps": actual_style_props.get("force_all_caps"),
                "outline_enabled": actual_style_props.get("text_outline"), "outline_color": actual_style_props.get("outline_color"), "outline_width": actual_style_props.get("outline_thickness"),
                "shadow_enabled": actual_style_props.get("text_shadow"), "shadow_color": actual_style_props.get("shadow_color"), "shadow_offset_x": actual_style_props.get("shadow_x"), "shadow_offset_y": actual_style_props.get("shadow_y"),
            })
            resolved_layout["text_boxes"].append(resolved_tb)
        return resolved_layout

    # The old add_new_template, delete_template, update_template_settings methods
    # would need to be significantly refactored to work with categories (styles, layouts, master_templates)
    # or be removed if all modifications are handled through the TemplateEditorWindow and update_from_collection.
    # For now, they are effectively replaced by the editor's more comprehensive management.
    # If direct API access to add/delete individual styles/layouts/masters is needed later,
    # new methods like `add_style_definition`, `delete_layout_definition` etc. should be created.

    def _ensure_settings_dir_exists(self):
        """Ensures the directory for the settings file exists."""
        settings_dir = os.path.dirname(self.TEMPLATE_COLLECTION_FILE)
        if not os.path.exists(settings_dir):
            try:
                os.makedirs(settings_dir)
                print(f"TemplateManager: Created settings directory at {settings_dir}")
            except OSError as e:
                print(f"TemplateManager: Error creating settings directory {settings_dir}: {e}")

    def _ensure_default_entries(self):
        """Ensures default categories and entries exist in the current collection."""
        if "styles" not in self._template_collection or not isinstance(self._template_collection["styles"], dict):
            self._template_collection["styles"] = {}
        if "Default Style" not in self._template_collection["styles"]:
            self._template_collection["styles"]["Default Style"] = copy.deepcopy(DEFAULT_STYLE_PROPS)
            
        if "layouts" not in self._template_collection or not isinstance(self._template_collection["layouts"], dict):
            self._template_collection["layouts"] = {}
        if "Default Layout" not in self._template_collection["layouts"]:
            self._template_collection["layouts"]["Default Layout"] = copy.deepcopy(DEFAULT_LAYOUT_PROPS)

        if "master_templates" not in self._template_collection or not isinstance(self._template_collection["master_templates"], dict):
            self._template_collection["master_templates"] = {}
        if "Default Master" not in self._template_collection["master_templates"]:
            self._template_collection["master_templates"]["Default Master"] = copy.deepcopy(DEFAULT_MASTER_TEMPLATE_PROPS)

    def _load_templates_from_file(self):
        try:
            if os.path.exists(self.TEMPLATE_COLLECTION_FILE):
                with open(self.TEMPLATE_COLLECTION_FILE, 'r', encoding='utf-8') as f:
                    loaded_collection = json.load(f)
                    self._template_collection = loaded_collection # Replace defaults with loaded
                print(f"TemplateManager: Templates loaded from {self.TEMPLATE_COLLECTION_FILE}")
            else:
                print(f"TemplateManager: Template file not found at {self.TEMPLATE_COLLECTION_FILE}. Using default templates.")
        except json.JSONDecodeError:
            print(f"TemplateManager: Error decoding JSON from {self.TEMPLATE_COLLECTION_FILE}. Using default templates.")
        except Exception as e:
            print(f"TemplateManager: Error loading templates from file: {e}. Using default templates.")
        self._ensure_default_entries() # Always ensure defaults after attempting to load

    def _save_templates_to_file(self):
        try:
            with open(self.TEMPLATE_COLLECTION_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._template_collection, f, indent=2, ensure_ascii=False)
            print(f"TemplateManager: Templates saved to {self.TEMPLATE_COLLECTION_FILE}")
        except Exception as e:
            print(f"TemplateManager: Error saving templates to file: {e}")