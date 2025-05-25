import copy
from typing import Dict, Any, List, Optional
import json # Import the json module
import os # For file path operations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor # For default color values

try:
    from core.plucky_standards import PluckyStandards
    # If PluckyStandards defines these, use them:
    # DEFAULT_LAYOUT_NAME = PluckyStandards.DEFAULT_LAYOUT_NAME
    # DEFAULT_STYLE_NAME = PluckyStandards.DEFAULT_STYLE_NAME
except ImportError:
    # Fallback if PluckyStandards is not found or doesn't define these
    from plucky_standards import PluckyStandards # Fallback for PluckyStandards itself

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

# Define standard names, ideally these would come from PluckyStandards
DEFAULT_LAYOUT_NAME = "Default Layout"
DEFAULT_STYLE_NAME = "Default Style"
SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME = "System Default Fallback"

class TemplateManager(QObject):
    """Manages the collection of named presentation templates."""

    # Emitted when the collection of templates changes (add, remove, rename)
    # or when a specific template's content is updated.
    templates_changed = Signal()

    # File extensions for template types
    STYLE_EXT = ".style.json"
    LAYOUT_EXT = ".layout.json"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template_collection: Dict[str, Dict[str, Any]] = {
            "styles": {},
            "layouts": {},
        }
        # Note: The old DEFAULT_TEMPLATE from slide_data.py is no longer directly used here.
        # This manager now deals with the structured collection.
        self._load_templates_from_files() # Load templates on initialization
        # _ensure_default_entries is called within _load_templates_from_files
        # to ensure defaults are present if not loaded.

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
        self._save_templates_to_files() # Save to individual files after updating
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

    # --- Deprecated/Replaced Methods (from the old flat template structure) ---
    # These methods are no longer directly applicable to the new structured system
    # in the same way. The TemplateEditorWindow will now work with the full collection.
    # If other parts of your application relied on these, they'll need to be updated
    # to use the new category-specific getters or work with the full collection.

    # This method is fully deprecated as "master templates" are removed.
    def get_template_names_old(self) -> List[str]:
        """DEPRECATED: Master templates are removed. This will return an empty list."""
        print("TemplateManager: get_template_names_old() is deprecated. Master templates are removed.")
        return []

    # This method is fully deprecated as "master templates" are removed.
    def get_template_settings_old(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Tries to return a master template definition as a stand-in.
        The concept of a single 'template_settings' is replaced by structured data.
        """
        print(f"TemplateManager: get_template_settings_old('{template_name}') is deprecated. Use get_master_template_definition() or resolve styles/layouts.")
        # This is a placeholder. The actual "settings" for a slide will come from resolving
        # a layout and its styles. Master templates are removed.
        return None

    def resolve_layout_template(self, layout_name: str) -> Dict[str, Any]:
        """
        Resolves a layout template by name, including resolving styles for its text boxes.
        Returns a dictionary structure suitable for SlideData.template_settings.
        """
        layout_definitions = self._template_collection.get("layouts", {})
        style_definitions = self._template_collection.get("styles", {})

        # print(f"DEBUG_TM: resolve_layout_template called for: '{layout_name}'") # General call

        if layout_name not in layout_definitions or not layout_definitions[layout_name]: # Check if empty or None
            # print(f"DEBUG_TM: Layout '{layout_name}' NOT FOUND or is invalid/empty in collection.")
            if layout_name != DEFAULT_LAYOUT_NAME and DEFAULT_LAYOUT_NAME in layout_definitions:
                print(f"TemplateManager: Falling back to '{DEFAULT_LAYOUT_NAME}' for unresolved '{layout_name}'.")
                return self.resolve_layout_template(DEFAULT_LAYOUT_NAME)
            # Ultimate fallback: empty structure
            # print(f"DEBUG_TM: Layout '{layout_name}' - Returning ultimate fallback (empty text_boxes).")
            # Ensure this fallback also doesn't force a background_color if not intended
            return {"layout_name": layout_name, "text_boxes": [], "text_content": {}}

        layout_def = layout_definitions[layout_name]
        resolved_layout = {
            "layout_name": layout_name,
            "text_boxes": [],
            # "description": layout_def.get("description", ""), # Optionally carry over description
            "text_content": {} # This will be populated by MainWindow or lyric editor later
        }
        
        # Only add background_color to resolved_layout if it's explicitly in layout_def
        if "background_color" in layout_def:
            resolved_layout["background_color"] = layout_def.get("background_color")

        # print(f"DEBUG_TM: Resolving layout '{layout_name}'. Original text_boxes: {layout_def.get('text_boxes')}")
        for tb_def in layout_def.get("text_boxes", []):
            resolved_tb = { # Start with geometry and alignment from layout
                "id": tb_def.get("id", "unknown_tb_id"),
                "x_pc": tb_def.get("x_pc", 0.0), "y_pc": tb_def.get("y_pc", 0.0),
                "width_pc": tb_def.get("width_pc", 100.0), "height_pc": tb_def.get("height_pc", 100.0),
                "h_align": tb_def.get("h_align", "center"), "v_align": tb_def.get("v_align", "center"),
            }

            style_name = tb_def.get("style_name") # Style name assigned in layout editor
            # Get the actual style properties, falling back to "Default Style" or hardcoded defaults
            # print(f"DEBUG_TM: Text box '{resolved_tb['id']}' in layout '{layout_name}' requests style_name: '{style_name}'")
            actual_style_props = style_definitions.get(style_name, style_definitions.get(DEFAULT_STYLE_NAME, copy.deepcopy(DEFAULT_STYLE_PROPS)))

            # Merge (or rather, add) the resolved style properties into the text box definition
            # These keys should match what SlideRenderer expects
            resolved_tb.update({
                "font_family": actual_style_props.get("font_family"), "font_size": actual_style_props.get("font_size"),
                "font_color": actual_style_props.get("font_color"), "force_all_caps": actual_style_props.get("force_all_caps"),
                "outline_enabled": actual_style_props.get("text_outline"), "outline_color": actual_style_props.get("outline_color"), "outline_width": actual_style_props.get("outline_thickness"),
                "shadow_enabled": actual_style_props.get("text_shadow"), "shadow_color": actual_style_props.get("shadow_color"), "shadow_offset_x": actual_style_props.get("shadow_x"), "shadow_offset_y": actual_style_props.get("shadow_y"),
            })
            resolved_layout["text_boxes"].append(resolved_tb)
        # print(f"DEBUG_TM: Resolved layout '{layout_name}' has {len(resolved_layout['text_boxes'])} text_boxes.")
        return resolved_layout    # The old add_new_template, delete_template, update_template_settings methods
    # would need to be significantly refactored to work with categories (styles, layouts, master_templates)
    # or be removed if all modifications are handled through the TemplateEditorWindow and update_from_collection.
    # For now, they are effectively replaced by the editor's more comprehensive management.
    # If direct API access to add/delete individual styles/layouts/masters is needed later,
    # new methods like `add_style_definition`, `delete_layout_definition` etc. should be created.

    def _ensure_settings_dir_exists(self):
        """DEPRECATED: PluckyStandards now handles directory creation."""
        pass

    def _ensure_default_entries(self):
        """Ensures default categories and entries exist in the current collection."""
        if "styles" not in self._template_collection or not isinstance(self._template_collection["styles"], dict):
            self._template_collection["styles"] = {}
        if DEFAULT_STYLE_NAME not in self._template_collection["styles"]:
            self._template_collection["styles"][DEFAULT_STYLE_NAME] = copy.deepcopy(DEFAULT_STYLE_PROPS)
            self._save_single_template_to_file("styles", DEFAULT_STYLE_NAME, self._template_collection["styles"][DEFAULT_STYLE_NAME])
            
        if "layouts" not in self._template_collection or not isinstance(self._template_collection["layouts"], dict):
            self._template_collection["layouts"] = {}
        if DEFAULT_LAYOUT_NAME not in self._template_collection["layouts"]:
            self._template_collection["layouts"][DEFAULT_LAYOUT_NAME] = copy.deepcopy(DEFAULT_LAYOUT_PROPS)
            self._save_single_template_to_file("layouts", DEFAULT_LAYOUT_NAME, self._template_collection["layouts"][DEFAULT_LAYOUT_NAME])

        # Ensure "System Default Fallback" layout exists
        if SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME not in self._template_collection["layouts"]:
            fallback_layout_content = {
                "layout_name": SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME,
                "description": "System's default layout for slides without an assigned template. Edit this to change the default appearance.",
                "background_color": "#00000000", # Fully Transparent Black
                "text_boxes": [
                    {
                        "id": "main_text_fallback", # Unique ID for this box
                        "x_pc": 5.0, "y_pc": 5.0, "width_pc": 90.0, "height_pc": 90.0,
                        "h_align": "center", "v_align": "center",
                        "style_name": DEFAULT_STYLE_NAME # Reference the default style by name
                    }
                ]
            }
            self._template_collection["layouts"][SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME] = fallback_layout_content
            self._save_single_template_to_file("layouts", SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME, fallback_layout_content)
            print(f"TemplateManager: Created default fallback layout template: '{SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME}'")

    def _get_template_dir_and_ext(self, category: str) -> tuple[Optional[str], Optional[str]]:
        if category == "styles":
            return PluckyStandards.get_templates_styles_dir(), self.STYLE_EXT
        elif category == "layouts":
            return PluckyStandards.get_templates_layouts_dir(), self.LAYOUT_EXT
        return None, None

    def _load_templates_from_files(self):
        """Loads all templates from their individual files in respective subdirectories."""
        loaded_collection = {"styles": {}, "layouts": {}}
        categories = ["styles", "layouts"] # Removed "master_templates"

        for category in categories:
            template_dir, ext = self._get_template_dir_and_ext(category)
            if not template_dir or not ext:
                continue

            if not os.path.isdir(template_dir):
                print(f"TemplateManager: Directory not found for {category}: {template_dir}. Skipping load for this category.")
                continue

            for filename in os.listdir(template_dir):
                if filename.endswith(ext):
                    template_name = filename[:-len(ext)] # Remove extension to get name
                    filepath = os.path.join(template_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            template_data = json.load(f)
                        loaded_collection[category][template_name] = template_data
                        print(f"TemplateManager: Loaded {category} '{template_name}' from {filepath}")
                    except json.JSONDecodeError:
                        print(f"TemplateManager: Error decoding JSON from {filepath}. Skipping.")
                    except Exception as e:
                        print(f"TemplateManager: Error loading {filepath}: {e}. Skipping.")
        
        self._template_collection = loaded_collection
        self._ensure_default_entries() # Ensure defaults are present if not loaded from files
        self.templates_changed.emit() # Emit signal after loading

    def _save_single_template_to_file(self, category: str, template_name: str, template_data: Dict[str, Any]):
        """Saves a single template definition to its own file."""
        template_dir, ext = self._get_template_dir_and_ext(category)
        if not template_dir or not ext:
            print(f"TemplateManager: Invalid category '{category}' for saving single template.")
            return

        PluckyStandards.ensure_directory_exists(template_dir) # Ensure directory exists
        filename = f"{template_name}{ext}"
        filepath = os.path.join(template_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            print(f"TemplateManager: Saved {category} '{template_name}' to {filepath}")
        except Exception as e:
            print(f"TemplateManager: Error saving {filepath}: {e}")

    def _save_templates_to_files(self):
        """Saves all in-memory templates to their individual files and deletes orphaned files."""
        categories = ["styles", "layouts"] # Removed "master_templates"

        for category in categories:
            template_dir, ext = self._get_template_dir_and_ext(category)
            if not template_dir or not ext:
                continue

            PluckyStandards.ensure_directory_exists(template_dir)

            # Save current templates
            current_templates_in_memory = self._template_collection.get(category, {})
            expected_filenames = set()
            for template_name, template_data in current_templates_in_memory.items():
                filename = f"{template_name}{ext}"
                expected_filenames.add(filename)
                filepath = os.path.join(template_dir, filename)
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(template_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"TemplateManager: Error saving {filepath}: {e}")

            # Delete orphaned files
            if os.path.isdir(template_dir):
                for existing_filename in os.listdir(template_dir):
                    if existing_filename.endswith(ext) and existing_filename not in expected_filenames:
                        filepath_to_delete = os.path.join(template_dir, existing_filename)
                        try:
                            os.remove(filepath_to_delete)
                            print(f"TemplateManager: Deleted orphaned template file {filepath_to_delete}")
                        except Exception as e:
                            print(f"TemplateManager: Error deleting orphaned file {filepath_to_delete}: {e}")
        
        print(f"TemplateManager: All templates saved to individual files.")

    # Example of how a specific add/delete method might look (if needed beyond TemplateEditor)
    def add_style(self, name: str, definition: Dict[str, Any]):
        """Adds or updates a style definition and saves it."""
        if "styles" not in self._template_collection: self._template_collection["styles"] = {}
        self._template_collection["styles"][name] = definition
        self._save_single_template_to_file("styles", name, definition)
        self.templates_changed.emit()

    def delete_style(self, name: str):
        """Deletes a style definition and its file."""
        if "styles" in self._template_collection and name in self._template_collection["styles"]:
            del self._template_collection["styles"][name]
            template_dir, ext = self._get_template_dir_and_ext("styles")
            if template_dir and ext:
                filepath = os.path.join(template_dir, f"{name}{ext}")
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        print(f"TemplateManager: Deleted style file {filepath}")
                    except Exception as e:
                        print(f"TemplateManager: Error deleting style file {filepath}: {e}")
            self.templates_changed.emit()
        # The 'except' block was misplaced and its message was incorrect for a delete operation.
        # It's removed from this level. Specific exceptions are handled around os.remove.

    def resolve_slide_template_for_block(self, slide_block_data: dict, section_data: dict) -> Optional[dict]:
        """
        Resolves the template settings for a given slide block.
        If template_id is None, it uses the SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME.
        """
        template_id = slide_block_data.get("template_id")
        
        if template_id: # A specific layout template is assigned to the slide block
            return self.resolve_layout_template(template_id)
        else: # No specific template_id on the slide block. Try to use the system default fallback.
            # print(f"DEBUG_TM: template_id is None for slide block. Attempting to use '{SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME}'.")
            fallback_settings = self.resolve_layout_template(SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME)
            if fallback_settings:
                # print(f"DEBUG_TM: Successfully resolved '{SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME}'. text_boxes count: {len(fallback_settings.get('text_boxes', []))}")
                return fallback_settings
            # Ultimate fallback if SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME also fails to resolve (shouldn't happen if _ensure_default_entries works)
            # print(f"DEBUG_TM: FAILED to resolve '{SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME}'. Returning None.")
            return None # SlideRenderer will use its hardcoded defaults.