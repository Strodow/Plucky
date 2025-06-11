import sys
import os
import re
import logging
import time
import subprocess
from abc import ABC, abstractmethod, ABCMeta
from typing import Optional, List, Tuple, Dict, Any

# Third-party libraries
import ffmpeg
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QTextOption, QFontInfo, QImage, QPen, QBrush
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QThread, Signal, Slot, QObject

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---

def pc_to_px(rect_pc: Dict[str, float], parent_width: int, parent_height: int) -> QRectF:
    """Converts a rectangle defined in percentages to pixel coordinates."""
    x = (rect_pc.get('x_pc', 0) / 100.0) * parent_width
    y = (rect_pc.get('y_pc', 0) / 100.0) * parent_height
    w = (rect_pc.get('width_pc', 100) / 100.0) * parent_width
    h = (rect_pc.get('height_pc', 100) / 100.0) * parent_height
    return QRectF(x, y, w, h)

def get_scaled_font(base_size: int, target_height: int, reference_height: int = 1080) -> int:
    """Scales font size based on render height to maintain visual consistency."""
    if target_height <= 0 or reference_height <= 0:
        return base_size
    scaling_factor = target_height / reference_height
    return max(8, int(base_size * scaling_factor))


# =============================================================================
# METACLASS FOR QOBJECT AND ABC COMPATIBILITY
# =============================================================================

class QObjectABCMeta(type(QObject), ABCMeta):
    """
    A metaclass that inherits from both the metaclass of QObject and ABCMeta.
    This allows a class to inherit from both QObject and an ABC, resolving metaclass conflicts.
    """
    pass

# =============================================================================
# ABSTRACT RENDER HANDLER
# =============================================================================

