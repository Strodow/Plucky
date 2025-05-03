import sys
import os # Import os to check file existence
import json # Import json for loading template
import logging # Added for better error handling
import time # Import time for measuring image load
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QMenu
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QTextDocument, QPainterPath, QAction
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal

from template_editor import TemplateEditorWindow # Import the new editor window


class LyricCardWidget(QWidget):
    # Define a signal that will be emitted when the widget is clicked
    clicked = Signal()

    def __init__(self, button_id="", slide_number=0, section_name="", lyrics="", background_image_path=None, parent=None):
        super().__init__(parent)

        self.button_id = button_id # Store button_id for external reference
        self._slide_number = slide_number
        self.lyric_text = lyrics # Store original lyrics text
        self.section_name = section_name # Store the section name
        self._is_clicked = False # State for external highlighting
        self._background_image_path = background_image_path
        self._background_pixmap = QPixmap() # Pixmap for the background image
        self._last_image_load_time = 0.0 # Store time taken for the last image load attempt
        self._bar_color = QColor(0, 120, 215) # Default blue color for the bottom bar

        # --- Configuration --- (Moved from global scope for clarity)
        self.CONFIG_DIR = os.path.dirname(os.path.abspath(__file__)) # Get script's directory
        self.TEMPLATE_FILE = os.path.join(self.CONFIG_DIR, 'template.json')
        # --- Logging Setup --- (Moved from global scope for clarity)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        self._lyrics_pixmap = QPixmap() # Pixmap to hold rendered lyrics

        # Define a base size for rendering the lyrics pixmap.
        # This is the "logical" resolution of the text content before scaling.
        # Adjust this size to control the "resolution" and potential pixelation.
        # It doesn't strictly need to be 16x9, but a reasonable size for text rendering.
        self._base_lyrics_render_size = QSize(640, 300) # Base size for rendering text


        # Initial render of the lyrics pixmap
        self._render_lyrics_to_pixmap()
        self._load_background_image() # Load the background image if path provided


    def set_slide_number(self, number):
        """Sets the slide number displayed in the bottom left."""
        self._slide_number = number
        self.update() # Trigger repaint to show the new number/name combo

    def set_lyrics(self, lyrics):
        """Sets the lyrics text and re-renders the lyrics pixmap."""
        self.lyric_text = lyrics
        self._render_lyrics_to_pixmap() # Re-render pixmap when lyrics change
        self.update() # Repaint

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
                print(f"Successfully loaded background for {self.button_id}: {self._background_image_path}")
            else:
                print(f"Warning: Failed to load background image for {self.button_id} from {self._background_image_path}")
                self._background_image_path = None # Clear path if loading failed
        # No need to call self.update() here, as it's called during init or when path changes externally (if needed)
        self._last_image_load_time = time.time() - start_time

    def get_last_image_load_time(self):
        """Returns the time taken for the last background image load attempt."""
        return self._last_image_load_time

    def _render_lyrics_to_pixmap(self):
        """Renders the current lyrics to a QPixmap of the base render size."""
        # Ensure base render size is valid and there's text to render
        if self._base_lyrics_render_size.isEmpty() or not self.lyric_text:
            # Create a transparent pixmap of the base size even if empty,
            # so paintEvent doesn't try to draw a null pixmap.
            self._lyrics_pixmap = QPixmap(self._base_lyrics_render_size)
            self._lyrics_pixmap.fill(QColor(0, 0, 0, 0))
            return

        # Create a pixmap of the defined base render size
        pixmap = QPixmap(self._base_lyrics_render_size)
        # Fill with a transparent background so the black widget background shows through
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        # Use Antialiasing for smoother text edges when rendering to the pixmap
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set up text document for rendering to handle wrapping and alignment
        text_document = QTextDocument()
        # Use HTML for color and centering, handle newlines with <br>
        # Set text color directly in HTML for the document
        html_content = f"<p style='color: white; text-align: center; margin: 0;'>{self.lyric_text.replace('\n', '<br>')}</p>"
        text_document.setHtml(html_content)

        # Set the default font for the document
        # Adjust font size relative to the base pixmap height for consistent rendering
        font = QFont("Arial", int(self._base_lyrics_render_size.height() * 0.15)) # Font size scaled to base height (adjusted factor)
        text_document.setDefaultFont(font)

        # Set the text width for wrapping within the base pixmap size
        text_document.setTextWidth(self._base_lyrics_render_size.width())

        # Calculate the drawing rectangle within the pixmap to center the text vertically
        # Get the actual size of the text layout after wrapping
        text_layout_size = text_document.size().toSize()
        # Ensure the text drawing rectangle doesn't exceed the pixmap bounds
        text_draw_rect = QRect(0, (self._base_lyrics_render_size.height() - text_layout_size.height()) // 2,
                               self._base_lyrics_render_size.width(), text_layout_size.height())
        # Clamp the height to the pixmap height
        text_draw_rect.setHeight(min(text_draw_rect.height(), self._base_lyrics_render_size.height()))


        # Draw the text document onto the pixmap
        text_document.drawContents(painter, text_draw_rect)

        painter.end() # End painting on the pixmap

        self._lyrics_pixmap = pixmap # Store the generated pixmap


    def paintEvent(self, event):
        """Handles the custom drawing of the widget, maintaining 16x9 aspect ratio, rounded corners, and scaling number font."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # Enable antialiasing for smooth corners

        widget_rect = self.rect() # The actual bounds of the widget

        # --- Calculate the 16x9 target rectangle for the content ---
        # When using QSizePolicy.Fixed, the widget's size should be close to sizeHint().
        # We'll draw the content to fill the widget's actual rectangle, which should be consistent.
        content_rect = widget_rect

        # --- Create a QPainterPath for rounded corners ---
        corner_radius = 10 # Adjust the radius as needed
        path = QPainterPath()
        path.addRoundedRect(content_rect, corner_radius, corner_radius)

        # --- Clip the painter to the rounded path ---
        painter.setClipPath(path)

        # --- Draw Background Image or Color within the content area (now clipped) ---
        if not self._background_pixmap.isNull():
            # Draw the background image scaled to fill the content_rect (aspect ratio ignored)
            painter.drawPixmap(content_rect, self._background_pixmap)
        else:
            # Draw the default black background if no image is loaded
            painter.fillRect(content_rect, QColor(0, 0, 0)) # Black background

        # --- Draw Bottom Blue Bar within the content area (now clipped) ---
        # Scale the blue bar height relative to the content height
        # Assuming the original blue bar was about 25px in a 150px tall area (from original image/design)
        # Ratio: 25 / 150 = 1/6
        scaled_blue_bar_height = int(content_rect.height() / 6) # Scale height based on content area
        # Ensure minimum height for visibility
        scaled_blue_bar_height = max(scaled_blue_bar_height, 10) # Minimum height

        blue_bar_rect = QRect(content_rect.left(), content_rect.bottom() - scaled_blue_bar_height,
                              content_rect.width(), scaled_blue_bar_height)
        painter.fillRect(blue_bar_rect, self._bar_color) # Use the stored bar color

        # --- Draw Number and Section Name Text directly on the blue bar ---
        painter.setPen(Qt.GlobalColor.white) # White text

        # Calculate font size based on the scaled blue bar height
        number_font_size = int(scaled_blue_bar_height * 0.65) # Adjusted scaling factor
        number_font_size = max(number_font_size, 8) # Minimum font size
        number_font = QFont("Arial", number_font_size, QFont.Weight.Bold)
        painter.setFont(number_font)

        # Combine slide number and section name
        number_text = f"{self._slide_number} - {self.section_name}"
        number_margin = 8 # Margin from the left edge

        # The lyrics pixmap should fill the area above the blue bar within the content_rect

        # --- Draw Highlight Border if Clicked around the content area ---
        # Draw the border using the same rounded path
        if self._is_clicked:
            border_width = 3 # Adjust border thickness
            painter.setPen(QColor(255, 255, 255)) # White border color
            painter.setBrush(Qt.BrushStyle.NoBrush) # Don't fill the border rectangle
            # Draw the rounded rectangle border
            painter.drawPath(path)


        # --- Draw Scaled Lyrics Pixmap within the content area (now clipped) ---
        # The lyrics pixmap should fill the area above the blue bar within the content_rect
        lyrics_area_in_content = QRect(content_rect.left(), content_rect.top(),
                                       content_rect.width(), content_rect.height() - scaled_blue_bar_height)

        if not lyrics_area_in_content.isEmpty() and not self._lyrics_pixmap.isNull():
             # Draw the lyrics pixmap scaled to the calculated area within the content_rect
             # Use SmoothTransformation for better scaling quality
             painter.drawPixmap(lyrics_area_in_content, self._lyrics_pixmap)

        # --- Draw Number/Name Text (after lyrics pixmap, so it's on top) ---
        # Define the rectangle within the blue bar for the text, align text vertically centered
        text_draw_rect = QRect(blue_bar_rect.left() + number_margin, blue_bar_rect.top(),
                               blue_bar_rect.width() - number_margin * 2, blue_bar_rect.height())
        # Draw the text, left-aligned and vertically centered
        painter.drawText(text_draw_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, number_text)


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
        self._bar_color = color # Store the new color
        self.update() # Trigger a repaint to show the change

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
