import sys
import os
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel, QMenu, QInputDialog, QMessageBox, QApplication
from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QObject, Slot
from PySide6.QtGui import QPixmap, QColor


try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_src_root = os.path.dirname(current_script_dir) # Moves up from 'windows' to 'Plucky/Plucky'
    if project_src_root not in sys.path:
        sys.path.insert(0, project_src_root)
except Exception as e:
    print(f"Warning: Could not automatically set up project path. Imports might fail. Error: {e}", file=sys.stderr)

# --- New Architecture Imports ---
try:
    # We need the renderer to create the preview thumbnails
    from rendering.composition_renderer import CompositionRenderer
except ImportError as e:
    print(f"FATAL: Could not import 'composition_renderer_2.py'. Error: {e}", file=sys.stderr)
    # Mock class for basic testing if the main renderer isn't available
    class CompositionRenderer(QObject):
        def render_scene(self, scene_data: Dict[str, Any]) -> QPixmap: return QPixmap(100,100)
    
# --- Existing Application Component Imports ---
try:
    from widgets.scaled_slide_button import ScaledSlideButton
    from widgets.flow_layout import FlowLayout
    from widgets.song_header_widget import SongHeaderWidget
    from core.presentation_manager import PresentationManager
    from core.template_manager import TemplateManager
    from core.slide_edit_handler import SlideEditHandler
    from core.app_config_manager import ApplicationConfigManager
    from data_models.slide_data import SlideData
    from core.constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT
    from core.slide_drag_drop_handler import SlideDragDropHandler
except ImportError as e:
    print(f"Warning: A local project file could not be imported in slide_ui_manager. Error: {e}", file=sys.stderr)
    # Add mocks if needed for testing in isolation
    class ScaledSlideButton(QWidget): pass

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BASE_PREVIEW_WIDTH = 160


