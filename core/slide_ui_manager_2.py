import sys
import os
import logging
import json
from typing import Optional, List, Dict, Any
import uuid # Added for context menu actions

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
    from commands.slide_commands import AddSlideBlockToSectionCommand # Added for context menu
    from core.slide_drag_drop_handler import SlideDragDropHandler
    from commands.slide_commands import ChangeOverlayLabelCommand, ChangeBannerColorCommand # Import the commands
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
    request_set_status_message_signal = Signal(str, int) # Added from old manager
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

        # Enable custom context menu for the slide_buttons_widget (for adding slides/sections to panel)
        self.slide_buttons_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.slide_buttons_widget.customContextMenuRequested.connect(self._handle_slide_panel_custom_context_menu)

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

        # Install event filter on the QScrollArea for keyboard navigation
        self.scroll_area.installEventFilter(self)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Connect to PresentationManager signals
        self.presentation_manager.presentation_changed.connect(self.refresh_slide_display)
        self.presentation_manager.slide_visual_property_changed.connect(self._handle_slide_visual_property_change)

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
            if box_id: # Create layer even if content is empty. Renderer will handle not drawing empty text.
                scene['layers'].append({
                    "id": f"{slide_data.id}_p_{box_id}", "type": "text",
                    "position": {"x_pc": box.get("x_pc", 0), "y_pc": box.get("y_pc", 0), "width_pc": box.get("width_pc", 100), "height_pc": box.get("height_pc", 100)},
                    "properties": {
                        "content": content,
                        "font_family": box.get("font_family", "Arial"),
                        "font_size": box.get("font_size", 48),
                        "font_color": box.get("font_color", "#FFFFFFFF"),
                        "h_align": box.get("h_align", "center"),
                        "v_align": box.get("v_align", "center"),
                        "force_all_caps": box.get("force_all_caps", False),
                        "shadow": {
                            "enabled": box.get("shadow_enabled", False),
                            "color": box.get("shadow_color", "#00000080"),
                            "offset_x": box.get("shadow_offset_x", 2),
                            "offset_y": box.get("shadow_offset_y", 2),
                            "blur": box.get("shadow_blur", 2)
                        },
                        "outline": {
                            "enabled": box.get("outline_enabled", False),
                            "color": box.get("outline_color", "#000000FF"),
                            "width": box.get("outline_width", 1)
                        }
                    }
                })
        
        # Shapes from template_settings (NEW)
        if slide_data.template_settings:
            template_shapes = slide_data.template_settings.get("shapes", [])
            for shape_def in template_shapes:
                shape_id = shape_def.get("id")
                if shape_id:
                    scene['layers'].append({
                        "id": f"shape_{shape_id}_{slide_data.id}",
                        "type": "shape",
                        "position": {"x_pc": shape_def.get("x_pc", 0), "y_pc": shape_def.get("y_pc", 0), "width_pc": shape_def.get("width_pc", 100), "height_pc": shape_def.get("height_pc", 100)},
                        "properties": {
                            "shape_type": shape_def.get("type", "rectangle"),
                            "fill_color": shape_def.get("fill_color", "#000000FF"),
                            "stroke": {
                                "enabled": shape_def.get("stroke_width", 0) > 0,
                                "color": shape_def.get("stroke_color", "#000000FF"),
                                "width": shape_def.get("stroke_width", 0)
                            },
                            "opacity": shape_def.get("opacity", 1.0)
                        }
                    }
                )
        try:
            logging.debug(f"SlideUIManager: Built preview scene data for slide '{slide_data.id}': {json.dumps(scene, indent=2)}")
        except TypeError:
            logging.debug(f"SlideUIManager: Built preview scene data for slide '{slide_data.id}' (non-serializable): {scene}")
        return scene


    def refresh_slide_display(self):
        """Rebuilds the entire slide preview area using the new rendering method."""
        logging.info("SlideUIManager: Refreshing slide display.")

        old_single_selected_slide_id_str: Optional[str] = None
        if self.current_slide_index != -1 and len(self._selected_slide_indices) == 1:
            # Try to get the ID of the currently selected slide to restore selection later
            # This requires PresentationManager to be in a consistent state before refresh
            # For simplicity, we assume get_slides() can be called here if PM state is stable before UI rebuild.
            # A more robust way might be to store the ID when selection changes.
            slides_before_rebuild = self.presentation_manager.get_slides() # Potentially problematic if PM is mid-change
            if 0 <= self.current_slide_index < len(slides_before_rebuild):
                 old_single_selected_slide_id_str = slides_before_rebuild[self.current_slide_index].id

        self._selected_slide_indices.clear() # Clear selection before rebuild
        self.current_slide_index = -1       # Reset current index

        # --- Clear existing widgets (same as original) ---
        while self.slide_buttons_layout.count():
            item = self.slide_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.slide_buttons_list.clear()
        
        slides = self.presentation_manager.get_slides()
        if not slides:
            no_slides_label = QLabel("No slides. Use context menu or 'Presentation > Add New Section'.")
            no_slides_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slide_buttons_layout.addWidget(no_slides_label)
            self.active_slide_changed_signal.emit(-1) # Signal no active slide
            return

        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)
        last_section_id = None
        current_flow_layout = None

        for index, slide_data in enumerate(slides):
            # Group slides by section
            if slide_data.section_id_in_manifest != last_section_id:
                last_section_id = slide_data.section_id_in_manifest
                
                # Add a header for the new section (using song_title as section title for now)
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
                if full_res_pixmap:
                    logging.debug(f"SlideUIManager.refresh: Rendered full-res pixmap for '{slide_id_str}' - Size: {full_res_pixmap.size()}, isNull: {full_res_pixmap.isNull()}")
                else:
                    logging.debug(f"SlideUIManager.refresh: Renderer returned None for full-res pixmap for '{slide_id_str}'.")

                preview_pixmap = full_res_pixmap.scaled(
                    current_dynamic_preview_width, current_dynamic_preview_height,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.preview_pixmap_cache[slide_id_str] = preview_pixmap

            preview_pixmap = self.preview_pixmap_cache[slide_id_str]
            # --- End New Rendering Logic ---

            # Call with positional arguments: (parent, slide_id, instance_id, mime_type)
            # The parent is the 'container' widget for the current FlowLayout.
            # Pass custom args positionally, and specify the parent with the 'parent' keyword.
            # Use keyword arguments for everything to match the new __init__
            button = ScaledSlideButton(
                slide_id=index,
                instance_id=slide_id_str,
                plucky_slide_mime_type=PLUCKY_SLIDE_MIME_TYPE,
                parent=container
            )
            button.set_pixmap(preview_pixmap)
            
            # --- Restore all signal connections ---
            button.slide_selected.connect(self._handle_manual_slide_selection)
            button.toggle_selection_requested.connect(self._handle_toggle_selection) # For Ctrl/Shift click
            button.edit_requested.connect(self.slide_edit_handler.handle_edit_slide_requested)
            button.delete_requested.connect(self.request_delete_slide)
            button.apply_template_to_slide_requested.connect(self.request_apply_template) # Connect to the new signal
            button.insert_slide_from_layout_requested.connect(self._handle_insert_slide_from_button_context_menu) # This seems to be a placeholder/WIP connection
            button.insert_new_section_requested.connect(self._handle_insert_new_section_from_button_context_menu)
            # Connect the button's signal to a slot within SlideUIManager_2
            button.center_overlay_label_changed.connect(self._handle_slide_button_overlay_label_changed) 
            button.banner_color_change_requested.connect(self._handle_slide_button_banner_color_changed)

            # Set button properties
            button.set_is_background_slide(slide_data.is_background_slide)
            current_label_for_banner = "BG" if slide_data.is_background_slide else ""
            button.set_slide_info(number=index + 1, label=current_label_for_banner)
            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            if hasattr(slide_data, 'banner_color') and slide_data.banner_color:
                button.set_banner_color(QColor(slide_data.banner_color))
            else:
                button.set_banner_color(None)

            layout_template_names_list = self.template_manager.get_layout_names()
            button.set_available_templates(layout_template_names_list)
            
            if current_flow_layout:
                current_flow_layout.addWidget(button)
            self.slide_buttons_list.append(button)

        self.slide_buttons_layout.addStretch(1)
        self._update_all_button_overlay_labels()

        # Clear stale pixmap cache entries
        current_slide_ids = {s.id for s in slides}
        cached_ids_to_remove = [cached_id for cached_id in self.preview_pixmap_cache if cached_id not in current_slide_ids]
        for stale_id in cached_ids_to_remove:
            if stale_id in self.preview_pixmap_cache: # Double check before del
                del self.preview_pixmap_cache[stale_id]

        # Restore selection
        new_single_selected_index = -1
        if old_single_selected_slide_id_str is not None:
            for idx, s_data in enumerate(slides):
                if s_data.id == old_single_selected_slide_id_str:
                    new_single_selected_index = idx
                    break
        
        if new_single_selected_index != -1:
            button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_single_selected_index), None)
            if button_to_select:
                self._selected_slide_indices.add(new_single_selected_index)
                self.current_slide_index = new_single_selected_index
                button_to_select.setChecked(True)
                self.active_slide_changed_signal.emit(new_single_selected_index)
                self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
            else: # Should not happen if logic is correct
                self.active_slide_changed_signal.emit(-1)
        elif slides: # If no previous selection, or previous selection not found, select first slide
            self._handle_manual_slide_selection(0) # This will emit active_slide_changed_signal
            if self.slide_buttons_list:
                self.scroll_area.ensureWidgetVisible(self.slide_buttons_list[0], 50, 50)
        else: # No slides, ensure -1 is emitted
            self.active_slide_changed_signal.emit(-1)

    def clear_selection(self):
        """Clears the current slide selection."""
        logging.info("SlideUIManager: Clearing selection.")
        self._selected_slide_indices.clear()
        if self.current_slide_index != -1: # Only emit if it actually changes
            self.current_slide_index = -1
            self.active_slide_changed_signal.emit(-1)
        self._update_button_checked_states()

    def set_preview_scale_factor(self, scale_factor: float):
        """Sets the scale factor for slide preview buttons and refreshes the display."""
        logging.info(f"SlideUIManager: Setting preview scale factor to {scale_factor}.")
        self.button_scale_factor = float(scale_factor)
        self.config_manager.set_app_setting("preview_size", int(scale_factor))
        self.preview_pixmap_cache.clear()
        self.refresh_slide_display()

    @Slot(list) # list of int (indices)
    def _handle_slide_visual_property_change(self, updated_indices: List[int]):
        """
        Handles visual property changes for specific slides without a full UI rebuild.
        Re-renders previews for the specified slide indices.
        """
        logging.info(f"SlideUIManager: Handling visual property change for indices: {updated_indices}")
        all_current_slides_data = self.presentation_manager.get_slides()

        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)

        for index in updated_indices:
            if not (0 <= index < len(self.slide_buttons_list) and 0 <= index < len(all_current_slides_data)):
                logging.warning(f"SlideUIManager: Index {index} out of bounds for visual property change. Buttons: {len(self.slide_buttons_list)}, Slides: {len(all_current_slides_data)}")
                continue

            button = self.slide_buttons_list[index]
            slide_data = all_current_slides_data[index]

            if not isinstance(button, ScaledSlideButton):
                logging.warning(f"SlideUIManager: Expected ScaledSlideButton at index {index}, got {type(button)}. Skipping.")
                continue

            slide_id_str = slide_data.id
            if slide_id_str in self.preview_pixmap_cache:
                del self.preview_pixmap_cache[slide_id_str]
                logging.debug(f"SlideUIManager: Invalidated cache for slide instance {slide_id_str} (global index {index})")

            try:
                scene_to_render = self._build_scene_for_preview(slide_data)
                full_res_pixmap = self.renderer.render_scene(scene_to_render)
                if full_res_pixmap:
                    logging.debug(f"SlideUIManager.visual_change: Rendered full-res pixmap for '{slide_id_str}' - Size: {full_res_pixmap.size()}, isNull: {full_res_pixmap.isNull()}")
                else:
                    logging.debug(f"SlideUIManager.visual_change: Renderer returned None for full-res pixmap for '{slide_id_str}'.")

                preview_pixmap = full_res_pixmap.scaled(
                    current_dynamic_preview_width, current_dynamic_preview_height,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                button.set_pixmap(preview_pixmap)
                self.preview_pixmap_cache[slide_id_str] = preview_pixmap
            except Exception as e:
                logging.error(f"SlideUIManager: Error re-rendering preview for slide {index} (ID {slide_data.id}): {e}")
                error_pixmap = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height)
                error_pixmap.fill(Qt.GlobalColor.magenta)
                button.set_pixmap(error_pixmap)

            if hasattr(slide_data, 'banner_color') and slide_data.banner_color:
                button.set_banner_color(QColor(slide_data.banner_color))
            else:
                button.set_banner_color(None)
            button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)
            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            button.set_is_background_slide(slide_data.is_background_slide)
            button.update()

    @Slot(int, str)
    def _handle_slide_button_overlay_label_changed(self, slide_index: int, new_label: str):
        """
        Handles the center_overlay_label_changed signal from a ScaledSlideButton.
        Updates the SlideData in the PresentationManager.
        """
        logging.info(f"SlideUIManager: Overlay label changed for slide index {slide_index} to '{new_label}'.")
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            slide_data = slides[slide_index]
            # Use slide_data.id which is the instance_id for the command
            cmd = ChangeOverlayLabelCommand(
                self.presentation_manager,
                slide_data.id, # Pass the instance_id
                slide_data.overlay_label, # Old label
                new_label # New label
            )
            self.presentation_manager.do_command(cmd)
        else:
            logging.warning(f"SlideUIManager: Cannot change overlay label for invalid slide index {slide_index}.")
    
    @Slot(int, QColor) # QColor can be None if resetting to default
    def _handle_slide_button_banner_color_changed(self, slide_index: int, new_qcolor: Optional[QColor]):
        """
        Handles the banner_color_change_requested signal from a ScaledSlideButton.
        Updates the SlideData in the PresentationManager via a command.
        """
        logging.info(f"SlideUIManager: Banner color change requested for slide index {slide_index} to {new_qcolor.name() if new_qcolor else 'None'}.")
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            slide_data = slides[slide_index]
            instance_id = slide_data.id # Use the unique instance ID for the command

            # Get old color from slide_data.banner_color (which is already a QColor or None)
            old_qcolor = slide_data.banner_color
            old_color_hex = old_qcolor.name(QColor.NameFormat.HexArgb) if old_qcolor and old_qcolor.isValid() else None
            
            new_color_hex = new_qcolor.name(QColor.NameFormat.HexArgb) if new_qcolor and new_qcolor.isValid() else None

            cmd = ChangeBannerColorCommand(
                self.presentation_manager,
                instance_id,
                old_color_hex,
                new_color_hex
            )
            self.presentation_manager.do_command(cmd)
        else:
            logging.warning(f"SlideUIManager: Cannot change banner color for invalid slide index {slide_index}.")

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

    def _update_all_button_overlay_labels(self):
        slides = self.presentation_manager.get_slides()
        for index, slide_data in enumerate(slides):
            button = next((btn for btn in self.slide_buttons_list if btn._slide_id == index), None)
            if button and isinstance(button, ScaledSlideButton):
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

    def eventFilter(self, watched_object, event):
        if watched_object == self.scroll_area and event.type() == QEvent.Type.KeyPress:
            if event.isAutoRepeat():
                return True

            key = event.key()
            slides = self.presentation_manager.get_slides()
            num_slides = len(slides)

            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                return super().eventFilter(watched_object, event)

            if num_slides == 0:
                return super().eventFilter(watched_object, event)

            current_selection_index = self.current_slide_index
            new_selection_index = current_selection_index

            if key == Qt.Key_Right:
                if current_selection_index == -1 and num_slides > 0: new_selection_index = 0
                elif current_selection_index < num_slides - 1: new_selection_index = current_selection_index + 1
                elif current_selection_index == num_slides - 1: new_selection_index = 0 # Wrap
                else: return super().eventFilter(watched_object, event)
            elif key == Qt.Key_Left:
                if current_selection_index == -1 and num_slides > 0: new_selection_index = num_slides - 1 # Wrap
                elif current_selection_index > 0: new_selection_index = current_selection_index - 1
                elif current_selection_index == 0 and num_slides > 0: new_selection_index = num_slides - 1 # Wrap
                else: return super().eventFilter(watched_object, event)
            else:
                return super().eventFilter(watched_object, event)

            if new_selection_index != current_selection_index or \
               (current_selection_index == -1 and new_selection_index != -1):
                button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
                if button_to_select:
                    self._handle_manual_slide_selection(new_selection_index)
                    self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
                return True
        return super().eventFilter(watched_object, event)

    def _determine_insertion_context(self, global_pos: QPoint) -> dict:
        # This method needs to be adapted from the old slide_ui_manager.py
        # It determines where a new slide/section should be inserted based on click position.
        # For brevity, this is a simplified placeholder. The full logic is quite extensive.
        # The original logic iterates up the parent chain from childAt(pos) to find
        # ScaledSlideButton or SongHeaderWidget or FlowLayout container.
        # It then uses PresentationManager._get_arrangement_info_from_instance_id.
        # This method is crucial for the context menu to work correctly.
        # A full port would be needed.
        slides = self.presentation_manager.get_slides()
        num_manifest_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
        
        # Fallback context if no specific item is clicked
        context = {
            "action_on_slide_instance_id": None,
            "target_section_id_for_slide_insert": slides[0].section_id_in_manifest if slides else None,
            "target_arrangement_name_for_slide_insert": slides[0].active_arrangement_name_for_section if slides else "Default",
            "index_in_arrangement_for_slide_insert": len(slides) if slides else 0, # Append to end of first section by default
            "manifest_index_for_new_section_insert": num_manifest_sections # Append new section to end of manifest
        }
        # A more complete implementation would analyze widget_at_pos like in the original.
        return context

    @Slot(QPoint)
    def _handle_slide_panel_custom_context_menu(self, local_pos: QPoint):
        global_pos = self.slide_buttons_widget.mapToGlobal(local_pos)
        context = self._determine_insertion_context(global_pos)
        
        context_menu = QMenu(self.slide_buttons_widget)
        add_slide_menu = context_menu.addMenu("Add new slide from Layout")

        if context["target_section_id_for_slide_insert"] and context["target_arrangement_name_for_slide_insert"] is not None:
            layout_template_names = self.template_manager.get_layout_names()
            if not layout_template_names:
                no_layouts_action = add_slide_menu.addAction("No Layout Templates Available")
                no_layouts_action.setEnabled(False)
            else:
                for layout_name in layout_template_names:
                    action = add_slide_menu.addAction(layout_name)
                    action.triggered.connect(
                        lambda checked=False, name=layout_name,
                               section_id=context["target_section_id_for_slide_insert"],
                               arr_name=context["target_arrangement_name_for_slide_insert"],
                               idx_in_arr=context["index_in_arrangement_for_slide_insert"]:
                        self._handle_insert_slide_from_layout_action(name, section_id, arr_name, idx_in_arr)
                    )
        else:
            add_slide_menu.setEnabled(False)
            add_slide_menu.setToolTip("Click on or within a section to insert a slide.")
        
        context_menu.addSeparator()
        add_section_action = context_menu.addAction("Add new Section here")
        add_section_action.triggered.connect(
            lambda checked=False, manifest_idx=context["manifest_index_for_new_section_insert"]:
            self.parent_main_window._prompt_and_insert_new_section(manifest_idx) # Delegate to MainWindow
        )
        context_menu.exec(global_pos)

    def _handle_insert_slide_from_layout_action(self, layout_name_to_apply: str,
                                                target_section_id_in_manifest: str,
                                                target_arrangement_name: str,
                                                insert_at_index_in_arrangement: int):
        resolved_template_settings = self.template_manager.resolve_layout_template(layout_name_to_apply)
        if not resolved_template_settings:
            self.request_show_error_message_signal.emit(f"Could not resolve layout template '{layout_name_to_apply}'.")
            return

        new_slide_block_id = f"slide_{uuid.uuid4().hex[:12]}"
        bg_color_hex = resolved_template_settings.get("background_color")
        bg_source = bg_color_hex if bg_color_hex and bg_color_hex.lower() != "#00000000" else None
        new_text_content = {tb.get("id"): "" for tb in resolved_template_settings.get("text_boxes", []) if tb.get("id")}

        new_slide_block_data = {
            "slide_id": new_slide_block_id, "label": "New Slide", "content": new_text_content,
            "template_id": layout_name_to_apply, "background_source": bg_source, "notes": None
        }
        cmd = AddSlideBlockToSectionCommand(
            self.presentation_manager, target_section_id_in_manifest, new_slide_block_data,
            target_arrangement_name, insert_at_index_in_arrangement
        )
        self.presentation_manager.do_command(cmd)
        self.request_set_status_message_signal.emit(f"Added slide from layout '{layout_name_to_apply}'.", 3000)

    def _handle_insert_slide_from_button_context_menu(self, after_slide_global_idx: int, layout_name: str):
        # Similar to _handle_insert_slide_from_layout_action, but context comes from button
        # This requires getting arrangement info from the after_slide_global_idx
        # Placeholder - full implementation would mirror the old manager
        self.request_show_error_message_signal.emit("Insert slide from button context menu not fully implemented in new manager.")

    def _handle_insert_new_section_from_button_context_menu(self, after_slide_global_idx: int):
        # Placeholder - full implementation would mirror the old manager
        self.request_show_error_message_signal.emit("Insert new section from button context menu not fully implemented in new manager.")

    def invalidate_cache_for_section(self, section_id_to_invalidate: str):
        if not section_id_to_invalidate: return
        slides_to_check = self.presentation_manager.get_slides()
        instance_ids_to_invalidate = [s.id for s in slides_to_check if s.section_id_in_manifest == section_id_to_invalidate]
        invalidated_count = 0
        for instance_id in instance_ids_to_invalidate:
            if instance_id in self.preview_pixmap_cache:
                del self.preview_pixmap_cache[instance_id]
                invalidated_count += 1
        logging.info(f"SlideUIManager: Invalidated {invalidated_count} cached previews for section '{section_id_to_invalidate}'.")

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
