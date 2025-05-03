import sys
import os # Import os to check file existence
import json # Import json for loading template
import logging # Added for better error handling
import time # Import time for measuring image load
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QMenu
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QTextDocument, QPainterPath, QAction, QTextOption, QFontInfo, QFontMetrics, QPen
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal, QRectF

from template_editor import TemplateEditorWindow # Import the new editor window


class ContentAreaWidget(QWidget):
    """Widget responsible for drawing the background and lyrics content."""
    # Add card_background_color parameter with default
    def __init__(self, template_settings=None, background_path=None, initial_lyrics="", card_background_color="#000000", parent=None):
        super().__init__(parent)
        self.template_settings = template_settings if template_settings else {}
        self._background_image_path = background_path
        self.lyric_text = initial_lyrics
        self._card_background_color = QColor(card_background_color) # Store as QColor
        self._background_pixmap = QPixmap()
        self._last_image_load_time = 0.0

        self._load_background_image()

    def set_template_settings(self, settings):
        self.template_settings = settings if settings else {}
        self.update()

    def set_lyrics(self, lyrics):
        self.lyric_text = lyrics
        self.update()

    def set_background(self, path):
        self._background_image_path = path
        self._load_background_image()
        self.update()

    def _load_background_image(self):
        """Loads the background image from the stored path."""
        start_time = time.time()
        load_successful = False
        self._background_pixmap = QPixmap() # Clear existing pixmap first
        if self._background_image_path and os.path.exists(self._background_image_path):
            loaded_pixmap = QPixmap(self._background_image_path)
            if not loaded_pixmap.isNull():
                self._background_pixmap = loaded_pixmap
                load_successful = True
                # print(f"Successfully loaded background: {self._background_image_path}") # Optional logging
            else:
                logging.warning(f"Failed to load background image from {self._background_image_path}")
                self._background_image_path = None # Clear path if loading failed
        self._last_image_load_time = time.time() - start_time

    def get_last_image_load_time(self):
        return self._last_image_load_time

    def set_card_background_color(self, hex_color):
        """Sets the background color used when no image is present."""
        self._card_background_color = QColor(hex_color) # Update the color
        self.update() # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        content_rect = self.rect() # Use the widget's full rect

        # --- Create Rounded Path for Top Corners ---
        corner_radius = 10 # Same radius as parent
        path = QPainterPath()
        # Add a rect with only top corners rounded
        path.moveTo(content_rect.left(), content_rect.bottom())
        path.lineTo(content_rect.left(), content_rect.top() + corner_radius)
        path.arcTo(content_rect.left(), content_rect.top(), corner_radius * 2, corner_radius * 2, 180, -90)
        path.lineTo(content_rect.right() - corner_radius, content_rect.top())
        path.arcTo(content_rect.right() - corner_radius * 2, content_rect.top(), corner_radius * 2, corner_radius * 2, 90, -90)
        path.lineTo(content_rect.right(), content_rect.bottom())
        path.closeSubpath()
        painter.setClipPath(path) # Clip this widget's drawing

        # --- Draw Background Image or Color ---
        if not self._background_pixmap.isNull():
            # Draw background *after* setting clip path
            painter.drawPixmap(content_rect, self._background_pixmap)
        else:
            # Draw background color *after* setting clip path
            painter.fillRect(content_rect, self._card_background_color) # Use the stored background color

        # --- Draw Scaled Lyrics Text (will also be clipped by the path set above) ---
        if not content_rect.isEmpty() and self.lyric_text:
            # --- Get Template Settings (Moved here to ensure they are always defined if text is drawn) ---
            font_settings = self.template_settings.get("font", {})
            font_family = font_settings.get("family", "Arial") # Get family from font_settings dict
            font_size_setting = font_settings.get("size", 58) # Get size from font_settings dict
            font_bold = font_settings.get("bold", False)
            font_italic = font_settings.get("italic", False)
            font_underline = font_settings.get("underline", False)
            font_color_hex = self.template_settings.get("color", "#FFFFFF")
            alignment_setting = self.template_settings.get("alignment", "center")
            vertical_alignment_setting = self.template_settings.get("vertical_alignment", "center")
            position_settings = self.template_settings.get("position", {"y": "80%"})
            outline_settings = self.template_settings.get("outline", {})
            outline_enabled = outline_settings.get("enabled", False)
            outline_color_hex = outline_settings.get("color", "#000000")
            outline_width = outline_settings.get("width", 2)
            shadow_settings = self.template_settings.get("shadow", {})
            shadow_enabled = shadow_settings.get("enabled", False)
            shadow_color_hex = shadow_settings.get("color", "#000000")
            shadow_offset_x = shadow_settings.get("offset_x", 3)
            shadow_offset_y = shadow_settings.get("offset_y", 3)

            # --- Calculate Scaled Font Size (Copied) ---
            actual_font_size_pt = 10
            if isinstance(font_size_setting, (int, float)):
                base_point_size = float(font_size_setting)
                target_output_height = 1080
                current_preview_height = content_rect.height() # Use this widget's height
                if target_output_height > 0 and current_preview_height > 0:
                    scaling_factor = current_preview_height / target_output_height
                    actual_font_size_pt = int(base_point_size * scaling_factor)
                else:
                    actual_font_size_pt = int(base_point_size)
                actual_font_size_pt = max(6, actual_font_size_pt)

            # --- Set Font (Copied) ---
            font = QFont()
            font.setFamily(font_family)
            if not QFontInfo(font).exactMatch():
                 logging.warning(f"ContentArea: Font family '{font_family}' not found. Using default.")
            font.setPointSize(actual_font_size_pt)
            font.setBold(font_bold)
            font.setItalic(font_italic)
            font.setUnderline(font_underline)
            painter.setFont(font)

            # --- Set Text Options (Copied) ---
            text_option = QTextOption()
            h_align = Qt.AlignmentFlag.AlignHCenter
            if alignment_setting == "left": h_align = Qt.AlignmentFlag.AlignLeft
            elif alignment_setting == "right": h_align = Qt.AlignmentFlag.AlignRight
            v_align = Qt.AlignmentFlag.AlignVCenter
            if vertical_alignment_setting == "top": v_align = Qt.AlignmentFlag.AlignTop
            elif vertical_alignment_setting == "bottom": v_align = Qt.AlignmentFlag.AlignBottom
            text_option.setAlignment(h_align | v_align)
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)

            # --- Calculate Text Bounding Box (Copied) ---
            anchor_y = content_rect.top() + content_rect.height() * 0.8
            pos_y_setting = position_settings.get("y", "80%")
            try:
                if isinstance(pos_y_setting, str) and pos_y_setting.endswith('%'):
                    anchor_y = content_rect.top() + content_rect.height() * (float(pos_y_setting[:-1]) / 100.0)
                elif isinstance(pos_y_setting, (int, float)):
                    target_output_height = 1080
                    scaling_factor = content_rect.height() / target_output_height if target_output_height > 0 else 1
                    anchor_y = content_rect.top() + float(pos_y_setting) * scaling_factor
            except ValueError:
                logging.warning(f"Invalid position.y format: {pos_y_setting}. Using default.")

            fm = QFontMetrics(font)
            text_flags = Qt.TextFlag.TextWordWrap
            if h_align == Qt.AlignmentFlag.AlignLeft: text_flags |= Qt.AlignmentFlag.AlignLeft
            elif h_align == Qt.AlignmentFlag.AlignRight: text_flags |= Qt.AlignmentFlag.AlignRight
            else: text_flags |= Qt.AlignmentFlag.AlignHCenter
            calculation_rect = QRect(0, 0, content_rect.width(), 9999)
            text_bounding_rect = fm.boundingRect(calculation_rect, text_flags, self.lyric_text)
            text_height = text_bounding_rect.height()
            text_width = text_bounding_rect.width()

            final_top_y = anchor_y
            if vertical_alignment_setting == "center": final_top_y = anchor_y - text_height / 2
            elif vertical_alignment_setting == "bottom": final_top_y = anchor_y - text_height
            final_left_x = content_rect.left()
            if alignment_setting == "center": final_left_x = content_rect.center().x() - text_width / 2
            elif alignment_setting == "right": final_left_x = content_rect.right() - text_width

            final_draw_rect = QRectF(final_left_x, final_top_y, text_width, text_height)
            final_draw_rect = final_draw_rect.intersected(QRectF(content_rect))

            # --- Draw Text (Shadow, Outline, Main) (Copied) ---
            if shadow_enabled:
                shadow_rect = final_draw_rect.translated(shadow_offset_x, shadow_offset_y)
                painter.setPen(QColor(shadow_color_hex))
                painter.drawText(shadow_rect, self.lyric_text, text_option)
            if outline_enabled and outline_width > 0:
                painter.setPen(QColor(outline_color_hex))
                for dx in range(-outline_width, outline_width + 1, outline_width):
                     for dy in range(-outline_width, outline_width + 1, outline_width):
                         if dx != 0 or dy != 0:
                             offset_rect = final_draw_rect.translated(dx, dy)
                             painter.drawText(offset_rect, self.lyric_text, text_option)
            painter.setPen(QColor(font_color_hex))
            painter.drawText(final_draw_rect, self.lyric_text, text_option)


