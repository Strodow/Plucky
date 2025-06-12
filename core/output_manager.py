import sys
import os
import logging
from typing import Optional, Dict, Any

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import QObject, Signal, QSize, Qt, Slot, QTimer

# Assume composition_renderer.py is in the same directory or a reachable path
try:
    from rendering.composition_renderer import CompositionRenderer
except ImportError:
    # A fallback mock for standalone testing if the main renderer isn't available
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
        self._last_pixmap.fill(Qt.GlobalColor.black)

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
            # If scene is None, just create a blank pixmap
            if self._last_pixmap is None or self._last_pixmap.size() != self._default_size:
                 self._create_blank_pixmap()
            else:
                 self._last_pixmap.fill(Qt.GlobalColor.black)
        
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
# OUTPUT MANAGER
# =============================================================================

class OutputManager(QObject):
    """
    Manages all output channels (e.g., Program, Preview) and orchestrates
    the flow of scenes between them using a central renderer.
    """
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # The manager owns the renderer and the channels
        self.renderer = CompositionRenderer()
        self.program = OutputChannel("Program", self.renderer)
        self.preview = OutputChannel("Preview", self.renderer)
        
        # Connect signals
        self.renderer.needs_update.connect(self._on_renderer_update)
        logging.info("OutputManager initialized with Program and Preview channels.")

    def update_preview(self, scene: Dict[str, Any]):
        """Sets or updates the scene for the Preview channel."""
        logging.info("OutputManager: Updating Preview.")
        self.preview.update_scene(scene)
        
    def take(self):
        """
        Takes the scene currently in Preview and makes it live in Program.
        This is the primary "Go Live" operation.
        """
        logging.info("OutputManager: TAKE command received. Moving Preview to Program.")
        preview_scene = self.preview._current_scene
        self.program.update_scene(preview_scene)

    def clear_all(self):
        """Clears both the Program and Preview channels to a blank state."""
        logging.info("OutputManager: Clearing all channels.")
        self.program.update_scene(None)
        self.preview.update_scene(None)

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

    def cleanup(self):
        """Cleans up resources, particularly the renderer's threads."""
        logging.info("OutputManager: Cleaning up resources.")
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

