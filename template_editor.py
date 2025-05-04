import sys
import json
import os
import logging
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog, QSizePolicy,
    QPushButton, QSpacerItem, QTextEdit, QFormLayout, QLineEdit, QSpinBox,
    QCheckBox, QComboBox, QColorDialog, QGroupBox, QScrollArea, QDialogButtonBox
)
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QFontDatabase, QTextOption, QFontInfo, QPalette
from PySide6.QtCore import Qt, QRectF, QSize, QRect
import copy # For deep copying template data
class TemplatePreviewWidget(QWidget):
    """Widget to display a visual preview of the template, maintaining a 16:9 aspect ratio."""
    def __init__(self, template_data, parent=None):
        super().__init__(parent)
        self.template_data = template_data
        # Set a base minimum size that respects the 16:9 ratio
        self.setMinimumSize(320, 180) # Example base 16:9 size (e.g., 320x180 is 16:9)
        # Use Expanding policy to allow it to take available space
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.sample_text = "Sample Text\nSecond Line" # Default sample text

    def set_template_data(self, template_data):
        """Updates the template data used for drawing."""
        self.template_data = template_data
        self.update() # Trigger repaint when data changes

    def set_sample_text(self, text):
        """Updates the sample text to be rendered."""
        self.sample_text = text
        self.update() # Trigger repaint when text changes

    def resizeEvent(self, event):
        """Ensures the widget maintains a 16:9 aspect ratio when resized."""
        new_size = event.size()
        new_width = new_size.width()
        new_height = new_size.height()

        # Define the desired aspect ratio (16:9)
        aspect_ratio = 16.0 / 9.0

        # Calculate the dimensions that maintain the aspect ratio
        # We prioritize the larger dimension to avoid shrinking the widget unnecessarily
        if new_width / new_height > aspect_ratio:
            # The current width is too large relative to the height, adjust width
            calculated_width = int(new_height * aspect_ratio)
            self.resize(calculated_width, new_height)
        else:
            # The current height is too large relative to the width, adjust height
            calculated_height = int(new_width / aspect_ratio)
            self.resize(new_width, calculated_height)

        # Call the base class implementation
        super().resizeEvent(event)

    def paintEvent(self, event):
        """Draws the template representation."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        preview_rect = self.rect()
        preview_width = preview_rect.width()
        preview_height = preview_rect.height()

        # --- Draw Checkerboard Background ---
        check_size = 10 # Size of each checkerboard square
        light_color = QColor(200, 200, 200) # Light gray
        dark_color = QColor(150, 150, 150)  # Dark gray

        for y in range(0, preview_height, check_size):
            for x in range(0, preview_width, check_size):
                if (x // check_size + y // check_size) % 2 == 0:
                    painter.fillRect(x, y, check_size, check_size, light_color)
                else:
                    painter.fillRect(x, y, check_size, check_size, dark_color)
        # --- End Checkerboard Background ---


        # --- Draw Bounding Box based on template_data ---
        # Get template settings with defaults
        position_settings = self.template_data.get("position", {"x": "50%", "y": "80%"}) # Default lower center
        max_width_setting = self.template_data.get("max_width", "80%") # Default 80% width
        alignment_setting = self.template_data.get("alignment", "center") # Default center align
        # --- Font Settings ---
        font_settings = self.template_data.get("font", {})
        font_family = font_settings.get("family", "Arial")
        # Read font_size as potentially a percentage string or a fixed point size
        font_size_setting = font_settings.get("size", 58) # Default font size from template
        font_bold = font_settings.get("bold", False)
        font_italic = font_settings.get("italic", False)
        font_underline = font_settings.get("underline", False)

        font_color_hex = self.template_data.get("color", "#FFFFFF") # Default white
        vertical_alignment_setting = self.template_data.get("vertical_alignment", "top") # Default top align
        force_caps = self.template_data.get("force_caps", False) # Get force_caps setting

        # --- Calculate Box Width in Pixels ---
        box_width_pixels = preview_width # Default to full width
        if isinstance(max_width_setting, str) and max_width_setting.endswith('%'):
            try:
                percentage = float(max_width_setting[:-1]) / 100.0
                box_width_pixels = int(preview_width * percentage)
            except ValueError:
                pass # Keep default if parsing fails
        elif isinstance(max_width_setting, (int, float)):
             box_width_pixels = int(max_width_setting)
        box_width_pixels = max(10, min(box_width_pixels, preview_width)) # Clamp width


        # --- Estimate Box Height (e.g., based on width for aspect ratio) ---
        # This estimation is primarily for drawing the dashed bounding box and potentially vertical centering.
        # The text drawing will use the full height of the bounding_rect and be clipped.
        # Since the widget now maintains 16:9, we can use the actual preview_height for a more accurate box height estimate
        # Let's still use a ratio relative to the box width for flexibility in template design
        box_height_pixels_estimated = max(20, int(box_width_pixels / 3)) # Using a 3:1 width-to-height ratio for the box
        box_height_pixels_estimated = min(box_height_pixels_estimated, preview_height) # Clamp height to preview height


        # --- Calculate Anchor Point in Pixels ---
        anchor_x = 0
        anchor_y = 0
        # Calculate X anchor
        pos_x = position_settings.get("x", "50%")
        if isinstance(pos_x, str) and pos_x.endswith('%'):
            anchor_x = int(preview_width * (float(pos_x[:-1]) / 100.0))
        elif isinstance(pos_x, (int, float)):
            anchor_x = int(pos_x)
        # Calculate Y anchor
        pos_y = position_settings.get("y", "80%")
        if isinstance(pos_y, str) and pos_y.endswith('%'):
            anchor_y = int(preview_height * (float(pos_y[:-1]) / 100.0))
        elif isinstance(pos_y, (int, float)):
            anchor_y = int(pos_y)

        # --- Calculate Top-Left Corner (box_x, box_y) based on Anchor and Alignment ---
        # The bounding_rect will define the *area* where text should be drawn and potentially clipped.
        # Its position is based on the anchor and alignment, and its size on max_width and an estimated height (for drawing the box).
        # The actual text drawing will wrap within the width and be clipped by the height if clipping is enabled.

        # Start with a rectangle at the anchor point with calculated width and the estimated height
        bounding_rect = QRectF(anchor_x, anchor_y, box_width_pixels, box_height_pixels_estimated)

        # Adjust X based on horizontal alignment
        if alignment_setting == "center":
            bounding_rect.moveLeft(anchor_x - box_width_pixels // 2)
        elif alignment_setting == "right":
            bounding_rect.moveLeft(anchor_x - box_width_pixels)

        # Adjust Y based on vertical alignment
        if vertical_alignment_setting == "center":
             # Align the center of the estimated box height to the anchor.
             bounding_rect.moveTop(anchor_y - box_height_pixels_estimated // 2)
        elif vertical_alignment_setting == "top":
             # Align the top of the box to the anchor.
             bounding_rect.moveTop(anchor_y)
        elif vertical_alignment_setting == "bottom":
             # Align the bottom of the box to the anchor.
             bounding_rect.moveBottom(anchor_y)


        # Ensure the bounding_rect is within the preview bounds for drawing the dashed line and clipping
        bounding_rect = bounding_rect.intersected(preview_rect.adjusted(1, 1, -1, -1))


        box_pen = QPen(QColor("yellow"), 2, Qt.PenStyle.DashLine) # Dashed yellow line
        painter.setPen(box_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush) # Ensure no fill
        # Draw the dashed bounding box based on the calculated rectangle
        # painter.drawRect(bounding_rect) # Temporarily disable drawing the box itself, focus on text

        # --- Draw Sample Text ---
        if self.sample_text and bounding_rect.isValid():
            # --- Apply Force Caps ---
            text_to_draw = self.sample_text.upper() if force_caps else self.sample_text
            # --- End Apply Force Caps --
            font = QFont()
            # Attempt to set font family
            font.setFamily(font_family)
            # Check if the system resolved the font correctly, otherwise use a default
            if not QFontInfo(font).exactMatch():
                 logging.warning(f"Font family '{font_family}' not found or resolved differently. Using default.")
                 # Keep the default font QFont chose if the specified one isn't exact

            # Calculate actual font size based on 1080p scaling if fixed size is provided
            actual_font_size_pt = 24 # Default if setting is invalid

            if isinstance(font_size_setting, (int, float)):
                base_point_size = float(font_size_setting)
                target_output_height = 1080 # Pixels for 1080p
                current_preview_height = preview_height # Pixels of the current preview widget

                # Calculate the scaled point size for the current preview height
                # We scale the base point size based on the ratio of current height to target height
                if target_output_height > 0: # Avoid division by zero
                    scaling_factor = current_preview_height / target_output_height
                    actual_font_size_pt = int(base_point_size * scaling_factor)
                else:
                     actual_font_size_pt = int(base_point_size) # Use base size if target height is zero or invalid

                # Add a minimum font size to prevent it from being too small
                actual_font_size_pt = max(8, actual_font_size_pt) # Minimum 8 points

            elif isinstance(font_size_setting, str) and font_size_setting.endswith('%'):
                 # --- Keep the previous percentage logic as an alternative if needed ---
                 try:
                    percentage = float(font_size_setting[:-1]) / 100.0
                    actual_font_size_pt = int(preview_height * percentage)
                    actual_font_size_pt = max(8, actual_font_size_pt) # Minimum 8 points
                 except ValueError:
                    logging.warning(f"Invalid font size percentage format: {font_size_setting}. Using default.")
                 # --- End previous percentage logic ---
            else:
                 logging.warning(f"Invalid font size setting: {font_size_setting}. Must be number or percentage string. Using default.")


            font.setPointSize(actual_font_size_pt) # Use the calculated/fixed size

            # Set font styles
            font.setBold(font_bold)
            font.setItalic(font_italic)
            font.setUnderline(font_underline)

            painter.setFont(font)

            # Set text alignment options
            text_option = QTextOption()
            # Align text to the top of the bounding box for drawText
            if alignment_setting == "left":
                text_option.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            elif alignment_setting == "right":
                text_option.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            else: # Default to center
                text_option.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

            text_option.setWrapMode(QTextOption.WrapMode.WordWrap) # Enable wrapping

            # --- Outline Settings ---
            outline_settings = self.template_data.get("outline", {})
            outline_enabled = outline_settings.get("enabled", False)
            outline_color_hex = outline_settings.get("color", "#000000")
            outline_width = outline_settings.get("width", 2)

            # --- Shadow Settings (Basic implementation - QPainter doesn't directly support complex shadows easily) ---
            # For a simple offset shadow, we can draw the text twice.
            # For blur, QGraphicsDropShadowEffect applied to the widget is better, but complex here.
            shadow_settings = self.template_data.get("shadow", {})
            shadow_enabled = shadow_settings.get("enabled", False)
            shadow_color_hex = shadow_settings.get("color", "#000000")
            shadow_offset_x = shadow_settings.get("offset_x", 3)
            shadow_offset_y = shadow_settings.get("offset_y", 3)
            # shadow_blur_radius = shadow_settings.get("blur_radius", 5) # Not easily used with QPainter directly

            # --- Text Drawing ---
            # 1. Draw Shadow (if enabled) - simple offset version
            if shadow_enabled:
                shadow_rect = bounding_rect.translated(shadow_offset_x, shadow_offset_y)
                painter.setPen(QColor(shadow_color_hex))
                painter.drawText(shadow_rect, text_to_draw, text_option) # Use text_to_draw

            # 2. Draw Outline (if enabled) - by drawing multiple offset versions
            if outline_enabled and outline_width > 0:
                painter.setPen(QColor(outline_color_hex))
                # Draw text slightly offset in multiple directions
                for dx in range(-outline_width, outline_width + 1, outline_width):
                     for dy in range(-outline_width, outline_width + 1, outline_width):
                         if dx != 0 or dy != 0: # Don't redraw at the exact center
                             offset_rect = bounding_rect.translated(dx, dy)
                             painter.drawText(offset_rect, text_to_draw, text_option) # Use text_to_draw

            # 3. Draw Main Text (on top)
            painter.setPen(QColor(font_color_hex)) # Set main text color
            painter.drawText(bounding_rect, text_to_draw, text_option) # Use text_to_draw

            # **If clipping was enabled, remember to clear it**
            # painter.setClipping(False)





class TemplateEditorWindow(QDialog):
    """Window for editing template properties."""
    def __init__(self, template_data, parent=None):
        super().__init__(parent)
        # Use a deep copy to avoid modifying the original dict until save
        self.template_data = copy.deepcopy(template_data)
        # Define template file path within the editor instance
        self.CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
        self.TEMPLATE_FILE = os.path.join(self.CONFIG_DIR, 'template.json')
        self.setWindowTitle(f"Edit Template: {self.template_data.get('template_name', 'Unnamed Template')}")
        self.setMinimumSize(800, 600) # Increased size for controls

        # Main layout: Preview on left, controls on right
        main_layout = QHBoxLayout(self)

        # --- Top Bar for Name and Refresh ---
        top_bar_layout = QHBoxLayout() # This will go inside the left_layout
        self.name_label = QLabel(f"Template: {template_data.get('template_name', 'Unnamed Template')}")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) # Allow label to expand
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Reload template.json")
        self.refresh_button.clicked.connect(self._refresh_template)

        top_bar_layout.addWidget(self.name_label)
        top_bar_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)) # Spacer
        top_bar_layout.addWidget(self.refresh_button)
        # --- End Top Bar ---

        # --- Left Panel (Preview & Sample Text) ---
        left_layout = QVBoxLayout()
        left_layout.addLayout(top_bar_layout)
        self.preview_widget = TemplatePreviewWidget(self.template_data)

        # --- Sample Text Input ---
        self.sample_text_label = QLabel("Sample Text:")
        self.sample_text_input = QTextEdit()
        self.sample_text_input.setPlaceholderText("Type sample text here...")
        self.sample_text_input.setText(self.preview_widget.sample_text) # Initialize with default
        self.sample_text_input.setMaximumHeight(80) # Limit height of input box
        self.sample_text_input.textChanged.connect(self._on_sample_text_changed)
        # --- End Sample Text Input ---

        left_layout.addWidget(self.preview_widget, 1) # Allow preview to stretch
        left_layout.addWidget(self.sample_text_label)
        left_layout.addWidget(self.sample_text_input)

        # --- Right Panel (Settings) ---
        settings_scroll_area = QScrollArea()
        settings_scroll_area.setWidgetResizable(True)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # Keep controls packed at the top

        # -- Font Group --
        font_group = QGroupBox("Font")
        font_layout = QFormLayout(font_group)

        self.font_family_combo = QComboBox() # Using QComboBox for simplicity, QFontComboBox is better but needs more setup
        self.font_family_combo.addItems(QFontDatabase.families()) # Populate with system fonts
        self.font_family_combo.currentTextChanged.connect(lambda text: self._update_setting(['font', 'family'], text))

        self.font_size_input = QLineEdit() # Use LineEdit to allow % or px
        self.font_size_input.setPlaceholderText("e.g., 58 or 10%")
        self.font_size_input.textChanged.connect(self._update_font_size)

        self.font_bold_check = QCheckBox("Bold")
        self.font_bold_check.toggled.connect(lambda checked: self._update_setting(['font', 'bold'], checked))
        self.font_italic_check = QCheckBox("Italic")
        self.font_italic_check.toggled.connect(lambda checked: self._update_setting(['font', 'italic'], checked))
        self.font_underline_check = QCheckBox("Underline")
        self.font_underline_check.toggled.connect(lambda checked: self._update_setting(['font', 'underline'], checked))
        # --- Add Force Caps Checkbox ---
        self.force_caps_check = QCheckBox("Force Uppercase")
        self.force_caps_check.toggled.connect(lambda checked: self._update_setting(['force_caps'], checked))
        
        font_layout.addRow("Family:", self.font_family_combo)
        font_layout.addRow("Size:", self.font_size_input)
        font_style_layout = QHBoxLayout()
        font_style_layout.addWidget(self.font_bold_check)
        font_style_layout.addWidget(self.font_italic_check)
        font_style_layout.addWidget(self.font_underline_check)
        font_style_layout.addWidget(self.force_caps_check) # Add to layout
        font_layout.addRow("Style:", font_style_layout)
        settings_layout.addWidget(font_group)

        # -- Color --
        color_group = QGroupBox("Color")
        color_layout = QHBoxLayout(color_group)
        self.color_button = QPushButton("Choose Color")
        self.color_button.clicked.connect(self._choose_color)
        self.color_preview = QLabel() # Shows the selected color
        self.color_preview.setMinimumWidth(40)
        self.color_preview.setAutoFillBackground(True)
        color_layout.addWidget(self.color_button)
        color_layout.addWidget(self.color_preview)
        color_layout.addStretch()
        settings_layout.addWidget(color_group)

        # -- Position & Layout Group --
        pos_group = QGroupBox("Position & Layout")
        pos_layout = QFormLayout(pos_group)

        self.pos_x_input = QLineEdit()
        self.pos_x_input.setPlaceholderText("e.g., 50% or 960")
        self.pos_x_input.textChanged.connect(lambda text: self._update_setting(['position', 'x'], text))
        self.pos_y_input = QLineEdit()
        self.pos_y_input.setPlaceholderText("e.g., 80% or 864")
        self.pos_y_input.textChanged.connect(lambda text: self._update_setting(['position', 'y'], text))

        self.align_combo = QComboBox()
        self.align_combo.addItems(["left", "center", "right"])
        self.align_combo.currentTextChanged.connect(lambda text: self._update_setting(['alignment'], text))

        self.valign_combo = QComboBox()
        self.valign_combo.addItems(["top", "center", "bottom"])
        self.valign_combo.currentTextChanged.connect(lambda text: self._update_setting(['vertical_alignment'], text))

        self.max_width_input = QLineEdit()
        self.max_width_input.setPlaceholderText("e.g., 90% or 1728")
        self.max_width_input.textChanged.connect(lambda text: self._update_setting(['max_width'], text))

        pos_layout.addRow("Position X:", self.pos_x_input)
        pos_layout.addRow("Position Y:", self.pos_y_input)
        pos_layout.addRow("Alignment:", self.align_combo)
        pos_layout.addRow("Vertical Align:", self.valign_combo)
        pos_layout.addRow("Max Width:", self.max_width_input)
        settings_layout.addWidget(pos_group)

        # -- Outline Group --
        self.outline_group = QGroupBox("Outline") # Assign to self.outline_group
        self.outline_group.setCheckable(True) # Enable/disable outline
        # Connect toggled signal to update setting AND enable/disable controls
        self.outline_group.toggled.connect(self._on_group_toggled)
        outline_layout = QFormLayout(self.outline_group) # Use self.outline_group here

        self.outline_color_button = QPushButton("Choose Color")
        self.outline_color_button.clicked.connect(self._choose_outline_color)
        self.outline_color_preview = QLabel()
        self.outline_color_preview.setMinimumWidth(40)
        self.outline_color_preview.setAutoFillBackground(True)
        outline_color_layout = QHBoxLayout()
        outline_color_layout.addWidget(self.outline_color_button)
        outline_color_layout.addWidget(self.outline_color_preview)
        outline_color_layout.addStretch()

        self.outline_width_spin = QSpinBox()
        self.outline_width_spin.setMinimum(0)
        self.outline_width_spin.setMaximum(20)
        self.outline_width_spin.valueChanged.connect(lambda value: self._update_setting(['outline', 'width'], value))

        outline_layout.addRow("Color:", outline_color_layout)
        outline_layout.addRow("Width:", self.outline_width_spin)
        settings_layout.addWidget(self.outline_group)

        # -- Shadow Group (Basic) --
        self.shadow_group = QGroupBox("Shadow (Basic Offset)") # Assign to self.shadow_group
        self.shadow_group.setCheckable(True)
        # Connect toggled signal to update setting AND enable/disable controls
        self.shadow_group.toggled.connect(self._on_group_toggled)
        shadow_layout = QFormLayout(self.shadow_group) # Use self.shadow_group here

        self.shadow_color_button = QPushButton("Choose Color")
        self.shadow_color_button.clicked.connect(self._choose_shadow_color)
        self.shadow_color_preview = QLabel()
        self.shadow_color_preview.setMinimumWidth(40)
        self.shadow_color_preview.setAutoFillBackground(True)
        shadow_color_layout = QHBoxLayout()
        shadow_color_layout.addWidget(self.shadow_color_button)
        shadow_color_layout.addWidget(self.shadow_color_preview)
        shadow_color_layout.addStretch()

        self.shadow_offset_x_spin = QSpinBox()
        self.shadow_offset_x_spin.setRange(-50, 50)
        self.shadow_offset_x_spin.valueChanged.connect(lambda value: self._update_setting(['shadow', 'offset_x'], value))
        self.shadow_offset_y_spin = QSpinBox()
        self.shadow_offset_y_spin.setRange(-50, 50)
        self.shadow_offset_y_spin.valueChanged.connect(lambda value: self._update_setting(['shadow', 'offset_y'], value))

        shadow_layout.addRow("Color:", shadow_color_layout)
        shadow_layout.addRow("Offset X:", self.shadow_offset_x_spin)
        shadow_layout.addRow("Offset Y:", self.shadow_offset_y_spin)
        settings_layout.addWidget(self.shadow_group)

        settings_scroll_area.setWidget(settings_widget)

        # --- Bottom Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._save_and_accept) # Save and close
        button_box.rejected.connect(self.reject) # Just close

        # --- Assemble Main Layout ---
        main_layout.addLayout(left_layout, 2) # Give preview more space initially
        main_layout.addWidget(settings_scroll_area, 1)
        left_layout.addWidget(button_box) # Add buttons below preview area

        self._load_settings_to_widgets() # Load initial values

    def _refresh_template(self):
        """Reloads template data from the JSON file and updates the preview."""
        logging.info(f"Refreshing template editor from: {self.TEMPLATE_FILE}")
        try:
            with open(self.TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                new_template_data = json.load(f)

            # Use deepcopy to avoid modifying original until save
            self.template_data = copy.deepcopy(new_template_data)
            self.preview_widget.set_template_data(self.template_data) # Update the preview widget's data
            self.preview_widget.update() # Trigger repaint of the preview

            # Update window title and label in case the name changed
            new_name = self.template_data.get('template_name', 'Unnamed Template')
            self.setWindowTitle(f"Edit Template: {new_name}")
            self.name_label.setText(f"Template: {new_name}")

            self._load_settings_to_widgets() # Reload values into controls

            logging.info("Template editor refreshed successfully.")
        except FileNotFoundError:
            logging.error(f"Template file not found during refresh: {self.TEMPLATE_FILE}")
            # Optionally show a message box to the user
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON during refresh: {self.TEMPLATE_FILE}")
            # Optionally show a message box to the user
        except Exception as e:
            logging.error(f"An unexpected error occurred during template refresh: {e}", exc_info=True)

    def _on_sample_text_changed(self):
        """Called when the text in the sample input box changes."""
        current_text = self.sample_text_input.toPlainText()
        self.preview_widget.set_sample_text(current_text)

    def _on_group_toggled(self, checked):
        """Handles the toggled signal for checkable QGroupBoxes."""
        sender_group = self.sender() # Get the group box that emitted the signal
        if sender_group == self.outline_group:
            setting_key = ['outline', 'enabled']
        elif sender_group == self.shadow_group:
            setting_key = ['shadow', 'enabled']
        else:
            return # Should not happen if connected correctly

        # 1. Update the setting in template_data
        self._update_setting(setting_key, checked)

        # 2. Enable/disable controls within the group
        for child in sender_group.findChildren(QWidget):
            if child != sender_group: # Don't disable the groupbox itself
                child.setEnabled(checked)

    def _update_setting(self, keys, value):
        """Updates a potentially nested setting in template_data and refreshes preview."""
        data = self.template_data
        # Navigate through keys except the last one
        for key in keys[:-1]:
            data = data.setdefault(key, {}) # Create dict if key doesn't exist

        # Set the final value
        data[keys[-1]] = value

        # Refresh the preview
        self.preview_widget.set_template_data(self.template_data)
        # self.preview_widget.update() # set_template_data already calls update

    def _update_font_size(self, text):
        """Handles font size updates, converting to int if possible."""
        if text.endswith('%'):
            try:
                # Keep percentage as string
                _ = float(text[:-1]) # Validate format
                self._update_setting(['font', 'size'], text)
            except ValueError:
                logging.warning(f"Invalid percentage format for font size: {text}")
                # Optionally revert or show error
        else:
            try:
                # Convert to number (int or float)
                size_val = int(text) # Prefer int for point sizes
                self._update_setting(['font', 'size'], size_val)
            except ValueError:
                 logging.warning(f"Invalid numeric format for font size: {text}")
                 # Optionally revert or show error

    def _choose_color(self):
        """Opens a color dialog to choose the main font color."""
        initial_color = QColor(self.template_data.get("color", "#FFFFFF"))
        color = QColorDialog.getColor(initial_color, self, "Choose Font Color")
        if color.isValid():
            hex_color = color.name(QColor.NameFormat.HexRgb)
            self._update_setting(['color'], hex_color)
            self._update_color_preview(self.color_preview, hex_color)

    def _choose_outline_color(self):
        """Opens a color dialog to choose the outline color."""
        initial_color = QColor(self.template_data.get("outline", {}).get("color", "#000000"))
        color = QColorDialog.getColor(initial_color, self, "Choose Outline Color")
        if color.isValid():
            hex_color = color.name(QColor.NameFormat.HexRgb)
            self._update_setting(['outline', 'color'], hex_color)
            self._update_color_preview(self.outline_color_preview, hex_color)

    def _choose_shadow_color(self):
        """Opens a color dialog to choose the shadow color."""
        initial_color = QColor(self.template_data.get("shadow", {}).get("color", "#000000"))
        color = QColorDialog.getColor(initial_color, self, "Choose Shadow Color")
        if color.isValid():
            hex_color = color.name(QColor.NameFormat.HexRgb)
            self._update_setting(['shadow', 'color'], hex_color)
            self._update_color_preview(self.shadow_color_preview, hex_color)

    def _update_color_preview(self, label_widget, hex_color):
        """Updates the background color of a QLabel to show a color preview."""
        palette = label_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(hex_color))
        label_widget.setPalette(palette)

    def _load_settings_to_widgets(self):
        """Loads current template_data values into the editor widgets."""
        # Block signals temporarily to prevent update loops during loading
        for widget in self.findChildren(QWidget):
            widget.blockSignals(True)

        try:
            # Font
            font_settings = self.template_data.get("font", {})
            self.font_family_combo.setCurrentText(font_settings.get("family", "Arial"))
            self.font_size_input.setText(str(font_settings.get("size", 58)))
            self.font_bold_check.setChecked(font_settings.get("bold", False))
            self.font_italic_check.setChecked(font_settings.get("italic", False))
            self.font_underline_check.setChecked(font_settings.get("underline", False))
            self.force_caps_check.setChecked(self.template_data.get("force_caps", False)) # Load force_caps setting

            # Color
            main_color = self.template_data.get("color", "#FFFFFF")
            self._update_color_preview(self.color_preview, main_color)

            # Position & Layout
            pos_settings = self.template_data.get("position", {})
            self.pos_x_input.setText(str(pos_settings.get("x", "50%")))
            self.pos_y_input.setText(str(pos_settings.get("y", "60%"))) # Default from original json
            self.align_combo.setCurrentText(self.template_data.get("alignment", "center"))
            self.valign_combo.setCurrentText(self.template_data.get("vertical_alignment", "top")) # Default from original json
            self.max_width_input.setText(str(self.template_data.get("max_width", "90%"))) # Default from original json

            # Outline
            outline_settings = self.template_data.get("outline", {})
            outline_enabled = outline_settings.get("enabled", False)
            self.outline_group.setChecked(outline_enabled)
            outline_color = outline_settings.get("color", "#000000")
            self._update_color_preview(self.outline_color_preview, outline_color)
            self.outline_width_spin.setValue(outline_settings.get("width", 2))
            # Enable/disable controls within the group based on the checkbox
            for child in self.outline_group.findChildren(QWidget):
                 if child not in [self.outline_group]: # Don't disable the groupbox itself
                     child.setEnabled(outline_enabled)

            # Shadow
            shadow_settings = self.template_data.get("shadow", {})
            shadow_enabled = shadow_settings.get("enabled", False)
            self.shadow_group.setChecked(shadow_enabled)
            shadow_color = shadow_settings.get("color", "#000000")
            self._update_color_preview(self.shadow_color_preview, shadow_color)
            self.shadow_offset_x_spin.setValue(shadow_settings.get("offset_x", 3))
            self.shadow_offset_y_spin.setValue(shadow_settings.get("offset_y", 3))
            # Enable/disable controls within the group
            for child in self.shadow_group.findChildren(QWidget):
                 if child not in [self.shadow_group]:
                     child.setEnabled(shadow_enabled)

        finally:
            # Unblock signals
            for widget in self.findChildren(QWidget):
                widget.blockSignals(False)

    def _save_template(self):
        """Saves the current template_data to the JSON file."""
        logging.info(f"Saving template data to: {self.TEMPLATE_FILE}")
        try:
            with open(self.TEMPLATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.template_data, f, indent=2) # Use indent for readability
            logging.info("Template saved successfully.")
            # Optionally show a success message
        except Exception as e:
            logging.error(f"Error saving template file: {e}", exc_info=True)
            # Optionally show an error message to the user

    def _save_and_accept(self):
        """Saves the template and then closes the dialog."""
        self._save_template()
        self.accept() # Close the dialog with accept status