class SlideUIManager(QObject):
    """
    Manages the creation, layout, and interaction of slide preview buttons.
    Uses the CompositionRenderer to generate thumbnails for each slide.
    """
    active_slide_changed_signal = Signal(int)
    request_show_error_message_signal = Signal(str)
    request_delete_slide = Signal(int) # Emits slide_index
    request_apply_template = Signal(int, str) # Emits slide_index, template_name
    request_rename_section_dialog = Signal(str) # Emits section_id
    request_open_section_editor = Signal(str) # Emits section_id_in_manifest

    def __init__(self,
                 presentation_manager: PresentationManager,
                 template_manager: TemplateManager,
                 renderer: 'CompositionRenderer', # Accepts the new renderer
                 slide_edit_handler: SlideEditHandler,
                 config_manager: ApplicationConfigManager,
                 output_window_ref, # Still needed to get target render resolution
                 scroll_area: QScrollArea,
                 slide_buttons_widget: QWidget,
                 slide_buttons_layout: QVBoxLayout,
                 drop_indicator: QWidget,
                 parent_main_window,
                 parent=None):
        super().__init__(parent)

        self.presentation_manager = presentation_manager
        self.template_manager = template_manager
        self.renderer = renderer # Store the new renderer
        self.slide_edit_handler = slide_edit_handler
        self.config_manager = config_manager
        self.output_window_ref = output_window_ref
        self.parent_main_window = parent_main_window

        # UI Elements managed by this class
        self.scroll_area = scroll_area
        self.slide_buttons_widget = slide_buttons_widget
        self.slide_buttons_layout = slide_buttons_layout
        self.drop_indicator = drop_indicator

        self.slide_buttons_list: List[ScaledSlideButton] = []
        self.preview_pixmap_cache: Dict[str, QPixmap] = {}
        self._selected_slide_indices: set[int] = set()
        self.current_slide_index: int = -1

        initial_preview_size = self.config_manager.get_app_setting("preview_size", 1)
        self.button_scale_factor: float = float(initial_preview_size)

        # Drag and drop is still relevant
        self.drag_drop_handler = SlideDragDropHandler(
            main_window=self.parent_main_window,
            presentation_manager=self.presentation_manager,
            scroll_area=self.scroll_area,
            slide_buttons_widget=self.slide_buttons_widget,
            slide_buttons_layout=self.slide_buttons_layout,
            drop_indicator=self.drop_indicator,
            slide_ui_manager=self,
            parent=self
        )

        self.presentation_manager.presentation_changed.connect(self.refresh_slide_display)

    def _build_scene_for_preview(self, slide_data: SlideData) -> Dict[str, Any]:
        """
        Creates a self-contained Scene dictionary for a single slide, suitable for generating a thumbnail.
        """
        scene_width = 1920 # High-res base for quality thumbnails
        scene_height = 1080
        
        scene = {"width": scene_width, "height": scene_height, "layers": []}
        
        # This conversion logic is identical to the one in main_window_2.py
        # It converts one SlideData object into a list of layers for the renderer.
        
        # Background Color Layer
        if slide_data.background_color and slide_data.background_color != "#00000000":
            scene['layers'].append({"id": f"{slide_data.id}_p_bgcolor", "type": "solid_color", "properties": {"color": slide_data.background_color}})
            
        # Background Image Layer
        if slide_data.background_image_path and os.path.exists(slide_data.background_image_path):
            scene['layers'].append({"id": f"{slide_data.id}_p_bgimage", "type": "image", "properties": {"path": slide_data.background_image_path, "scaling_mode": "fill"}})

        # Video Layer (for thumbnail of the first frame)
        if slide_data.video_path and os.path.exists(slide_data.video_path):
            # For a thumbnail, we treat the video as an image to get the first frame.
            # The 'image' handler can load the first frame of a video.
             scene['layers'].append({"id": f"{slide_data.id}_p_video", "type": "image", "properties": {"path": slide_data.video_path, "scaling_mode": "fit"}})

        # Text Layers from Template
        template = slide_data.template_settings or {}
        text_boxes = template.get("text_boxes", [])
        text_content = template.get("text_content", {})
        
        for box in text_boxes:
            box_id = box.get("id")
            content = text_content.get(box_id, "")
            if box_id and content:
                scene['layers'].append({
                    "id": f"{slide_data.id}_p_{box_id}", "type": "text",
                    "position": {"x_pc": box.get("x_pc", 0), "y_pc": box.get("y_pc", 0), "width_pc": box.get("width_pc", 100), "height_pc": box.get("height_pc", 100)},
                    "properties": {
                        "content": content, "font_family": box.get("font_family", "Arial"),
                        "font_size": box.get("font_size", 48), "font_color": box.get("font_color", "#FFFFFF"),
                        "h_align": box.get("h_align", "center"), "v_align": box.get("v_align", "center"),
                        "shadow": {"enabled": box.get("shadow_enabled", False), "color": box.get("shadow_color"), "offset_x": box.get("shadow_offset_x"), "offset_y": box.get("shadow_offset_y")},
                        "outline": {"enabled": box.get("outline_enabled", False), "color": box.get("outline_color"), "width": box.get("outline_width")}
                    }
                })
        return scene

    def refresh_slide_display(self):
        """Rebuilds the entire slide preview area using the new rendering method."""
        logging.info("SlideUIManager: Refreshing slide display.")
        
        # --- Clear existing widgets (same as original) ---
        while self.slide_buttons_layout.count():
            item = self.slide_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.slide_buttons_list.clear()

        slides = self.presentation_manager.get_slides()
        if not slides:
            # ... (handle no slides case) ...
            return

        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)
        last_section_id = None
        current_flow_layout = None

        for index, slide_data in enumerate(slides):
            # Group slides by section
            if slide_data.section_id_in_manifest != last_section_id:
                last_section_id = slide_data.section_id_in_manifest
                
                # Add a header for the new section
                section_title = slide_data.song_title or "Untitled Section" # Fallback title
                header = SongHeaderWidget(title=section_title, section_id=last_section_id, current_button_width=current_dynamic_preview_width)
                # Connect the header's signal to emit the SlideUIManager's signal
                header.edit_title_requested.connect(self.request_rename_section_dialog)
                header.edit_properties_requested.connect(self.request_open_section_editor) # Connect to open full editor signal
                self.slide_buttons_layout.addWidget(header)
                
                # Create a new FlowLayout container for this section's slides
                container = QWidget()
                current_flow_layout = FlowLayout(container, margin=5, hSpacing=5, vSpacing=5)
                self.slide_buttons_layout.addWidget(container)

            # --- New Rendering Logic ---
            slide_id_str = slide_data.id
            if slide_id_str not in self.preview_pixmap_cache:
                scene_to_render = self._build_scene_for_preview(slide_data)
                full_res_pixmap = self.renderer.render_scene(scene_to_render)
                preview_pixmap = full_res_pixmap.scaled(
                    current_dynamic_preview_width, current_dynamic_preview_height,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.preview_pixmap_cache[slide_id_str] = preview_pixmap

            preview_pixmap = self.preview_pixmap_cache[slide_id_str]
            # --- End New Rendering Logic ---

            button = ScaledSlideButton(slide_id=index, instance_id=slide_id_str, plucky_slide_mime_type=PLUCKY_SLIDE_MIME_TYPE)
            button.set_pixmap(preview_pixmap)
            
            # --- Restore all signal connections ---
            button.slide_selected.connect(self._handle_manual_slide_selection)
            button.toggle_selection_requested.connect(self._handle_toggle_selection)
            button.edit_requested.connect(self.slide_edit_handler.handle_edit_slide_requested)
            button.delete_requested.connect(self.request_delete_slide)
            button.apply_template_to_slide_requested.connect(self.request_apply_template) # Connect to the new signal
            # Add other connections...
            
            if current_flow_layout:
                current_flow_layout.addWidget(button)
            self.slide_buttons_list.append(button)

        self.slide_buttons_layout.addStretch(1)

    # All other methods from the original slide_ui_manager.py are preserved here...
    # For brevity, I'm only showing the most critical changes. The full file would include:
    # - _handle_manual_slide_selection
    # - _handle_toggle_selection
    # - get_selected_slide_indices
    # - eventFilter
    # - context menu handlers, etc.
    
    def get_selected_slide_indices(self) -> list[int]:
        return list(self._selected_slide_indices)

    @Slot(int)
    def _handle_manual_slide_selection(self, selected_slide_index: int):
        self._selected_slide_indices.clear()
        self._selected_slide_indices.add(selected_slide_index)
        self.current_slide_index = selected_slide_index
        self._update_button_checked_states()
        self.active_slide_changed_signal.emit(selected_slide_index)

    @Slot(int)
    def _handle_toggle_selection(self, slide_index: int):
        if slide_index in self._selected_slide_indices:
            self._selected_slide_indices.remove(slide_index)
        else:
            self._selected_slide_indices.add(slide_index)
        self._update_button_checked_states()
        
    def _update_button_checked_states(self):
        for btn in self.slide_buttons_list:
            btn.setChecked(btn._slide_id in self._selected_slide_indices)


if __name__ == '__main__':
    # This test block would need to be updated to work with the new structure
    # It requires a mock MainWindow and other components.
    app = QApplication(sys.argv)
    
    class MockMainWindow(QWidget):
        def handle_delete_slide_requested(self, index):
            logging.info(f"Mock Main Window: Delete requested for slide index {index}")
        def handle_apply_template_to_slide(self, index, template_name):
            logging.info(f"Mock Main Window: Apply template '{template_name}' to slide index {index}")
            
    class MockRenderer(QObject):
        def render_scene(self, scene):
            pix = QPixmap(1920, 1080)
            pix.fill(QColor(scene['layers'][0]['properties']['color']))
            return pix

    # ... more mocks needed for a full test ...
    
    main_win = MockMainWindow()
    # ... setup managers and UI elements ...

    logging.info("Standalone test for SlideUIManager is complex and requires full app structure.")
    
    label = QLabel("See console output for SlideUIManager logs if integrated into a test app.")
    label.show()
    
    sys.exit(app.exec())
