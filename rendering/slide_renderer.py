import sys
import os
import logging
import time # For benchmarking
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

    def __init__(self, app_settings=None):
        """
        Initializes the SlideRenderer.
        app_settings: Optional application settings object to control features
                      like checkerboard for transparency.
        """
        self.app_settings = app_settings
        self._init_checkerboard_style()

    def render_slide(self, slide_data: SlideData, width: int, height: int, base_pixmap: QPixmap = None, is_final_output: bool = False) -> tuple[QPixmap, bool, dict]:
        """
        Renders the given slide data onto a QPixmap of the specified dimensions.

        Args:
            slide_data: An instance of SlideData containing the content and style.
            width: The target width of the output pixmap.
            height: The target height of the output pixmap.
            base_pixmap: Optional. If provided, this pixmap is used as the base layer.
                         The current slide's content will be rendered on top of it.
            is_final_output: bool. True if this render is for the live output window,
                                  False for previews (e.g., slide buttons).

        Returns:
            A tuple containing:
                - A QPixmap with the rendered slide.
                - A boolean indicating if a font error/fallback occurred (True if error, False otherwise).
                - A dictionary with detailed benchmark timings for this slide.
        """
        total_render_start_time = time.perf_counter()
        slide_id_for_log = slide_data.id if slide_data else "UNKNOWN_SLIDE"

        font_error_occurred = False # Initialize error flag
        time_spent_on_images = 0.0
        time_spent_on_fonts = 0.0
        time_spent_on_text_layout = 0.0
        time_spent_on_text_draw = 0.0
        
        benchmark_data = {
            "total_render": 0.0, "images": 0.0, "fonts": 0.0, 
            "layout": 0.0, "draw": 0.0
        }

        if width <= 0 or height <= 0:
            logging.warning(f"Invalid dimensions for rendering slide: {width}x{height}. Returning blank pixmap.")
            pixmap = QPixmap(1, 1) 
            pixmap.fill(Qt.GlobalColor.transparent)
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            # Return True for font_error_occurred to signal a problem
            return pixmap, True, benchmark_data

        is_on_base = False
        if base_pixmap and not base_pixmap.isNull() and base_pixmap.size() == QSize(width, height):
            pixmap = base_pixmap.copy() # Work on a copy to not alter the original base
            is_on_base = True
            # If using a base, we don't fill it with transparent initially,
            # as we want to preserve the base_pixmap's content.
            # The slide's own background (if any) will be drawn over this.
        else:
            if base_pixmap: # Log if provided but invalid (e.g., wrong size)
                logging.warning(f"Provided base_pixmap for slide {slide_id_for_log} is invalid "
                                f"(isNull: {base_pixmap.isNull()}, size: {base_pixmap.size()} vs target: {width}x{height}). "
                                "Creating new pixmap instead.")
            pixmap = QPixmap(width, height)


            # Initialize new pixmap to be fully transparent.
            # This is the base if no opaque background is specified or drawn for this slide.
            pixmap.fill(Qt.GlobalColor.transparent)
            
        if pixmap.isNull():
            logging.error(f"Failed to create QPixmap of size {width}x{height} for slide_data: {slide_data.id}") # Line 94
            error_pixmap = QPixmap(1, 1) # Line 95
            error_pixmap.fill(Qt.GlobalColor.magenta)
            return error_pixmap, True, benchmark_data # Line 98

        
            
        # --- Prepare Painter ---
        painter = QPainter(pixmap)
        if not painter.isActive():
            logging.error(f"QPainter could not be activated on pixmap for slide_data: {slide_data.id}")
            painter.end() 
            error_pixmap = QPixmap(1, 1); error_pixmap.fill(Qt.GlobalColor.red)
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            return error_pixmap, True, benchmark_data
        self._setup_painter_hints(painter)

        # --- Draw Background (Image, Color, or Checkerboard) ---
        time_spent_on_images += self._render_background(painter, slide_data, pixmap.rect(), slide_id_for_log, is_on_base, is_final_output)

        # --- Render Text Boxes from Layout ---
        current_template_settings = slide_data.template_settings if slide_data.template_settings else {}
        defined_text_boxes = current_template_settings.get("text_boxes", [])
        slide_text_content_map = current_template_settings.get("text_content", {})

        # Fallback for slides that only have slide_data.lyrics (older format or simple slides)
        # If no text_boxes are defined in template_settings, but lyrics exist, render them with a default.
        if not defined_text_boxes and slide_data.lyrics:
            # Use a simplified default text box definition for rendering legacy lyrics
            # This ensures something is shown.
            # These properties should match the expected keys from a resolved style.
            logging.info(f"Slide {slide_id_for_log}: No text_boxes in template_settings, falling back to rendering slide_data.lyrics with defaults.")
            defined_text_boxes = [{
                "id": "legacy_lyrics_box", # Internal ID for this fallback
                "x_pc": 5.0, "y_pc": 5.0, "width_pc": 90.0, "height_pc": 90.0, # Default position/size
                "h_align": "center", "v_align": "center", # Default alignment
                # Resolved style properties (not just a style name)
                "font_family": "Arial", 
                "font_size": 58, # Base size for 1080p
                "font_color": "#FFFFFF",
                "force_all_caps": False,
                "outline_enabled": False, 
                # "outline_color": "#000000", "outline_width": 2,
                "shadow_enabled": False,
                # "shadow_color": "#00000080", "shadow_offset_x": 2, "shadow_offset_y": 2, "shadow_blur_radius": 4
                # Add other style properties as needed for the fallback (bold, italic, etc.)
            }]
            # Use the slide's main lyrics for this fallback box
            slide_text_content_map = {"legacy_lyrics_box": slide_data.lyrics}

        if not defined_text_boxes: # No text boxes to render, even after fallback
            painter.end()
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            benchmark_data["images"] = time_spent_on_images
            benchmark_data["fonts"] = time_spent_on_fonts
            return pixmap, font_error_occurred, benchmark_data

        for tb_props in defined_text_boxes:
            tb_id = tb_props.get("id", "unknown_box")
            text_to_draw = slide_text_content_map.get(tb_id, "") # Get text for this specific box

            if not text_to_draw.strip(): # Skip if no text for this box
                continue

            # --- Prepare Font for this text box (using resolved style properties from tb_props) ---
            font_setup_start_time = time.perf_counter()
            font = QFont()
            font_family = tb_props.get("font_family", "Arial") # Default from resolved style
            font.setFamily(font_family)
            font_info_check = QFontInfo(font)
            if font_info_check.family().lower() != font_family.lower() and not font_info_check.exactMatch():
                logging.warning(f"Font family '{font_family}' for textbox '{tb_id}' (slide {slide_id_for_log}) not found. Using fallback '{font_info_check.family()}'.")
                font_error_occurred = True # Flag that a font issue occurred on this slide

            base_font_size_pt = tb_props.get("font_size", 58) # Default from resolved style
            target_output_height_for_font_scaling = 1080 # The height the base_font_size_pt is designed for
            
            font_scaling_factor = 1.0
            if target_output_height_for_font_scaling > 0 and height > 0:
                 font_scaling_factor = height / target_output_height_for_font_scaling
            
            actual_font_size_pt = max(8, int(base_font_size_pt * font_scaling_factor))
            font.setPointSize(actual_font_size_pt)

            # Apply other font properties from tb_props (resolved style)
            # font.setBold(tb_props.get("font_bold", False)) # Example
            # font.setItalic(tb_props.get("font_italic", False)) # Example
            painter.setFont(font)
            time_spent_on_fonts += (time.perf_counter() - font_setup_start_time)

            # --- Prepare Text for this text box ---
            if tb_props.get("force_all_caps", False): # From resolved style
                text_to_draw = text_to_draw.upper()

            # --- Calculate Text Layout for this text box ---
            text_layout_start_time = time.perf_counter()

            # Calculate pixel rectangle for this text box based on percentages from tb_props
            tb_x_pc = tb_props.get("x_pc", 0.0)
            tb_y_pc = tb_props.get("y_pc", 0.0)
            tb_w_pc = tb_props.get("width_pc", 100.0)
            tb_h_pc = tb_props.get("height_pc", 100.0)

            tb_pixel_rect_x = (tb_x_pc / 100.0) * width
            tb_pixel_rect_y = (tb_y_pc / 100.0) * height
            tb_pixel_rect_w = (tb_w_pc / 100.0) * width
            tb_pixel_rect_h = (tb_h_pc / 100.0) * height
            # This is the QRectF where painter.drawText will place the text, respecting alignment.
            text_box_draw_rect = QRectF(tb_pixel_rect_x, tb_pixel_rect_y, tb_pixel_rect_w, tb_pixel_rect_h)

            # Text alignment options for this text box
            tb_text_option = QTextOption()
            h_align_str = tb_props.get("h_align", "center") # From layout definition
            v_align_str = tb_props.get("v_align", "center") # From layout definition

            qt_h_align = Qt.AlignmentFlag.AlignHCenter
            if h_align_str == "left": qt_h_align = Qt.AlignmentFlag.AlignLeft
            elif h_align_str == "right": qt_h_align = Qt.AlignmentFlag.AlignRight

            qt_v_align = Qt.AlignmentFlag.AlignVCenter
            if v_align_str == "top": qt_v_align = Qt.AlignmentFlag.AlignTop
            elif v_align_str == "bottom": qt_v_align = Qt.AlignmentFlag.AlignBottom
            
            tb_text_option.setAlignment(qt_h_align | qt_v_align)
            tb_text_option.setWrapMode(QTextOption.WrapMode.WordWrap) # Text will wrap within text_box_draw_rect
            
            time_spent_on_text_layout += (time.perf_counter() - text_layout_start_time)

            # --- Draw Text Effects and Main Text for this text box ---
            # All colors, offsets, etc., should come from tb_props (resolved style)
            tb_main_text_color = QColor(tb_props.get("font_color", "#FFFFFF"))

            # Shadow for this text box
            if tb_props.get("shadow_enabled", False):
                shadow_color = QColor(tb_props.get("shadow_color", "#00000080")) # Default from resolved style
                # Scale shadow offsets by the same factor as font size for consistency relative to text
                shadow_offset_x = tb_props.get("shadow_offset_x", 2) * font_scaling_factor
                shadow_offset_y = tb_props.get("shadow_offset_y", 2) * font_scaling_factor
                # Note: QPainter.drawText doesn't have a direct blur radius for shadow.
                # A true blur would require more complex rendering (e.g., QGraphicsDropShadowEffect on a QGraphicsTextItem,
                # then rendering that scene to a pixmap, or manual multi-pass drawing with varying opacity).
                # For now, we just use the offset.
                shadow_rect = text_box_draw_rect.translated(shadow_offset_x, shadow_offset_y)
                painter.setPen(shadow_color)
                draw_call_start_time = time.perf_counter()
                painter.drawText(shadow_rect, text_to_draw, tb_text_option)
                time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)

            # Outline for this text box
            if tb_props.get("outline_enabled", False):
                outline_color = QColor(tb_props.get("outline_color", "#000000")) # Default from resolved style
                # Scale outline width by font_scaling_factor to keep it proportional to text size
                outline_width_px = max(1, int(tb_props.get("outline_width", 1) * font_scaling_factor)) 
                
                painter.setPen(outline_color) # Pen for outline color
                draw_call_start_time = time.perf_counter()
                # Simple multi-draw outline: draw text at 8 surrounding points
                for dx_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                    for dy_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                        if dx_o != 0 or dy_o != 0: # Don't draw center point (main text will cover)
                            offset_rect = text_box_draw_rect.translated(dx_o, dy_o)
                            painter.drawText(offset_rect, text_to_draw, tb_text_option)
                time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)

            # Main Text for this text box (drawn on top of shadow/outline)
            painter.setPen(tb_main_text_color)
            draw_call_start_time = time.perf_counter()
            painter.drawText(text_box_draw_rect, text_to_draw, tb_text_option)
            time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)

        # --- Cleanup ---
        painter.end()

        benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
        benchmark_data["images"] = time_spent_on_images
        benchmark_data["fonts"] = time_spent_on_fonts
        benchmark_data["layout"] = time_spent_on_text_layout
        benchmark_data["draw"] = time_spent_on_text_draw

        return pixmap, font_error_occurred, benchmark_data
    def _init_checkerboard_style(self):
        """Initializes checkerboard style attributes."""
        self.checker_color1 = QColor(220, 220, 220)  # Light gray
        self.checker_color2 = QColor(200, 200, 200)  # Slightly darker gray
        self.checker_size = 10  # Size of each square in pixels

    def _setup_painter_hints(self, painter: QPainter):
        """Sets common render hints for the painter."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def _draw_checkerboard_pattern(self, painter: QPainter, target_rect: QRect):
        """Draws a checkerboard pattern within the target_rect."""
        painter.save()
        painter.setPen(Qt.NoPen)
        for y_start in range(target_rect.top(), target_rect.bottom(), self.checker_size):
            for x_start in range(target_rect.left(), target_rect.right(), self.checker_size):
                is_even_row = ((y_start - target_rect.top()) // self.checker_size) % 2 == 0
                is_even_col = ((x_start - target_rect.left()) // self.checker_size) % 2 == 0
                current_color = self.checker_color1 if is_even_row == is_even_col else self.checker_color2
                cell_width = min(self.checker_size, target_rect.right() - x_start + 1)
                cell_height = min(self.checker_size, target_rect.bottom() - y_start + 1)
                painter.fillRect(x_start, y_start, cell_width, cell_height, current_color)
        painter.restore()

    def _render_background(self, painter: QPainter, slide_data: SlideData, target_rect: QRect, slide_id_for_log: str, is_on_base: bool, is_final_output: bool) -> float:
        """Renders the background (image, color, or checkerboard) and returns time spent on image operations."""
        time_spent_on_images_local = 0.0

        # 1. Try Background Image first
        bg_image_load_start_time = time.perf_counter()
        bg_pixmap_loaded = None
        if slide_data.background_image_path and os.path.exists(slide_data.background_image_path):
            loaded_bg = QPixmap(slide_data.background_image_path)
            if not loaded_bg.isNull():
                bg_pixmap_loaded = loaded_bg
            else:
                logging.warning(f"Could not load background image: {slide_data.background_image_path} for slide ID {slide_id_for_log}")
        time_spent_on_images_local += (time.perf_counter() - bg_image_load_start_time)

        if bg_pixmap_loaded:
            bg_image_draw_start_time = time.perf_counter()
            painter.drawPixmap(target_rect, bg_pixmap_loaded)
            time_spent_on_images_local += (time.perf_counter() - bg_image_draw_start_time)
        else:
            # No valid background image, so use background_color or checkerboard
            bg_qcolor = QColor(slide_data.background_color)
            if not bg_qcolor.isValid():
                logging.warning(f"Invalid background_color string: '{slide_data.background_color}' for slide ID {slide_id_for_log}. Defaulting to transparent.")
                bg_qcolor = QColor(Qt.GlobalColor.transparent)

            if bg_qcolor.alpha() == 0:  # Fully transparent color
                # Only show checkerboard if this slide is standalone (not on a base)
                # and the setting is enabled, AND it's not for final output.
                show_checkerboard_setting = True # Default if no app_settings
                if self.app_settings and hasattr(self.app_settings, 'get_setting'):
                    show_checkerboard_setting = self.app_settings.get_setting("display_checkerboard_for_transparency", True)
                
                if show_checkerboard_setting and not is_on_base and not is_final_output:
                    self._draw_checkerboard_pattern(painter, target_rect)
                # If is_on_base is True, or show_checkerboard_setting is False, do nothing, leaving the underlying pixmap visible.
            else:  # Opaque or semi-transparent color
                painter.fillRect(target_rect, bg_qcolor)
        return time_spent_on_images_local



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
    slides_to_test.append(SlideData(lyrics="Transparent BG (Checkerboard)", background_color="#00000000")) # Alpha = 00
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
    
    # Mock AppSettings for testing checkerboard
    class MockAppSettings:
        def get_setting(self, key, default_value):
            if key == "display_checkerboard_for_transparency":
                return True # Test with checkerboard enabled
            return default_value
    
    # --- Create Renderer ---
    renderer = SlideRenderer(app_settings=MockAppSettings())

    # --- Render and Save Each Slide ---
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Create the output directory relative to the script's location
    output_dir = os.path.join(script_dir, "test_renders")
    os.makedirs(output_dir, exist_ok=True)

    for i, slide in enumerate(slides_to_test):
        print(f"Rendering standalone slide {i+1}...")
        rendered_pixmap, _, _ = renderer.render_slide(slide, TARGET_WIDTH, TARGET_HEIGHT, is_final_output=False) # For preview, show checkerboard


        output_filename = os.path.join(output_dir, f"test_render_{i+1}.png")
        if rendered_pixmap.save(output_filename):
            print(f"Saved: {output_filename}")
        else:
            print(f"Error saving: {output_filename}")
    
    print("\n--- Testing Layered Rendering ---")
    # Create a base background slide (e.g., with an image)
    base_bg_slide_data = SlideData(lyrics="", background_image_path="c:/Users/Logan/Documents/Plucky/Plucky/resources/default_background.png")
    if not os.path.exists(base_bg_slide_data.background_image_path):
        print(f"WARNING: Base background image not found: {base_bg_slide_data.background_image_path}. Layered test might not show image.")
        # Fallback to a color if image not found for test
        base_bg_slide_data = SlideData(lyrics="", background_color="#3333DD") # A noticeable color

    print("Rendering base background layer...")
    base_bg_pixmap, _, _ = renderer.render_slide(base_bg_slide_data, TARGET_WIDTH, TARGET_HEIGHT, is_final_output=True) # This is for a live output base
    base_bg_pixmap.save(os.path.join(output_dir, "test_render_LAYER_0_base_background.png"))
    print("Saved: test_render_LAYER_0_base_background.png")

    # Create a lyric slide with a fully transparent background
    lyric_slide_overlay_data = SlideData(
        lyrics="Lyrics Overlaid on Image\n(Transparent Slide Background)",
        background_color="#00000000", # Fully transparent
        template_settings={"color": "#FFFF00", "font": {"size": 70, "family": "Arial"}, "alignment": "center"}
    )
    print("Rendering lyric slide ON TOP of base background...")
    layered_pixmap, _, _ = renderer.render_slide(lyric_slide_overlay_data, TARGET_WIDTH, TARGET_HEIGHT, base_pixmap=base_bg_pixmap, is_final_output=True)
    layered_pixmap.save(os.path.join(output_dir, "test_render_LAYER_1_lyrics_on_base.png"))
    print("Saved: test_render_LAYER_1_lyrics_on_base.png")

    # Create another lyric slide, this time with a semi-transparent background of its own
    semi_transparent_overlay_data = SlideData(
        lyrics="Text on Semi-Transparent Bar",
        background_color="#80000000", # Semi-transparent black
        template_settings={"color": "#FFFFFF", "font": {"size": 60, "family": "Verdana"}, "alignment": "center", "position": {"y": "50%"}}
    )
    print("Rendering semi-transparent lyric slide ON TOP of base background...")
    layered_semi_pixmap, _, _ = renderer.render_slide(semi_transparent_overlay_data, TARGET_WIDTH, TARGET_HEIGHT, base_pixmap=base_bg_pixmap, is_final_output=True)
    layered_semi_pixmap.save(os.path.join(output_dir, "test_render_LAYER_2_semi_transparent_on_base.png"))
    print("Saved: test_render_LAYER_2_semi_transparent_on_base.png")

    print("\nTest rendering complete. Check the 'test_renders' directory.")
    # Note: QApplication doesn't need exec() here as we're not showing windows.