class RenderLayerHandler(metaclass=QObjectABCMeta):
    """Abstract base class for a render layer handler, compatible with QObject inheritance."""

    @abstractmethod
    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        """
        Renders this layer's content using the provided painter.

        Args:
            painter: The QPainter to draw with. It is already active on a canvas.
            layer_data: The dictionary for the specific layer being rendered.
            target_width: The target width of the entire scene.
            target_height: The target height of the entire scene.
        """
        pass

    def _setup_painter_hints(self, painter: QPainter):
        """Sets common render hints for the painter."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

# =============================================================================
# CONCRETE RENDER HANDLERS
# =============================================================================

class SolidColorLayerHandler(RenderLayerHandler):
    """Renders a solid color rectangle."""
    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        self._setup_painter_hints(painter)
        props = layer_data.get('properties', {})
        color_hex = props.get('color', '#00000000') # Default to transparent
        color = QColor(color_hex)

        if color.alpha() > 0:
            draw_rect = pc_to_px(layer_data.get('position', {}), target_width, target_height)
            painter.fillRect(draw_rect, color)

class ShapeLayerHandler(RenderLayerHandler):
    """Renders a basic geometric shape like an ellipse or rectangle."""
    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        self._setup_painter_hints(painter)
        props = layer_data.get('properties', {})
        shape_type = props.get('shape_type', 'rectangle')
        fill_color_hex = props.get('fill_color', '#00000000')
        stroke_props = props.get('stroke', {})

        draw_rect = pc_to_px(layer_data.get('position', {}), target_width, target_height)
        
        # Configure Brush (Fill)
        fill_color = QColor(fill_color_hex)
        if fill_color.alpha() > 0:
            painter.setBrush(QBrush(fill_color))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        # Configure Pen (Stroke)
        if stroke_props.get('enabled', False):
            stroke_color = QColor(stroke_props.get('color', '#FFFFFFFF'))
            stroke_width = get_scaled_font(stroke_props.get('width', 1), target_height)
            pen = QPen(stroke_color, stroke_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        # Draw the shape
        if shape_type == 'ellipse':
            painter.drawEllipse(draw_rect)
        elif shape_type == 'rectangle':
            painter.drawRect(draw_rect)
        else:
            logging.warning(f"Unsupported shape_type: '{shape_type}'")

class ImageLayerHandler(RenderLayerHandler):
    """Renders a static image, handling scaling."""
    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        self._setup_painter_hints(painter)
        props = layer_data.get('properties', {})
        path = props.get('path')
        if not path or not os.path.exists(path):
            logging.warning(f"Image path not found or not provided: {path}")
            return

        image = QImage(path)
        if image.isNull():
            logging.error(f"Failed to load image: {path}")
            return
            
        layer_rect_px = pc_to_px(layer_data.get('position', {}), target_width, target_height)
        
        # Determine scaling mode
        scaling_mode_str = props.get('scaling_mode', 'fit')
        aspect_mode = Qt.AspectRatioMode.KeepAspectRatio
        if scaling_mode_str == 'fill':
            aspect_mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
        elif scaling_mode_str == 'stretch':
            aspect_mode = Qt.AspectRatioMode.IgnoreAspectRatio

        # Scale the image
        scaled_image = image.scaled(layer_rect_px.size().toSize(), aspect_mode, Qt.TransformationMode.SmoothTransformation)

        # Center the image within the layer's bounding box if necessary (for 'fit' mode)
        draw_x = layer_rect_px.x() + (layer_rect_px.width() - scaled_image.width()) / 2
        draw_y = layer_rect_px.y() + (layer_rect_px.height() - scaled_image.height()) / 2
        
        painter.drawImage(QPointF(draw_x, draw_y), scaled_image)

class TextLayerHandler(RenderLayerHandler):
    """Renders a block of text with styling."""
    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        self._setup_painter_hints(painter)
        props = layer_data.get('properties', {})
        content = props.get('content', '')
        if not content.strip():
            return
            
        # Font setup
        font_family = props.get('font_family', 'Arial')
        base_font_size = props.get('font_size', 32)
        font = QFont(font_family, get_scaled_font(base_font_size, target_height))
        
        font_info = QFontInfo(font)
        if font_info.family().lower() != font_family.lower():
            logging.warning(f"Font '{font_family}' not found. Using fallback '{font_info.family()}'.")

        painter.setFont(font)

        # Text transformations
        if props.get('force_all_caps', False):
            content = content.upper()

        # Bounding box and alignment
        draw_rect = pc_to_px(layer_data.get('position', {}), target_width, target_height)
        text_option = QTextOption()
        h_align = props.get('h_align', 'center')
        v_align = props.get('v_align', 'center')
        
        qt_h_align = {'left': Qt.AlignmentFlag.AlignLeft, 'center': Qt.AlignmentFlag.AlignHCenter, 'right': Qt.AlignmentFlag.AlignRight}.get(h_align, Qt.AlignmentFlag.AlignHCenter)
        qt_v_align = {'top': Qt.AlignmentFlag.AlignTop, 'center': Qt.AlignmentFlag.AlignVCenter, 'bottom': Qt.AlignmentFlag.AlignBottom}.get(v_align, Qt.AlignmentFlag.AlignVCenter)
        text_option.setAlignment(qt_h_align | qt_v_align)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)

        # --- Drawing Order: Shadow -> Outline -> Main Text ---
        font_scaling_factor = target_height / 1080.0

        # Shadow
        shadow_props = props.get('shadow', {})
        if shadow_props.get('enabled', False):
            shadow_color = QColor(shadow_props.get('color', '#00000080'))
            if shadow_color.alpha() > 0:
                offset_x = shadow_props.get('offset_x', 2) * font_scaling_factor
                offset_y = shadow_props.get('offset_y', 2) * font_scaling_factor
                shadow_rect = draw_rect.translated(offset_x, offset_y)
                painter.setPen(shadow_color)
                painter.drawText(shadow_rect, content, text_option)
        
        # Outline
        outline_props = props.get('outline', {})
        if outline_props.get('enabled', False):
            outline_color = QColor(outline_props.get('color', '#000000FF'))
            if outline_color.alpha() > 0:
                width = max(1, int(outline_props.get('width', 1) * font_scaling_factor))
                painter.setPen(QPen(outline_color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                
                # This is a simplified outline; a better one uses QPainterPath
                for dx in range(-width, width + 1, width):
                    for dy in range(-width, width + 1, width):
                        if dx != 0 or dy != 0:
                            painter.drawText(draw_rect.translated(dx, dy), content, text_option)

        # Main Text
        main_color = QColor(props.get('font_color', '#FFFFFFFF'))
        painter.setPen(main_color)
        painter.drawText(draw_rect, content, text_option)


# =============================================================================
# VIDEO HANDLING (FFMPEG THREAD)
# =============================================================================

class FFmpegDecodeThread(QThread):
    """Decodes video frames in a separate thread."""
    frame_decoded = Signal(QImage)
    decoding_error = Signal(str)
    finished = Signal()

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self._is_running = True

    def run(self):
        try:
            probe = ffmpeg.probe(self.video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            process = (
                ffmpeg
                .input(self.video_path, thread_queue_size=512)
                .output('pipe:', format='rawvideo', pix_fmt='rgba')
                .run_async(pipe_stdout=True, pipe_stderr=True)
            )

            while self._is_running:
                in_bytes = process.stdout.read(width * height * 4)
                if not in_bytes:
                    break
                image = QImage(in_bytes, width, height, QImage.Format.Format_RGBA8888).copy()
                if self._is_running:
                    self.frame_decoded.emit(image)

            process.stdout.close()
            process.stderr.close()
            process.wait()

        except Exception as e:
            logging.error(f"FFmpeg thread error for '{self.video_path}': {e}")
            self.decoding_error.emit(str(e))
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False


class VideoLayerHandler(QObject, RenderLayerHandler):
    """Renders video frames using FFmpeg."""
    # Signal to notify the main thread to re-render
    new_frame_available = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent) # Correctly initializes QObject
        self._current_frame: Optional[QImage] = None
        self._ffmpeg_thread: Optional[FFmpegDecodeThread] = None
        self._active_video_path: Optional[str] = None
        self._loop = False

    def render(self, painter: QPainter, layer_data: Dict[str, Any], target_width: int, target_height: int) -> None:
        props = layer_data.get('properties', {})
        video_path = props.get('path')

        if not video_path or not os.path.exists(video_path):
            self._stop_ffmpeg_thread()
            return
            
        self._loop = props.get('loop', False)

        # Start or restart the thread if the video path changes
        if video_path != self._active_video_path:
            self._start_ffmpeg_thread(video_path)
        
        # Draw the current frame if available
        if self._current_frame and not self._current_frame.isNull():
            self._setup_painter_hints(painter)
            layer_rect_px = pc_to_px(layer_data.get('position', {}), target_width, target_height)
            
            # Use the same scaling logic as the ImageLayerHandler
            scaling_mode_str = props.get('scaling_mode', 'fit')
            aspect_mode = Qt.AspectRatioMode.KeepAspectRatio
            if scaling_mode_str == 'fill':
                aspect_mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
            elif scaling_mode_str == 'stretch':
                aspect_mode = Qt.AspectRatioMode.IgnoreAspectRatio

            scaled_frame = self._current_frame.scaled(layer_rect_px.size().toSize(), aspect_mode, Qt.TransformationMode.SmoothTransformation)
            draw_x = layer_rect_px.x() + (layer_rect_px.width() - scaled_frame.width()) / 2
            draw_y = layer_rect_px.y() + (layer_rect_px.height() - scaled_frame.height()) / 2
            
            painter.drawImage(QPointF(draw_x, draw_y), scaled_frame)

    @Slot(QImage)
    def _handle_new_frame(self, frame: QImage):
        """Stores the new frame and emits a signal to trigger a re-render."""
        self._current_frame = frame
        self.new_frame_available.emit()

    def _handle_thread_finished(self):
        """Handle FFmpeg thread finishing, possibly looping."""
        path_to_restart = self._active_video_path
        if self._loop and path_to_restart:
            self._start_ffmpeg_thread(path_to_restart)
        else:
            self._stop_ffmpeg_thread()

    def _start_ffmpeg_thread(self, video_path: str):
        self._stop_ffmpeg_thread()
        self._active_video_path = video_path
        self._ffmpeg_thread = FFmpegDecodeThread(video_path)
        self._ffmpeg_thread.frame_decoded.connect(self._handle_new_frame)
        self._ffmpeg_thread.finished.connect(self._handle_thread_finished)
        self._ffmpeg_thread.start()
        logging.info(f"Started video thread for: {video_path}")
        
    def _stop_ffmpeg_thread(self):
        if self._ffmpeg_thread:
            logging.info(f"Stopping video thread for: {self._active_video_path}")
            self._ffmpeg_thread.stop()
            self._ffmpeg_thread.wait(2000) # Wait for thread to finish
            self._ffmpeg_thread = None
        self._active_video_path = None
        self._current_frame = None

    def cleanup(self):
        """Should be called when the application closes."""
        self._loop = False
        self._stop_ffmpeg_thread()


# =============================================================================
# MAIN COMPOSITION RENDERER
# =============================================================================

class CompositionRenderer(QObject):
    """
    Renders a scene composed of multiple layers onto a QPixmap.
    This class orchestrates the various layer handlers.
    """
    # This signal is emitted whenever a video layer has a new frame,
    # telling the UI to request a new render.
    needs_update = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.video_handler = VideoLayerHandler()
        
        self.handlers: Dict[str, RenderLayerHandler] = {
            "solid_color": SolidColorLayerHandler(),
            "shape": ShapeLayerHandler(),
            "image": ImageLayerHandler(),
            "text": TextLayerHandler(),
            "video": self.video_handler,
        }
        # Connect the video handler's signal to the renderer's signal
        self.video_handler.new_frame_available.connect(self.needs_update.emit)

    def render_scene(self, scene_data: Dict[str, Any]) -> QPixmap:
        """
        Renders a full scene from its dictionary definition.

        Args:
            scene_data: A dictionary representing the scene, including width,
                        height, and a list of layers.

        Returns:
            A QPixmap of the fully rendered scene.
        """
        width = scene_data.get('width', 1920)
        height = scene_data.get('height', 1080)
        layers = scene_data.get('layers', [])

        # Create the base canvas
        canvas = QPixmap(width, height)
        if canvas.isNull():
            logging.error(f"Failed to create QPixmap of size {width}x{height}.")
            # Return a small magenta pixmap to indicate error
            error_pixmap = QPixmap(100, 100)
            error_pixmap.fill(Qt.GlobalColor.magenta)
            return error_pixmap
            
        canvas.fill(Qt.GlobalColor.transparent)

        # Set up the painter for the entire scene
        painter = QPainter(canvas)
        if not painter.isActive():
            logging.error("Failed to activate QPainter on canvas.")
            return canvas

        # Render each layer in order
        for layer in layers:
            if not layer.get('visible', True):
                continue

            handler = self.handlers.get(layer.get('type'))
            if not handler:
                logging.warning(f"No handler found for layer type: {layer.get('type')}")
                continue

            painter.save() # Save state before drawing a layer

            # Apply global layer opacity
            opacity = layer.get('opacity', 1.0)
            if opacity < 1.0:
                painter.setOpacity(opacity)

            # Render the layer using its handler
            handler.render(painter, layer, width, height)
            
            painter.restore() # Restore state after drawing layer

        painter.end()
        return canvas

    def cleanup(self):
        """Cleans up resources, particularly the video handler."""
        self.video_handler.cleanup()


# =============================================================================
# STANDALONE TEST BLOCK
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # --- Create a sample Scene Definition ---
    # This scene demonstrates all available layer types.
    # Note: You will need to provide valid paths for the image and video files.
    
    # Create a dummy image file for testing if it doesn't exist
    TEST_IMAGE_PATH = "./temp/LogoTransparent.png"
    if not os.path.exists(TEST_IMAGE_PATH):
        img_pixmap = QPixmap(400, 300)
        img_pixmap.fill(Qt.GlobalColor.darkCyan)
        p = QPainter(img_pixmap)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Arial", 40))
        p.drawText(img_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Test Image")
        p.end()
        img_pixmap.save(TEST_IMAGE_PATH)
        logging.info(f"Created dummy test image at '{TEST_IMAGE_PATH}'")

    # NOTE: You must provide your own video file for the video layer test.
    # If this path is invalid, the video layer will simply not appear.
    TEST_VIDEO_PATH = "./temp/TestVideo.mp4" # <--- CHANGE THIS TO A REAL VIDEO FILE
    if not os.path.exists(TEST_VIDEO_PATH):
        logging.warning(f"Test video not found at '{TEST_VIDEO_PATH}'. The video layer will be skipped.")

    test_scene = {
        "width": 1280,
        "height": 720,
        "layers": [
            # 1. A solid dark blue background filling the whole screen
            {
                "id": "background_color",
                "type": "solid_color",
                "visible": True,
                "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100},
                "properties": {"color": "#102040"}
            },
            # 2. A background image, filling the space, but slightly transparent
            {
                "id": "background_image",
                "type": "image",
                "visible": True,
                "opacity": 0.4,
                "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100},
                "properties": {
                    "path": TEST_IMAGE_PATH,
                    "scaling_mode": "fill"
                }
            },
            # 3. A looping video in the bottom right corner
            {
                "id": "video_feature",
                "type": "video",
                "visible": True,
                "opacity": 1.0,
                "position": {"x_pc": 65, "y_pc": 55, "width_pc": 30, "height_pc": 30},
                "properties": {
                    "path": TEST_VIDEO_PATH,
                    "scaling_mode": "fit",
                    "loop": True
                }
            },
            # 4. A semi-transparent red circle on the left side
            {
                "id": "decorative_shape",
                "type": "shape",
                "visible": True,
                "opacity": 0.8,
                "position": {"x_pc": 5, "y_pc": 25, "width_pc": 25, "height_pc": 40},
                "properties": {
                    "shape_type": "ellipse",
                    "fill_color": "#FF0000A0",
                    "stroke": {"enabled": True, "color": "#FFFFFF", "width": 4}
                }
            },
            # 5. Main Title Text
            {
                "id": "main_title",
                "type": "text",
                "visible": True,
                "position": {"x_pc": 5, "y_pc": 5, "width_pc": 90, "height_pc": 20},
                "properties": {
                    "content": "Dynamic Layer Renderer",
                    "font_family": "Impact",
                    "font_size": 80,
                    "font_color": "#FFFF80",
                    "h_align": "center",
                    "v_align": "center",
                    "outline": {"enabled": True, "color": "#000000", "width": 3}
                }
            },
            # 6. Body Text with shadow
            {
                "id": "body_text",
                "type": "text",
                "visible": True,
                "position": {"x_pc": 10, "y_pc": 75, "width_pc": 80, "height_pc": 20},
                "properties": {
                    "content": "This text is rendered on top of all other layers.\nIt supports multiple lines, alignment, and effects.",
                    "font_family": "Arial",
                    "font_size": 32,
                    "font_color": "#E0E0E0",
                    "h_align": "center",
                    "v_align": "center",
                    "shadow": {"enabled": True, "color": "#000000C0", "offset_x": 3, "offset_y": 3}
                }
            }
        ]
    }

    # --- Render the Scene ---
    renderer = CompositionRenderer()

    def render_and_save():
        logging.info("Rendering scene...")
        start_time = time.perf_counter()
        output_pixmap = renderer.render_scene(test_scene)
        end_time = time.perf_counter()
        logging.info(f"Scene rendered in {end_time - start_time:.4f} seconds.")
        
        output_filename = "test_composition.png"
        if output_pixmap.save(output_filename):
            logging.info(f"Saved initial render to '{output_filename}'")
        else:
            logging.error(f"Error saving render to '{output_filename}'")

    # The renderer's needs_update signal will trigger this function
    renderer.needs_update.connect(render_and_save)

    # Perform the initial render
    render_and_save()

    logging.info("Initial render complete. Watching for video frame updates...")
    logging.info("Press Ctrl+C in the console to exit.")

    # Keep the application running to allow the video thread to emit frames
    # In a real GUI app, the app.exec() would handle this.
    try:
        # A simple way to keep the script alive for demonstration
        app.exec()
    finally:
        renderer.cleanup() # Important to stop the video thread
        logging.info("Application finished.")