class InfoBarWidget(QWidget):
    """Widget for the bottom info bar (slide number, section name)."""
    def __init__(self, slide_number=0, section_name="", bar_color=QColor(0, 120, 215), parent=None):
        super().__init__(parent)
        self._slide_number = slide_number
        self.section_name = section_name
        self._bar_color = bar_color
        # Set a fixed height based on the desired ratio (e.g., 1/6th of 135)
        self.setFixedHeight(22) # 135 / 6 = 22.5, round down or up
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, slide_number, section_name):
        self._slide_number = slide_number
        self.section_name = section_name
        self.update()

    def set_bar_color(self, color):
        self._bar_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_rect = self.rect()

        # --- Create Rounded Path for Bottom Corners ---
        corner_radius = 10 # Same radius as parent
        path = QPainterPath()
        path.moveTo(bar_rect.left(), bar_rect.top())
        path.lineTo(bar_rect.right(), bar_rect.top())
        path.lineTo(bar_rect.right(), bar_rect.bottom() - corner_radius)
        path.arcTo(bar_rect.right() - corner_radius * 2, bar_rect.bottom() - corner_radius * 2, corner_radius * 2, corner_radius * 2, 0, -90)
        path.lineTo(bar_rect.left() + corner_radius, bar_rect.bottom())
        path.arcTo(bar_rect.left(), bar_rect.bottom() - corner_radius * 2, corner_radius * 2, corner_radius * 2, 270, -90)
        path.closeSubpath()
        painter.setClipPath(path) # Clip this widget's drawing

        # Draw Background Bar
        painter.fillRect(bar_rect, self._bar_color)

        # Draw Text (Slide Number and Section Name)
        painter.setPen(Qt.GlobalColor.white) # White text

        # Calculate font size based on the fixed bar height
        bar_height = bar_rect.height()
        number_font_size = int(bar_height * 0.65) # Scale based on actual height
        number_font_size = max(number_font_size, 8) # Minimum font size
        number_font = QFont("Arial", number_font_size, QFont.Weight.Bold)
        painter.setFont(number_font)

        # Combine slide number and section name
        number_text = f"{self._slide_number} - {self.section_name}"
        number_margin = 8 # Margin from the left edge

        # Define the rectangle within the blue bar for the text
        text_draw_rect = QRect(bar_rect.left() + number_margin, bar_rect.top(),
                               bar_rect.width() - number_margin * 2, bar_rect.height())
        # Draw the text, left-aligned and vertically centered
        painter.drawText(text_draw_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, number_text)


