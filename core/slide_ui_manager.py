import sys
import os
import uuid
import copy
from PySide6.QtWidgets import ( # QWidget removed from this direct import list for SlideUIManager base
    QWidget, QVBoxLayout, QScrollArea, QLabel, QMenu, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QObject # QObject added
from PySide6.QtGui import QPixmap, QColor

try:
    from widgets.scaled_slide_button import ScaledSlideButton
    from widgets.song_header_widget import SongHeaderWidget
    from widgets.flow_layout import FlowLayout
    from core.presentation_manager import PresentationManager # Keep this
    from core.template_manager import TemplateManager # Keep this
    from rendering.slide_renderer import LayeredSlideRenderer # Changed to LayeredSlideRenderer
    from core.slide_edit_handler import SlideEditHandler
    from core.app_config_manager import ApplicationConfigManager
    from data_models.slide_data import SlideData
    from core.constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT
    from core.slide_drag_drop_handler import SlideDragDropHandler
    from commands.slide_commands import AddSlideBlockToSectionCommand
    from core.section_factory import SectionFactory # For inserting new sections

except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from widgets.scaled_slide_button import ScaledSlideButton
    from widgets.song_header_widget import SongHeaderWidget
    from widgets.flow_layout import FlowLayout
    from core.presentation_manager import PresentationManager # Keep this
    from core.template_manager import TemplateManager # Keep this
    from rendering.slide_renderer import LayeredSlideRenderer # Changed to LayeredSlideRenderer
    from core.slide_edit_handler import SlideEditHandler
    from core.app_config_manager import ApplicationConfigManager
    from data_models.slide_data import SlideData
    from core.constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT
    from core.slide_drag_drop_handler import SlideDragDropHandler
    from commands.slide_commands import AddSlideBlockToSectionCommand
    from core.section_factory import SectionFactory

BASE_PREVIEW_WIDTH = 160 # Keep consistent with MainWindow if not moved to constants

class SlideUIManager(QObject): # Changed base class from QWidget to QObject
    active_slide_changed_signal = Signal(int) # Emits the global index of the new active slide
    request_show_error_message_signal = Signal(str)
    request_set_status_message_signal = Signal(str, int)

    def __init__(self,
                 presentation_manager: PresentationManager,
                 template_manager: TemplateManager,
                 slide_renderer: 'LayeredSlideRenderer', # Changed type hint
                 slide_edit_handler: SlideEditHandler,
                 config_manager: ApplicationConfigManager,
                 output_window_ref, # To check if output is visible for render resolution
                 scroll_area: QScrollArea,
                 slide_buttons_widget: QWidget,
                 slide_buttons_layout: QVBoxLayout,
                 drop_indicator: QWidget,
                 parent_main_window, # For dialogs and accessing main window methods if needed
                 parent=None):
        super().__init__(parent)

        self.presentation_manager = presentation_manager
        self.template_manager = template_manager
        self.slide_renderer = slide_renderer
        self.slide_edit_handler = slide_edit_handler
        self.config_manager = config_manager
        self.output_window_ref = output_window_ref
        self.parent_main_window = parent_main_window

        # UI Elements managed by this class
        self.scroll_area = scroll_area
        self.slide_buttons_widget = slide_buttons_widget
        self.slide_buttons_layout = slide_buttons_layout # Main VBox in slide_buttons_widget
        self.drop_indicator = drop_indicator

        self.slide_buttons_list = []
        self.preview_pixmap_cache = {}
        self._selected_slide_indices = set()
        self.current_slide_index = -1 # Tracks the singly selected slide for output

        initial_preview_size = self.config_manager.get_app_setting("preview_size", 1)
        self.button_scale_factor = float(initial_preview_size)

        # Enable custom context menu for the slide_buttons_widget
        self.slide_buttons_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.slide_buttons_widget.customContextMenuRequested.connect(self._handle_slide_panel_custom_context_menu)

        # Install event filter on the QScrollArea for keyboard navigation
        self.scroll_area.installEventFilter(self)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Instantiate the SlideDragDropHandler
        self.drag_drop_handler = SlideDragDropHandler(
            main_window=self.parent_main_window, # DND handler might still need main_window for some global ops
            presentation_manager=self.presentation_manager,
            scroll_area=self.scroll_area,
            slide_buttons_widget=self.slide_buttons_widget,
            slide_buttons_layout=self.slide_buttons_layout,
            drop_indicator=self.drop_indicator,
            slide_ui_manager=self, # Pass self (the SlideUIManager instance)
            parent=self # QObject parent is SlideUIManager
        )

        # Connect to PresentationManager signals
        self.presentation_manager.presentation_changed.connect(self.refresh_slide_display)
        self.presentation_manager.slide_visual_property_changed.connect(self._handle_slide_visual_property_change)

    def set_preview_scale_factor(self, scale_factor: float):
        self.button_scale_factor = scale_factor
        self.config_manager.set_app_setting("preview_size", int(scale_factor))
        self.preview_pixmap_cache.clear()
        self.refresh_slide_display()

    def refresh_slide_display(self):
        print("SlideUIManager: refresh_slide_display called")
        old_single_selected_slide_id_str: str | None = None
        if self.current_slide_index != -1 and len(self._selected_slide_indices) == 1:
            slides_before_rebuild = self.presentation_manager.get_slides()
            if 0 <= self.current_slide_index < len(slides_before_rebuild):
                old_single_selected_slide_id_str = slides_before_rebuild[self.current_slide_index].id

        self._selected_slide_indices.clear()
        self.current_slide_index = -1

        while self.slide_buttons_layout.count():
            item = self.slide_buttons_layout.takeAt(0)
            widget_in_vbox = item.widget()
            if widget_in_vbox:
                if isinstance(widget_in_vbox.layout(), FlowLayout):
                    flow_layout_inside = widget_in_vbox.layout()
                    while flow_layout_inside.count():
                        flow_item = flow_layout_inside.takeAt(0)
                        slide_button_widget = flow_item.widget()
                        if slide_button_widget:
                            try: slide_button_widget.slide_selected.disconnect(self._handle_manual_slide_selection)
                            except (TypeError, RuntimeError): pass
                            try: slide_button_widget.toggle_selection_requested.disconnect(self._handle_toggle_selection)
                            except (TypeError, RuntimeError): pass
                widget_in_vbox.setParent(None)
                widget_in_vbox.deleteLater()
        self.slide_buttons_list.clear()

        slides = self.presentation_manager.get_slides()

        if not slides:
            no_slides_label = QLabel("No slides. Use 'File > Load' or 'Presentation > Add New Section'.")
            no_slides_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slide_buttons_layout.addWidget(no_slides_label)
            self.active_slide_changed_signal.emit(-1) # Signal no active slide
            return

        last_processed_title: object = object()
        current_song_flow_layout: FlowLayout | None = None
        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)

        for index, slide_data in enumerate(slides):
            current_title = slide_data.song_title
            if current_title != last_processed_title:
                last_processed_title = current_title
                if current_title is not None:
                    song_header = SongHeaderWidget(current_title, current_button_width=current_dynamic_preview_width)
                    # Connect song_header signals if needed (e.g., to MainWindow or PresentationManager via signals)
                    # song_header.edit_song_requested.connect(self.parent_main_window.handle_edit_song_title_requested)
                    self.slide_buttons_layout.addWidget(song_header)

                song_slides_container = QWidget()
                current_song_flow_layout = FlowLayout(song_slides_container, margin=5, hSpacing=5, vSpacing=5)
                self.slide_buttons_layout.addWidget(song_slides_container)

            preview_render_width = self.output_window_ref.width() if self.output_window_ref.isVisible() else 1920
            preview_render_height = self.output_window_ref.height() if self.output_window_ref.isVisible() else 1080
            slide_id_str = slide_data.id
            has_font_error = False

            if slide_id_str in self.preview_pixmap_cache:
                cached_pixmap = self.preview_pixmap_cache[slide_id_str]
                if cached_pixmap.width() == current_dynamic_preview_width and \
                   cached_pixmap.height() == current_dynamic_preview_height:
                    preview_pixmap = cached_pixmap
                else:
                    del self.preview_pixmap_cache[slide_id_str]
                    preview_pixmap = None
            else:
                preview_pixmap = None

            if preview_pixmap is None:
                try:
                    full_res_pixmap, has_font_error, _ = self.slide_renderer.render_slide(
                        slide_data, preview_render_width, preview_render_height, is_final_output=False
                    )
                    preview_pixmap = full_res_pixmap.scaled(current_dynamic_preview_width, current_dynamic_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.preview_pixmap_cache[slide_id_str] = preview_pixmap
                except Exception as e:
                    print(f"SlideUIManager: ERROR rendering preview for slide {index} (ID {slide_data.id}): {e}")
                    has_font_error = True
                    preview_pixmap = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height)
                    preview_pixmap.fill(Qt.GlobalColor.darkGray)

            button = ScaledSlideButton(
                slide_id=index, # Global index for UI list management
                instance_id=slide_data.id, # The unique instance ID for drag/data operations
                plucky_slide_mime_type=PLUCKY_SLIDE_MIME_TYPE
            )
            button.set_pixmap(preview_pixmap)
            button.set_icon_state("error", False)
            button.set_icon_state("warning", False)
            button.set_is_background_slide(slide_data.is_background_slide)
            current_label_for_banner = "BG" if slide_data.is_background_slide else ""
            button.set_slide_info(number=index + 1, label=current_label_for_banner)
            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")

            button.toggle_selection_requested.connect(self._handle_toggle_selection)
            button.slide_selected.connect(self._handle_manual_slide_selection)
            button.edit_requested.connect(self.slide_edit_handler.handle_edit_slide_requested)
            # Connect delete_requested to MainWindow's handler or emit a signal
            button.delete_requested.connect(self.parent_main_window.handle_delete_slide_requested)

            if hasattr(slide_data, 'banner_color') and slide_data.banner_color:
                button.set_banner_color(QColor(slide_data.banner_color))
            else:
                button.set_banner_color(None)

            layout_template_names_list = self.template_manager.get_layout_names()
            button.set_available_templates(layout_template_names_list)
            # Connect apply_template_to_slide_requested to MainWindow's handler
            button.apply_template_to_slide_requested.connect(self.parent_main_window.handle_apply_template_to_slide)
            button.insert_slide_from_layout_requested.connect(self._handle_insert_slide_from_button_context_menu)
            button.center_overlay_label_changed.connect(self.parent_main_window.handle_slide_overlay_label_changed)
            button.banner_color_change_requested.connect(self.parent_main_window.handle_banner_color_change_requested)
            button.insert_new_section_requested.connect(self._handle_insert_new_section_from_button_context_menu)

            if has_font_error:
                button.set_icon_state("error", True)

            if current_song_flow_layout:
                current_song_flow_layout.addWidget(button)
            self.slide_buttons_list.append(button)

        current_slide_ids = {s.id for s in slides}
        cached_ids_to_remove = [cached_id for cached_id in self.preview_pixmap_cache if cached_id not in current_slide_ids]
        for stale_id in cached_ids_to_remove:
            del self.preview_pixmap_cache[stale_id]

        self.slide_buttons_layout.addStretch(1)
        self._update_all_button_overlay_labels()

        new_single_selected_index = -1
        if old_single_selected_slide_id_str is not None:
            for index, slide_data in enumerate(slides):
                if slide_data.id == old_single_selected_slide_id_str:
                    new_single_selected_index = index
                    break

        if new_single_selected_index != -1:
            button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_single_selected_index), None)
            if button_to_select:
                self._selected_slide_indices.add(new_single_selected_index)
                self.current_slide_index = new_single_selected_index
                button_to_select.setChecked(True)
                self.active_slide_changed_signal.emit(new_single_selected_index)
                self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
            else:
                self.active_slide_changed_signal.emit(-1)
        elif slides:
            self._handle_manual_slide_selection(0) # This will emit active_slide_changed_signal
            if self.slide_buttons_list:
                self.scroll_area.ensureWidgetVisible(self.slide_buttons_list[0], 50, 50)
        else:
            self.active_slide_changed_signal.emit(-1)

    def _update_button_checked_states(self):
        for button_widget in self.slide_buttons_list:
            button_widget.setChecked(button_widget._slide_id in self._selected_slide_indices)

    def _handle_toggle_selection(self, slide_index: int):
        if slide_index in self._selected_slide_indices:
            self._selected_slide_indices.remove(slide_index)
        else:
            self._selected_slide_indices.add(slide_index)
        self._update_button_checked_states()

    def _handle_manual_slide_selection(self, selected_slide_index: int):
        self._selected_slide_indices.clear()
        self._selected_slide_indices.add(selected_slide_index)
        self.current_slide_index = selected_slide_index
        self._update_button_checked_states()
        self.active_slide_changed_signal.emit(selected_slide_index)
        self.scroll_area.setFocus()

    def _update_all_button_overlay_labels(self):
        slides = self.presentation_manager.get_slides()
        for index, slide_data in enumerate(slides):
            button = next((btn for btn in self.slide_buttons_list if btn._slide_id == index), None)
            if button and isinstance(button, ScaledSlideButton):
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

    def get_selected_slide_indices(self) -> list[int]:
        return list(self._selected_slide_indices)

    def _handle_slide_visual_property_change(self, updated_indices: list[int]):
        print(f"SlideUIManager: _handle_slide_visual_property_change for indices: {updated_indices}")
        # Get the fresh list of ALL SlideData objects ONCE before the loop.
        # This is crucial because PresentationManager.get_slides() rebuilds the list and its internal maps.
        all_current_slides_data = self.presentation_manager.get_slides()

        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)
        preview_render_width = self.output_window_ref.width() if self.output_window_ref.isVisible() else 1920
        preview_render_height = self.output_window_ref.height() if self.output_window_ref.isVisible() else 1080

        for index in updated_indices:
            if not (0 <= index < len(self.slide_buttons_list) and 0 <= index < len(all_current_slides_data)):
                print(f"SlideUIManager: Warning - Index {index} out of bounds for visual property change. Buttons: {len(self.slide_buttons_list)}, Slides: {len(all_current_slides_data)}")
                continue

            button = self.slide_buttons_list[index]
            slide_data = all_current_slides_data[index] # Use the fresh SlideData
            
            if not isinstance(button, ScaledSlideButton): # Should always be true, but good check
                button = self.slide_buttons_list[index]
                continue

            # Invalidate cache for this specific slide instance ID before re-rendering
            if slide_data.id in self.preview_pixmap_cache:
                del self.preview_pixmap_cache[slide_data.id]
                print(f"SlideUIManager: Invalidated cache for slide instance {slide_data.id} (global index {index})")

                try:
                    full_res_pixmap, has_font_error, _ = self.slide_renderer.render_slide(
                        slide_data, preview_render_width, preview_render_height, is_final_output=False
                    )
                    preview_pixmap = full_res_pixmap.scaled(
                        current_dynamic_preview_width, current_dynamic_preview_height,
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                    button.set_pixmap(preview_pixmap)
                    self.preview_pixmap_cache[slide_data.id] = preview_pixmap
                    button.set_icon_state("error", has_font_error)
                except Exception as e:
                    print(f"SlideUIManager: Error re-rendering preview for slide {index} in _handle_slide_visual_property_change: {e}")
                    error_preview = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height)
                    error_preview.fill(Qt.GlobalColor.magenta)
                    button.set_pixmap(error_preview)
                    button.set_icon_state("error", True)

                if hasattr(slide_data, 'banner_color'):
                    new_color = QColor(slide_data.banner_color) if slide_data.banner_color else None
                    button.set_banner_color(new_color)

                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)
                button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
                button.set_is_background_slide(slide_data.is_background_slide)
                current_label_for_banner = "BG" if slide_data.is_background_slide else ""
                button.set_slide_info(number=index + 1, label=current_label_for_banner)
                button.update()

                if self.current_slide_index == index: # If the updated slide is live
                    self.active_slide_changed_signal.emit(index) # Re-emit to trigger re-display

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
                elif current_selection_index == num_slides - 1: new_selection_index = 0
                else: return super().eventFilter(watched_object, event)
            elif key == Qt.Key_Left:
                if current_selection_index == -1 and num_slides > 0: new_selection_index = num_slides - 1
                elif current_selection_index > 0: new_selection_index = current_selection_index - 1
                elif current_selection_index == 0 and num_slides > 0: new_selection_index = num_slides - 1
                else: return super().eventFilter(watched_object, event)
            else:
                return super().eventFilter(watched_object, event)

            if new_selection_index != current_selection_index or \
               (current_selection_index == -1 and new_selection_index != -1):
                button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
                if button_to_select:
                    self._handle_manual_slide_selection(new_selection_index) # This emits signal
                    self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
                return True
        return super().eventFilter(watched_object, event)

    def _determine_insertion_context(self, global_pos: QPoint) -> dict:
        pos_in_slide_buttons_widget = self.slide_buttons_widget.mapFromGlobal(global_pos)
        slides = self.presentation_manager.get_slides()
        num_manifest_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0

        context = {
            "action_on_slide_instance_id": None,
            "target_section_id_for_slide_insert": None,
            "target_arrangement_name_for_slide_insert": None,
            "index_in_arrangement_for_slide_insert": 0,
            "manifest_index_for_new_section_insert": num_manifest_sections
        }

        if not slides:
            context["manifest_index_for_new_section_insert"] = 0
            return context

        clicked_widget = self.slide_buttons_widget.childAt(pos_in_slide_buttons_widget)
        widget_iterator = clicked_widget

        while widget_iterator and widget_iterator != self.slide_buttons_widget:
            if isinstance(widget_iterator, ScaledSlideButton):
                global_idx_clicked = widget_iterator._slide_id
                clicked_slide_data = slides[global_idx_clicked]
                instance_id = clicked_slide_data.id
                arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(instance_id)
                if arrangement_info:
                    context["action_on_slide_instance_id"] = instance_id
                    context["target_section_id_for_slide_insert"] = arrangement_info["section_id_in_manifest"]
                    context["target_arrangement_name_for_slide_insert"] = arrangement_info["arrangement_name"]
                    context["index_in_arrangement_for_slide_insert"] = arrangement_info["index_in_arrangement"] + 1
                    manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
                    for i, manifest_sec_entry in enumerate(manifest_sections):
                        if manifest_sec_entry["id"] == arrangement_info["section_id_in_manifest"]:
                            context["manifest_index_for_new_section_insert"] = i + 1
                            break
                return context

            if widget_iterator.parentWidget() == self.slide_buttons_widget:
                if isinstance(widget_iterator, SongHeaderWidget):
                    header_title = widget_iterator.get_song_title()
                    for slide_data_item in slides:
                        if slide_data_item.song_title == header_title:
                            instance_id = slide_data_item.id
                            arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(instance_id)
                            if arrangement_info:
                                context["target_section_id_for_slide_insert"] = arrangement_info["section_id_in_manifest"]
                                context["target_arrangement_name_for_slide_insert"] = arrangement_info["arrangement_name"]
                                context["index_in_arrangement_for_slide_insert"] = 0
                                manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
                                for i, manifest_sec_entry in enumerate(manifest_sections):
                                    if manifest_sec_entry["id"] == arrangement_info["section_id_in_manifest"]:
                                        context["manifest_index_for_new_section_insert"] = i + 1
                                        break
                            return context
                elif isinstance(widget_iterator.layout(), FlowLayout):
                    if widget_iterator.layout().count() > 0:
                        first_button_in_flow = widget_iterator.layout().itemAt(0).widget()
                        if isinstance(first_button_in_flow, ScaledSlideButton):
                            first_slide_data = slides[first_button_in_flow._slide_id]
                            instance_id = first_slide_data.id
                            arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(instance_id)
                            if arrangement_info:
                                context["target_section_id_for_slide_insert"] = arrangement_info["section_id_in_manifest"]
                                context["target_arrangement_name_for_slide_insert"] = arrangement_info["arrangement_name"]
                                arr_list = self.presentation_manager.loaded_sections[arrangement_info["section_id_in_manifest"]]["section_content_data"]["arrangements"][arrangement_info["arrangement_name"]]
                                context["index_in_arrangement_for_slide_insert"] = len(arr_list)
                                manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
                                for i, manifest_sec_entry in enumerate(manifest_sections):
                                    if manifest_sec_entry["id"] == arrangement_info["section_id_in_manifest"]:
                                        context["manifest_index_for_new_section_insert"] = i + 1
                                        break
                                return context
                return context
            widget_iterator = widget_iterator.parentWidget()
        return context # Fallback if click on empty area or unhandled widget

    def _handle_slide_panel_custom_context_menu(self, local_pos: QPoint):
        global_pos = self.slide_buttons_widget.mapToGlobal(local_pos)
        context = self._determine_insertion_context(global_pos)
        
        context_menu = QMenu(self.slide_buttons_widget) # Correct parent
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
            self._prompt_and_insert_new_section_action(manifest_idx)
        )
        context_menu.exec(global_pos)

    def _handle_insert_slide_from_layout_action(self, layout_name_to_apply: str,
                                                target_section_id_in_manifest: str,
                                                target_arrangement_name: str,
                                                insert_at_index_in_arrangement: int):
        resolved_template_settings = self.template_manager.resolve_layout_template(layout_name_to_apply)
        if not resolved_template_settings:
            self.request_show_error_message_signal.emit(f"Could not resolve layout template '{layout_name_to_apply}'. Cannot insert slide.")
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

    def _prompt_and_insert_new_section_action(self, manifest_insertion_index: int):
        # This method now belongs to SlideUIManager but needs to interact with MainWindow for QInputDialog
        # and SectionFactory. For simplicity, we'll call MainWindow's existing method.
        # A more decoupled way would be to emit a signal that MainWindow connects to.
        self.parent_main_window._prompt_and_insert_new_section(manifest_insertion_index)

    # --- Methods for ScaledSlideButton context menu actions (called from MainWindow) ---
    # These are slightly different from the panel background context menu actions

    def _handle_insert_slide_from_button_context_menu(self, after_slide_global_idx: int, layout_name: str):
        slides = self.presentation_manager.get_slides()
        if not (0 <= after_slide_global_idx < len(slides)):
            self.request_show_error_message_signal.emit(f"Cannot insert slide: Reference slide index {after_slide_global_idx} is invalid.")
            return

        clicked_slide_data = slides[after_slide_global_idx]
        instance_id_of_clicked_slide = clicked_slide_data.id
        arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(instance_id_of_clicked_slide)
        if not arrangement_info:
            self.request_show_error_message_signal.emit(f"Could not determine context for slide instance '{instance_id_of_clicked_slide}'.")
            return

        self._handle_insert_slide_from_layout_action(
            layout_name,
            arrangement_info["section_id_in_manifest"],
            arrangement_info["arrangement_name"],
            arrangement_info["index_in_arrangement"] + 1
        )

    def _handle_insert_new_section_from_button_context_menu(self, after_slide_global_idx: int):
        slides = self.presentation_manager.get_slides()
        if not (0 <= after_slide_global_idx < len(slides)):
            self.request_show_error_message_signal.emit(f"Cannot insert new section: Reference slide index {after_slide_global_idx} is invalid.")
            return

        # Determine the manifest index for the new section
        # It should be after the section containing 'after_slide_global_idx'
        clicked_slide_data = slides[after_slide_global_idx]
        instance_id = clicked_slide_data.id
        arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(instance_id)
        manifest_idx_for_new_section = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) # Default to end

        if arrangement_info:
            section_id_of_clicked = arrangement_info["section_id_in_manifest"]
            manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
            for i, sec_entry in enumerate(manifest_sections):
                if sec_entry["id"] == section_id_of_clicked:
                    manifest_idx_for_new_section = i + 1
                    break
        
        self._prompt_and_insert_new_section_action(manifest_idx_for_new_section)