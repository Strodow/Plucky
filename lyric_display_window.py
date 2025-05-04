# lyric_display_window.py

from PySide6.QtWidgets import (
    QWidget, QApplication, QSizePolicy
)
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QPixmap
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize
import os # Import os to check file existence


class LyricDisplayWindow(QWidget):
    def __init__(self, template_settings=None, parent=None):
        super().__init__(parent)

        # Window settings
        self.setWindowTitle("Lyric Output")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint) # Remove window frame
        # WA_TranslucentBackground allows the alpha channel of the background image to show through
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Default background color if no image is set or image loading fails
        self.setStyleSheet("background-color: black;")

        self._current_lyric = ""
        self._template_settings = template_settings if template_settings is not None else {}
        self._background_image_path = None # Attribute to store the background image path
        self._background_pixmap = QPixmap() # Attribute to store the loaded pixmap


        # Ensure the window stays on top (optional, might be useful for presentation)
        # self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        # Set size policy to fixed, as its size will be determined by the screen it's on
        # This prevents the layout system from trying to resize this window based on its contents
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


    # Method to Set Background Image
    def set_background_image(self, image_path):
        """Loads and sets the background image."""
        # Check if the provided path is not empty and the file actually exists
        if image_path and os.path.exists(image_path):
            self._background_image_path = image_path
            self._background_pixmap = QPixmap(image_path)
            if self._background_pixmap.isNull():
                # If loading failed, print a warning and clear the path/pixmap
                print(f"Warning: Could not load background image from {image_path}")
                self._background_image_path = None
                self._background_pixmap = QPixmap() # Clear the pixmap
            # Trigger a repaint to draw the new background (or lack thereof)
            self.update()
        else:
            # If the path is invalid or empty, clear any existing background
            self._background_image_path = None
            self._background_pixmap = QPixmap() # Clear the pixmap
            # Trigger a repaint to show the default background color
            self.update()


    def set_template_settings(self, settings):
        """Sets the template settings for rendering."""
        self._template_settings = settings
        self.update() # Request a repaint to apply new settings

    def display_lyric(self, lyric_text):
        """Sets the lyric text to be displayed and triggers a repaint."""
        self._current_lyric = lyric_text
        self.update() # Request a repaint to show new lyrics

    def paintEvent(self, event):
        """Handles the painting of the window content."""
        painter = QPainter(self)
        # Enable antialiasing for smoother text rendering and drawing
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)


        # Get window dimensions (which will be fullscreen on a monitor)
        window_width = self.width()
        window_height = self.height()

        # --- Draw Background Image (if set) ---
        if not self._background_pixmap.isNull():
            # Draw the background image scaled to fit the entire window rectangle
            # The image will be stretched/compressed to fit the window dimensions
            painter.drawPixmap(self.rect(), self._background_pixmap)
        else:
            # If no background image is loaded, fill the background with the default color (black)
            painter.fillRect(self.rect(), QColor(Qt.GlobalColor.black))
        # --- End Draw Background Image ---


        # --- Apply Template Settings ---
        # Get template settings with default fallbacks
        font_settings = self._template_settings.get("font", {})
        color_setting = self._template_settings.get("color", "#FFFFFF") # Default to white
        position_settings = self._template_settings.get("position", {"x": "50%", "y": "50%"}) # Default to center
        alignment_setting = self._template_settings.get("alignment", "center") # Default center
        vertical_alignment_setting = self._template_settings.get("vertical_alignment", "bottom") # Default bottom
        max_width_setting = self._template_settings.get("max_width", "100%") # Default 100%
        outline_settings = self._template_settings.get("outline", {"enabled": False})
        shadow_settings = self._template_settings.get("shadow", {"enabled": False})
        # Bounding box stroke settings
        force_caps = self._template_settings.get("force_caps", False) # Get force_caps setting
        bounding_box_settings = self._template_settings.get("bounding_box_stroke", {"enabled": False})


        # Set Font for the painter
        font = QFont()
        font.setFamily(font_settings.get("family", "Arial"))
        font.setPointSize(font_settings.get("size", 48))
        font.setBold(font_settings.get("bold", False))
        font.setItalic(font_settings.get("italic", False))
        font.setUnderline(font_settings.get("underline", False))
        painter.setFont(font)

        # Set Text Color using QPen (will be used for main text and potentially outline)
        color = QColor(color_setting)
        # painter.setPen(color) # Pen is set later for drawing text/outline


        # Calculate Drawing Rectangle and Position
        # Need font metrics to calculate text size and positioning accurately
        font_metrics = QFontMetrics(font)

        # Determine max width for wrapping based on template setting (pixels or percentage)
        max_width = window_width # Default max width is window width
        if isinstance(max_width_setting, str) and max_width_setting.endswith('%'):
            try:
                percentage = float(max_width_setting[:-1]) / 100.0
                max_width = int(window_width * percentage)
            except ValueError:
                pass # Keep default max_width if percentage parsing fails
        elif isinstance(max_width_setting, (int, float)):
            max_width = int(max_width_setting)

        # --- Apply Force Caps ---
        text_to_draw = self._current_lyric.upper() if force_caps else self._current_lyric
        # --- End Apply Force Caps ---

        # Calculate bounding rectangle for the text, considering potential wrapping and max_width
        # We use a large height initially to allow for full text height calculation with wrapping
        text_rect_size = font_metrics.boundingRect(0, 0, max_width, window_height * 2, Qt.TextFlag.TextWordWrap, text_to_draw) # Use text_to_draw


        # Calculate anchor point based on template position (pixels or percentages)
        anchor_x = 0
        anchor_y = 0

        # Calculate X anchor based on percentage or pixel value
        if isinstance(position_settings.get("x"), str) and position_settings["x"].endswith('%'):
            try:
                percentage = float(position_settings["x"][:-1]) / 100.0
                anchor_x = int(window_width * percentage)
            except ValueError:
                pass # Keep default 0 if percentage parsing fails
        elif isinstance(position_settings.get("x"), (int, float)):
             anchor_x = int(position_settings["x"])

        # Calculate Y anchor based on percentage or pixel value
        if isinstance(position_settings.get("y"), str) and position_settings["y"].endswith('%'):
            try:
                percentage = float(position_settings["y"][:-1]) / 100.0
                anchor_y = int(window_height * percentage)
            except ValueError:
                pass # Keep default 0 if percentage parsing fails
        elif isinstance(position_settings.get("y"), (int, float)):
             anchor_y = int(position_settings["y"])

        # --- Calculate the Top-Left Corner of the Drawing Rectangle ---
        draw_rect_x = anchor_x
        draw_rect_y = anchor_y

        # Horizontal Alignment adjustment for the drawing rectangle position
        if alignment_setting == "center":
            draw_rect_x = anchor_x - text_rect_size.width() // 2
        elif alignment_setting == "right":
            draw_rect_x = anchor_x - text_rect_size.width()
        # else "left" remains draw_rect_x = anchor_x

        # Vertical Alignment adjustment for the drawing rectangle position
        if vertical_alignment_setting == "center":
            draw_rect_y = anchor_y - text_rect_size.height() // 2
        elif vertical_alignment_setting == "top":
            draw_rect_y = anchor_y # Top of text aligns with anchor_y
        elif vertical_alignment_setting == "bottom":
             draw_rect_y = anchor_y - text_rect_size.height() # Bottom of text aligns with anchor_y

        # Create the final drawing rectangle
        drawing_rect = QRect(draw_rect_x, draw_rect_y, text_rect_size.width(), text_rect_size.height())


        # --- Determine Text Alignment Flags for drawText ---
        text_alignment_flags = Qt.TextFlag.TextWordWrap # Always wrap text

        if alignment_setting == "center":
            text_alignment_flags |= Qt.AlignmentFlag.AlignHCenter
        elif alignment_setting == "right":
            text_alignment_flags |= Qt.AlignmentFlag.AlignRight
        else: # Default to left alignment
            text_alignment_flags |= Qt.AlignmentFlag.AlignLeft

        # Note: Vertical alignment for drawing within a rect is handled by Qt.
        # We are primarily concerned with horizontal alignment here.


        # --- Draw Bounding Box Stroke (if enabled) ---
        if bounding_box_settings.get("enabled", False):
            stroke_color = QColor(bounding_box_settings.get("color", "#FFFFFF")) # Default to white
            stroke_width = bounding_box_settings.get("width", 1) # Default to 1 pixel

            # Create a pen for the stroke
            stroke_pen = QPen(stroke_color, stroke_width, Qt.PenStyle.SolidLine)
            painter.setPen(stroke_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush) # Don't fill the rectangle

            # Draw the rectangle using the calculated drawing_rect
            painter.drawRect(drawing_rect)

            # Restore the painter's pen and brush for text drawing
            painter.setPen(color) # Restore text color pen
            painter.setBrush(Qt.BrushStyle.NoBrush) # Ensure no brush is set for text


        # --- Draw Shadow (if enabled) ---
        if shadow_settings.get("enabled", False):
            shadow_color = QColor(shadow_settings.get("color", "#000000"))
            shadow_offset_x = shadow_settings.get("offset_x", 3)
            shadow_offset_y = shadow_settings.get("offset_y", 3)

            painter.setPen(shadow_color)
            # Draw text with shadow offset and determined alignment flags
            # Use the calculated drawing_rect, shifted by the shadow offset
            shadow_rect = QRect(drawing_rect.x() + shadow_offset_x, drawing_rect.y() + shadow_offset_y, drawing_rect.width(), drawing_rect.height())
            painter.drawText(shadow_rect, text_alignment_flags, text_to_draw) # Use text_to_draw
            painter.setPen(color) # Restore original text color for subsequent drawing


        # --- Draw Outline (if enabled) ---
        if outline_settings.get("enabled", False):
            outline_color = QColor(outline_settings.get("color", "#000000"))
            outline_width = outline_settings.get("width", 2)

            original_pen = painter.pen() # Store the current pen
            # Create a pen for the outline with specified color and width
            # Note: Drawing outline by drawing shifted text can be an approximation.
            # For true outline, using QPainterPath is more accurate but complex.
            # This simplified approach draws multiple shifted copies:
            outline_pen = QPen(outline_color, outline_width * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(outline_pen)
            # Draw text for the outline with determined alignment flags
            # Use the calculated drawing_rect and text_to_draw
            painter.drawText(drawing_rect, text_alignment_flags, text_to_draw) # Use text_to_draw
            painter.setPen(original_pen) # Restore original pen


        # --- Draw Main Text ---
        painter.setPen(color) # Ensure the correct text color is set for the main text
        # Draw the main lyric text using the calculated drawing_rect, alignment flags, and text_to_draw
        painter.drawText(drawing_rect, text_alignment_flags, text_to_draw) # Use text_to_draw


        painter.end() # End painting session

    def set_fullscreen_on_screen(self, screen_index):
        """Attempts to show the window fullscreen on a specific screen."""
        screens = QApplication.screens()
        if 0 <= screen_index < len(screens):
            target_screen = screens[screen_index]
            # Set the window's geometry to match the target screen's geometry
            self.setGeometry(target_screen.geometry())
            # Show the window in fullscreen mode
            self.showFullScreen()
        else:
            # Fallback to primary screen if the requested index is invalid
            print(f"Warning: Screen index {screen_index} is out of range ({len(screens)} screens available). Showing fullscreen on primary screen.")
            self.setGeometry(screens[0].geometry()) # Set geometry to primary screen
            self.showFullScreen()
