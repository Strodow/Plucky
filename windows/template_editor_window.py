import copy # For deep copying templates
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox,
    QComboBox, QWidget, QScrollArea, QFormLayout, QInputDialog, QMessageBox, QCheckBox,
    QTabWidget, QFontComboBox, QSpinBox, QColorDialog, QLineEdit,
    QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsDropShadowEffect # New for QGraphicsScene
)
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QTextCharFormat, QTextCursor # For font and color manipulation, and QPainter, Added QPen, QTextCharFormat, QTextCursor
from PySide6.QtCore import Qt, Slot, QDir, QFileInfo, Signal # Added Signal
from PySide6.QtUiTools import QUiLoader

from data_models.slide_data import DEFAULT_TEMPLATE # To access initial defaults

class OutlinedGraphicsTextItem(QGraphicsTextItem):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._outline_pen = QPen(Qt.PenStyle.NoPen)
        self._text_fill_color = QColor(Qt.GlobalColor.black)
        self._has_outline = False
        self._current_font = QFont() # Store the current font

        # Initialize with default font and color to ensure _apply_format_to_document works
        super().setFont(self._current_font)
        super().setDefaultTextColor(self._text_fill_color)

        if text:
            self.setPlainText(text) # This will call _apply_format_to_document

    def setOutline(self, color: QColor, thickness: int):
        if thickness > 0 and color.isValid():
            # The pen width for setTextOutline is the actual stroke width.
            self._outline_pen = QPen(color, float(thickness))
            self._outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin) # Makes corners look better
            self._has_outline = True
        else:
            self._outline_pen = QPen(Qt.PenStyle.NoPen)
            self._has_outline = False
        self._apply_format_to_document()

    def setTextFillColor(self, color: QColor):
        self._text_fill_color = color
        # Also call super's method if it's used for default text color elsewhere
        super().setDefaultTextColor(color)
        self._apply_format_to_document()

    def setFont(self, font: QFont):
        self._current_font = font
        super().setFont(font)
        # When font changes, we need to re-apply the whole format
        self._apply_format_to_document()

    def setPlainText(self, text: str):
        super().setPlainText(text)
        # After text is set/changed, re-apply the format
        self._apply_format_to_document()

    def setHtml(self, html: str):
        super().setHtml(html)
        # After html is set/changed, re-apply the format
        self._apply_format_to_document()

    def _apply_format_to_document(self):
        if not self.document():  # Document might not exist if no text/HTML has been set
            return

        self.prepareGeometryChange() # Important if formatting affects bounding rect

        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)

        text_format = QTextCharFormat()
        # Apply all relevant properties in one go
        text_format.setFont(self._current_font)
        text_format.setForeground(self._text_fill_color) # This is the brush for the text fill

        if self._has_outline:
            text_format.setTextOutline(self._outline_pen)
        else:
            # Explicitly remove outline by setting a NoPen
            text_format.setTextOutline(QPen(Qt.PenStyle.NoPen))

        cursor.mergeCharFormat(text_format)
        # self.update() # mergeCharFormat usually triggers necessary updates