class LyricCardWidget(QWidget):
    # Define a signal that will be emitted when the widget is clicked
    clicked = Signal()
    # Define a signal to request editing the song this card belongs to
    edit_song_requested = Signal(str) # Emits the song_key
    # Define a signal to request editing this specific section
    edit_section_requested = Signal(str) # Emits the button_id (songkey_sectionname)

    # Add card_background_color parameter
    def __init__(self, button_id="", slide_number=0, section_name="", song_title="", lyrics="", background_image_path=None, template_settings=None, card_background_color="#000000", parent=None): # Added song_title
        super().__init__(parent)

        self.button_id = button_id # Store button_id for external reference
        self._slide_number = slide_number
        self.song_title = song_title # Store the song title
        self.lyric_text = lyrics # Store original lyrics text
        self._card_background_color_hex = card_background_color # Store hex just in case
        self._is_clicked = False # State for external highlighting
        self._last_image_load_time = 0.0 # Store time taken for the last image load attempt
        self.template_settings = template_settings if template_settings else {} # Store template settings
        self._bar_color = QColor(0, 120, 215) # Default blue color for the bottom bar

        # --- Configuration --- (Moved from global scope for clarity)
        self.CONFIG_DIR = os.path.dirname(os.path.abspath(__file__)) # Get script's directory
        self.TEMPLATE_FILE = os.path.join(self.CONFIG_DIR, 'template.json')
        # --- Logging Setup --- (Moved from global scope for clarity)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # No longer need this as children handle their corners
        # self.setAutoFillBackground(False)

        # --- Create Child Widgets ---
        self.content_area = ContentAreaWidget(
            template_settings=self.template_settings,
            background_path=background_image_path,
            initial_lyrics=self.lyric_text,
            card_background_color=card_background_color, # Pass color down
            parent=self
        )
        self._last_image_load_time = self.content_area.get_last_image_load_time() # Get initial load time

        self.info_bar = InfoBarWidget(
            slide_number=self._slide_number,
            section_name=section_name, # Pass section name here
            bar_color=self._bar_color,
            parent=self
        )

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # No margins around the children
        layout.setSpacing(0) # No spacing between content and info bar
        layout.addWidget(self.content_area, 1) # Content area takes available vertical space
        layout.addWidget(self.info_bar, 0) # Info bar takes its fixed height

        # --- Set Fixed Size for the entire card ---
        self.setFixedSize(self.sizeHint()) # Use the fixed size hint


    def set_slide_number(self, number):
        """Sets the slide number displayed in the bottom left."""
        self._slide_number = number
        # Update the info bar directly (assuming section name doesn't change here)
        self.info_bar.set_data(self._slide_number, self.info_bar.section_name)

    def set_lyrics(self, lyrics):
        """Sets the lyrics text and re-renders the lyrics pixmap."""
        self.lyric_text = lyrics
        self.content_area.set_lyrics(lyrics) # Update the content area

    def set_card_background_color(self, hex_color):
        """Updates the background color of the content area."""
        self._card_background_color_hex = hex_color # Update stored hex if needed
        self.content_area.set_card_background_color(hex_color) # Pass call to content area

    def get_last_image_load_time(self):
        """Returns the time taken for the last background image load attempt."""
        # Could return the content_area's time, or keep the initial one stored
        return self.content_area.get_last_image_load_time()

    def paintEvent(self, event):
        """Handles the custom drawing of the widget, maintaining 16x9 aspect ratio, rounded corners, and scaling number font."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Enable antialiasing for smooth corners

        # Use the widget's full rect for clipping and border
        widget_rect = self.rect()
        content_rect = widget_rect

        # --- Create a QPainterPath for rounded corners ---
        corner_radius = 10 # Adjust the radius as needed
        path = QPainterPath()
        path.addRoundedRect(content_rect, corner_radius, corner_radius)

        # --- DO NOT Clip the painter here anymore ---
        # painter.setClipPath(path)

        # The lyrics pixmap should fill the area above the blue bar within the content_rect

        # --- Draw Highlight Border if Clicked around the content area ---
        # Draw the border using the same rounded path
        if self._is_clicked:
            border_width = 3 # Adjust border thickness
            # Need to save painter state before changing pen/brush for border
            painter.save()
            pen = QPen(QColor(255, 255, 255), border_width) # White border color and width
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush) # Don't fill the border rectangle
            # Draw the rounded rectangle border
            painter.drawPath(path)
            painter.restore() # Restore painter state after drawing border


    def resizeEvent(self, event):
        """Handles resize events. No specific logic needed here as paintEvent handles layout."""
        # The layout of elements is now handled entirely within paintEvent based on
        # the calculated 16x9 content area. We just need to trigger a repaint.
        self.update()
        # super().resizeEvent(event) # No longer needed as we don't have child widgets to manage


    def mousePressEvent(self, event):
        """Handles mouse clicks on the widget."""
        # Use standardButtons() for PySide6 to check for left button
        # Emit the signal when clicked
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """Handles right-click events to show a context menu."""
        menu = QMenu(self)

        # --- Edit Song Action ---
        # Extract song_key from button_id (using '__' as delimiter)
        song_key = self.button_id.split('__', 1)[0] if '__' in self.button_id else self.button_id
        if song_key:
            edit_song_action = QAction(f"Edit Song: {self.song_title}", self) # Use self.song_title
            # Use lambda to emit the signal with the song_key
            edit_song_action.triggered.connect(lambda checked=False, sk=song_key: self.edit_song_requested.emit(sk))
            menu.addAction(edit_song_action)
            menu.addSeparator()

        # --- Edit Section Action ---
        edit_section_action = QAction(f"Edit Section: {self.info_bar.section_name}", self)
        # Emit the signal with the full button_id for this specific section card
        edit_section_action.triggered.connect(lambda checked=False, bid=self.button_id: self.edit_section_requested.emit(bid))
        menu.addAction(edit_section_action)

        # --- Color Submenu ---
        color_menu = menu.addMenu("Set Bar Color")

        # Action for Red
        red_action = QAction("Red", self)
        red_action.triggered.connect(lambda: self.set_bar_color(QColor("red")))
        color_menu.addAction(red_action)

        # Action for Green
        green_action = QAction("Green", self)
        green_action.triggered.connect(lambda: self.set_bar_color(QColor("green")))
        color_menu.addAction(green_action)

        # Action for Blue (original color)
        blue_action = QAction("Blue", self)
        blue_action.triggered.connect(lambda: self.set_bar_color(QColor(0, 120, 215)))
        color_menu.addAction(blue_action)

        # --- Edit Template Action ---
        menu.addSeparator() # Add a separator for visual distinction
        edit_template_action = QAction("Edit Template", self)
        edit_template_action.triggered.connect(self._handle_edit_template) # Connect to a new handler
        menu.addAction(edit_template_action)
        # Show the menu at the cursor's global position
        menu.exec(event.globalPos())

    def set_highlight(self, highlight: bool):
        """Sets the highlighted state externally and triggers a repaint."""
        if self._is_clicked != highlight: # Only update and repaint if the state changes
            self._is_clicked = highlight
            self.update() # Trigger repaint

    def sizeHint(self):
        """Provides a recommended size for the widget."""
        # Define the consistent fixed size for the widget
        return QSize(240, 135) # Example 16:9 size (240x135)

    def set_bar_color(self, color):
        """Sets the color of the bottom bar and triggers a repaint."""
        self._bar_color = color # Store locally if needed for context menu default
        self.info_bar.set_bar_color(color) # Update the info bar widget

    def minimumSizeHint(self):
        """Provides a minimum size for the widget."""
        # When using a Fixed policy, minimumSizeHint is often the same as sizeHint
        return self.sizeHint()

    def _handle_edit_template(self):
        """Placeholder handler for the 'Edit Template' action."""
        logging.info(f"Edit Template action triggered for button: {self.button_id}")
        try:
            with open(self.TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            # Create and show the editor window
            # Pass 'self' or 'self.window()' as parent if needed for modality/behavior
            self.editor_window = TemplateEditorWindow(template_data, self.window())
            self.editor_window.exec() # Use exec() for a modal dialog

        except FileNotFoundError:
            logging.error(f"Template file not found: {self.TEMPLATE_FILE}")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from template file: {self.TEMPLATE_FILE}")
        except Exception as e:
            logging.error(f"An unexpected error occurred opening the template editor: {e}", exc_info=True)



if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Example usage:
    # Create a main window or a container widget to hold the LyricCardWidgets
    main_widget = QWidget()
    # Use a layout that allows stretching to see the aspect ratio in action
    layout = QVBoxLayout(main_widget)

    widget1 = LyricCardWidget(button_id="widget1", slide_number=3, lyrics="IF THE MOUNTAINS\nWERE WHERE YOU HIDE")
    widget2 = LyricCardWidget(button_id="widget2", slide_number=99, lyrics="Another line of lyrics that is a bit longer to test wrapping and scaling the pixmap in PySide6. This text should wrap and be displayed as a scaled image.")

    layout.addWidget(widget1)
    layout.addWidget(widget2)

    main_widget.setWindowTitle("Lyric Card Example")
    main_widget.resize(800, 600) # Give the main window some space to stretch
    main_widget.show()

    # Connect signals to a slot to demonstrate highlighting
    def handle_widget_click():
        # This is a simplified example. In a real application, you would
        # likely manage the highlighted state of all widgets in a central place.
        sender_widget = app.sender() # Get the widget that emitted the signal
        if isinstance(sender_widget, LyricCardWidget):
            # Toggle highlight for the clicked widget and turn off others (basic example)
            for widget in [widget1, widget2]:
                if widget is sender_widget:
                    widget.set_highlight(True)
                else:
                    widget.set_highlight(False)


    widget1.clicked.connect(handle_widget_click)
    widget2.clicked.connect(handle_widget_click)


    sys.exit(app.exec())
