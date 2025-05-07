import copy # For deep copying templates
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox,
    QComboBox, QWidget, QScrollArea, QFormLayout # For future complex layouts
)
from PySide6.QtCore import Qt, Slot

from data_models.slide_data import DEFAULT_TEMPLATE # To access initial defaults

class TemplateEditorWindow(QDialog):
    def __init__(self, all_templates: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Template Editor")
        self.setMinimumSize(400, 500)

        # Store a deep copy to avoid modifying the original dict directly until "OK"
        self.templates_data_copy = copy.deepcopy(all_templates)
        if not self.templates_data_copy: # Ensure there's at least one template to work with
            self.templates_data_copy["Default"] = DEFAULT_TEMPLATE.copy()
            
        self.currently_editing_template_name: str = list(self.templates_data_copy.keys())[0]

        self.main_layout = QVBoxLayout(self)
        
        # --- Template Selector ---
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Edit Template:"))
        self.template_selector_combo = QComboBox()
        self.template_selector_combo.addItems(self.templates_data_copy.keys())
        self.template_selector_combo.setCurrentText(self.currently_editing_template_name)
        self.template_selector_combo.currentTextChanged.connect(self.on_template_selected)
        selector_layout.addWidget(self.template_selector_combo, 1)
        # Add buttons for New, Rename, Delete template in the future here
        self.main_layout.addLayout(selector_layout)

        # Placeholder for template editing controls
        # This area will eventually hold QFontComboBox, QColorDialog triggers, QSpinBoxes etc.
        self.placeholder_label = QLabel("Template editing controls will go here.\n"
                                        "E.g., Font, Color, Position, Alignment...")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.placeholder_label)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept) # Closes dialog with QDialog.Accepted
        self.button_box.rejected.connect(self.reject) # Closes dialog with QDialog.Rejected

        self.main_layout.addWidget(self.button_box)

        self.load_template_settings()
        
    @Slot(str)
    def on_template_selected(self, template_name: str):
        if template_name and template_name in self.templates_data_copy:
            # Before switching, consider saving any changes from UI to self.templates_data_copy[self.currently_editing_template_name]
            # For now, we just switch and reload.
            self.currently_editing_template_name = template_name
            self.load_template_settings()

    def load_template_settings(self):
        # In the future, this will populate UI controls from self.current_template_data
        if self.currently_editing_template_name:
            current_settings = self.templates_data_copy.get(self.currently_editing_template_name, {})
            self.placeholder_label.setText(f"Editing: {self.currently_editing_template_name}\n"
                                           f"Settings: {current_settings.get('font', {}).get('family', 'N/A')}, "
                                           f"{current_settings.get('font', {}).get('size', 'N/A')}pt, "
                                           f"Color: {current_settings.get('color', 'N/A')}")
            print(f"Template Editor: Loaded settings for '{self.currently_editing_template_name}': {current_settings}")

    def get_updated_templates(self): # Renamed method
        # In the future, this will collect data from UI controls and update self.templates_data_copy[self.currently_editing_template_name]
        print(f"Template Editor: 'OK' clicked. Returning updated templates collection.")
        return self.templates_data_copy # Return the (potentially modified) copy
