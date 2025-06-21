import sys
import os
import logging
import json
from typing import Optional, Dict, Any
from typing import List # Added List for type hinting
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import QObject, Signal, QSize, Qt, Slot, QTimer, QRect

# Assume composition_renderer.py is in the same directory or a reachable path
try:
    from rendering.composition_renderer import CompositionRenderer
except ImportError:
    # A fallback mock for standalone testing if the main renderer isn't available
    # Attempt to import decklink_handler for the DeckLinkTarget mock
    try:
        from .. import decklink_handler # type: ignore
    except ImportError:
        import decklink_handler # type: ignore
    print("Warning: Could not import CompositionRenderer. Using a mock class for testing.", file=sys.stderr)
    class CompositionRenderer(QObject):
        needs_update = Signal()
        def render_scene(self, scene_data: Dict[str, Any]) -> QPixmap:
            w = scene_data.get('width', 100)
            h = scene_data.get('height', 100)
            pixmap = QPixmap(w, h)
            pixmap.fill(QColor(scene_data.get('mock_color', Qt.GlobalColor.magenta)))
            return pixmap
        def cleanup(self): pass

# Import SlideData for type hinting in the new methods
try:
    from data_models.slide_data import SlideData
    # For set_screen_output_target_visibility, we might need OutputWindow type hint
    # This creates a potential circular dependency if OutputWindow imports OutputManager.
    # We can use a forward declaration string for type hinting if needed, or pass QWidget.
    # For now, let's assume MainWindow passes its OutputWindow instance.
    from windows.output_window import OutputWindow # Assuming this path is correct

except ImportError:
    SlideData = None # Fallback for type hinting if running standalone

# Attempt to import decklink_handler for the DeckLinkTarget
try:
    from .. import decklink_handler # type: ignore
except ImportError:
    import decklink_handler # type: ignore
# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================================================================
# OUTPUT CHANNEL
# =============================================================================

class OutputChannel(QObject):
    """
    Represents a single destination for rendered content (e.g., Program, Preview).
    It holds a scene, renders it, and provides the resulting pixmap and key matte.
    """
    pixmap_updated = Signal(QPixmap)
    key_matte_updated = Signal(QPixmap)

    def __init__(self, name: str, renderer: 'CompositionRenderer', default_size: QSize = QSize(1920, 1080), parent: Optional[QObject] = None):
        super().__init__(parent)
        self._name = name
        self._renderer = renderer
        self._default_size = default_size
        self._current_scene: Optional[Dict[str, Any]] = None
        self._last_pixmap: Optional[QPixmap] = None

        self._create_blank_pixmap()
    
    def _create_blank_pixmap(self):
        """Creates an empty, black pixmap to ensure there's always a valid output."""
        self._last_pixmap = QPixmap(self._default_size)
        if self._last_pixmap.isNull():
            logging.error(f"Channel '{self._name}': Failed to create blank pixmap.")
            self._last_pixmap = QPixmap(1, 1) # Fallback
        self._last_pixmap.fill(Qt.GlobalColor.transparent) # Initialize with transparency

    def update_scene(self, scene: Optional[Dict[str, Any]]):
        """Assigns a new scene to this channel and triggers an immediate re-render."""
        logging.info(f"Channel '{self._name}': Scene update received.")
        self._current_scene = scene
        self.render()

    def render(self):
        """
        Renders the currently assigned scene using the CompositionRenderer.
        If the scene is None, it renders a blank output. Emits update signals.
        """
        logging.info(f"Channel '{self._name}': Starting render.")
        if self._current_scene:
            self._last_pixmap = self._renderer.render_scene(self._current_scene)
        else:
            # If scene is None, just create a blank transparent pixmap
            if self._last_pixmap is None or self._last_pixmap.size() != self._default_size:
                 self._create_blank_pixmap()
            else:
                 self._last_pixmap.fill(Qt.GlobalColor.transparent) # Ensure transparency when clearing
        
        if self._last_pixmap is None or self._last_pixmap.isNull():
            logging.error(f"Channel '{self._name}': Render result is null. Creating fallback.")
            self._create_blank_pixmap()

        logging.info(f"Channel '{self._name}': Render complete. Emitting signals.")
        self.pixmap_updated.emit(self._last_pixmap)
        
        # Also generate and emit the key matte
        key_matte = self._generate_key_matte()
        self.key_matte_updated.emit(key_matte)

    def has_video(self) -> bool:
        """Checks if the current scene contains a video layer."""
        if not self._current_scene or 'layers' not in self._current_scene:
            return False
        return any(layer.get('type') == 'video' for layer in self._current_scene['layers'])

    def get_current_pixmap(self) -> QPixmap:
        """Returns the last rendered pixmap for this channel."""
        return self._last_pixmap

    def _generate_key_matte(self) -> QPixmap:
        """
        Generates a key matte from the alpha channel of the last rendered pixmap.
        Opaque areas in the fill become white, transparent areas become black.
        """
        if self._last_pixmap is None or self._last_pixmap.isNull():
            return QPixmap(self._default_size)

        source_image = self._last_pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if source_image.isNull():
            logging.error(f"Channel '{self._name}': Failed to convert pixmap to image for key matte.")
            return QPixmap(self._default_size)
            
        # Convert the source image to an 8-bit alpha mask.
        alpha_mask_image = source_image.convertToFormat(QImage.Format_Alpha8)

        # Create the key matte pixmap with a black background
        key_matte = QPixmap(source_image.size())
        key_matte.fill(Qt.GlobalColor.black)

        # Use a painter to draw the white key signal
        painter = QPainter(key_matte)
        
        # Create a temporary white image and set its alpha channel from the source image's alpha
        white_source = QImage(source_image.size(), QImage.Format_ARGB32_Premultiplied)
        white_source.fill(Qt.GlobalColor.white)
        white_source.setAlphaChannel(alpha_mask_image) # <<< FIX WAS HERE
        
        painter.drawImage(0, 0, white_source)
        painter.end()
        
        return key_matte

