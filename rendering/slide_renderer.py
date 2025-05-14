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
                logging.warning(
                    f"Provided base_pixmap for slide {slide_id_for_log} is invalid "
                    f"(isNull: {base_pixmap.isNull()}, size: {base_pixmap.size()} vs target: {width}x{height}). "
                    "Creating new pixmap instead."
                )
            pixmap = QPixmap(width, height)
            # Initialize new pixmap to be fully transparent.
            # This is the base if no opaque background is specified or drawn for this slide.
            pixmap.fill(Qt.GlobalColor.transparent)
            
        if pixmap.isNull():
            logging.error(f"Failed to create QPixmap of size {width}x{height} for slide_data: {slide_data.id}") # Line 94
            error_pixmap = QPixmap(1, 1) # Line 95
            error_pixmap.fill(Qt.GlobalColor.magenta) # Error indicator # Line 96
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time # Line 97
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
        font_setup_start_time = time.perf_counter()
        font = QFont()
        font_family = font_settings.get("family", "Arial")
        font.setFamily(font_family)
        font_info_check = QFontInfo(font) # Check against the font set on the painter later
        if font_info_check.family().lower() != font_family.lower() and not font_info_check.exactMatch() :
            logging.warning(f"Font family '{font_family}' not found or resolved differently for slide ID {slide_id_for_log}. Using default or system fallback '{font_info_check.family()}'.")
            font_error_occurred = True

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
        font_setup_duration = time.perf_counter() - font_setup_start_time
        time_spent_on_fonts += font_setup_duration
        # print(f"[BENCHMARK_RENDERER_DETAIL] Slide ID {slide_id_for_log} - Font Setup ('{font_family}', {actual_font_size_pt}pt): {font_setup_duration:.4f}s")

        # --- Prepare Text ---
        force_caps = font_settings.get('force_all_caps', False)
        text_to_draw = slide_data.lyrics.upper() if force_caps else slide_data.lyrics

        if not text_to_draw: # Nothing more to do if no lyrics
            painter.end()
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            benchmark_data["images"] = time_spent_on_images
            benchmark_data["fonts"] = time_spent_on_fonts
            # layout and draw remain 0.0
            
            # print(f"[BENCHMARK_RENDERER_SUMMARY] Slide ID {slide_id_for_log} - Total Render (no text): {benchmark_data['total_render']:.4f}s (Images: {benchmark_data['images']:.4f}s, Fonts: {benchmark_data['fonts']:.4f}s)")
            return pixmap, font_error_occurred, benchmark_data


        # --- Calculate Text Layout ---
        text_layout_start_time = time.perf_counter()
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

        text_layout_duration = time.perf_counter() - text_layout_start_time
        time_spent_on_text_layout += text_layout_duration
        # print(f"[BENCHMARK_RENDERER_DETAIL] Slide ID {slide_id_for_log} - Text Layout Calc: {text_layout_duration:.4f}s")
        # --- Draw Text Effects and Main Text ---
        main_text_color = QColor(color_setting)

        # 1. Draw Shadow
        if shadow_settings.get("enabled", False):
            shadow_color = QColor(shadow_settings.get("color", "#000000"))
            shadow_offset_x = shadow_settings.get("offset_x", 3) * (width / 1920.0) # Scale offset
            shadow_offset_y = shadow_settings.get("offset_y", 3) * (height / 1080.0) # Scale offset
            shadow_rect = final_draw_rect.translated(shadow_offset_x, shadow_offset_y)
            painter.setPen(shadow_color)
            shadow_draw_start_time = time.perf_counter()
            painter.drawText(shadow_rect, text_to_draw, text_option)
            time_spent_on_text_draw += time.perf_counter() - shadow_draw_start_time

        # 2. Draw Outline
        if outline_settings.get("enabled", False):
            outline_color = QColor(outline_settings.get("color", "#000000"))
            # Scale outline width slightly
            outline_width = max(1, int(outline_settings.get("width", 2) * (height / 1080.0)))
            painter.setPen(outline_color)
            # Simple multi-draw outline
            outline_draw_start_time = time.perf_counter()
            for dx in range(-outline_width, outline_width + 1, outline_width):
                 for dy in range(-outline_width, outline_width + 1, outline_width):
                     if dx != 0 or dy != 0:
                         offset_rect = final_draw_rect.translated(dx, dy)
                         painter.drawText(offset_rect, text_to_draw, text_option)
            time_spent_on_text_draw += time.perf_counter() - outline_draw_start_time

        # 3. Draw Main Text
        main_text_draw_start_time = time.perf_counter()
        painter.setPen(main_text_color)
        painter.drawText(final_draw_rect, text_to_draw, text_option)
        time_spent_on_text_draw += (time.perf_counter() - main_text_draw_start_time)
        # print(f"[BENCHMARK_RENDERER_DETAIL] Slide ID {slide_id_for_log} - Text Draw (incl. effects): {time_spent_on_text_draw:.4f}s")

        # --- Cleanup ---
        painter.end()

        benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
        benchmark_data["images"] = time_spent_on_images
        benchmark_data["fonts"] = time_spent_on_fonts
        benchmark_data["layout"] = time_spent_on_text_layout
        benchmark_data["draw"] = time_spent_on_text_draw

        # print(f"[BENCHMARK_RENDERER_SUMMARY] Slide ID {slide_id_for_log} - Total Render: {benchmark_data['total_render']:.4f}s (Images: {benchmark_data['images']:.4f}s, Fonts: {benchmark_data['fonts']:.4f}s, Layout: {benchmark_data['layout']:.4f}s, Draw: {benchmark_data['draw']:.4f}s)")

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