import sys
import os
import logging
from PySide6.QtWidgets import QApplication # Needed for testing QPixmap/QPainter
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QTextOption,
    QFontInfo
)
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize

# --- Local Imports ---
# Assume data_models is in the parent directory or accessible via PYTHONPATH
try:
    # This works if running from the YourProject directory
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE
except ImportError:
    # Fallback for running the script directly in the rendering folder
    import sys
    import os
    # Add the parent directory (YourProject) to the Python path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE


class SlideRenderer:
    """Renders SlideData onto a QPixmap."""

    def __init__(self):
        # Potential future optimizations: cache fonts, etc.
        pass

    def render_slide(self, slide_data: SlideData, width: int, height: int) -> QPixmap:
        """
        Renders the given slide data onto a QPixmap of the specified dimensions.

        Args:
            slide_data: An instance of SlideData containing the content and style.
            width: The target width of the output pixmap.
            height: The target height of the output pixmap.

        Returns:
            A QPixmap containing the rendered slide.
        """
        # Create the target pixmap
        pixmap = QPixmap(width, height)
        # Start with a default background (e.g., black)
        pixmap.fill(QColor(slide_data.background_color))

        # --- Draw Background Image (if specified and valid) ---
        bg_pixmap = QPixmap()
        if slide_data.background_image_path and os.path.exists(slide_data.background_image_path):
            loaded_bg = QPixmap(slide_data.background_image_path)
            if not loaded_bg.isNull():
                bg_pixmap = loaded_bg
            else:
                logging.warning(f"Could not load background image: {slide_data.background_image_path}")

        # --- Prepare Painter ---
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw background image if loaded
        if not bg_pixmap.isNull():
            # Scale the image to cover the entire pixmap area
            painter.drawPixmap(pixmap.rect(), bg_pixmap)

        # --- Apply Template Settings ---
        # Merge slide-specific template settings with defaults if necessary
        # For simplicity now, assume slide_data.template_settings is complete
        template = slide_data.template_settings

        font_settings = template.get("font", {})
        color_setting = template.get("color", "#FFFFFF")
        position_settings = template.get("position", {"x": "50%", "y": "80%"})
        alignment_setting = template.get("alignment", "center")
        vertical_alignment_setting = template.get("vertical_alignment", "center")
        max_width_setting = template.get("max_width", "90%")
        outline_settings = template.get("outline", {})
        shadow_settings = template.get("shadow", {})

        # --- Prepare Font ---
        font = QFont()
        font_family = font_settings.get("family", "Arial")
        font.setFamily(font_family)
        if not QFontInfo(font).exactMatch():
            logging.warning(f"Font family '{font_family}' not found or resolved differently. Using default.")

        # Calculate font point size based on target height (scaling from 1080p base)
        base_font_size_pt = font_settings.get("size", 58) # Base size for 1080p
        target_output_height = 1080 # The height the base size is designed for
        if target_output_height > 0 and height > 0:
            scaling_factor = height / target_output_height
            actual_font_size_pt = int(base_font_size_pt * scaling_factor)
        else:
            actual_font_size_pt = int(base_font_size_pt)
        actual_font_size_pt = max(8, actual_font_size_pt) # Ensure minimum size
        font.setPointSize(actual_font_size_pt)

        font.setBold(font_settings.get("bold", False))
        font.setItalic(font_settings.get("italic", False))
        font.setUnderline(font_settings.get("underline", False))
        painter.setFont(font)

        # --- Prepare Text ---
        force_caps = font_settings.get('force_all_caps', False)
        text_to_draw = slide_data.lyrics.upper() if force_caps else slide_data.lyrics

        if not text_to_draw: # Nothing more to do if no lyrics
            painter.end()
            return pixmap

        # --- Calculate Text Layout ---
        font_metrics = QFontMetrics(font)

        # Max width for text wrapping
        max_text_width_px = width # Default to full width
        if isinstance(max_width_setting, str) and max_width_setting.endswith('%'):
            try:
                percentage = float(max_width_setting[:-1]) / 100.0
                max_text_width_px = int(width * percentage)
            except ValueError: pass
        elif isinstance(max_width_setting, (int, float)):
             # Scale fixed pixel width based on target width vs a base (e.g., 1920)
             base_width = 1920
             scaling_factor = width / base_width if base_width > 0 else 1
             max_text_width_px = int(float(max_width_setting) * scaling_factor)
        max_text_width_px = max(10, min(max_text_width_px, width)) # Clamp

        # Calculate text bounding rect with wrapping
        text_flags = Qt.TextFlag.TextWordWrap
        # Use a large height for calculation to get the true wrapped height
        text_bounding_rect = font_metrics.boundingRect(QRect(0, 0, max_text_width_px, height * 2), text_flags, text_to_draw)

        # Calculate anchor point
        anchor_x = 0
        anchor_y = 0
        pos_x = position_settings.get("x", "50%")
        if isinstance(pos_x, str) and pos_x.endswith('%'): anchor_x = int(width * (float(pos_x[:-1]) / 100.0))
        elif isinstance(pos_x, (int, float)): anchor_x = int(pos_x * (width / 1920.0)) # Scale fixed pos
        pos_y = position_settings.get("y", "80%")
        if isinstance(pos_y, str) and pos_y.endswith('%'): anchor_y = int(height * (float(pos_y[:-1]) / 100.0))
        elif isinstance(pos_y, (int, float)): anchor_y = int(pos_y * (height / 1080.0)) # Scale fixed pos

        # Calculate final drawing rectangle top-left based on anchor and alignment
        draw_rect_x = anchor_x
        if alignment_setting == "center": draw_rect_x -= text_bounding_rect.width() // 2
        elif alignment_setting == "right": draw_rect_x -= text_bounding_rect.width()

        draw_rect_y = anchor_y
        if vertical_alignment_setting == "center": draw_rect_y -= text_bounding_rect.height() // 2
        elif vertical_alignment_setting == "top": draw_rect_y = anchor_y
        elif vertical_alignment_setting == "bottom": draw_rect_y -= text_bounding_rect.height()

        final_draw_rect = QRectF(draw_rect_x, draw_rect_y, text_bounding_rect.width(), text_bounding_rect.height())

        # --- Prepare Text Options for Drawing ---
        text_option = QTextOption()
        h_align = Qt.AlignmentFlag.AlignHCenter
        if alignment_setting == "left": h_align = Qt.AlignmentFlag.AlignLeft
        elif alignment_setting == "right": h_align = Qt.AlignmentFlag.AlignRight
        # Vertical alignment within the drawText rect is usually AlignTop when using boundingRect result
        text_option.setAlignment(h_align | Qt.AlignmentFlag.AlignTop)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)

        # --- Draw Text Effects and Main Text ---
        main_text_color = QColor(color_setting)

        # 1. Draw Shadow
        if shadow_settings.get("enabled", False):
            shadow_color = QColor(shadow_settings.get("color", "#000000"))
            shadow_offset_x = shadow_settings.get("offset_x", 3) * (width / 1920.0) # Scale offset
            shadow_offset_y = shadow_settings.get("offset_y", 3) * (height / 1080.0) # Scale offset
            shadow_rect = final_draw_rect.translated(shadow_offset_x, shadow_offset_y)
            painter.setPen(shadow_color)
            painter.drawText(shadow_rect, text_to_draw, text_option)

        # 2. Draw Outline
        if outline_settings.get("enabled", False):
            outline_color = QColor(outline_settings.get("color", "#000000"))
            # Scale outline width slightly
            outline_width = max(1, int(outline_settings.get("width", 2) * (height / 1080.0)))
            painter.setPen(outline_color)
            # Simple multi-draw outline
            for dx in range(-outline_width, outline_width + 1, outline_width):
                 for dy in range(-outline_width, outline_width + 1, outline_width):
                     if dx != 0 or dy != 0:
                         offset_rect = final_draw_rect.translated(dx, dy)
                         painter.drawText(offset_rect, text_to_draw, text_option)

        # 3. Draw Main Text
        painter.setPen(main_text_color)
        painter.drawText(final_draw_rect, text_to_draw, text_option)

        # --- Cleanup ---
        painter.end()

        return pixmap