# =============================================================================
# DECKLINK OUTPUT TARGET
# =============================================================================
class DeckLinkTarget(QObject):
    """Handles a single DeckLink output device."""
    error_occurred = Signal(str)

    def __init__(self, fill_device_idx: int, key_device_idx: int, video_mode_details: Dict[str, Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self.fill_idx = fill_device_idx
        self.key_idx = key_device_idx
        self.mode_details = video_mode_details
        self.is_active = False
        logging.info(f"DeckLinkTarget created for Fill:{fill_device_idx}, Key:{key_device_idx}, Mode:{video_mode_details.get('name', 'N/A') if video_mode_details else 'N/A'}")

    def initialize(self) -> bool:
        if not decklink_handler.decklink_dll and not decklink_handler.load_dll():
            self.error_occurred.emit("Failed to load DeckLink DLL.")
            return False
        if decklink_handler.decklink_dll.InitializeDLL() != decklink_handler.S_OK: # type: ignore
            self.error_occurred.emit("Failed to initialize DeckLink API (InitializeDLL).")
            return False
        if not decklink_handler.initialize_selected_devices(self.fill_idx, self.key_idx, self.mode_details):
            self.error_occurred.emit(f"Failed to initialize DeckLink devices (Fill:{self.fill_idx}, Key:{self.key_idx}).")
            decklink_handler.decklink_dll.ShutdownDLL() # type: ignore
            return False
        self.is_active = True
        logging.info("DeckLinkTarget initialized successfully.")
        return True

    def send_frame(self, fill_pixmap: QPixmap, key_matte_pixmap: QPixmap):
        if not self.is_active or fill_pixmap.isNull() or key_matte_pixmap.isNull():
            logging.debug(f"DeckLinkTarget: Send frame skipped. Active: {self.is_active}, FillNull: {fill_pixmap.isNull()}, KeyNull: {key_matte_pixmap.isNull()}")
            return

        # Convert QPixmaps to QImages, then to bytes
        fill_image = fill_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        key_image = key_matte_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

        fill_bytes = decklink_handler.get_image_bytes_from_qimage(fill_image)
        key_bytes = decklink_handler.get_image_bytes_from_qimage(key_image)

        if not (fill_bytes and key_bytes):
            logging.error("DeckLinkTarget: Failed to convert pixmaps to bytes for sending.")
            return

        if not decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
            logging.error("DeckLinkTarget: decklink_handler.send_external_keying_frames reported failure.")

    def shutdown(self):
        if self.is_active:
            logging.info("DeckLinkTarget: Shutting down devices and SDK.")
            decklink_handler.shutdown_selected_devices()
            if decklink_handler.decklink_dll: # Check if DLL is still loaded
                 hr_shutdown = decklink_handler.decklink_dll.ShutdownDLL() # type: ignore
                 if hr_shutdown != decklink_handler.S_OK:
                     logging.warning(f"DeckLinkTarget: ShutdownDLL returned HRESULT {hr_shutdown:#010x}")
            self.is_active = False
        else:
            logging.info("DeckLinkTarget: Shutdown called but not active.")

# =============================================================================
# OUTPUT MANAGER
# =============================================================================

class OutputManager(QObject):
    """
    Manages all output channels (e.g., Program, Preview) and orchestrates
    the flow of scenes between them using a central renderer.
    """
    # Signal to notify MainWindow of DeckLink errors
    decklink_error_occurred = Signal(str)
    # Signal to directly notify MainWindow about program output changes
    program_pixmap_updated = Signal(QPixmap)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # The manager owns the renderer and the channels
        self.renderer = CompositionRenderer()
        self.program = OutputChannel("Program", self.renderer)
        self.preview = OutputChannel("Preview", self.renderer)
        self.decklink_target: Optional[DeckLinkTarget] = None
        self._screen_output_window: Optional['OutputWindow'] = None # Reference to the screen output window
        
        # Connect signals
        # Connect program channel's pixmap_updated to our own program_pixmap_updated
        self.program.pixmap_updated.connect(self._forward_program_pixmap)
        # Also connect program channel's pixmap_updated to update DeckLink if active
        self.program.pixmap_updated.connect(self._update_decklink_target_frame)
        self.renderer.needs_update.connect(self._on_renderer_update)
        logging.info("OutputManager initialized with Program and Preview channels.")

    def update_preview(self, scene: Dict[str, Any]):
        """Sets or updates the scene for the Preview channel."""
        logging.info("OutputManager: Updating Preview.")
        self.preview.update_scene(scene)

    def register_screen_output_window(self, window: 'OutputWindow'):
        """Allows MainWindow to register its OutputWindow instance with the OutputManager."""
        self._screen_output_window = window
        
    def update_preview_slides(self, background_slide: Optional[SlideData], content_slide: Optional[SlideData]):
        """
        Builds a scene from SlideData objects and updates the Preview channel.
        (This method will need the scene building logic from MainWindow)
        """
        logging.info(f"OutputManager: Updating Preview with slides. BG: {background_slide.id if background_slide else 'None'}, Content: {content_slide.id if content_slide else 'None'}")
        # Placeholder for scene building logic (to be moved from MainWindow)
        scene = self._build_scene_from_slides(background_slide, content_slide)
        self.preview.update_scene(scene)

    def take(self):
        """
        Takes the scene currently in Preview and makes it live in Program.
        This is the primary "Go Live" operation.
        """
        logging.info("OutputManager: TAKE command received. Moving Preview to Program.")
        preview_scene = self.preview._current_scene
        self.program.update_scene(preview_scene)
        # The program.pixmap_updated signal will trigger _update_decklink_target_frame

    def clear_all(self):
        """Clears both the Program and Preview channels to a blank state."""
        logging.info("OutputManager: Clearing all channels.")
        self.program.update_scene(None)
        self.preview.update_scene(None)

    def clear_program(self):
        """Clears only the Program channel to a blank state."""
        logging.info("OutputManager: Clearing Program channel.")
        self.program.update_scene(None)
        # The program.pixmap_updated signal will trigger _update_decklink_target_frame
        # and _forward_program_pixmap

    @Slot()
    def _on_renderer_update(self):
        """
        Slot connected to the renderer's 'needs_update' signal.
        This is typically triggered by a new video frame being ready.
        It forces a re-render on any channel currently displaying a video.
        """
        logging.info("OutputManager: Renderer needs update (video frame). Checking channels.")
        if self.program.has_video():
            logging.info("--> Program channel has video. Re-rendering.")
            self.program.render()
        
        if self.preview.has_video():
            logging.info("--> Preview channel has video. Re-rendering.")
            self.preview.render()

    @Slot(QPixmap)
    def _forward_program_pixmap(self, pixmap: QPixmap):
        """Forwards the program channel's pixmap_updated signal."""
        self.program_pixmap_updated.emit(pixmap)

    @Slot(QPixmap)
    def _update_decklink_target_frame(self, program_fill_pixmap: QPixmap):
        """Sends the current program frame to the active DeckLink target."""
        if self.decklink_target and self.decklink_target.is_active:
            program_key_matte = self.program._generate_key_matte()
            logging.debug("OutputManager: Sending frame to active DeckLinkTarget.")
            self.decklink_target.send_frame(program_fill_pixmap, program_key_matte)

    def enable_decklink_output(self, fill_idx: int, key_idx: int, mode_details: Optional[Dict[str, Any]]) -> bool:
        logging.info(f"OutputManager: Enabling DeckLink output. Fill:{fill_idx}, Key:{key_idx}, Mode:{mode_details.get('name', 'N/A') if mode_details else 'N/A'}")
        if self.decklink_target and self.decklink_target.is_active:
            logging.info("OutputManager: DeckLink already active, shutting down existing target first.")
            self.decklink_target.shutdown()
            self.decklink_target = None

        if mode_details is None:
            logging.error("OutputManager: Cannot enable DeckLink output, video mode details are missing.")
            return False

        self.decklink_target = DeckLinkTarget(fill_idx, key_idx, mode_details, parent=self)
        self.decklink_target.error_occurred.connect(self.decklink_error_occurred) # Connect error signal
        if self.decklink_target.initialize():
            logging.info("OutputManager: DeckLink target initialized. Sending current program frame.")
            # Send current program frame if available
            current_program_pixmap = self.program.get_current_pixmap()
            if not current_program_pixmap.isNull():
                self._update_decklink_target_frame(current_program_pixmap)
            return True
        else:
            logging.error("OutputManager: Failed to initialize DeckLink target.")
            self.decklink_target = None # Clear if initialization failed
            return False

    def disable_decklink_output(self):
        logging.info("OutputManager: Disabling DeckLink output.")
        if self.decklink_target:
            self.decklink_target.shutdown()
            try:
                self.decklink_target.error_occurred.disconnect(self.decklink_error_occurred)
            except RuntimeError: # Already disconnected or target deleted
                pass
            self.decklink_target = None
        logging.info("OutputManager: DeckLink output disabled.")

    def set_screen_output_target_visibility(self, visible: bool, screen_geometry: Optional[QRect] = None):
        """Manages the visibility of the screen output window."""
        if not self._screen_output_window:
            logging.warning("OutputManager: Screen output window not registered. Cannot set visibility.")
            return

        if visible and screen_geometry:
            self._screen_output_window.setGeometry(screen_geometry)
            self._screen_output_window.showFullScreen()
            logging.info(f"OutputManager: Screen output window shown fullscreen on geometry: {screen_geometry}")
        elif not visible:
            self._screen_output_window.hide()
            logging.info("OutputManager: Screen output window hidden.")

    def _build_scene_from_slides(self, background_slide: Optional[SlideData], content_slide: Optional[SlideData]) -> Dict[str, Any]:
        """
        Creates a 'Scene' dictionary for the renderer from SlideData objects.
        (This logic will be moved from MainWindow._build_scene_from_active_slides)
        """
        # Use the OutputManager's default size or a configured scene size
        scene_width, scene_height = self.program._default_size.width(), self.program._default_size.height()
        scene = {"width": scene_width, "height": scene_height, "layers": []}

        if background_slide:
            scene['layers'].extend(self._convert_slidedata_to_layers(background_slide))

        if content_slide and content_slide != background_slide: # Avoid duplicate layers if BG is also content
            scene['layers'].extend(self._convert_slidedata_to_layers(content_slide))
        try:
            logging.debug(f"OutputManager: Built scene data: {json.dumps(scene, indent=2)}")
        except TypeError:
            logging.debug(f"OutputManager: Built scene data (non-serializable): {scene}")
        return scene

    def _convert_slidedata_to_layers(self, slide: SlideData) -> List[Dict[str, Any]]:
        """
        Translates a single SlideData object into a list of Layer dictionaries.
        (Copied from MainWindow._convert_slidedata_to_layers)
        """
        layers = []
        if not slide: # Should not happen if called from _build_scene_from_slides with valid SlideData
            return layers

        if slide.background_color and slide.background_color != "#00000000": # Check for actual color, not just transparent
            layers.append({"id": f"{slide.id}_bgcolor", "type": "solid_color", "properties": {"color": slide.background_color}})
        if slide.background_image_path and os.path.exists(slide.background_image_path):
            layers.append({"id": f"{slide.id}_bgimage", "type": "image", "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100}, "properties": {"path": slide.background_image_path, "scaling_mode": "fill"}})
        if slide.video_path and os.path.exists(slide.video_path):
            layers.append({"id": f"{slide.id}_video", "type": "video", "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100}, "properties": {"path": slide.video_path, "loop": True, "scaling_mode": "fit"}})
        
        template = slide.template_settings or {}
        text_boxes = template.get("text_boxes", [])
        text_content = template.get("text_content", {})
        
        for box in text_boxes:
            box_id = box.get("id")
            content = text_content.get(box_id, "") # Get content for this box_id
            if box_id: # Create layer even if content is empty. Renderer will handle not drawing empty text.
                layers.append({
                    "id": f"{slide.id}_{box_id}", "type": "text",
                    "position": {"x_pc": box.get("x_pc", 0), "y_pc": box.get("y_pc", 0), "width_pc": box.get("width_pc", 100), "height_pc": box.get("height_pc", 100)},
                    "properties": {
                        "content": content,
                        "font_family": box.get("font_family", "Arial"),
                        "font_size": box.get("font_size", 48),
                        "font_color": box.get("font_color", "#FFFFFF"),
                        "h_align": box.get("h_align", "center"),
                        "v_align": box.get("v_align", "center"),
                        "shadow": box.get("shadow", {}), # Pass shadow dict
                        "outline": box.get("outline", {}) # Pass outline dict
                    }
                })
        return layers

    def cleanup(self):
        """Cleans up resources, particularly the renderer's threads."""
        logging.info("OutputManager: Cleaning up resources.")
        if self.decklink_target:
            self.decklink_target.shutdown()
            # No need to disconnect here as decklink_target will be deleted if parent is self
            self.decklink_target = None
        self.renderer.cleanup()


# =============================================================================
# STANDALONE TEST BLOCK
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # --- Test Setup ---
    output_dir = "temp"
    os.makedirs(output_dir, exist_ok=True)

    manager = OutputManager()
    
    # --- Create Sample Scenes ---
    SCENE_WIDTH = 640
    SCENE_HEIGHT = 360

    title_scene = {
        "width": SCENE_WIDTH, "height": SCENE_HEIGHT,
        "layers": [
            {"type": "solid_color", "properties": {"color": "#2E3B4E"}},
            {"type": "text", 
             "position": {"x_pc": 5, "y_pc": 20, "width_pc": 90, "height_pc": 60},
             "properties": {
                 "content": "TITLE SLIDE",
                 "font_family": "Impact", "font_size": 80, "font_color": "#FFFFFF",
                 "h_align": "center", "v_align": "center",
                 "outline": {"enabled": True, "color": "#111111", "width": 3}
             }}
        ]
    }
    
    content_scene = {
        "width": SCENE_WIDTH, "height": SCENE_HEIGHT,
        "layers": [
            {"type": "solid_color", "properties": {"color": "#4A2E4E"}},
            {"type": "text",
             "position": {"x_pc": 10, "y_pc": 10, "width_pc": 80, "height_pc": 80},
             "properties": {
                 "content": "This is the main content.\nIt will appear after 'TAKE'.",
                 "font_family": "Arial", "font_size": 40, "font_color": "#F0F0F0",
                 "h_align": "center", "v_align": "center"
             }}
        ]
    }

    # --- Test Slots to Save Images ---
    @Slot(QPixmap)
    def save_program_pixmap(pixmap: QPixmap):
        path = os.path.join(output_dir, "program_output.png")
        pixmap.save(path)
        logging.info(f"--- Saved Program output to '{path}' ---")

    @Slot(QPixmap)
    def save_preview_pixmap(pixmap: QPixmap):
        path = os.path.join(output_dir, "preview_output.png")
        pixmap.save(path)
        logging.info(f"--- Saved Preview output to '{path}' ---")

    manager.program.pixmap_updated.connect(save_program_pixmap)
    manager.preview.pixmap_updated.connect(save_preview_pixmap)
    
    # --- Simulate UI Workflow ---
    
    # 1. Start with everything clear
    QTimer.singleShot(100, manager.clear_all)
    
    # 2. After 1 second, show the title slide in PREVIEW
    QTimer.singleShot(1000, lambda: manager.update_preview(title_scene))
    
    # 3. After 3 seconds, TAKE the title slide to PROGRAM
    QTimer.singleShot(3000, manager.take)
    
    # 4. After 4 seconds, show the content slide in PREVIEW
    QTimer.singleShot(4000, lambda: manager.update_preview(content_scene))
    
    # 5. After 6 seconds, TAKE the content slide to PROGRAM
    QTimer.singleShot(6000, manager.take)
    
    # 6. After 8 seconds, clear everything
    QTimer.singleShot(8000, manager.clear_all)

    # 7. After 9 seconds, quit the app
    QTimer.singleShot(9000, app.quit)

    logging.info(f"Starting test workflow. Check the '{output_dir}' directory for PNG files.")
    
    try:
        app.exec()
    finally:
        manager.cleanup()
        logging.info("Test finished.")
