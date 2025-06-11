import sys
import os
import subprocess
import time # For any delays if needed
import logging
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap, QColor
from PySide6.QtCore import QThread, Signal, Qt, Slot, QSize
import ffmpeg # Import the ffmpeg-python library

# --- Configuration ---
VIDEO_FILE_PATH = "temp/TestVideo.mp4"  # <--- IMPORTANT: SET THIS TO YOUR VIDEO FILE
# VIDEO_FILE_PATH = "temp/TestVideo.mp4" # Or try the original
# VIDEO_FILE_PATH = "path/to/a/known_good_simple.mp4" # Or a completely different test video

FFMPEG_EXE = "ffmpeg" # Assumes ffmpeg is in your system PATH

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')

class FFmpegDecodeThread(QThread):
    frame_decoded = Signal(bytes, int, int)  # raw_frame_data, width, height
    decoding_error = Signal(str)
    process_finished = Signal(int) # Exit code

    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.ffmpeg_process = None
        self._is_running = True
        self.width = 0
        self.height = 0
        self.fps = 30 # Default, will try to probe

    def _get_video_info(self):
        """Tries to get video info using ffprobe (via ffmpeg-python)."""
        try:
            logging.info(f"Probing video file: {self.video_path}")
            # Log the typical command structure for ffprobe
            ffprobe_cmd_example = f"{FFMPEG_EXE.replace('ffmpeg', 'ffprobe')} -v error -show_format -show_streams \"{self.video_path}\""
            logging.info(f"Using ffmpeg.probe(), which typically executes a command like: {ffprobe_cmd_example}")
            probe = ffmpeg.probe(self.video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if video_stream:
                self.width = int(video_stream['width'])
                self.height = int(video_stream['height'])
                
                # Get frame rate
                r_frame_rate_str = video_stream.get('r_frame_rate', '30/1')
                if '/' in r_frame_rate_str:
                    num, den = map(int, r_frame_rate_str.split('/'))
                    if den != 0:
                        self.fps = num / den
                else:
                    self.fps = float(r_frame_rate_str)
                
                #logging.info(f"Probed video info: {self.width}x{self.height} @ {self.fps:.2f} FPS")
                return True
            else:
                logging.error("No video stream found in probe.")
        except ffmpeg.Error as e:
            logging.error(f"ffmpeg.probe error: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
        except Exception as e:
            logging.error(f"Exception during video probe: {e}")
        return False

    def run(self):
        if not os.path.exists(self.video_path):
            self.decoding_error.emit(f"Video file not found: {self.video_path}")
            return

        if not self._get_video_info() or self.width == 0 or self.height == 0:
            self.decoding_error.emit(f"Failed to get video dimensions for: {self.video_path}")
            # Fallback dimensions if probe fails, adjust if needed
            self.width, self.height = 1920, 1080 
            logging.warning(f"Using fallback dimensions: {self.width}x{self.height}")


        # FFmpeg command to decode video to raw RGBA frames
        command = [
            FFMPEG_EXE,
            '-nostdin',         # No interaction on stdin
            # '-loglevel', 'debug', # Get all logs from FFmpeg - Too verbose, might cause pipe blocks
            '-v', 'error',      # Only output errors to stderr
            '-i', self.video_path,
            '-f', 'rawvideo',   # Output format
            '-pix_fmt', 'rgba', # Pixel format (RGBA for QImage)
            '-r', str(int(self.fps)), # Output framerate matching source or fixed
            'pipe:1'            # Output to stdout
        ]
        logging.info(f"Starting FFmpeg command: {' '.join(command)}")

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            self.ffmpeg_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Capture stderr
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags
            )

            frame_size = self.width * self.height * 4  # RGBA = 4 bytes per pixel
            logging.info(f"Expected frame size: {frame_size} bytes ({self.width}x{self.height})")

            while self._is_running:
                if self.ffmpeg_process.poll() is not None:
                    logging.info(f"FFmpeg process exited during read loop with code: {self.ffmpeg_process.returncode}")
                    break
                
                #logging.debug("Attempting to read frame from FFmpeg stdout...")
                raw_frame = self.ffmpeg_process.stdout.read(frame_size)
                bytes_read = len(raw_frame)
                #logging.debug(f"Read {bytes_read} bytes from stdout.")

                if bytes_read == 0:
                    logging.info("FFmpeg stdout pipe closed (EOF).")
                    break
                
                if bytes_read == frame_size:
                    #logging.debug(f"Successfully read full frame ({bytes_read} bytes). Emitting.")
                    self.frame_decoded.emit(raw_frame, self.width, self.height)
                elif bytes_read < frame_size:
                    logging.warning(f"Read incomplete frame ({bytes_read} bytes, expected {frame_size}). Assuming EOF or error.")
                    break
                
                # Optional: control frame rate if FFmpeg -r isn't perfectly syncing
                # self.msleep(int(1000 / self.fps)) 

            logging.info("FFmpeg frame reading loop finished.")

        except FileNotFoundError:
            self.decoding_error.emit(f"FFmpeg executable not found at '{FFMPEG_EXE}'. Make sure it's in your PATH.")
            return # Exit run method
        except Exception as e:
            logging.error(f"Exception in FFmpegDecodeThread: {e}", exc_info=True)
            self.decoding_error.emit(str(e))
        finally:
            if self.ffmpeg_process:
                # Read remaining stderr
                stderr_output = ""
                if self.ffmpeg_process.stderr:
                    try:
                        # Non-blocking read for stderr if possible, or use communicate with timeout
                        # For simplicity here, we'll rely on communicate after ensuring process is ending.
                        pass
                    except Exception as e_stderr:
                        logging.error(f"Error reading stderr: {e_stderr}")

                if self.ffmpeg_process.poll() is None: # If still running
                    logging.info("FFmpeg process still running in finally, terminating.")
                    self.ffmpeg_process.terminate()
                    try:
                        stdout_rem, stderr_rem = self.ffmpeg_process.communicate(timeout=1.0)
                        if stderr_rem: stderr_output += stderr_rem.decode('utf-8', errors='ignore')
                    except subprocess.TimeoutExpired:
                        logging.warning("Timeout waiting for FFmpeg to terminate after terminate(), killing.")
                        self.ffmpeg_process.kill()
                        stdout_rem, stderr_rem = self.ffmpeg_process.communicate() # Wait for kill
                        if stderr_rem: stderr_output += stderr_rem.decode('utf-8', errors='ignore')
                    except Exception as e_comm_fin:
                         logging.error(f"Error during final communicate: {e_comm_fin}")
                else: # Process already exited
                    try:
                        stdout_rem, stderr_rem = self.ffmpeg_process.communicate(timeout=0.1) # Quick check for remaining output
                        if stderr_rem: stderr_output += stderr_rem.decode('utf-8', errors='ignore')
                    except Exception: pass # Ignore errors if already exited

                exit_code = self.ffmpeg_process.returncode
                logging.info(f"FFmpeg process finished with exit code: {exit_code}")
                if stderr_output:
                    logging.info(f"FFmpeg stderr output:\n{stderr_output}")
                if exit_code != 0 and self._is_running : # If it wasn't an external stop
                     self.decoding_error.emit(f"FFmpeg exited with code {exit_code}.\nStderr:\n{stderr_output[:1000]}") # Emit first 1000 chars
                self.process_finished.emit(exit_code if exit_code is not None else -1)

            self._is_running = False
            logging.info("FFmpegDecodeThread finished.")

    def stop(self):
        logging.info("FFmpegDecodeThread stop requested.")
        self._is_running = False
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            logging.info("Terminating FFmpeg process due to stop().")
            self.ffmpeg_process.terminate()
            # Give it a moment to terminate, then kill if necessary
            try:
                self.ffmpeg_process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                logging.warning("FFmpeg process did not terminate gracefully after stop(), killing.")
                self.ffmpeg_process.kill()
        self.wait(2000) # Wait for the run() method to finish

class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Standalone FFmpeg Player")
        self.setGeometry(100, 100, 640, 360) # Initial size

        self.layout = QVBoxLayout(self)
        self.video_label = QLabel("Waiting for video...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.layout.addWidget(self.video_label)

        self._current_pixmap = None

    @Slot(bytes, int, int)
    def update_frame(self, frame_data, width, height):
        #logging.debug(f"VideoPlayerWidget: Received frame data (len: {len(frame_data)}), {width}x{height}")
        try:
            # Create QImage from raw RGBA data
            image = QImage(frame_data, width, height, QImage.Format.Format_RGBA8888)
            if image.isNull():
                logging.error("VideoPlayerWidget: Failed to create QImage from frame data (isNull).")
                self.video_label.setText("Error: Could not create image from frame.")
                return

            # Convert QImage to QPixmap for display
            self._current_pixmap = QPixmap.fromImage(image)
            if self._current_pixmap.isNull():
                logging.error("VideoPlayerWidget: Failed to create QPixmap from QImage (isNull).")
                self.video_label.setText("Error: Could not create pixmap from image.")
                return
            
            # Scale pixmap to fit label while maintaining aspect ratio
            self.video_label.setPixmap(
                self._current_pixmap.scaled(
                    self.video_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            #logging.debug("VideoPlayerWidget: Frame updated on label.")
        except Exception as e:
            logging.error(f"VideoPlayerWidget: Exception in update_frame: {e}", exc_info=True)
            self.video_label.setText(f"Error processing frame: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_pixmap and not self._current_pixmap.isNull():
            self.video_label.setPixmap(
                self._current_pixmap.scaled(
                    self.video_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

    def closeEvent(self, event):
        logging.info("VideoPlayerWidget: Close event received.")
        if hasattr(self, 'decode_thread') and self.decode_thread:
            self.decode_thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)

    # --- Check if VIDEO_FILE_PATH is set ---
    if not VIDEO_FILE_PATH or VIDEO_FILE_PATH == "temp/TestVideo_aggressive_reencode.mp4": # Default placeholder
        logging.error("Please set the VIDEO_FILE_PATH variable in the script to your video file.")
        # Optionally, show a dialog or exit
        # For now, we'll try to run with the default and let it fail if not found.
        # sys.exit(1)


    player_widget = VideoPlayerWidget()
    
    # Ensure the video file exists before starting the thread
    if not os.path.exists(VIDEO_FILE_PATH):
        logging.error(f"Video file does not exist: {VIDEO_FILE_PATH}")
        player_widget.video_label.setText(f"Error: Video file not found\n{VIDEO_FILE_PATH}")
        player_widget.show()
        return app.exec() # Start event loop to show error

    decode_thread = FFmpegDecodeThread(VIDEO_FILE_PATH)
    player_widget.decode_thread = decode_thread # Store reference for cleanup

    decode_thread.frame_decoded.connect(player_widget.update_frame)
    decode_thread.decoding_error.connect(lambda msg: (
        logging.error(f"Decoding Error from thread: {msg}"),
        player_widget.video_label.setText(f"Decoding Error:\n{msg[:200]}...") # Show first 200 chars
    ))
    decode_thread.process_finished.connect(lambda code: logging.info(f"FFmpeg process ended with code: {code}"))
    
    # Clean up thread when app quits
    app.aboutToQuit.connect(decode_thread.stop)

    player_widget.show()
    decode_thread.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
