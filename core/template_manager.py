import copy
from typing import Dict, Any, List, Optional

from PySide6.QtCore import QObject, Signal

from data_models.slide_data import DEFAULT_TEMPLATE # For the initial default

class TemplateManager(QObject):
    """Manages the collection of named presentation templates."""

    # Emitted when the collection of templates changes (add, remove, rename)
    # or when a specific template's content is updated.
    templates_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._named_templates: Dict[str, Dict[str, Any]] = {
            "Default": DEFAULT_TEMPLATE.copy()
        }

    def get_template_names(self) -> List[str]:
        """Returns a list of all current template names."""
        return list(self._named_templates.keys())

    def get_template_settings(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns a deep copy of the settings for a given template name.
        Returns None if the template name doesn't exist.
        """
        if template_name in self._named_templates:
            return copy.deepcopy(self._named_templates[template_name])
        return None

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """Returns a deep copy of the entire collection of named templates."""
        return copy.deepcopy(self._named_templates)

    def update_template_settings(self, template_name: str, new_settings: Dict[str, Any]):
        """
        Updates the settings for an existing template.
        If the template doesn't exist, it can optionally create it or log a warning.
        """
        # For simplicity, we assume new_settings is a complete, valid template dict.
        # If template_name doesn't exist, this will add it.
        # If you want to strictly update existing, add: if template_name not in self._named_templates: return False
        self._named_templates[template_name] = copy.deepcopy(new_settings)
        self.templates_changed.emit()
        print(f"TemplateManager: Template '{template_name}' updated/added.")

    def add_new_template(self, new_template_name: str, base_template_name: Optional[str] = None) -> bool:
        """Adds a new template, optionally based on an existing one or the default."""
        if not new_template_name.strip() or new_template_name in self._named_templates:
            print(f"TemplateManager: Invalid or duplicate new template name '{new_template_name}'.")
            return False
        
        if base_template_name and base_template_name in self._named_templates:
            self._named_templates[new_template_name] = copy.deepcopy(self._named_templates[base_template_name])
        else:
            self._named_templates[new_template_name] = DEFAULT_TEMPLATE.copy()
        
        self.templates_changed.emit()
        print(f"TemplateManager: New template '{new_template_name}' added.")
        return True

    def delete_template(self, template_name: str) -> bool:
        """Deletes a template. Prevents deleting the last template."""
        if template_name not in self._named_templates:
            print(f"TemplateManager: Template '{template_name}' not found for deletion.")
            return False
        if len(self._named_templates) <= 1 and "Default" in self._named_templates and template_name == "Default":
            print("TemplateManager: Cannot delete the 'Default' template if it's the only one.")
            # Or, more strictly, always prevent deleting "Default" if it exists.
            # Or, if deleting last, re-add "Default". For now, prevent deleting last.
            return False
            
        del self._named_templates[template_name]
        if not self._named_templates: # Ensure "Default" always exists if all are deleted
            self._named_templates["Default"] = DEFAULT_TEMPLATE.copy()

        self.templates_changed.emit()
        print(f"TemplateManager: Template '{template_name}' deleted.")
        return True

    def update_from_collection(self, new_collection: Dict[str, Dict[str, Any]]):
        """Replaces the entire internal collection with a new one. Used by TemplateEditorWindow."""
        self._named_templates = copy.deepcopy(new_collection)
        if "Default" not in self._named_templates: # Ensure "Default" always exists
            self._named_templates["Default"] = DEFAULT_TEMPLATE.copy()
        self.templates_changed.emit()
        print("TemplateManager: Entire template collection updated.")