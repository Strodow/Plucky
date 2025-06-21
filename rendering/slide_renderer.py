import sys
import os
import re # For metadata placeholder replacement
import logging
import time # For benchmarking
from PySide6.QtWidgets import QApplication # Needed for testing QPixmap/QPainter
import copy # For deepcopy
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QTextOption,
    QFontInfo, QImage, qAlpha, qRgba # Added QImage, qAlpha, qRgba here
)
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize, QThread, Signal, QUrl, Slot, QObject
from typing import Optional, List, Tuple, Dict, Any # Added List, Tuple, Dict, Any
from abc import ABCMeta, abstractmethod # Changed from ABC
import subprocess # For TimeoutExpired
import ffmpeg # For video decoding
import numpy as np # For frame data manipulation

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

# Define a combined metaclass for QObject compatibility with ABC
class QObjectABCMeta(type(QObject), ABCMeta):
    pass

class RenderLayerHandler(metaclass=QObjectABCMeta):
    """Abstract base class for a render layer, compatible with QObject inheritance."""
    def __init__(self, app_settings: Optional[Any] = None):
        self.app_settings = app_settings

    @abstractmethod
    def render(self,
               current_pixmap: QPixmap,
               slide_data: SlideData,
               target_width: int, target_height: int,
               is_final_output: bool,
               section_metadata: Optional[List[Dict[str, str]]] = None,
               section_title: Optional[str] = None) -> Tuple[QPixmap, bool, Dict[str, float]]:
        """
        Renders this layer's content onto/into the current_pixmap.
        
        Args:
            current_pixmap: The pixmap from the previous layer (or initial canvas).
            slide_data: The data for the current slide.
            target_width: The target width of the output.
            target_height: The target height of the output.
            is_final_output: True if for live output, False for previews.
            section_metadata: Optional list of metadata dicts for placeholder replacement.
            section_title: Optional title of the section.

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

    def render(self,
               current_pixmap: QPixmap,
               slide_data: SlideData,
               target_width: int, target_height: int,
               is_final_output: bool,
               section_metadata: Optional[List[Dict[str, str]]] = None,
               section_title: Optional[str] = None) -> Tuple[QPixmap, bool, Dict[str, float]]:
        start_time = time.perf_counter()
        print(f"--- DEBUG BRL: render() called for slide_id: {slide_data.id if slide_data else 'None'}, video_path: {slide_data.video_path if slide_data else 'N/A'}", file=sys.stderr) # ADDED
        # This layer draws the slide's own background onto the current_pixmap.
        # If current_pixmap was a base (e.g., live background), this draws over it.
        output_pixmap = current_pixmap.copy() # Work on a copy

        painter = QPainter(output_pixmap)
        if not painter.isActive(): return output_pixmap, False, {"images": 0.0}
        self._setup_painter_hints(painter)

        # --- Logic from SlideRenderer._render_background ---
        effective_bg_color_hex: Optional[str] = None
        effective_media_path: Optional[str] = None # Will hold image or video path
        # media_type: Optional[str] = None # 'image' or 'video_frame' - not strictly needed for current QImage logic

        if slide_data.background_image_path and os.path.exists(slide_data.background_image_path):
            effective_media_path = slide_data.background_image_path
            # media_type = 'image'
        elif slide_data.video_path and os.path.exists(slide_data.video_path): # Check for video_path next
            effective_media_path = slide_data.video_path
            # media_type = 'video_frame'
        elif slide_data.background_color:
            effective_bg_color_hex = slide_data.background_color
        elif slide_data.template_settings:
            bg_image_path_from_template = slide_data.template_settings.get("background_image_path")
            if bg_image_path_from_template and os.path.exists(bg_image_path_from_template):
                effective_media_path = bg_image_path_from_template
                # media_type = 'image'
            else:
                effective_bg_color_hex = slide_data.template_settings.get("background_color")
        # Note: Templates currently don't define video_path, but could be extended.
        
        # Detailed image processing benchmarks
        time_img_load = 0.0
        time_img_scale = 0.0
        time_img_from_image = 0.0
        time_img_draw = 0.0
        print(f"--- DEBUG BRL: For slide {slide_data.id if slide_data else 'None'}, initial effective_media_path is: '{effective_media_path}', effective_bg_color_hex is: '{effective_bg_color_hex}'", file=sys.stderr) # ADDED

        if effective_media_path:
            loaded_bg_pixmap_for_drawing = QPixmap() # Initialize as null
            target_qsize = QSize(target_width, target_height)
            cached_image_path = None

            if self.image_cache_manager:
                cached_image_path = self.image_cache_manager.get_cached_image_path(effective_media_path, target_qsize)

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
                source_image = QImage(effective_media_path) # QImage attempts to load first frame for videos
                time_img_load = time.perf_counter() - img_load_start

                if slide_data.video_path and slide_data.video_path == effective_media_path: # If we are trying to load a video
                    if source_image.isNull():
                        print(f"!!! DEBUG BRL: QImage FAILED to load video frame from: {effective_media_path}", file=sys.stderr)
                    else:
                        print(f"!!! DEBUG BRL: QImage SUCCEEDED to load a frame from video: {effective_media_path} (Size: {source_image.width()}x{source_image.height()})", file=sys.stderr)

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
                        if self.image_cache_manager and not scaled_qimage.isNull(): # Cache the newly scaled image/frame
                            self.image_cache_manager.cache_image(effective_media_path, target_qsize, scaled_qimage)
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
                effective_media_path = None # Fallback to color
        
        if not effective_media_path: # If no image/video_frame was successfully loaded
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

class FFmpegDecodeThread(QThread):
    frame_decoded = Signal(bytes, int, int, str) # frame_data, width, height, pixel_format ('rgba' or 'rgb24')
    decoding_error = Signal(str)
    finished_normally = Signal()

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self._is_running = True
        self.process = None

    def run(self):
        try:
            probe = ffmpeg.probe(self.video_path)
        except ffmpeg.Error as e:
            self.decoding_error.emit(f"FFmpeg probe error: {e.stderr.decode('utf8')}")
            return

        video_stream_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if not video_stream_info:
            self.decoding_error.emit("No video stream found.")
            return

        width = int(video_stream_info['width'])
        height = int(video_stream_info['height'])
        pix_fmt_in = video_stream_info.get('pix_fmt')

        # Determine output pixel format: prefer RGBA, fallback to RGB
        # Common FFmpeg pixel formats that QImage can handle well with alpha: 'rgba', 'bgra', 'argb', 'abgr'
        # Common without alpha: 'rgb24', 'bgr24'
        # We will request 'rgba' from FFmpeg.
        output_pix_fmt = 'rgba'
        qimage_format = QImage.Format_RGBA8888
        
        fps_str = video_stream_info.get('r_frame_rate', '30/1')
        fps = 30.0 # Default fps
        try:
            num_str, den_str = fps_str.split('/')
            fps = int(num_str) / int(den_str)
        except (ValueError, ZeroDivisionError) as e_fps:
            logging.warning(f"FFmpegDecodeThread: Could not parse r_frame_rate '{fps_str}': {e_fps}. Defaulting to 30fps.")

        try:
            # Construct FFmpeg command arguments directly
            stream_spec = (
                # Ensure self.video_path is absolute for FFmpeg
                # If it's already absolute, os.path.abspath does nothing.
                # If it's relative, it's resolved against the current CWD of the Python script.
                # We need to ensure this CWD is the project root if paths are relative like "temp/..."
                # For the -i argument, we will pass an absolute path.
                # The cwd for Popen will be set to the project root for robustness.
                ffmpeg.input(self.video_path, fflags='+discardcorrupt', probesize='50M', analyzeduration='15M')
                .output('pipe:', format='rawvideo', pix_fmt=output_pix_fmt, r=fps, **{'c:v': 'rawvideo'})
            )
            # Get the base command list from ffmpeg-python (includes executable path and stream specs)
            base_compiled_args = stream_spec.compile()
            if not base_compiled_args:
                logging.error("FFmpegDecodeThread: ffmpeg.compile() returned an empty list.")
                self.decoding_error.emit("FFmpeg command compilation failed (empty).")
                return

            # Ensure all parts of compiled_args are strings
            base_compiled_args = [str(arg) for arg in base_compiled_args]

            executable = base_compiled_args[0]
            stream_related_args = base_compiled_args[1:]

            # Ensure the input video path in stream_related_args is absolute
            # The -i flag is usually followed by the path.
            abs_video_path = os.path.abspath(self.video_path)
            found_input_arg = False
            for i, arg in enumerate(stream_related_args):
                if arg == '-i' and i + 1 < len(stream_related_args):
                    # Replace the original relative/absolute path with a guaranteed absolute one
                    stream_related_args[i+1] = abs_video_path
                    found_input_arg = True
                    break
            if not found_input_arg: # Should not happen if ffmpeg.input() worked
                logging.error(f"FFmpegDecodeThread: Could not find -i argument to make absolute. Args: {stream_related_args}")
                self.decoding_error.emit("Internal error preparing FFmpeg command.")
                return

            # Insert our desired global options after the executable
            final_args = [executable, '-nostdin', '-v', 'error'] + stream_related_args
            
            logging.info(f"FFmpeg command for Plucky (manual): {' '.join(final_args)}")
            self.process = subprocess.Popen(final_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0) # Removed explicit cwd

            logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: FFmpeg process started.")
            frame_size = width * height * 4  # 4 bytes per pixel for RGBA

            while self._is_running:
                current_poll = self.process.poll() if self.process else "NoProcess"
                logging.debug(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Top of loop. _is_running: {self._is_running}, process.poll(): {current_poll}")

                if current_poll is not None:
                    logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: FFmpeg process poll() is not None ({current_poll}), breaking read loop.")
                    break

                if not self._is_running:
                    logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: _is_running is false, breaking read loop.")
                    break

                in_bytes = b''
                bytes_read_this_iteration = 0
                try:
                    # Read in chunks to be more responsive and handle partial data better
                    # This is a simplified chunking; a more robust one would loop until frame_size is met or EOF
                    logging.debug(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Attempting to read {frame_size} bytes...")
                    in_bytes = self.process.stdout.read(frame_size) # Still try to read full frame
                    bytes_read_this_iteration = len(in_bytes)
                    logging.debug(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Read {bytes_read_this_iteration} bytes.")

                    if bytes_read_this_iteration == 0: # Clean EOF or pipe closed
                        logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: stdout.read returned 0 bytes (EOF or pipe closed).")
                        break
                    
                    if bytes_read_this_iteration == frame_size:
                        logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Emitting frame_decoded signal, data length: {len(in_bytes)}")
                        self.frame_decoded.emit(in_bytes, width, height, output_pix_fmt)
                    elif bytes_read_this_iteration < frame_size:
                        logging.warning(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Read incomplete frame (got {bytes_read_this_iteration}, expected {frame_size}). Loop terminating. This often means FFmpeg exited.")
                        break 
                except Exception as e_read: # Catch potential errors during read (e.g., if pipe closes unexpectedly)
                    logging.error(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Error during stdout.read: {e_read}")
                    break
                
                # Give a tiny bit of time for other events if needed, though QThread should handle this.
                # self.msleep(1) # Optional, usually not needed.

            # After the loop, wait for the process to finish to get return code and stderr
            # If communicate() was already called implicitly or process exited, this might be quick
            if self.process: # Ensure process exists before calling communicate
                try:
                    # Ensure stderr is read
                    # Only call communicate if the process hasn't been fully processed (e.g. poll() is None or just finished)
                    # If poll() is not None, it means the process already terminated.
                    # communicate() will wait for the process to terminate.
                    logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Calling communicate(). Process poll: {self.process.poll()}")
                    stdout_data, stderr_data = self.process.communicate(timeout=1.0) # Use a shorter timeout as a fallback
                    if self.process.returncode != 0: # Check return code after communicate
                        err_output = stderr_data.decode('utf8', errors='ignore') if stderr_data else "No stderr output."
                        err_msg = f"FFmpeg process for {os.path.basename(self.video_path)} exited with error (code {self.process.returncode}): {err_output}"
                        logging.error(err_msg)
                        if self._is_running: # Only emit error if not stopped externally by self.stop()
                            self.decoding_error.emit(err_msg)
                except subprocess.TimeoutExpired:
                    logging.warning(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Timeout during communicate(). Process might be stuck or already terminated.")
                except Exception as e_comm:
                    logging.error(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Error during communicate(): {e_comm}")

        except ffmpeg.Error as e:
            err_msg = f"FFmpeg runtime error for {os.path.basename(self.video_path)}: {e.stderr.decode('utf8', errors='ignore') if e.stderr else 'Unknown FFmpeg error'}"
            logging.error(err_msg)
            self.decoding_error.emit(err_msg)
        except Exception as e_gen:
            err_msg_gen = f"General error in FFmpeg thread for {os.path.basename(self.video_path)}: {e_gen}"
            logging.error(err_msg_gen)
            self.decoding_error.emit(err_msg_gen)
        finally:
            logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Entering finally block.")
            if self.process and self.process.poll() is None: # Check if process is still running
                logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Process still running in finally, killing.")
                self.process.kill() # Ensure it's killed if loop exited for other reasons
            # Wait for the process to ensure resources are freed, but with a timeout
            if self.process:
                try:
                    # communicate() above already waits, so this wait might be redundant or very short
                    logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Ensuring FFmpeg process has terminated in finally block...")
                    self.process.wait(timeout=0.5) 
                    logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: FFmpeg process confirmed terminated in finally block.")
                except subprocess.TimeoutExpired: 
                    logging.warning(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Timeout waiting for FFmpeg process to terminate after kill in finally block.")
                except Exception as e_wait_finally: 
                    logging.error(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Error during process.wait() in finally block: {e_wait_finally}")
            self.finished_normally.emit()
            logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Run method finished.")

    def stop(self):
        self._is_running = False
        logging.info(f"FFmpegDecodeThread stop requested for {os.path.basename(self.video_path)}.")
        if self.process:
            logging.info(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: Terminating FFmpeg process.")
            self.process.terminate() # Ask ffmpeg to terminate
            try:
                self.process.wait(timeout=1.0) # Wait a bit for it to close gracefully
            except subprocess.TimeoutExpired: # Use subprocess.TimeoutExpired
                logging.warning(f"FFmpegDecodeThread for {os.path.basename(self.video_path)}: FFmpeg process did not terminate gracefully, killing.")
                self.process.kill() # Force kill if it doesn't terminate

class VideoRenderLayer(QObject, RenderLayerHandler): # Inherit from QObject
    new_frame_ready = Signal() # Define as class attribute

    def __init__(self, app_settings: Optional[Any] = None, parent: Optional[QObject] = None):
        QObject.__init__(self, parent) # Call QObject initializer
        RenderLayerHandler.__init__(self, app_settings) # Call RenderLayerHandler initializer
        # self.new_frame_ready is now an instance of the class attribute Signal
        self._current_video_qimage: Optional[QImage] = None
        self._ffmpeg_thread: Optional[FFmpegDecodeThread] = None
        self._active_video_path: Optional[str] = None

    @Slot(bytes, int, int, str)
    def _handle_new_video_frame(self, frame_data: bytes, width: int, height: int, pix_fmt: str):
        logging.info(f"VideoRenderLayer._handle_new_video_frame: Received frame for {self._active_video_path}, size {width}x{height}, pix_fmt {pix_fmt}, data_len {len(frame_data)}")
        if pix_fmt == 'rgba':
            self._current_video_qimage = QImage(frame_data, width, height, QImage.Format_RGBA8888).copy()
        elif pix_fmt == 'rgb24':
             self._current_video_qimage = QImage(frame_data, width, height, QImage.Format_RGB888).copy()
        else:
            logging.warning(f"VideoRenderLayer: Received frame with unhandled pixel format: {pix_fmt}")
            self._current_video_qimage = None # Ensure it's None if format is unhandled
            return
        
        if self._current_video_qimage and self._current_video_qimage.isNull():
            logging.error(f"VideoRenderLayer._handle_new_video_frame: QImage became null after creation for {self._active_video_path}!")
            self._current_video_qimage = None # Set to None if invalid

        if self._current_video_qimage and not self._current_video_qimage.isNull():
            logging.info(f"VideoRenderLayer._handle_new_video_frame: QImage created successfully for {self._active_video_path}. Emitting new_frame_ready.")
            self.new_frame_ready.emit() # Emit signal when a new frame is processed

    @Slot(str)
    def _handle_decoding_error(self, error_message: str):
        logging.error(f"VideoRenderLayer: Error decoding video '{self._active_video_path}': {error_message}")
        self._stop_ffmpeg_thread() # Stop on error

    def _start_ffmpeg_thread(self, video_path: str):
        self._stop_ffmpeg_thread() # Stop any existing thread
        self._active_video_path = video_path
        self._ffmpeg_thread = FFmpegDecodeThread(video_path)
        self._ffmpeg_thread.frame_decoded.connect(self._handle_new_video_frame)
        self._ffmpeg_thread.decoding_error.connect(self._handle_decoding_error)
        self._ffmpeg_thread.start()
        logging.info(f"VideoRenderLayer: Started FFmpeg thread for {video_path}")

    def _stop_ffmpeg_thread(self):
        if self._ffmpeg_thread:
            logging.info(f"VideoRenderLayer: Stopping FFmpeg thread for {self._active_video_path}...")
            self._ffmpeg_thread.stop()
            logging.info(f"VideoRenderLayer: Waiting for FFmpeg thread {self._active_video_path} to finish...")
            if not self._ffmpeg_thread.wait(5000): # Wait for 5 seconds
                logging.warning(f"VideoRenderLayer: Timeout waiting for FFmpeg thread {self._active_video_path} to finish. Thread state: {self._ffmpeg_thread.isRunning()}")
            else:
                logging.info(f"VideoRenderLayer: FFmpeg thread {self._active_video_path} finished.")
            
            try:
                self._ffmpeg_thread.frame_decoded.disconnect(self._handle_new_video_frame)
                self._ffmpeg_thread.decoding_error.disconnect(self._handle_decoding_error)
            except RuntimeError: # Signals might have already been disconnected
                pass
            self._ffmpeg_thread = None
        self._current_video_qimage = None # Clear last frame
        self._active_video_path = None
        logging.info("VideoRenderLayer: FFmpeg thread resources cleaned up.")

    def render(self,
               current_pixmap: QPixmap,
               slide_data: SlideData,
               target_width: int, target_height: int,
               is_final_output: bool,
               section_metadata: Optional[List[Dict[str, str]]] = None,
               section_title: Optional[str] = None) -> Tuple[QPixmap, bool, Dict[str, float]]:
        start_time = time.perf_counter()
        output_pixmap = current_pixmap.copy()

        # DEBUG: Log paths before the check
        logging.info(f"VideoRenderLayer.render for slide '{slide_data.id}': self._active_video_path='{self._active_video_path}', slide_data.video_path='{slide_data.video_path}'")

        if slide_data.video_path and os.path.exists(slide_data.video_path):
            if self._active_video_path != slide_data.video_path:
                self._start_ffmpeg_thread(slide_data.video_path)
            # Check if current_video_qimage is valid and attempt to draw
            if self._current_video_qimage and not self._current_video_qimage.isNull():
                logging.info(f"VideoRenderLayer.render for slide '{slide_data.id}': Attempting to draw _current_video_qimage (isNull: {self._current_video_qimage.isNull()})")
                painter = QPainter(output_pixmap)
                if painter.isActive():
                    logging.info(f"VideoRenderLayer.render for slide '{slide_data.id}': Painter active, drawing image.")
                    self._setup_painter_hints(painter)
                    # Scale video frame to fit target, keeping aspect ratio, centered
                    scaled_video_qimage = self._current_video_qimage.scaled(
                        target_width, target_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    x_offset = (target_width - scaled_video_qimage.width()) / 2
                    y_offset = (target_height - scaled_video_qimage.height()) / 2
                    painter.drawImage(QPointF(x_offset, y_offset), scaled_video_qimage)
                    painter.end()
            elif slide_data.video_path == self._active_video_path: # Video is supposed to be active, but no frame yet or frame is null
                logging.info(f"VideoRenderLayer.render for slide '{slide_data.id}': Video path matches active, but _current_video_qimage is None or null (isNull: {self._current_video_qimage.isNull() if self._current_video_qimage else 'None'}).")
        else: # No video path in slide_data, or file doesn't exist
            if self._active_video_path: # If a video was playing, stop it
                self._stop_ffmpeg_thread()

        benchmarks = {"total_video_layer": time.perf_counter() - start_time}
        return output_pixmap, False, benchmarks

    def cleanup(self): # Call this when the renderer is being destroyed
        self._stop_ffmpeg_thread()

class TextContentRenderLayer(RenderLayerHandler):

    def _resolve_text_with_metadata(self, text: str, metadata_list: Optional[List[Dict[str, str]]], section_title: Optional[str]) -> str:
        if (not metadata_list and not section_title) or not text or not isinstance(text, str):
            return text

        metadata_map = {}
        # User-defined metadata (can be overridden by section_title if keys clash)
        for item in reversed(metadata_list): # Last definition of a key wins
            key = item.get('key')
            value = item.get('value')
            if isinstance(key, str) and isinstance(value, str):
                 if key not in metadata_map:
                    metadata_map[key] = value
            elif isinstance(key, str) and value is None: # Handle None values as empty strings
                 if key not in metadata_map:
                    metadata_map[key] = ""
        # Add section title with a predefined key (e.g., "SectionTitle")
        if section_title:
            metadata_map["SectionTitle"] = section_title # You can choose a different key like "SongTitle"


        if not metadata_map: # No valid metadata to process
            return text

        def replace_match(match):
            key = match.group(1)
            return metadata_map.get(key, match.group(0)) # Return original placeholder if key not found

        try:
            resolved_text = re.sub(r"\{\{([\w_]+)\}\}", replace_match, text)
        except Exception as e:
            logging.error(f"Error during regex substitution for metadata: {e}")
            return text # Return original text on error
        return resolved_text

    def render(self, current_pixmap: QPixmap, slide_data: SlideData, target_width: int, target_height: int,
               is_final_output: bool,
               section_metadata: Optional[List[Dict[str, str]]] = None,
               section_title: Optional[str] = None,
               render_for_keying: bool = False) -> Tuple[QPixmap, bool, Dict[str, float]]:
        start_time = time.perf_counter()
        output_pixmap = current_pixmap.copy() # Work on a copy, or if render_for_keying, this might be a new transparent pixmap
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
            # Ensure painter is ended if it was active.
            # If painter was never active (e.g. output_pixmap.isNull()), this is safe.
            if painter.isActive():
                painter.end()
            return output_pixmap, False, {"fonts": 0, "layout": 0, "draw": 0, "total_text_layer": time.perf_counter() - start_time}

        for tb_props in defined_text_boxes:
            tb_id = tb_props.get("id", "unknown_box")
            text_to_draw = slide_text_content_map.get(tb_id, "")

            # Resolve metadata placeholders
            text_to_draw = self._resolve_text_with_metadata(text_to_draw, section_metadata, section_title)

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
            
            keying_color = QColor(Qt.GlobalColor.white) if render_for_keying else None

            # Shadow
            if tb_props.get("shadow_enabled", False):
                shadow_qcolor = keying_color if render_for_keying else QColor(tb_props.get("shadow_color", "#00000080"))
                # If keying, and shadow has alpha, its alpha contributes to the matte.
                # If shadow_color from props has alpha 0, it won't draw.
                if shadow_qcolor.alpha() > 0:
                    shadow_offset_x = tb_props.get("shadow_offset_x", 2) * font_scaling_factor
                    shadow_offset_y = tb_props.get("shadow_offset_y", 2) * font_scaling_factor
                    shadow_rect = text_box_draw_rect.translated(shadow_offset_x, shadow_offset_y)
                    painter.setPen(shadow_qcolor)
                    draw_call_start_time = time.perf_counter(); painter.drawText(shadow_rect, text_to_draw, tb_text_option); time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)
            
            # Outline
            if tb_props.get("outline_enabled", False):
                outline_qcolor = keying_color if render_for_keying else QColor(tb_props.get("outline_color", "#000000"))
                if outline_qcolor.alpha() > 0: # Only draw if outline color is not fully transparent
                    outline_width_px = max(1, int(tb_props.get("outline_width", 1) * font_scaling_factor))
                    painter.setPen(outline_qcolor)
                    draw_call_start_time = time.perf_counter()
                    for dx_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                        for dy_o in range(-outline_width_px, outline_width_px + 1, outline_width_px):
                            if dx_o != 0 or dy_o != 0: # Don't redraw center point
                                painter.drawText(text_box_draw_rect.translated(dx_o, dy_o), text_to_draw, tb_text_option)
                    time_spent_on_text_draw += (time.perf_counter() - draw_call_start_time)

            # Main Text
            main_text_qcolor = keying_color if render_for_keying else QColor(tb_props.get("font_color", "#FFFFFF"))
            if main_text_qcolor.alpha() > 0: # Only draw if main text color is not fully transparent
                painter.setPen(main_text_qcolor)
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
            VideoRenderLayer(app_settings), # Add VideoRenderLayer
            TextContentRenderLayer(app_settings) # Text on top of video/background
            # Future layers can be added here
        ]

    def render_slide(self,
                     slide_data: SlideData,
                     width: int, height: int,
                     base_pixmap: Optional[QPixmap] = None, # Made Optional explicit
                     is_final_output: bool = False,
                     section_metadata: Optional[List[Dict[str, str]]] = None,
                     section_title: Optional[str] = None) -> tuple[QPixmap, bool, dict]:

        print(f"--- DEBUG LSR: render_slide() called for slide_id: {slide_data.id if slide_data else 'None'}, video_path in slide_data: {slide_data.video_path if slide_data else 'N/A'}", file=sys.stderr) # ADDED
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
            section_metadata: Optional list of metadata dicts for placeholder replacement.
            section_title: Optional title of the section.

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
            "total_background_layer": 0.0, # From BackgroundRenderLayer
            "total_video_layer": 0.0,      # From VideoRenderLayer
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

        # --- Step 6: Handle "Template Missing" Error State ---
        if slide_data and slide_data.template_settings and \
           slide_data.template_settings.get('layout_name') == "MISSING_LAYOUT_ERROR":
            
            original_template_name = slide_data.template_settings.get('original_template_name', 'Unknown')
            error_message = f"Error: Template Missing!\nOriginal: '{original_template_name}'"
            
            painter = QPainter(current_canvas)
            if painter.isActive():
                # Fill with a noticeable error background
                painter.fillRect(current_canvas.rect(), QColor(255, 200, 200, 200)) # Light red, semi-transparent
                
                # Draw error text
                error_font = QFont("Arial", 40 * (height / 1080.0)) # Scale font size
                painter.setFont(error_font)
                painter.setPen(QColor(Qt.GlobalColor.black))
                
                text_option = QTextOption(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
                
                painter.drawText(QRectF(current_canvas.rect()), error_message, text_option)
                painter.end()
            else:
                logging.error(f"LayeredSlideRenderer: QPainter failed to activate for error message on slide {slide_id_for_log}")

            benchmark_data["total_render"] = time.perf_counter() - total_render_start_time
            # Return the canvas with the error message, True for font_error to be safe, and current benchmarks
            return current_canvas, True, benchmark_data
        # --- End Step 6 ---

        for layer_handler in self.render_layers:
            layer_output_pixmap, layer_font_error, layer_benchmarks = layer_handler.render(
                current_canvas,
                slide_data,
                width, height,
                is_final_output,
                section_metadata,
                section_title
                # render_for_keying would be passed here if this layer supported it directly
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

    def render_key_matte(self,
                         slide_data: SlideData,
                         width: int, height: int,
                         section_metadata: Optional[List[Dict[str, str]]] = None,
                         section_title: Optional[str] = None) -> QPixmap:

        """
        Renders a key matte for the given slide data.
        The matte will have a black background, with all text elements
        (including shadows and outlines if enabled) rendered in solid white.

        Args:
            slide_data: An instance of SlideData containing the content and style.
            width: The target width of the output pixmap (e.g., DeckLink width).
            height: The target height of the output pixmap (e.g., DeckLink height).
            section_metadata: Optional list of metadata dicts for placeholder replacement.
            section_title: Optional title of the section.

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

        # Use TextContentRenderLayer to render the text elements for keying
        text_layer = self._get_text_content_render_layer()
        if text_layer:
            # Render text onto the transparent 'content_with_alpha_pixmap'
            # Pass render_for_keying=True to TextContentRenderLayer
            content_with_alpha_pixmap, _, _ = text_layer.render(
                content_with_alpha_pixmap, # Base is transparent
                slide_data,
                width, height,
                is_final_output=True, # Key matte is usually for final output
                section_metadata=section_metadata,
                section_title=section_title,
                render_for_keying=True # Key instruction
            )
        else:
            logging.warning(f"KeyMatte for Slide {slide_id_for_log}: TextContentRenderLayer not found. Key matte will be black.")
            # Fall through to the conversion step, which will result in a black matte.

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

    def _get_text_content_render_layer(self) -> Optional[TextContentRenderLayer]:
        """Helper to find the TextContentRenderLayer instance."""
        for layer in self.render_layers:
            if isinstance(layer, TextContentRenderLayer):
                return layer
        return None


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