class TemplateEditorWindow(QDialog):
    # Signal to indicate that the current templates (styles, etc.) should be saved
    templates_save_requested = Signal(dict)

    def __init__(self, all_templates: dict, parent=None):
        super().__init__(parent)

        # Load the UI file
        # Assuming the .ui file is in the same directory as this .py file
        script_file_info = QFileInfo(__file__) # Get info about the current script file
        script_directory_path = script_file_info.absolutePath() # Get the absolute path of the directory
        script_qdir = QDir(script_directory_path) # Create a QDir object for that directory
        ui_file_path = script_qdir.filePath("template_editor_window.ui") # Construct path to .ui file

        loader = QUiLoader()
        self.ui = loader.load(ui_file_path, self)

        # --- Access widgets from the loaded UI (Styles Tab) ---
        self.style_selector_combo: QComboBox = self.ui.findChild(QComboBox, "style_selector_combo")
        self.add_style_button: QPushButton = self.ui.findChild(QPushButton, "add_style_button")
        self.remove_style_button: QPushButton = self.ui.findChild(QPushButton, "remove_style_button")
        
        self.preview_text_input_edit: QLineEdit = self.ui.findChild(QLineEdit, "preview_text_input_edit")
        self.font_family_combo: QFontComboBox = self.ui.findChild(QFontComboBox, "font_family_combo")
        self.font_size_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "font_size_spinbox")
        self.font_color_button: QPushButton = self.ui.findChild(QPushButton, "font_color_button")
        self.font_color_preview_label: QLabel = self.ui.findChild(QLabel, "font_color_preview_label")
        
        self.force_caps_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "force_caps_checkbox")
        self.text_shadow_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "text_shadow_checkbox")
        self.text_outline_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "text_outline_checkbox")
        
        # Shadow Detail Controls
        self.shadow_properties_group = self.ui.findChild(QWidget, "shadow_properties_group") # QGroupBox is a QWidget
        self.shadow_x_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_x_spinbox")
        self.shadow_y_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_y_spinbox")
        self.shadow_blur_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_blur_spinbox")
        self.shadow_color_button: QPushButton = self.ui.findChild(QPushButton, "shadow_color_button")
        self.shadow_color_preview_label: QLabel = self.ui.findChild(QLabel, "shadow_color_preview_label")
        
        # Outline Detail Controls
        self.outline_properties_group = self.ui.findChild(QWidget, "outline_properties_group") # QGroupBox is a QWidget
        self.outline_thickness_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "outline_thickness_spinbox")
        self.outline_color_button: QPushButton = self.ui.findChild(QPushButton, "outline_color_button")
        self.outline_color_preview_label: QLabel = self.ui.findChild(QLabel, "outline_color_preview_label")

        # Graphics View for Style Preview
        self.style_preview_graphics_view: QGraphicsView = self.ui.findChild(QGraphicsView, "style_preview_graphics_view")
        self.style_preview_scene = QGraphicsScene(self)
        self.style_preview_graphics_view.setScene(self.style_preview_scene)
        self.style_preview_text_item = OutlinedGraphicsTextItem() # Use the new custom item
        self.style_preview_text_item.setFont(QFont()) # Initialize with a default font
        self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black)) # Initialize fill
        self.style_preview_scene.addItem(self.style_preview_text_item)
        self.style_preview_graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style_preview_graphics_view.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Initialize a variable to store the current font color
        self._current_style_font_color = QColor(Qt.GlobalColor.black) 
        self._current_shadow_color = QColor(0,0,0,180) # Default shadow: semi-transparent black
        self._current_outline_color = QColor(Qt.GlobalColor.black) # Default outline: solid black

        # Set the layout for the QDialog itself if not handled by QUiLoader correctly for top-level
        if self.layout() is None: # Check if a layout is already set
            main_layout_from_ui = self.ui.layout()
            if main_layout_from_ui:
                self.setLayout(main_layout_from_ui)
            else: # Fallback if the .ui file's top widget doesn't have a layout for the dialog
                fallback_layout = QVBoxLayout(self)
                fallback_layout.addWidget(self.ui)
                self.setLayout(fallback_layout)

        self.setWindowTitle(self.ui.windowTitle()) # Set window title from UI file
        self.resize(self.ui.size()) # Set initial size from UI file

        # --- Style Definitions Data ---
        self.style_definitions = {} 
        # Example structure for a style:
        # {
        #     "font_family": "Arial", "font_size": 12, "font_color": "#RRGGBB", 
        #     "preview_text": "...", "force_all_caps": False, 
        #     "text_shadow": False, 
        #     "shadow_x": 1, "shadow_y": 1, "shadow_blur": 2, "shadow_color": "#000000B4",
        #     "text_outline": False,
        #     "outline_thickness": 1, "outline_color": "#000000"
        # }
        self._currently_editing_style_name: str | None = None

        # Load existing styles from the passed 'all_templates' dictionary
        # Make a deep copy to avoid modifying the original dict directly until "OK"
        self.style_definitions = copy.deepcopy(all_templates.get("styles", {}))

        # If, after loading, there are no styles, create a default one.
        if not self.style_definitions: # Check if it's still empty
            default_style_props = {
                "font_family": self.font_family_combo.font().family(), # Get default from combo
                "font_size": self.font_size_spinbox.value(),
                "font_color": self._current_style_font_color.name(), # Store as hex string
                "preview_text": "Sample Text Aa Bb Cc", # Initial text
                "force_all_caps": False,
                "text_shadow": False,
                "text_outline": False,
                "shadow_x": self.shadow_x_spinbox.value(), "shadow_y": self.shadow_y_spinbox.value(), 
                "shadow_blur": self.shadow_blur_spinbox.value(), "shadow_color": self._current_shadow_color.name(QColor.NameFormat.HexArgb),
                "outline_thickness": self.outline_thickness_spinbox.value(), "outline_color": self._current_outline_color.name(),
            }
            self.style_definitions["Default Style"] = default_style_props
        # --- Connect signals from the loaded UI ---
        self.ui.button_box.accepted.connect(self.accept)
        self.ui.button_box.rejected.connect(self.reject)

        # Add a "Save" button to the dialog's button box
        self.save_button = QPushButton("Save")
        self.ui.button_box.addButton(self.save_button, QDialogButtonBox.ButtonRole.ApplyRole) # ApplyRole is good for "save and continue"
        self.save_button.clicked.connect(self._handle_save_action)
        # Tooltip for clarity
        self.save_button.setToolTip("Save current changes and continue editing.")

        # --- Style Tab Connections ---
        self.add_style_button.clicked.connect(self.add_new_style_definition)
        self.remove_style_button.clicked.connect(self.remove_selected_style_definition)
        self.style_selector_combo.currentTextChanged.connect(self.on_style_selected)

        self.preview_text_input_edit.textChanged.connect(self.update_style_from_preview_text_input)
        self.font_family_combo.currentFontChanged.connect(self.update_style_from_font_controls)
        self.font_size_spinbox.valueChanged.connect(self.update_style_from_font_controls)
        self.font_color_button.clicked.connect(self.choose_style_font_color)
        
        self.force_caps_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        self.text_shadow_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        self.text_outline_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        
        # Shadow detail connections
        self.shadow_x_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_y_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_blur_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_color_button.clicked.connect(self.choose_shadow_color)
        # Outline detail connections
        self.outline_thickness_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.outline_color_button.clicked.connect(self.choose_outline_color)

        self._populate_style_selector()
        if self.style_selector_combo.count() > 0:
            # Set the index first
            self.style_selector_combo.setCurrentIndex(0)
            # Manually call on_style_selected to ensure it runs for the initial item,
            # in case setCurrentIndex(0) doesn't trigger currentTextChanged if the
            # text was somehow considered unchanged by Qt's internal state.
            print(f"DEBUG: __init__ - Manually calling on_style_selected with: '{self.style_selector_combo.currentText()}'") # DEBUG
            self.on_style_selected(self.style_selector_combo.currentText())
        else:
            self._clear_style_controls() # No styles, clear controls
            self._update_style_remove_button_state()
            
        # Initial state for detail groups
        self._toggle_shadow_detail_group()
        self._toggle_outline_detail_group()

    # --- Style Tab Methods ---
    def _populate_style_selector(self):
        self.style_selector_combo.blockSignals(True)
        self.style_selector_combo.clear()
        self.style_selector_combo.addItems(self.style_definitions.keys())
        self.style_selector_combo.blockSignals(False)

    @Slot()
    def add_new_style_definition(self):
        style_name, ok = QInputDialog.getText(self, "New Style", "Enter name for the new style:")
        if ok and style_name:
            style_name = style_name.strip()
            if not style_name:
                QMessageBox.warning(self, "Invalid Name", "Style name cannot be empty.")
                return
            if style_name in self.style_definitions:
                QMessageBox.warning(self, "Name Exists", f"A style named '{style_name}' already exists.")
                return

            new_style_props = {
                "font_family": self.font_family_combo.font().family(),
                "font_size": self.font_size_spinbox.value(),
                "font_color": QColor(Qt.GlobalColor.black).name(), # Default to black
                "preview_text": "New Style Text",
                "force_all_caps": False,
                "text_shadow": False,
                "text_outline": False,
                "shadow_x": 1, "shadow_y": 1, "shadow_blur": 2, "shadow_color": QColor(0,0,0,180).name(QColor.NameFormat.HexArgb),
                "outline_thickness": 1, "outline_color": QColor(Qt.GlobalColor.black).name(),

            }
            self.style_definitions[style_name] = new_style_props
            self._populate_style_selector()
            self.style_selector_combo.setCurrentText(style_name) # Triggers on_style_selected
        elif ok and not style_name.strip():
            QMessageBox.warning(self, "Invalid Name", "Style name cannot be empty.")

    @Slot()
    def remove_selected_style_definition(self):
        if not self._currently_editing_style_name:
            return
        if len(self.style_definitions) <= 1: # Prevent deleting the last style
            QMessageBox.warning(self, "Cannot Remove", "Cannot remove the last style definition.")
            return

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Are you sure you want to remove the style '{self._currently_editing_style_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.style_definitions[self._currently_editing_style_name]
            self._currently_editing_style_name = None
            self._populate_style_selector()
            if self.style_selector_combo.count() > 0:
                self.style_selector_combo.setCurrentIndex(0)
            else: # Should not happen due to the "last style" check
                self._clear_style_controls()

    @Slot(str)
    def on_style_selected(self, style_name: str):
        print(f"DEBUG: on_style_selected called with style_name: '{style_name}'") # DEBUG
        if not style_name or style_name not in self.style_definitions:
            self._clear_style_controls()
            self._currently_editing_style_name = None
            print(f"DEBUG: on_style_selected - style_name invalid or not found. _currently_editing_style_name set to None.") # DEBUG
            return

        self._currently_editing_style_name = style_name # This sets it
        style_props = self.style_definitions[style_name]

        # Block signals while setting UI to prevent feedback loops
        self.preview_text_input_edit.blockSignals(True)
        self.font_family_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)
        self.force_caps_checkbox.blockSignals(True)
        self.text_shadow_checkbox.blockSignals(True)
        self.text_outline_checkbox.blockSignals(True)
        self.shadow_x_spinbox.blockSignals(True)
        self.shadow_y_spinbox.blockSignals(True)
        self.shadow_blur_spinbox.blockSignals(True)
        self.shadow_color_button.blockSignals(True) # Not strictly necessary but good practice
        self.outline_thickness_spinbox.blockSignals(True)
        self.outline_color_button.blockSignals(True) # Not strictly necessary

        self.preview_text_input_edit.setText(style_props.get("preview_text", "Sample Text"))
        self.font_family_combo.setCurrentFont(QFont(style_props.get("font_family", "Arial")))
        self.font_size_spinbox.setValue(style_props.get("font_size", 12))
        
        self._current_style_font_color = QColor(style_props.get("font_color", "#000000"))
        self._update_font_color_preview_label()
        
        self.force_caps_checkbox.setChecked(style_props.get("force_all_caps", False))
        self.text_shadow_checkbox.setChecked(style_props.get("text_shadow", False))
        self.text_outline_checkbox.setChecked(style_props.get("text_outline", False))
        
        self.shadow_x_spinbox.setValue(style_props.get("shadow_x", 1))
        self.shadow_y_spinbox.setValue(style_props.get("shadow_y", 1))
        self.shadow_blur_spinbox.setValue(style_props.get("shadow_blur", 2))
        self._current_shadow_color = QColor(style_props.get("shadow_color", QColor(0,0,0,180).name(QColor.NameFormat.HexArgb)))
        self._update_shadow_color_preview_label()
        
        self.outline_thickness_spinbox.setValue(style_props.get("outline_thickness", 1))
        self._current_outline_color = QColor(style_props.get("outline_color", QColor(Qt.GlobalColor.black).name()))
        self._update_outline_color_preview_label()

        self.preview_text_input_edit.blockSignals(False)
        self.font_family_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.force_caps_checkbox.blockSignals(False)
        self.text_shadow_checkbox.blockSignals(False)
        self.text_outline_checkbox.blockSignals(False)
        self.shadow_x_spinbox.blockSignals(False)
        self.shadow_y_spinbox.blockSignals(False)
        self.shadow_blur_spinbox.blockSignals(False)
        self.shadow_color_button.blockSignals(False) # Unblock shadow color button
        self.outline_thickness_spinbox.blockSignals(False)
        self.outline_color_button.blockSignals(False) # Unblock outline color button

        print(f"DEBUG: on_style_selected - _currently_editing_style_name is now: '{self._currently_editing_style_name}'") # DEBUG
        self._apply_style_to_preview_area()
        self._update_style_remove_button_state()
        self._toggle_shadow_detail_group() # Update enabled state of shadow group
        self._toggle_outline_detail_group() # Update enabled state of outline group

    @Slot(str)
    def update_style_from_preview_text_input(self, text: str):
        print(f"DEBUG: update_style_from_preview_text_input called with text: '{text}'") # DEBUG
        print(f"DEBUG: At start of update_style_from_preview_text_input, _currently_editing_style_name is: '{self._currently_editing_style_name}'") # DEBUG
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            print(f"DEBUG: Condition PASSED. Updating preview for '{self._currently_editing_style_name}'.") # DEBUG
            self.style_definitions[self._currently_editing_style_name]["preview_text"] = text
            self._apply_style_to_preview_area() # Update the preview label's text
            print(f"DEBUG: Updated style_definitions for '{self._currently_editing_style_name}', preview_text is now: '{self.style_definitions[self._currently_editing_style_name]['preview_text']}'") # DEBUG
        else: # DEBUG
            print(f"DEBUG: Condition FAILED. _currently_editing_style_name: '{self._currently_editing_style_name}', in definitions: {self._currently_editing_style_name in self.style_definitions if self._currently_editing_style_name else 'N/A'}") # DEBUG

    @Slot()
    def update_style_from_font_controls(self):
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            style_props = self.style_definitions[self._currently_editing_style_name]
            style_props["font_family"] = self.font_family_combo.currentFont().family()
            style_props["font_size"] = self.font_size_spinbox.value()
            # Color is handled by choose_style_font_color
            self._apply_style_to_preview_area()
            
    @Slot()
    def update_style_from_formatting_controls(self):
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            style_props = self.style_definitions[self._currently_editing_style_name]
            style_props["force_all_caps"] = self.force_caps_checkbox.isChecked()
            style_props["text_shadow"] = self.text_shadow_checkbox.isChecked()
            style_props["text_outline"] = self.text_outline_checkbox.isChecked()
            
            style_props["shadow_x"] = self.shadow_x_spinbox.value()
            style_props["shadow_y"] = self.shadow_y_spinbox.value()
            style_props["shadow_blur"] = self.shadow_blur_spinbox.value()
            # Shadow color is updated by its own picker
            style_props["outline_thickness"] = self.outline_thickness_spinbox.value()
            # Outline color is updated by its own picker
            self._apply_style_to_preview_area()
            self._toggle_shadow_detail_group() # Enable/disable based on checkbox
            print(f"DEBUG: Shadow group enabled: {self.shadow_properties_group.isEnabled()}, shadow_color_button enabled: {self.shadow_color_button.isEnabled()}") # DEBUG
            self._toggle_outline_detail_group() # Enable/disable based on checkbox
            print(f"DEBUG: Outline group enabled: {self.outline_properties_group.isEnabled()}, outline_color_button enabled: {self.outline_color_button.isEnabled()}") # DEBUG


    def load_template_settings(self):
        # TODO: This method needs a complete rewrite.
        # It will involve populating the controls within the active tab of self.ui.main_tab_widget
        # based on the selected Layout, Style, or Master Template.
        print(f"Template Editor: load_template_settings() called - needs rewrite for new UI.")

    @Slot()
    def choose_style_font_color(self):
        if not self._currently_editing_style_name: return

        initial_color = self._current_style_font_color
        color = QColorDialog.getColor(initial_color, self, "Choose Font Color")
        if color.isValid():
            self._current_style_font_color = color
            self.style_definitions[self._currently_editing_style_name]["font_color"] = color.name() # Store as hex
            self._update_font_color_preview_label()
            self._apply_style_to_preview_area()

    @Slot()
    def choose_shadow_color(self):
        if not self._currently_editing_style_name: return
        initial_color = self._current_shadow_color
        # Allow choosing alpha for shadow color
        color = QColorDialog.getColor(initial_color, self, "Choose Shadow Color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self._current_shadow_color = color
            self.style_definitions[self._currently_editing_style_name]["shadow_color"] = color.name(QColor.NameFormat.HexArgb)
            self._update_shadow_color_preview_label()
            self._apply_style_to_preview_area()
            
    @Slot()
    def choose_outline_color(self):
        if not self._currently_editing_style_name: return
        initial_color = self._current_outline_color
        color = QColorDialog.getColor(initial_color, self, "Choose Outline Color") # No alpha for basic outline usually
        if color.isValid():
            self._current_outline_color = color
            self.style_definitions[self._currently_editing_style_name]["outline_color"] = color.name()
            self._update_outline_color_preview_label()
            self._apply_style_to_preview_area()

    def _update_font_color_preview_label(self):
        palette = self.font_color_preview_label.palette()
        palette.setColor(QPalette.ColorRole.Window, self._current_style_font_color) # QPalette.Window is background for QLabel
        self.font_color_preview_label.setPalette(palette)
        # Ensure the label updates its display if its background is transparent by default
        self.font_color_preview_label.setAutoFillBackground(True) 
        self.font_color_preview_label.update()

        
    def _update_shadow_color_preview_label(self):
        self.shadow_color_preview_label.setStyleSheet(f"background-color: {self._current_shadow_color.name(QColor.NameFormat.HexArgb)};")

    def _update_outline_color_preview_label(self):
        self.outline_color_preview_label.setStyleSheet(f"background-color: {self._current_outline_color.name()};")

    def _apply_style_to_preview_area(self):
        print(f"DEBUG: _apply_style_to_preview_area called. Current style: '{self._currently_editing_style_name}'") # DEBUG
        if not self._currently_editing_style_name or self._currently_editing_style_name not in self.style_definitions:
            default_font = QFont()
            self.style_preview_text_item.setFont(default_font)
            self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black))
            self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # No outline
            self.style_preview_text_item.setPlainText("Select a style to preview.")
            self.style_preview_text_item.setGraphicsEffect(None) # Remove effects
            self.style_preview_scene.update()
            return
        print(f"DEBUG: Applying style for '{self._currently_editing_style_name}'") # DEBUG

        style_props = self.style_definitions[self._currently_editing_style_name]
        font_family = style_props.get("font_family", "Arial")
        font_size = style_props.get("font_size", 12)
        font_color_hex = style_props.get("font_color", "#000000")
        force_caps = style_props.get("force_all_caps", False)
        has_shadow = style_props.get("text_shadow", False)
        has_outline = style_props.get("text_outline", False)
        
        shadow_x = style_props.get("shadow_x", 1)
        shadow_y = style_props.get("shadow_y", 1)
        shadow_blur = style_props.get("shadow_blur", 2)
        shadow_color_hexargb = style_props.get("shadow_color", QColor(0,0,0,180).name(QColor.NameFormat.HexArgb))
        outline_thickness = style_props.get("outline_thickness", 1)
        outline_color_hex = style_props.get("outline_color", "#000000")
        preview_text = style_props.get("preview_text", "Sample Text")

        # ---- ADDING MORE DEBUG PRINTS HERE ----
        print(f"DEBUG: _apply_style_to_preview_area - has_shadow: {has_shadow}, has_outline: {has_outline}")
        print(f"DEBUG: _apply_style_to_preview_area - shadow_color: {shadow_color_hexargb}, shadow_x: {shadow_x}, shadow_y: {shadow_y}, shadow_blur: {shadow_blur}")
        print(f"DEBUG: _apply_style_to_preview_area - outline_color: {outline_color_hex}, outline_thickness: {outline_thickness}")
        if force_caps:
            preview_text = preview_text.upper()

        # Apply to OutlinedGraphicsTextItem
        current_font = QFont(font_family, font_size)
        self.style_preview_text_item.setFont(current_font)
        self.style_preview_text_item.setTextFillColor(QColor(font_color_hex))
        self.style_preview_text_item.setPlainText(preview_text)

        # --- Outline ---
        # This needs to be applied after font and color, or ensure _apply_format_to_document
        # correctly re-applies everything. Our OutlinedGraphicsTextItem is designed to do so.
        if has_outline:
            outline_qcolor = QColor(outline_color_hex)
            actual_thickness = max(1, outline_thickness) # Ensure thickness is at least 1 if outline is enabled
            self.style_preview_text_item.setOutline(outline_qcolor, actual_thickness)
            print(f"DEBUG: Applied Outline: Color {outline_color_hex}, Thickness {actual_thickness}")
        else:
            # Remove outline by setting thickness to 0
            self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # Color doesn't matter if pen is NoPen
            print("DEBUG: Removed Outline")

        # --- Shadow Effect ---
        current_effect = self.style_preview_text_item.graphicsEffect()
        if has_shadow:
            if not isinstance(current_effect, QGraphicsDropShadowEffect):
                shadow_effect = QGraphicsDropShadowEffect(self)
                self.style_preview_text_item.setGraphicsEffect(shadow_effect)
            else:
                shadow_effect = current_effect
            
            shadow_effect.setXOffset(shadow_x)
            shadow_effect.setYOffset(shadow_y)
            shadow_effect.setBlurRadius(shadow_blur * 2) # QGraphicsDropShadowEffect blur is different from CSS
            shadow_effect.setColor(QColor(shadow_color_hexargb))
            print(f"DEBUG: Applied QGraphicsDropShadowEffect: X:{shadow_x}, Y:{shadow_y}, Blur:{shadow_blur*2}, Color:{shadow_color_hexargb}")
        else:
            if isinstance(current_effect, QGraphicsDropShadowEffect): # Remove only if it's our shadow
                self.style_preview_text_item.setGraphicsEffect(None)
                print("DEBUG: Removed QGraphicsDropShadowEffect")

        # Adjust view / item position if necessary
        # For simplicity, let's ensure the item is at the top-left of the scene.
        # And then fit the view to the item.
        self.style_preview_text_item.setPos(0, 0) 

        # Set text width for wrapping (important for QGraphicsTextItem)
        # Use the view's width as a basis, minus some padding
        available_width = self.style_preview_graphics_view.viewport().width() - 20 # 10px padding each side
        print(f"DEBUG: _apply_style_to_preview_area - Viewport width: {self.style_preview_graphics_view.viewport().width()}, available_width for text: {available_width}") # DEBUG
        print(f"DEBUG: _apply_style_to_preview_area - TextItem boundingRect BEFORE setTextWidth: {self.style_preview_text_item.boundingRect()}") # DEBUG

        if available_width > 0 :
            self.style_preview_text_item.setTextWidth(available_width)
        else:
            self.style_preview_text_item.setTextWidth(-1) # No wrapping if view not sized yet

        self.style_preview_scene.update() # Ensure scene redraws
        # It's good to allow the scene to process updates which might affect bounding rect after setTextWidth
        print(f"DEBUG: _apply_style_to_preview_area - TextItem boundingRect AFTER setTextWidth: {self.style_preview_text_item.boundingRect()}") # DEBUG
        self.style_preview_graphics_view.fitInView(self.style_preview_text_item, Qt.AspectRatioMode.KeepAspectRatio)

    @Slot()
    def add_new_template(self):
        # TODO: This is for adding old-style templates.
        # You'll need separate logic for adding Layouts, Styles, and Master Templates
        # triggered by buttons within their respective tabs.
        new_template_name, ok = QInputDialog.getText(self, "New Template", "Enter name for the new template:")
        if ok and new_template_name:
            new_template_name = new_template_name.strip()
            # This method is now largely deprecated in favor of add_new_style_definition, etc.
            # For now, just print a message.
            print(f"Template Editor: add_new_template called with '{new_template_name}' - this is for old system.")

        elif ok and not new_template_name.strip():
             QMessageBox.warning(self, "Invalid Name", "Template name cannot be empty.")

    @Slot()
    def remove_selected_template(self):
        # TODO: This is for removing old-style templates.
        # Needs to be adapted for Layouts, Styles, Master Templates.
        print(f"Template Editor: remove_selected_template called - this is for old system.")

    def _clear_style_controls(self):
        self.preview_text_input_edit.blockSignals(True)
        self.font_family_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)
        self.force_caps_checkbox.blockSignals(True)
        self.text_shadow_checkbox.blockSignals(True)
        self.text_outline_checkbox.blockSignals(True)
        self.shadow_x_spinbox.blockSignals(True)
        self.shadow_y_spinbox.blockSignals(True)
        self.shadow_blur_spinbox.blockSignals(True)
        self.shadow_color_button.blockSignals(True)
        self.outline_thickness_spinbox.blockSignals(True)
        self.outline_color_button.blockSignals(True)

        self.preview_text_input_edit.clear()
        self.font_family_combo.setCurrentIndex(-1) # Or set to a default font
        self.font_size_spinbox.setValue(self.font_size_spinbox.minimum()) # Or a default size
        
        self._current_style_font_color = QColor(Qt.GlobalColor.black)
        self._update_font_color_preview_label()
        
        self.style_preview_text_item.setFont(QFont()) # Reset font
        self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black)) # Reset fill
        self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # Reset outline
        self.style_preview_text_item.setPlainText("No style selected or defined.") # Set text last
        
        self.force_caps_checkbox.setChecked(False)
        self.text_shadow_checkbox.setChecked(False)
        self.text_outline_checkbox.setChecked(False)
        
        self.shadow_x_spinbox.setValue(1)
        self.shadow_y_spinbox.setValue(1)
        self.shadow_blur_spinbox.setValue(2)
        self._current_shadow_color = QColor(0,0,0,180)
        self._update_shadow_color_preview_label()
        
        self.outline_thickness_spinbox.setValue(1)
        self._current_outline_color = QColor(Qt.GlobalColor.black)
        self._update_outline_color_preview_label()
        
        # Remove any graphics effects
        self.style_preview_text_item.setGraphicsEffect(None)
        self.style_preview_scene.update()

        self.preview_text_input_edit.blockSignals(False)
        self.font_family_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.force_caps_checkbox.blockSignals(False)
        self.text_shadow_checkbox.blockSignals(False)
        self.text_outline_checkbox.blockSignals(False)
        self.shadow_x_spinbox.blockSignals(False)
        self.shadow_y_spinbox.blockSignals(False)
        self.shadow_blur_spinbox.blockSignals(False)
        self.outline_thickness_spinbox.blockSignals(False)
        self.shadow_color_button.blockSignals(False) # Ensure unblocked here too
        self.outline_color_button.blockSignals(False)# Ensure unblocked here too
        
        self._toggle_shadow_detail_group()
        self._toggle_outline_detail_group()

    @Slot()
    def _handle_save_action(self):
        """Handles the action when the 'Save' button is clicked."""
        current_template_data = self.get_updated_templates()
        self.templates_save_requested.emit(current_template_data)
        print("Template Editor: 'Save' button clicked. templates_save_requested signal emitted.")
        self._toggle_outline_detail_group()

    def _update_style_remove_button_state(self):
        can_remove = self.style_selector_combo.count() > 1 and self._currently_editing_style_name is not None
        self.remove_style_button.setEnabled(can_remove)

    def get_updated_templates(self): # Renamed method
        # TODO: This method needs a complete rewrite.
        # It should gather the data for Layouts, Styles, and Master Templates
        # from the UI controls within each tab and return them in a structured way
        # (e.g., a dictionary with keys 'layouts', 'styles', 'master_templates').
        print(f"Template Editor: 'OK' clicked. Returning current style definitions.")
        # For now, just return the style definitions. This will need to be expanded.
        return {"styles": copy.deepcopy(self.style_definitions)}

    def _update_remove_button_state(self):
        """Enable/disable the remove button based on the selected template."""
        # TODO: This is for the old remove button.
        # Each tab (Layouts, Styles, Master Templates) will need its own logic
        # for enabling/disabling its respective remove button.
        # This method is now superseded by _update_style_remove_button_state for the styles tab.
        print(f"Template Editor: _update_remove_button_state() called - largely deprecated.")
        self._update_style_remove_button_state() # Call the new specific one for styles

    def _toggle_shadow_detail_group(self):
        is_enabled = self.text_shadow_checkbox.isChecked()
        self.shadow_properties_group.setEnabled(is_enabled)

    def _toggle_outline_detail_group(self):
        is_enabled = self.text_outline_checkbox.isChecked()
        self.outline_properties_group.setEnabled(is_enabled)
