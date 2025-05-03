import sys
import json
import os
import logging
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog, QSizePolicy, QPushButton, QSpacerItem, QTextEdit
)
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QFontDatabase, QTextOption
from PySide6.QtCore import Qt, QRectF, QSize, QRect

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
        font_size_setting = font_settings.get("size", 24) # Default font size

        font_color_hex = font_settings.get("color", "#FFFFFF") # Default white
        vertical_alignment_setting = self.template_data.get("vertical_alignment", "bottom") # Default bottom align

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


        pen = QPen(QColor("yellow"), 2, Qt.PenStyle.DashLine) # Dashed yellow line
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush) # Ensure no fill
        # Draw the dashed bounding box based on the calculated rectangle
        painter.drawRect(bounding_rect)

        # --- Draw Sample Text ---
        if self.sample_text and bounding_rect.isValid():
            font = QFont()
            # Attempt to set font family
            font.setFamily(font_family)
            # Check if the system resolved the font correctly, otherwise use a default
            if QFontDatabase.hasFamily(font_family) and font.family() != font_family:
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

            # Add other font attributes later (bold, italic, etc.) if needed

            painter.setFont(font)
            painter.setPen(QColor(font_color_hex)) # Set text color

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

            # **Clipping is removed as per user's request**
            # If you need clipping back, uncomment the lines below:
            # painter.setClipRect(bounding_rect)

            # Draw text within the bounding rectangle.
            # Without clipping, text might overflow the bounding_rect visually if it's too tall.
            # The text will still wrap within the width of bounding_rect.
            painter.drawText(bounding_rect, self.sample_text, text_option)

            # **If clipping was enabled, remember to clear it**
            # painter.setClipping(False)








class TemplateEditorWindow(QDialog):
    """Window for editing template properties."""
    def __init__(self, template_data, parent=None):
        super().__init__(parent)
        self.template_data = template_data
        # Define template file path within the editor instance
        self.CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
        self.TEMPLATE_FILE = os.path.join(self.CONFIG_DIR, 'template.json')
        self.setWindowTitle(f"Edit Template: {template_data.get('template_name', 'Unnamed Template')}")
        self.setMinimumSize(500, 500) # Increased height slightly for text input

        layout = QVBoxLayout(self)

        # --- Top Bar for Name and Refresh ---
        top_bar_layout = QHBoxLayout()
        self.name_label = QLabel(f"Template: {template_data.get('template_name', 'Unnamed Template')}")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) # Allow label to expand
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Reload template.json")
        self.refresh_button.clicked.connect(self._refresh_template)

        top_bar_layout.addWidget(self.name_label)
        top_bar_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)) # Spacer
        top_bar_layout.addWidget(self.refresh_button)
        # --- End Top Bar ---

        self.preview_widget = TemplatePreviewWidget(template_data)

        # --- Sample Text Input ---
        self.sample_text_label = QLabel("Sample Text:")
        self.sample_text_input = QTextEdit()
        self.sample_text_input.setPlaceholderText("Type sample text here...")
        self.sample_text_input.setText(self.preview_widget.sample_text) # Initialize with default
        self.sample_text_input.setMaximumHeight(80) # Limit height of input box
        self.sample_text_input.textChanged.connect(self._on_sample_text_changed)
        # --- End Sample Text Input ---

        layout.addLayout(top_bar_layout) # Add the horizontal layout to the main vertical layout
        layout.addWidget(self.preview_widget, 1) # Allow preview to stretch
        layout.addWidget(self.sample_text_label)
        layout.addWidget(self.sample_text_input)
        self.setLayout(layout)
    def _refresh_template(self):
        """Reloads template data from the JSON file and updates the preview."""
        logging.info(f"Refreshing template editor from: {self.TEMPLATE_FILE}")
        try:
            with open(self.TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                new_template_data = json.load(f)

            self.template_data = new_template_data # Update the editor's data store
            self.preview_widget.set_template_data(self.template_data) # Update the preview widget's data
            self.preview_widget.update() # Trigger repaint of the preview

            # Update window title and label in case the name changed
            new_name = self.template_data.get('template_name', 'Unnamed Template')
            self.setWindowTitle(f"Edit Template: {new_name}")
            self.name_label.setText(f"Template: {new_name}")
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