if __name__ == "__main__":
    # --- Test the SlideRenderer ---
    app = QApplication(sys.argv) # QApplication is needed for QPixmap, QFont etc.

    # Define target render size
    TARGET_WIDTH = 1920
    TARGET_HEIGHT = 1080
    # TARGET_WIDTH = 1280
    # TARGET_HEIGHT = 720

    # --- Create Sample Slide Data ---
    slides_to_test = []
    slides_to_test.append(SlideData(lyrics="Just simple lyrics.\nSecond line."))
    slides_to_test.append(SlideData(lyrics="Lyrics with Red Background", background_color="#800000"))
    # Use a real path to an image if you have one, otherwise this will just show the background color
    slides_to_test.append(SlideData(lyrics="Lyrics with Background Image", background_image_path="c:/Users/Logan/Documents/Plucky/Plucky/resources/default_background.png"))
    slides_to_test.append(SlideData(lyrics="BIG YELLOW TEXT\nCenter Aligned", template_settings={"color": "#FFFF00", "font": {"size": 100, "family": "Impact"}, "alignment": "center"}))
    slides_to_test.append(SlideData(lyrics="Right Aligned, Small", template_settings={"color": "#00FF00", "font": {"size": 40}, "alignment": "right", "position": {"x": "95%", "y": "10%"}}))
    outline_template = DEFAULT_TEMPLATE.copy()
    outline_template["outline"] = {"enabled": True, "color": "#0000FF", "width": 4}
    slides_to_test.append(SlideData(lyrics="Text with Outline", template_settings=outline_template))
    shadow_template = DEFAULT_TEMPLATE.copy()
    shadow_template["shadow"] = {"enabled": True, "color": "#404040", "offset_x": 5, "offset_y": 5}
    slides_to_test.append(SlideData(lyrics="Text with Shadow", template_settings=shadow_template))
    all_caps_template = DEFAULT_TEMPLATE.copy()
    all_caps_template["font"]["force_all_caps"] = True
    slides_to_test.append(SlideData(lyrics="This should be all caps", template_settings=all_caps_template))

    # --- Create Renderer ---
    renderer = SlideRenderer()

    # --- Render and Save Each Slide ---
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Create the output directory relative to the script's location
    output_dir = os.path.join(script_dir, "test_renders")
    os.makedirs(output_dir, exist_ok=True)

    for i, slide in enumerate(slides_to_test):
        print(f"Rendering slide {i+1}...")
        rendered_pixmap = renderer.render_slide(slide, TARGET_WIDTH, TARGET_HEIGHT)

        output_filename = os.path.join(output_dir, f"test_render_{i+1}.png")
        if rendered_pixmap.save(output_filename):
            print(f"Saved: {output_filename}")
        else:
            print(f"Error saving: {output_filename}")

    print("\nTest rendering complete. Check the 'test_renders' directory.")
    # Note: QApplication doesn't need exec() here as we're not showing windows.