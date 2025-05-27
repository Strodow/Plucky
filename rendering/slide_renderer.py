import sys
import os
import logging
import time # For benchmarking
from PySide6.QtWidgets import QApplication # Needed for testing QPixmap/QPainter
import copy # For deepcopy
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QTextOption,
    QFontInfo, QImage, qAlpha, qRgba # Added QImage, qAlpha, qRgba here
)
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize
from typing import Optional, List, Tuple, Dict, Any # Added List, Tuple, Dict, Any
from abc import ABC, abstractmethod # For abstract base class

# --- Local Imports ---
# Assume data_models is in the parent directory or accessible via PYTHONPATH
try:
    # This works if running from the YourProject directory
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE
except ImportError:
    # Fallback for different execution contexts or structures
    import sys
    import os
    # Add the parent directory (YourProject) to the Python path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data_models.slide_data import SlideData, DEFAULT_TEMPLATE
    # Attempt to import ImageCacheManager for standalone testing of this file
    from core.image_cache_manager import ImageCacheManager

class RenderLayerHandler(ABC):
    """Abstract base class for a render layer."""
    def __init__(self, app_settings: Optional[Any] = None):
        self.app_settings = app_settings

    @abstractmethod
    def render(self, current_pixmap: QPixmap, slide_data: SlideData, target_width: int, target_height: int, is_final_output: bool) -> Tuple[QPixmap, bool, Dict[str, float]]:
        """
        Renders this layer's content onto/into the current_pixmap.
        
        Args:
            current_pixmap: The pixmap from the previous layer (or initial canvas).
            slide_data: The data for the current slide.
            target_width: The target width of the output.
            target_height: The target height of the output.
            is_final_output: True if for live output, False for previews.

        Returns:
            A tuple: (output_pixmap, font_error_occurred_in_this_layer, benchmark_data_for_this_layer)
        """
        pass

    def _setup_painter_hints(self, painter: QPainter):
        """Sets common render hints for the painter."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

class BackgroundRenderLayer(RenderLayerHandler):
    def __init__(self, app_settings: Optional[Any] = None, image_cache_manager: Optional['ImageCacheManager'] = None):
        super().__init__(app_settings)
        self.image_cache_manager = image_cache_manager
        self._init_checkerboard_style() # From original SlideRenderer

    def _init_checkerboard_style(self): # From original SlideRenderer
        self.checker_color1 = QColor(220, 220, 220)
        self.checker_color2 = QColor(200, 200, 200)
        self.checker_size = 10

    def _draw_checkerboard_pattern(self, painter: QPainter, target_rect: QRect): # From original SlideRenderer
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for y_start in range(target_rect.top(), target_rect.bottom(), self.checker_size):
            for x_start in range(target_rect.left(), target_rect.right(), self.checker_size):
                is_even_row = ((y_start - target_rect.top()) // self.checker_size) % 2 == 0
                is_even_col = ((x_start - target_rect.left()) // self.checker_size) % 2 == 0
                current_color = self.checker_color1 if is_even_row == is_even_col else self.checker_color2
                cell_width = min(self.checker_size, target_rect.right() - x_start + 1)
                cell_height = min(self.checker_size, target_rect.bottom() - y_start + 1)
                painter.fillRect(x_start, y_start, cell_width, cell_height, current_color)
        painter.restore()

    def render(self, current_pixmap: QPixmap, slide_data: SlideData, target_width: int, target_height: int, is_final_output: bool) -> Tuple[QPixmap, bool, Dict[str, float]]:
        start_time = time.perf_counter()
        # This layer draws the slide's own background onto the current_pixmap.
        # If current_pixmap was a base (e.g., live background), this draws over it.
        output_pixmap = current_pixmap.copy() # Work on a copy

        painter = QPainter(output_pixmap)
        if not painter.isActive(): return output_pixmap, False, {"images": 0.0}
        self._setup_painter_hints(painter)

        # --- Logic from SlideRenderer._render_background ---
        effective_bg_color_hex: Optional[str] = None
        effective_background_image_path: Optional[str] = None

        if slide_data.background_image_path and os.path.exists(slide_data.background_image_path):
            effective_background_image_path = slide_data.background_image_path
        elif slide_data.background_color:
            effective_bg_color_hex = slide_data.background_color
        elif slide_data.template_settings:
            bg_image_path_from_template = slide_data.template_settings.get("background_image_path")
            if bg_image_path_from_template and os.path.exists(bg_image_path_from_template):
                effective_background_image_path = bg_image_path_from_template
            else:
                effective_bg_color_hex = slide_data.template_settings.get("background_color")
        
        # Detailed image processing benchmarks
        time_img_load = 0.0
        time_img_scale = 0.0
        time_img_from_image = 0.0
        time_img_draw = 0.0

        if effective_background_image_path:
            loaded_bg_pixmap_for_drawing = QPixmap() # Initialize as null
            target_qsize = QSize(target_width, target_height)
            cached_image_path = None

            if self.image_cache_manager:
                cached_image_path = self.image_cache_manager.get_cached_image_path(effective_background_image_path, target_qsize)

            if cached_image_path:
                # Load from cache
                img_load_start = time.perf_counter()
                # print(f"DEBUG BRL: Loading from CACHE: {cached_image_path}")
                cached_qimage = QImage(cached_image_path) # This is already scaled
                time_img_load = time.perf_counter() - img_load_start
                if not cached_qimage.isNull():
                    img_from_image_start = time.perf_counter()
                    loaded_bg_pixmap_for_drawing = QPixmap.fromImage(cached_qimage)
                    time_img_from_image = time.perf_counter() - img_from_image_start
                else:
                    print(f"BackgroundRenderLayer: Warning - Failed to load QImage from cached path: {cached_image_path}")
            else:
                # Not in cache or no cache manager, load original and scale
                img_load_start = time.perf_counter()
                source_image = QImage(effective_background_image_path)
                time_img_load = time.perf_counter() - img_load_start

                if not source_image.isNull():
                    img_scale_start = time.perf_counter()
                    scaled_qimage = source_image # Default to original if no scaling needed
                    # Scale to fit within target_width, target_height, keeping aspect ratio
                    scaled_qimage = source_image.scaled(target_width, target_height, 
                                                        Qt.AspectRatioMode.KeepAspectRatio, # Changed from KeepAspectRatioByExpanding
                                                        Qt.TransformationMode.SmoothTransformation)
                    time_img_scale = time.perf_counter() - img_scale_start
                    
                    img_from_image_start = time.perf_counter()
                    if not scaled_qimage.isNull():
                        loaded_bg_pixmap_for_drawing = QPixmap.fromImage(scaled_qimage)
                        if self.image_cache_manager and not scaled_qimage.isNull(): # Cache the newly scaled image
                            self.image_cache_manager.cache_image(effective_background_image_path, target_qsize, scaled_qimage)
                    time_img_from_image = time.perf_counter() - img_from_image_start

            if not loaded_bg_pixmap_for_drawing.isNull():
                img_draw_start = time.perf_counter()
                # Calculate position to center the aspect-ratio-preserved image
                final_pixmap_to_draw = loaded_bg_pixmap_for_drawing # This is already scaled to fit
                
                x_offset = (target_width - final_pixmap_to_draw.width()) / 2
                y_offset = (target_height - final_pixmap_to_draw.height()) / 2
                
                target_draw_rect = QRectF(x_offset, y_offset, 
                                          final_pixmap_to_draw.width(), 
                                          final_pixmap_to_draw.height())
                painter.drawPixmap(target_draw_rect.toRect(), final_pixmap_to_draw) # Draw centered
                time_img_draw = time.perf_counter() - img_draw_start
            else: # Failed to load or process image
                effective_background_image_path = None # Fallback to color
        
        if not effective_background_image_path: 
            bg_qcolor = QColor(Qt.GlobalColor.transparent)
            if effective_bg_color_hex:
                temp_qcolor = QColor(effective_bg_color_hex)
                if temp_qcolor.isValid(): bg_qcolor = temp_qcolor
            if bg_qcolor.alpha() == 0:
                show_checkerboard_setting = True
                if self.app_settings and hasattr(self.app_settings, 'get_setting'):
                    show_checkerboard_setting = self.app_settings.get_setting("display_checkerboard_for_transparency", True)
                if show_checkerboard_setting and not is_final_output:
                    self._draw_checkerboard_pattern(painter, output_pixmap.rect())
            else: # Opaque or semi-transparent color for this slide's background
                painter.fillRect(output_pixmap.rect(), bg_qcolor) # Draw onto the (potentially base) pixmap
        
        painter.end()
        benchmarks = {
            "images_total_processing": time_img_load + time_img_scale + time_img_from_image + time_img_draw, # Keep this for overall image time
            "image_load_qimage": time_img_load,
            "image_scale_qimage": time_img_scale,
            "image_from_qimage_to_qpixmap": time_img_from_image,
            "image_draw_qpixmap": time_img_draw,
            "total_background_layer": time.perf_counter() - start_time
        }
        return output_pixmap, False, benchmarks

class TextContentRenderLayer(RenderLayerHandler):
    def render(self, current_pixmap: QPixmap, slide_data: SlideData, target_width: int, target_height: int, is_final_output: bool) -> Tuple[QPixmap, bool, Dict[str, float]]:
        start_time = time.perf_counter()
        output_pixmap = current_pixmap.copy()
        painter = QPainter(output_pixmap)
        if not painter.isActive(): return output_pixmap, False, {}
        self._setup_painter_hints(painter)

        font_error_occurred = False
        time_spent_on_fonts = 0.0
        time_spent_on_text_layout = 0.0
        time_spent_on_text_draw = 0.0

        # --- Logic from original SlideRenderer for text boxes ---
        current_template_settings = slide_data.template_settings if slide_data.template_settings else {}
        defined_text_boxes = current_template_settings.get("text_boxes", [])
        slide_text_content_map = current_template_settings.get("text_content", {})

        if not defined_text_boxes:
            painter.end()
            return output_pixmap, False, {"fonts": 0, "layout": 0, "draw": 0, "total_text_layer": time.perf_counter() - start_time}

        for tb_props in defined_text_boxes:
            tb_id = tb_props.get("id", "unknown_box")
            text_to_draw = slide_text_content_map.get(tb_id, "")
            if not text_to_draw.strip(): continue

            font_setup_start_time = time.perf_counter()
            font = QFont()
            font_family = tb_props.get("font_family", "Arial")
            font.setFamily(font_family)
            font_info_check = QFontInfo(font)
            if font_info_check.family().lower() != font_family.lower() and not font_info_check.exactMatch():
                logging.warning(f"Font family '{font_family}' for textbox '{tb_id}' (slide {slide_data.id}) not found. Using fallback '{font_info_check.family()}'.")
                font_error_occurred = True

            base_font_size_pt = tb_props.get("font_size", 58)
            target_output_height_for_font_scaling = 1080
            font_scaling_factor = 1.0
            if target_output_height_for_font_scaling > 0 and target_height > 0:
                 font_scaling_factor = target_height / target_output_height_for_font_scaling
            actual_font_size_pt = max(8, int(base_font_size_pt * font_scaling_factor))
            font.setPointSize(actual_font_size_pt)
            painter.setFont(font)
            time_spent_on_fonts += (time.perf_counter() - font_setup_start_time)

            if tb_props.get("force_all_caps", False):
                text_to_draw = text_to_draw.upper()

            text_layout_start_time = time.perf_counter()
            tb_x_pc, tb_y_pc = tb_props.get("x_pc", 0.0), tb_props.get("y_pc", 0.0)
            tb_w_pc, tb_h_pc = tb_props.get("width_pc", 100.0), tb_props.get("height_pc", 100.0)
            tb_pixel_rect_x = (tb_x_pc / 100.0) * target_width
            tb_pixel_rect_y = (tb_y_pc / 100.0) * target_height
            tb_pixel_rect_w = (tb_w_pc / 100.0) * target_width
            tb_pixel_rect_h = (tb_h_pc / 100.0) * target_height
            text_box_draw_rect = QRectF(tb_pixel_rect_x, tb_pixel_rect_y, tb_pixel_rect_w, tb_pixel_rect_h)

            tb_text_option = QTextOption()
            h_align_str, v_align_str = tb_props.get("h_align", "center"), tb_props.get("v_align", "center")
            qt_h_align = Qt.AlignmentFlag.AlignLeft if h_align_str == "left" else Qt.AlignmentFlag.AlignRight if h_align_str == "right" else Qt.AlignmentFlag.AlignHCenter
            qt_v_align = Qt.AlignmentFlag.AlignTop if v_align_str == "top" else Qt.AlignmentFlag.AlignBottom if v_align_str == "bottom" else Qt.AlignmentFlag.AlignVCenter
            tb_text_option.setAlignment(qt_h_align | qt_v_align)
            tb_text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
            time_spent_on_text_layout += (time.perf_counter() - text_layout_start_time)

            tb_main_text_color = QColor(tb_props.get("font_color", "#FFFFFF"))
            if tb_props.get("shadow_enabled", False):
                shadow_color = QColor(tb_props.get("shadow_color", "#00000080"))
                shadow_offset_x = tb_props.get("shadow_offset_x", 2) * font_scaling_factor
                shadow_offset_y = tb_props.get("shadow_offset_y", 2) * font_scaling_factor
                shadow_rect = text_box_draw_rect.translated(shadow_offset_x, shadow_offset_y)
                painter.setPen(shadow_color)
                draw_call_start_time = time.perf_counter(); painter.drawText(shadow_rect, text_to_draw, tb_text_option); time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)
            if tb_props.get("outline_enabled", False):
                outline_color = QColor(tb_props.get("outline_color", "#000000"))
                outline_width_px = max(1, int(tb_props.get("outline_width", 1) * font_scaling_factor))
                painter.setPen(outline_color)
                draw_call_start_time = time.perf_counter()
                for dx_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                    for dy_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                        if dx_o != 0 or dy_o != 0: painter.drawText(text_box_draw_rect.translated(dx_o, dy_o), text_to_draw, tb_text_option)
                time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)
            painter.setPen(tb_main_text_color)
            draw_call_start_time = time.perf_counter(); painter.drawText(text_box_draw_rect, text_to_draw, tb_text_option); time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)

        painter.end()
        benchmarks = {"fonts": time_spent_on_fonts, "layout": time_spent_on_text_layout, "draw": time_spent_on_text_draw, "total_text_layer": time.perf_counter() - start_time}
        return output_pixmap, font_error_occurred, benchmarks

class LayeredSlideRenderer: # Renamed from SlideRenderer
    """Renders SlideData onto a QPixmap using a layered approach."""

    def __init__(self, app_settings=None, image_cache_manager: Optional['ImageCacheManager'] = None):
        """
        Initializes the LayeredSlideRenderer.
        app_settings: Optional application settings object to control features
                      like checkerboard for transparency.
        image_cache_manager: Optional manager for image caching.
        """
        self.app_settings = app_settings
        self.image_cache_manager = image_cache_manager
        if not self.image_cache_manager: # Create a default one if not provided
            self.image_cache_manager = ImageCacheManager()

        self.render_layers: List[RenderLayerHandler] = [
            BackgroundRenderLayer(app_settings, self.image_cache_manager),
            TextContentRenderLayer(app_settings)
            # Future layers can be added here
        ]

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
        
        benchmark_data = {
            "total_render": 0.0, 
            "images_total_processing": 0.0, # From BackgroundLayer (overall)
            "image_load_qimage": 0.0,
            "image_scale_qimage": 0.0,
            "image_from_qimage_to_qpixmap": 0.0,
            "image_draw_qpixmap": 0.0,
            "fonts": 0.0,  # From TextContentLayer
            "layout": 0.0, # From TextContentLayer
            "draw": 0.0,   # From TextContentLayer
            "total_background_layer": 0.0,
            "total_text_layer": 0.0
        }

        if width <= 0 or height <= 0:
            logging.warning(f"Invalid dimensions for rendering slide: {width}x{height}. Returning blank pixmap.")
            pixmap = QPixmap(1, 1) 
            pixmap.fill(Qt.GlobalColor.transparent)
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            return pixmap, True, benchmark_data

        # Initialize current_canvas
        current_canvas: QPixmap
        if base_pixmap and not base_pixmap.isNull() and base_pixmap.size() == QSize(width, height):
            current_canvas = base_pixmap.copy()
        else:
            if base_pixmap: # Log if provided but invalid (e.g., wrong size)
                logging.warning(f"Provided base_pixmap for slide {slide_id_for_log} is invalid "
                                f"(isNull: {base_pixmap.isNull()}, size: {base_pixmap.size()} vs target: {width}x{height}). "
                                "Creating new pixmap instead.")
            current_canvas = QPixmap(width, height)
            if current_canvas.isNull(): # Check if creation failed
                logging.error(f"Failed to create QPixmap of size {width}x{height} for slide_data: {slide_data.id}")
                error_pixmap = QPixmap(1, 1); error_pixmap.fill(Qt.GlobalColor.magenta)
                benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
                return error_pixmap, True, benchmark_data
            current_canvas.fill(Qt.GlobalColor.transparent)

        overall_font_error = False

        for layer_handler in self.render_layers:
            layer_output_pixmap, layer_font_error, layer_benchmarks = layer_handler.render(
                current_canvas, slide_data, width, height, is_final_output
            )
            current_canvas = layer_output_pixmap # Output of one layer is input to next
            
            if layer_font_error:
                overall_font_error = True
            
            for key, value in layer_benchmarks.items(): # Aggregate benchmarks
                benchmark_data[key] = benchmark_data.get(key, 0.0) + value
        
        if current_canvas.isNull(): # Should not happen if layers return valid pixmaps
            logging.error(f"Failed to create QPixmap of size {width}x{height} for slide_data: {slide_data.id}") # Line 94
            error_pixmap = QPixmap(1, 1) # Line 95
            error_pixmap.fill(Qt.GlobalColor.magenta)
            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            return error_pixmap, True, benchmark_data

        benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
        return current_canvas, overall_font_error, benchmark_data

    def render_key_matte(self, slide_data: SlideData, width: int, height: int) -> QPixmap:
        """
        Renders a key matte for the given slide data.
        The matte will have a black background, with all text elements
        (including shadows and outlines if enabled) rendered in solid white.

        Args:
            slide_data: An instance of SlideData containing the content and style.
            width: The target width of the output pixmap (e.g., DeckLink width).
            height: The target height of the output pixmap (e.g., DeckLink height).

        Returns:
            A QPixmap representing the key matte.
        """
        slide_id_for_log = slide_data.id if slide_data else "UNKNOWN_SLIDE_FOR_KEY_MATTE"

        if width <= 0 or height <= 0:
            logging.warning(f"Invalid dimensions for rendering key matte: {width}x{height}. Returning 1x1 black pixmap.")
            pixmap = QPixmap(1, 1)
            pixmap.fill(Qt.GlobalColor.black)
            return pixmap

        # 1. Render the slide's text content (with its inherent alpha) onto a temporary transparent base.
        content_with_alpha_pixmap = QPixmap(width, height)
        if content_with_alpha_pixmap.isNull():
            logging.error(f"Failed to create QPixmap of size {width}x{height} for key matte (slide_data: {slide_id_for_log})")
            error_pixmap = QPixmap(1, 1)
            error_pixmap.fill(Qt.GlobalColor.black) # Fallback to black
            return error_pixmap
        content_with_alpha_pixmap.fill(Qt.GlobalColor.transparent) # Start with a transparent base for content
        painter = QPainter(content_with_alpha_pixmap)
        if not painter.isActive():
            logging.error(f"QPainter could not be activated on pixmap for key matte (slide_data: {slide_id_for_log})")
            # painter.end() was already called implicitly by QPainter destructor if not active
            painter.end()
            return pixmap # Return the black pixmap

        self._setup_painter_hints(painter)
        
        # --- Render Text Boxes from Layout (similar to render_slide) ---
        current_template_settings = slide_data.template_settings if slide_data.template_settings else {}
        defined_text_boxes = current_template_settings.get("text_boxes", [])
        slide_text_content_map = current_template_settings.get("text_content", {})

        if not defined_text_boxes:
            # If no text boxes are defined (even from the System Default Fallback template),
            # then there's nothing to render for the key matte other than the black background.
            logging.info(f"KeyMatte for Slide {slide_id_for_log}: No text_boxes defined in template. Key matte will be black.")
            painter.end()
            # Fall through to the conversion step, which will result in a black matte.

        for tb_props in defined_text_boxes:
            tb_id = tb_props.get("id", "unknown_box_key")
            text_to_draw = slide_text_content_map.get(tb_id, "")

            if not text_to_draw.strip():
                continue

            font = QFont()
            font_family = tb_props.get("font_family", "Arial")
            font.setFamily(font_family)
            font_info_check = QFontInfo(font)
            if font_info_check.family().lower() != font_family.lower() and not font_info_check.exactMatch():
                logging.warning(f"KeyMatte Font: Family '{font_family}' for textbox '{tb_id}' (slide {slide_id_for_log}) not found. Using fallback '{font_info_check.family()}'.")

            base_font_size_pt = tb_props.get("font_size", 58)
            target_output_height_for_font_scaling = 1080
            font_scaling_factor = 1.0
            if target_output_height_for_font_scaling > 0 and height > 0:
                 font_scaling_factor = height / target_output_height_for_font_scaling
            actual_font_size_pt = max(8, int(base_font_size_pt * font_scaling_factor))
            font.setPointSize(actual_font_size_pt)
            painter.setFont(font)

            if tb_props.get("force_all_caps", False):
                text_to_draw = text_to_draw.upper()

            tb_x_pc, tb_y_pc = tb_props.get("x_pc", 0.0), tb_props.get("y_pc", 0.0)
            tb_w_pc, tb_h_pc = tb_props.get("width_pc", 100.0), tb_props.get("height_pc", 100.0)
            text_box_draw_rect = QRectF((tb_x_pc / 100.0) * width, (tb_y_pc / 100.0) * height,
                                        (tb_w_pc / 100.0) * width, (tb_h_pc / 100.0) * height)

            tb_text_option = self._get_text_options_from_props(tb_props)

            # --- CRITICAL CHANGE: Use actual colors from tb_props for rendering ---

            # Shadow (rendered with its actual color and alpha)
            if tb_props.get("shadow_enabled", False):
                shadow_color_hex = tb_props.get("shadow_color", "#00000080") # Default to semi-transparent black
                shadow_qcolor = QColor(shadow_color_hex)
                shadow_offset_x_scaled = tb_props.get("shadow_offset_x", 2) * font_scaling_factor
                shadow_offset_y_scaled = tb_props.get("shadow_offset_y", 2) * font_scaling_factor
                shadow_rect = text_box_draw_rect.translated(shadow_offset_x_scaled, shadow_offset_y_scaled)
                painter.setPen(shadow_qcolor)
                painter.drawText(shadow_rect, text_to_draw, tb_text_option)

            # Outline (rendered with its actual color and alpha)
            if tb_props.get("outline_enabled", False):
                outline_color_hex = tb_props.get("outline_color", "#000000") # Default to solid black
                outline_qcolor = QColor(outline_color_hex)
                outline_width_px_scaled = max(1, int(tb_props.get("outline_width", 1) * font_scaling_factor))
                painter.setPen(outline_qcolor)
                for dx_o in range(-outline_width_px_scaled, outline_width_px_scaled + 1, outline_width_px_scaled):
                    for dy_o in range(-outline_width_px_scaled, outline_width_px_scaled + 1, outline_width_px_scaled):
                        if dx_o != 0 or dy_o != 0:
                            painter.drawText(text_box_draw_rect.translated(dx_o, dy_o), text_to_draw, tb_text_option)
            
            # Main text (rendered with its actual color and alpha)
            font_color_hex = tb_props.get("font_color", "#FFFFFF") # Default to solid white
            main_text_qcolor = QColor(font_color_hex)
            painter.setPen(main_text_qcolor)
            painter.drawText(text_box_draw_rect, text_to_draw, tb_text_option)

        painter.end()

        # 2. Convert the content_with_alpha_pixmap (which has ARGB content)
        #    into a final matte pixmap (black background, with white elements
        #    whose intensity/alpha is derived from the original content's alpha).
        
        # Get the rendered content as a QImage
        source_content_image = content_with_alpha_pixmap.toImage()
        if source_content_image.isNull():
            logging.error(f"KeyMatte: Failed to convert content_with_alpha_pixmap to QImage for slide {slide_id_for_log}")
            error_matte = QPixmap(width, height); error_matte.fill(Qt.GlobalColor.black); return error_matte

        # Ensure it's in a format with an alpha channel we can extract
        if source_content_image.format() != QImage.Format_ARGB32_Premultiplied and source_content_image.format() != QImage.Format_ARGB32:
            source_content_image = source_content_image.convertToFormat(QImage.Format_ARGB32_Premultiplied)

        # Convert the source image to an 8-bit alpha mask.
        # Pixels in alpha_mask_image will have grayscale values corresponding to the alpha
        # based on the alpha of source_content_image.
        # This image will be used to set the alpha channel of our white matte source.
        alpha_mask_image = source_content_image.convertToFormat(QImage.Format_Alpha8)
        if alpha_mask_image.isNull():
            logging.error(f"KeyMatte: Failed to convert source_content_image to Format_Alpha8 for slide {slide_id_for_log}")
            error_matte = QPixmap(width, height); error_matte.fill(Qt.GlobalColor.black); return error_matte

        # Create the final matte pixmap, starting with black.
        final_matte_pixmap = QPixmap(width, height)
        if final_matte_pixmap.isNull(): # Should not happen
            logging.error(f"KeyMatte: Failed to create final_matte_pixmap for slide {slide_id_for_log}")
            error_matte = QPixmap(1,1); error_matte.fill(Qt.GlobalColor.black); return error_matte
        final_matte_pixmap.fill(Qt.GlobalColor.black)

        # Prepare to draw onto the matte. We'll draw white, but use the alpha_channel_img
        # to control the "opacity" of that white drawing.
        matte_painter = QPainter(final_matte_pixmap)
        if not matte_painter.isActive():
            logging.error(f"KeyMatte: QPainter failed to activate on final_matte_pixmap for slide {slide_id_for_log}")
            # matte_painter.end() implicitly called
            return final_matte_pixmap # Return black pixmap

        # Create a temporary white image that will have its alpha channel set by our mask.
        # This white image will then be drawn onto the black matte.
        white_source_for_matte = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        white_source_for_matte.fill(Qt.GlobalColor.white)
        white_source_for_matte.setAlphaChannel(alpha_mask_image) # Apply our alpha mask

        matte_painter.setCompositionMode(QPainter.CompositionMode_SourceOver) # Draw white (with alpha) over black
        matte_painter.drawImage(0, 0, white_source_for_matte)
        matte_painter.end()
            
        if final_matte_pixmap.isNull():
            logging.error(f"KeyMatte: Failed to convert matte_image to QPixmap for slide {slide_id_for_log}")
            error_matte = QPixmap(width, height); error_matte.fill(Qt.GlobalColor.black); return error_matte
            
        return final_matte_pixmap

    def _get_text_options_from_props(self, tb_props: dict) -> QTextOption:
        """
        Creates a QTextOption object from textbox properties.
        This logic is similar to what's in TextContentRenderLayer.
        """
        text_option = QTextOption()
        h_align_str = tb_props.get("h_align", "center")
        v_align_str = tb_props.get("v_align", "center")

        qt_h_align = Qt.AlignmentFlag.AlignLeft
        if h_align_str == "right":
            qt_h_align = Qt.AlignmentFlag.AlignRight
        elif h_align_str == "center":
            qt_h_align = Qt.AlignmentFlag.AlignHCenter

        qt_v_align = Qt.AlignmentFlag.AlignTop
        if v_align_str == "bottom":
            qt_v_align = Qt.AlignmentFlag.AlignBottom
        elif v_align_str == "center":
            qt_v_align = Qt.AlignmentFlag.AlignVCenter
        
        text_option.setAlignment(qt_h_align | qt_v_align)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap) # Default to WordWrap
        return text_option

    def _draw_text_element_for_key_matte(self, painter: QPainter, text_to_draw: str,
                                         text_box_draw_rect: QRectF, tb_text_option: QTextOption,
                                         tb_props: dict, text_color: QColor, font_scaling_factor: float):
        """Helper to draw text elements (shadow, outline, main) for the key matte, all in the specified text_color."""
        # This method's logic is now integrated into TextContentRenderLayer,
        # which would need a mode/parameter for keying.
        # For the fix, the logic from TextContentRenderLayer's drawing part,
        # adapted for keying (all white), is now directly in render_key_matte.
        # So this specific helper can remain pass or be removed if render_key_matte
        # inline its drawing logic.
        pass # Logic moved/adapted

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
    
    # The following private helper methods are now part of their respective layer handlers:
    # _init_checkerboard_style() -> BackgroundRenderLayer
    # _draw_checkerboard_pattern() -> BackgroundRenderLayer
    # _render_background() -> BackgroundRenderLayer (its logic is integrated into BackgroundRenderLayer.render)
    # _get_text_options_from_props() -> TextContentRenderLayer (or used internally by it)


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
    
    # --- Create ImageCacheManager for testing ---
    test_cache_manager = ImageCacheManager(cache_base_dir_name="test_plucky_image_cache")
    test_cache_manager.clear_entire_cache() # Start with a clean cache for testing

    # --- Create Renderer ---
    renderer = LayeredSlideRenderer(app_settings=MockAppSettings(), image_cache_manager=test_cache_manager)

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