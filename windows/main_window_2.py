import sys
import os
import uuid
import json
import copy
import time
import logging
from typing import Optional, List, Dict, Any, Set

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QVBoxLayout, QWidget,
    QPushButton, QInputDialog, QSpinBox, QLabel, QHBoxLayout, QSplitter,
    QScrollArea, QDialog, QDockWidget, QMenuBar, QMenu, QFrame
)
from PySide6.QtGui import (
    QScreen, QPixmap, QColor, QContextMenuEvent, QDragEnterEvent, QDragMoveEvent,
    QDragLeaveEvent, QDropEvent, QImage, QAction, QCursor, QActionGroup
)
from PySide6.QtCore import (
    Qt, QSize, Slot, QTimer, Signal, QObject, QEvent, QStandardPaths, QPoint, QRect, QMimeData, QByteArray
)

# --- Dynamic Path Setup ---
try:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming this file is in 'windows', this moves to the project root
    project_root = os.path.dirname(current_script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"Warning: Could not automatically set up project path. Imports might fail. Error: {e}", file=sys.stderr)


# --- UI and New Architecture Imports ---
from windows.main_window_ui import Ui_MainWindow # Import the generated UI class
from core.output_manager import OutputManager # Using new OutputManager
from core.slide_ui_manager_2 import SlideUIManager as SlideUIManager_2 # Using new SlideUIManager

# --- Existing Application Component Imports (from original main_window.py) ---
from windows.output_window import OutputWindow
from data_models.slide_data import SlideData
from core.presentation_manager import PresentationManager
from core.template_manager import TemplateManager
from core.app_config_manager import ApplicationConfigManager
from core.slide_edit_handler import SlideEditHandler
from core.image_cache_manager import ImageCacheManager
from widgets.section_management_panel import SectionManagementPanel
from dialogs.template_remapping_dialog import TemplateRemappingDialog
from windows.settings_window import SettingsWindow
from windows.template_editor_window import TemplateEditorWindow
from windows.resource_manager_window import ResourceManagerWindow
from core.section_factory import SectionFactory
from commands.slide_commands import (
    ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand,
    AddSlideBlockToSectionCommand
)
import decklink_handler

# --- Configuration & Constants ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
SCRIPT_DIR_MW = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_MW = os.path.dirname(SCRIPT_DIR_MW)
BENCHMARK_TEMP_DIR_MW = os.path.join(PROJECT_ROOT_MW, "temp")
BENCHMARK_HISTORY_FILE_PATH_MW = os.path.join(BENCHMARK_TEMP_DIR_MW, ".pluckybenches.json")


class MouseHoverDebugger(QObject):
    """A debug utility to print information about the widget under the mouse cursor."""
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            widget = QApplication.widgetAt(QCursor.pos())
            if widget:
                logging.debug(f"Mouse Hover: {widget.__class__.__name__} (ObjectName: '{widget.objectName()}')")
        return super().eventFilter(watched, event)

class MainWindow(QMainWindow, Ui_MainWindow):
    """
    The main application window, combining the UI definition from main_window_ui.py
    with the application logic and the new Preview/Program architecture.
    """
    def __init__(self):
        super().__init__()
        # setupUi is defined in main_window_ui.py and populates the window with widgets
        self.setupUi(self)
        self.setWindowTitle("Plucky Presentation (Redesigned)")

        # --- Core Application Components ---
        self.config_manager = ApplicationConfigManager(self)
        self.template_manager = TemplateManager()
        self.presentation_manager = PresentationManager(self.template_manager)
        self.slide_edit_handler = SlideEditHandler(self.presentation_manager, self)
        self.image_cache_manager = ImageCacheManager()

        # --- New Architecture Setup ---
        self.output_manager = OutputManager(self)

        # --- UI Windows ---
        self.output_window = OutputWindow()
        self._resource_manager_window_instance = None
        self._open_editor_windows = []

        # --- State Tracking ---
        self.active_background_slide: Optional[SlideData] = None
        self.active_content_slide: Optional[SlideData] = None
        self.is_decklink_output_active = False
        self.hover_debugger_instance: Optional[MouseHoverDebugger] = None

        # --- Drop Indicator for Drag & Drop ---
        self.drop_indicator = QFrame(self.slide_buttons_widget)
        self.drop_indicator.setFrameShape(QFrame.Shape.HLine)
        self.drop_indicator.setStyleSheet("QFrame { border: 2px solid #00A0F0; }")
        self.drop_indicator.setFixedHeight(4)
        self.drop_indicator.hide()

        # --- Slide UI Manager ---
        # Note: Using the provided SlideUIManager_2 from the new architecture
        self.slide_ui_manager = SlideUIManager_2(
            presentation_manager=self.presentation_manager,
            template_manager=self.template_manager,
            renderer=self.output_manager.renderer, # Pass the new renderer
            slide_edit_handler=self.slide_edit_handler,
            config_manager=self.config_manager,
            output_window_ref=self.output_window,
            scroll_area=self.scroll_area,
            slide_buttons_widget=self.slide_buttons_widget,
            slide_buttons_layout=self.slide_buttons_layout,
            drop_indicator=self.drop_indicator,
            parent_main_window=self
        )

        # --- Section Management Panel ---
        # Note: The DockWidget is named 'SectionManagementDock' in the UI file
        self.section_management_panel = SectionManagementPanel(self.presentation_manager, self)
        self.SectionManagementDock.setWidget(self.section_management_panel)
        self.SectionManagementDock.hide()

        # --- Initialize Button States ---
        self.go_live_button.setCheckable(True)
        self.go_live_button.setChecked(False) # Start in OFF state

        # --- Final Setup ---
        self._connect_signals()
        self._init_benchmarking()
        self.output_manager.clear_all()
        self.slide_ui_manager.refresh_slide_display()
        self._update_dirty_indicator()
        self.setAcceptDrops(True) # Enable Drag & Drop
        self._update_go_live_button_appearance() # Set initial appearance for go_live_button
        self.statusBar().showMessage("Ready")

    def _init_benchmarking(self):
        """Initializes the benchmark data store."""
        self.benchmark_data_store = {
            "app_init": 0.0,
            "mw_init": 0.0,
            "mw_show": 0.0,
            "last_presentation_path": "None",
            "last_presentation_pm_load": 0.0,
            "last_presentation_ui_update": 0.0,  # Ensure this key exists
            "last_presentation_render_total": 0.0,
            "last_presentation_render_images": 0.0,
            "last_presentation_render_fonts": 0.0,
            "last_presentation_render_layout": 0.0,
            "last_presentation_render_draw": 0.0,
        }
        self._app_start_time = QApplication.instance().property("app_start_time")

    def _connect_signals(self):
        """Connects all application signals to their slots."""
        # --- Output Manager -> UI ---
        self.output_manager.program.pixmap_updated.connect(self.output_window.set_pixmap)
        self.output_manager.program.pixmap_updated.connect(self._handle_decklink_frame)

        # --- UI Buttons -> Handlers ---
        self.go_live_button.clicked.connect(self.handle_take) # The 'Output' circle button
        self.decklink_output_toggle_button.toggled.connect(self.toggle_decklink_output_stream)
        self.undo_button.clicked.connect(self.handle_undo)
        self.redo_button.clicked.connect(self.handle_redo)
        self.edit_template_button.clicked.connect(self.handle_edit_template)
        self.preview_size_spinbox.valueChanged.connect(self.handle_preview_size_change)

        # --- Menu Actions -> Handlers ---
        self.actionNew.triggered.connect(self.handle_new)
        self.actionLoad.triggered.connect(lambda: self.handle_load(filepath=None))
        self.actionSave.triggered.connect(self.handle_save)
        self.actionSave_As.triggered.connect(self.handle_save_as)
        self.actionUndo.triggered.connect(self.handle_undo)
        self.actionRedo.triggered.connect(self.handle_redo)
        self.actionGo_Live.triggered.connect(self.handle_take)
        self.actionAdd_New_Section.triggered.connect(self.handle_add_new_section)
        self.actionSection_Manager_VMenu.triggered.connect(self._toggle_section_manager_panel)
        self.actionSection_Manager_PMenu.triggered.connect(self._toggle_section_manager_panel)
        self.actionOpen_Settings.triggered.connect(self.handle_open_settings)
        self.actionResource_Manager.triggered.connect(self.handle_open_resource_manager)
        self.actionEnable_Hover_Debug.toggled.connect(self._toggle_hover_debugger)
        self.actionRun_Compositing_Test.triggered.connect(self._run_compositing_pipeline_test)
        self.actionShow_Environment_Variables.triggered.connect(self._show_environment_variables)

        # --- Core Components -> UI/Handlers ---
        self.presentation_manager.presentation_changed.connect(self.slide_ui_manager.refresh_slide_display)
        self.presentation_manager.presentation_changed.connect(self._update_dirty_indicator)
        self.presentation_manager.error_occurred.connect(self.show_error_message)
        self.slide_ui_manager.active_slide_changed_signal.connect(self._handle_active_slide_changed)
        self.config_manager.recent_files_updated.connect(self._update_recent_files_menu)

        # --- Slide Context Menu & Edit Signals ---
        self.slide_ui_manager.request_delete_slide.connect(self.handle_delete_slide_requested)
        self.slide_ui_manager.request_apply_template.connect(self.handle_apply_template_to_slide)
        self.slide_ui_manager.request_rename_section_dialog.connect(self.handle_rename_section_dialog)
        self.slide_ui_manager.request_open_section_editor.connect(self._open_section_editor_window)

        # --- Section Manager Panel -> Handlers ---
        self.section_management_panel.request_reorder_section.connect(self._handle_request_reorder_section)
        self.section_management_panel.request_remove_section.connect(self._handle_request_remove_section)
        self.section_management_panel.request_add_existing_section.connect(self._handle_request_add_existing_section)
        self.section_management_panel.request_create_new_section.connect(self._handle_request_create_new_section_from_panel)
        self.presentation_manager.presentation_changed.connect(self.section_management_panel.refresh_sections_list)

    # --- Scene Building (New Architecture) ---

    def _build_scene_from_active_slides(self) -> Dict[str, Any]:
        """Creates a 'Scene' dictionary for the renderer from the current active slides."""
        scene_width, scene_height = (1920, 1080) # Or get from settings
        scene = {"width": scene_width, "height": scene_height, "layers": []}

        if self.active_background_slide:
            scene['layers'].extend(self._convert_slidedata_to_layers(self.active_background_slide))

        if self.active_content_slide and self.active_content_slide != self.active_background_slide:
            scene['layers'].extend(self._convert_slidedata_to_layers(self.active_content_slide))

        return scene

    def _convert_slidedata_to_layers(self, slide: SlideData) -> List[Dict[str, Any]]:
        """Translates a single SlideData object into a list of Layer dictionaries."""
        layers = []
        if slide.background_color and slide.background_color != "#00000000":
            layers.append({"id": f"{slide.id}_bgcolor", "type": "solid_color", "properties": {"color": slide.background_color}})
        if slide.background_image_path and os.path.exists(slide.background_image_path):
            layers.append({"id": f"{slide.id}_bgimage", "type": "image", "properties": {"path": slide.background_image_path, "scaling_mode": "fill"}})
        if slide.video_path and os.path.exists(slide.video_path):
            layers.append({"id": f"{slide.id}_video", "type": "video", "position": {"x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100}, "properties": {"path": slide.video_path, "loop": True, "scaling_mode": "fit"}})
        template = slide.template_settings or {}
        text_boxes = template.get("text_boxes", [])
        text_content = template.get("text_content", {})
        for box in text_boxes:
            box_id = box.get("id")
            content = text_content.get(box_id, "")
            if box_id and content:
                layers.append({
                    "id": f"{slide.id}_{box_id}", "type": "text",
                    "position": {"x_pc": box.get("x_pc", 0), "y_pc": box.get("y_pc", 0), "width_pc": box.get("width_pc", 100), "height_pc": box.get("height_pc", 100)},
                    "properties": {
                        "content": content, "font_family": box.get("font_family", "Arial"), "font_size": box.get("font_size", 48),
                        "font_color": box.get("font_color", "#FFFFFF"), "h_align": box.get("h_align", "center"),
                        "v_align": box.get("v_align", "center"), "shadow": box.get("shadow", {}), "outline": box.get("outline", {})
                    }
                })
        return layers

    # --- Major Action Handlers ---

    @Slot()
    def handle_take(self):
        """
        Handles the 'TAKE' (Go Live) button click.
        If the button is now checked (ON state): Shows the output window and takes Preview to Program.
        If the button is now unchecked (OFF state): Hides the output window.
        """
        if self.go_live_button.isChecked():  # Button is now ON
            logging.info("TAKE button: Output ON. Showing window and performing TAKE.")
            target_screen = self.config_manager.get_target_output_screen()
            if target_screen:
                if not self.output_window.isVisible():
                    self.output_window.setGeometry(target_screen.geometry())
                    self.output_window.showFullScreen()
                self.output_manager.take()  # Perform Preview -> Program
            else:
                QMessageBox.warning(self, "No Output Selected", "Please select an output monitor in Settings.")
                self.go_live_button.setChecked(False)  # Revert button state as action failed
        else:  # Button is now OFF
            logging.info("TAKE button: Output OFF. Hiding output window.")
            if self.output_window.isVisible():
                self.output_window.hide()
        self._update_go_live_button_appearance()

    @Slot(int)
    def _handle_active_slide_changed(self, slide_index: int):
        """Updates the active slides and sends the new scene to Preview."""
        slides = self.presentation_manager.get_slides()

        if slide_index == -1:
            self.active_content_slide = None
        elif 0 <= slide_index < len(slides):
            slide = slides[slide_index]
            if slide.is_background_slide:
                self.active_background_slide = slide
                self.active_content_slide = slide
            else:
                self.active_content_slide = slide
        else:
             self.active_content_slide = None

        logging.info(f"Active slide changed. BG: {self.active_background_slide.id if self.active_background_slide else 'None'}, Content: {self.active_content_slide.id if self.active_content_slide else 'None'}")
        scene = self._build_scene_from_active_slides()
        self.output_manager.update_preview(scene)

    @Slot()
    def handle_clear(self):
        """Clears selection and sends a blank scene to preview, which can then be taken."""
        logging.info("Clearing active slide selection.")
        self.slide_ui_manager.clear_selection()
        # _handle_active_slide_changed will be called with -1, clearing content
        self.active_content_slide = None
        scene = self._build_scene_from_active_slides() # Will have only background
        self.output_manager.update_preview(scene)

    # --- File Operations ---
    def handle_new(self):
        if self.presentation_manager.is_overall_dirty():
            if self._confirm_discard_changes() == QMessageBox.StandardButton.Cancel: return
        self.presentation_manager.clear_presentation()
        self.active_background_slide = None
        self.active_content_slide = None
        self.output_manager.clear_all()
        self.slide_ui_manager.clear_selection()
        self.setWindowTitle("Plucky Presentation - New Presentation")

    def handle_load(self, filepath: Optional[str] = None):
        if self.presentation_manager.is_overall_dirty():
            if self._confirm_discard_changes() == QMessageBox.StandardButton.Cancel: return

        if not filepath:
            default_path = self.config_manager.get_default_presentations_path()
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Presentation", default_path, "Plucky Presentation Files (*.plucky_pres)")

        if filepath:
            self.presentation_manager.load_presentation(filepath)
            self.setWindowTitle(f"Plucky - {os.path.basename(filepath)}")
            self.active_background_slide = None
            self.active_content_slide = None
            self.output_manager.clear_all()
            self.config_manager.add_recent_file(filepath)

    def handle_save(self) -> bool:
        if not self.presentation_manager.current_manifest_filepath:
            return self.handle_save_as()
        if self.presentation_manager.save_presentation():
            self.statusBar().showMessage(f"Saved to {os.path.basename(self.presentation_manager.current_manifest_filepath)}", 3000)
            return True
        return False

    def handle_save_as(self) -> bool:
        default_path = self.config_manager.get_default_presentations_path()
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Presentation As...", default_path, "Plucky Presentation Files (*.plucky_pres)")
        if filepath:
            if self.presentation_manager.save_presentation_as(filepath):
                self.setWindowTitle(f"Plucky - {os.path.basename(filepath)}")
                self.config_manager.add_recent_file(filepath)
                self.statusBar().showMessage(f"Saved as {os.path.basename(filepath)}", 3000)
                return True
        return False

    def _confirm_discard_changes(self):
        return QMessageBox.question(self, 'Unsaved Changes', "You have unsaved changes. Save before continuing?",
                                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                    QMessageBox.StandardButton.Save)

    # --- Undo / Redo ---
    def handle_undo(self): self.presentation_manager.undo()
    def handle_redo(self): self.presentation_manager.redo()

    # --- UI and Window Management ---
    def handle_open_settings(self):
        # Get current settings from config_manager to pass to SettingsWindow
        current_target_screen = self.config_manager.get_target_output_screen()
        decklink_fill_idx = self.config_manager.get_app_setting("decklink_fill_device_index", 0)
        decklink_key_idx = self.config_manager.get_app_setting("decklink_key_device_index", 2)
        decklink_video_mode = self.config_manager.get_app_setting("decklink_video_mode_details", None)

        settings_dialog = SettingsWindow(
            benchmark_data=self.benchmark_data_store,
            current_output_screen=current_target_screen,
            current_decklink_fill_index=decklink_fill_idx,
            current_decklink_key_index=decklink_key_idx,
            current_decklink_video_mode=decklink_video_mode,
            config_manager=self.config_manager,
            template_manager=self.template_manager,
            parent=self
        )
        # Connect signals from SettingsWindow to update MainWindow's state if dialog is accepted
        # Note: SettingsWindow now saves to config_manager directly on accept.
        # These signals are for MainWindow to update its *internal attributes* if they are used elsewhere.
        settings_dialog.output_monitor_config_updated.connect(self._handle_monitor_setting_accepted)
        settings_dialog.decklink_config_updated.connect(self._handle_decklink_settings_accepted)
        # production_mode_changed_signal can be connected here if MainWindow needs to react immediately
        # settings_dialog.production_mode_changed_signal.connect(self._handle_production_mode_setting_changed_from_settings)

        settings_dialog.exec()

    def handle_edit_template(self):
        editor = TemplateEditorWindow(all_templates=self.template_manager.get_all_templates(), parent=self)
        if editor.exec() == QDialog.Code.Accepted:
            self.template_manager.update_from_collection(editor.get_updated_templates())
            self.slide_ui_manager.refresh_slide_display() # Refresh to show new template options

    def handle_open_resource_manager(self):
        if self._resource_manager_window_instance is None:
            self._resource_manager_window_instance = ResourceManagerWindow(
                presentation_manager=self.presentation_manager,
                image_cache_manager=self.image_cache_manager,
                parent=self
            )
        self._resource_manager_window_instance.exec()

    def handle_preview_size_change(self, value: int):
        if self.slide_ui_manager:
            self.slide_ui_manager.set_preview_scale_factor(float(value))

    def _toggle_section_manager_panel(self):
        self.SectionManagementDock.setVisible(not self.SectionManagementDock.isVisible())

    def _update_dirty_indicator(self):
        is_dirty = self.presentation_manager.is_overall_dirty()
        style = "background-color: red; border-radius: 8px;" if is_dirty else "background-color: #4CAF50; border-radius: 8px;"
        tooltip = "Presentation has unsaved changes." if is_dirty else "No unsaved changes."
        self.dirty_indicator_label.setStyleSheet(style)
        self.dirty_indicator_label.setToolTip(tooltip)
        # Ensure visibility is also updated based on dirty state, not just color/tooltip
        # This was previously missing and only handled in the debug toggle.
        self.dirty_indicator_label.setVisible(is_dirty)

    def _update_recent_files_menu(self):
        self.recent_files_menu.clear()
        recent_files = self.config_manager.get_recent_files()
        if not recent_files:
            self.recent_files_menu.setEnabled(False)
            return
        self.recent_files_menu.setEnabled(True)
        for f in recent_files:
            action = self.recent_files_menu.addAction(os.path.basename(f))
            action.triggered.connect(lambda checked, path=f: self.handle_load(filepath=path))

    def _update_go_live_button_appearance(self):
        if self.go_live_button.isChecked():
            self.go_live_button.setToolTip("Screen Output is LIVE. Click to turn OFF.")
            self.go_live_button.setStyleSheet("QPushButton { background-color: red; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #FF4C4C; }")
        else:
            self.go_live_button.setToolTip("Screen Output is OFF. Click to TAKE Preview to Program and turn ON.")
            self.go_live_button.setStyleSheet("QPushButton { background-color: #ffd1d1; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: ##ffd1d1; }") # Original "TAKE" style

    def show_error_message(self, msg: str): QMessageBox.critical(self, "Error", msg)

    # --- Slots for SettingsWindow accepted signals ---
    @Slot(QScreen)
    def _handle_monitor_setting_accepted(self, screen: QScreen):
        # MainWindow's config_manager is already updated by SettingsWindow.
        # This slot is for MainWindow to update its own internal state if needed,
        # or react (e.g., if live output needs to change monitor immediately).
        # For now, we'll just log. MainWindow.toggle_live() re-reads from config.
        logging.info(f"MainWindow: Monitor setting accepted and saved by SettingsWindow: {screen.name() if screen else 'None'}")

    @Slot(int, int, dict)
    def _handle_decklink_settings_accepted(self, fill_idx: int, key_idx: int, video_mode: Optional[dict]):
        # MainWindow updates its internal attributes based on the accepted settings.
        self.decklink_fill_device_idx = fill_idx
        self.decklink_key_device_idx = key_idx
        self.current_decklink_video_mode_details = video_mode
        logging.info(f"MainWindow: DeckLink settings accepted and saved by SettingsWindow - Fill: {fill_idx}, Key: {key_idx}, Mode: {video_mode.get('name', 'None') if video_mode else 'None'}")
        # If DeckLink output is active, inform user to restart it.
        if self.is_decklink_output_active:
            self.show_error_message("DeckLink settings changed. Please toggle DeckLink output OFF and ON to apply the new settings.")

    # --- DeckLink ---
    @Slot(bool)
    def toggle_decklink_output_stream(self, checked: bool):
        if checked:
            fill_idx = self.config_manager.get_app_setting("decklink_fill_device_index", 0)
            key_idx = self.config_manager.get_app_setting("decklink_key_device_index", 2)
            mode = self.config_manager.get_app_setting("decklink_video_mode_details", None)
            if decklink_handler.initialize_sdk() and decklink_handler.initialize_selected_devices(fill_idx, key_idx, mode):
                self.is_decklink_output_active = True
                self.decklink_output_toggle_button.setStyleSheet("background-color: #4CAF50; border-radius: 12px;")
                self._handle_decklink_frame(self.output_manager.program.get_current_pixmap())
            else:
                self.show_error_message("Failed to initialize DeckLink.")
                self.decklink_output_toggle_button.setChecked(False)
        else:
            if self.is_decklink_output_active:
                decklink_handler.shutdown_selected_devices()
                decklink_handler.shutdown_sdk()
            self.is_decklink_output_active = False
            self.decklink_output_toggle_button.setStyleSheet("")

    @Slot(QPixmap)
    def _handle_decklink_frame(self, pixmap: QPixmap):
        if not self.is_decklink_output_active or pixmap.isNull(): return
        key_matte = self.output_manager.program._generate_key_matte()
        if key_matte.isNull(): return
        fill_bytes = decklink_handler.get_image_bytes_from_qimage(pixmap.toImage())
        key_bytes = decklink_handler.get_image_bytes_from_qimage(key_matte.toImage())
        if not (fill_bytes and key_bytes) or not decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
            logging.error("Failed to send frame to DeckLink.")

    # --- Slide/Section Manipulation Handlers ---
    @Slot(int)
    def handle_delete_slide_requested(self, slide_index: int):
        slides = self.presentation_manager.get_slides()
        indices = self.slide_ui_manager.get_selected_slide_indices()
        if slide_index not in indices or len(indices) <= 1:
            indices = [slide_index]
        reply = QMessageBox.question(self, 'Delete Slide(s)', f"Are you sure you want to delete {len(indices)} slide(s)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for idx in sorted(indices, reverse=True):
                if 0 <= idx < len(slides):
                    self.presentation_manager.do_command(DeleteSlideCommand(self.presentation_manager, slides[idx].id))

    @Slot(int, str)
    def handle_apply_template_to_slide(self, slide_index: int, template_name: str):
        # A full implementation requires the remapping dialog logic from original main_window.py
        slide_data = self.presentation_manager.get_slides()[slide_index]
        old_name = slide_data.template_settings.get('layout_name') if slide_data.template_settings else None
        old_content = slide_data.template_settings.get('text_content', {}) if slide_data.template_settings else {}
        cmd = ApplyTemplateCommand(self.presentation_manager, slide_data.id, old_name, template_name, old_content, {})
        self.presentation_manager.do_command(cmd)

    @Slot()
    def handle_add_new_section(self):
        title, ok = QInputDialog.getText(self, "Add New Section", "Enter the title for the new section:")
        if ok and title:
            # Simplified version of original logic
            section_data = SectionFactory.create_new_section_data(title=title)
            # This would need the full save/add logic from original file...
            # self.presentation_manager.add_section_to_presentation(...)
            self.statusBar().showMessage(f"Section '{title}' created (logic to add is placeholder).", 3000)

    @Slot(str)
    def _open_section_editor_window(self, section_id_in_manifest: str):
        self.show_error_message(f"Feature 'Section Editor' not fully ported yet for section {section_id_in_manifest}.")

    @Slot(str)
    def handle_rename_section_dialog(self, section_id_in_manifest: str):
        self.show_error_message(f"Feature 'Rename Section' not fully ported yet for section {section_id_in_manifest}.")

    # --- Section Panel Handlers (Placeholders) ---
    @Slot(str, int)
    def _handle_request_reorder_section(self, section_id, direction): self.show_error_message("Reorder not fully ported")
    @Slot(str)
    def _handle_request_remove_section(self, section_id): self.show_error_message("Remove not fully ported")
    @Slot()
    def _handle_request_add_existing_section(self): self.show_error_message("Add Existing not fully ported")
    @Slot()
    def _handle_request_create_new_section_from_panel(self): self.handle_add_new_section()

    # --- Event Handlers ---
    def closeEvent(self, event):
        reply = self.handle_save() if self.presentation_manager.is_overall_dirty() else True
        if not reply:
            confirm_close = self._confirm_discard_changes()
            if confirm_close == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        self.output_manager.cleanup()
        self.toggle_decklink_output_stream(False)
        self.output_window.close()
        self.config_manager.save_all_configs()
        state = self.saveState().toBase64().data().decode('utf-8')
        self.config_manager.set_app_setting("main_window_state", state)
        super().closeEvent(event)

    def showEvent(self, event):
        state = self.config_manager.get_app_setting("main_window_state")
        if state: self.restoreState(QByteArray.fromBase64(state.encode('utf-8')))
        self._update_recent_files_menu()
        super().showEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.slide_ui_manager and hasattr(self.slide_ui_manager, 'drag_drop_handler'):
            self.slide_ui_manager.drag_drop_handler.dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent):
        if self.slide_ui_manager and hasattr(self.slide_ui_manager, 'drag_drop_handler'):
            self.slide_ui_manager.drag_drop_handler.dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if self.slide_ui_manager and hasattr(self.slide_ui_manager, 'drag_drop_handler'):
            self.slide_ui_manager.drag_drop_handler.dropEvent(event)

    # --- Developer Tools ---
    @Slot(bool)
    def _toggle_hover_debugger(self, checked: bool):
        if checked and not self.hover_debugger_instance:
            self.hover_debugger_instance = MouseHoverDebugger(self)
            QApplication.instance().installEventFilter(self.hover_debugger_instance)
        elif not checked and self.hover_debugger_instance:
            QApplication.instance().removeEventFilter(self.hover_debugger_instance)
            self.hover_debugger_instance = None

    def _show_environment_variables(self):
        env_vars = "\n".join([f"{key}={value}" for key, value in os.environ.items()])
        QMessageBox.information(self, "Environment Variables", env_vars)

    def _run_compositing_pipeline_test(self):
        self._test_idx = 0
        self._test_scenes = [
            {"layers": [{"id": "bg", "type": "solid_color", "properties": {"color": "#FF0000"}}]},
            {"layers": [{"id": "bg", "type": "solid_color", "properties": {"color": "#00FF00"}}]},
            {"layers": [{"id": "bg", "type": "solid_color", "properties": {"color": "#0000FF"}},
                        {"id": "txt", "type": "text", "position": {"x_pc":10, "y_pc":40, "width_pc":80, "height_pc":20}, "properties": {"content": "Test"}}]}
        ]
        def next_test_slide():
            if self._test_idx < len(self._test_scenes):
                scene = {"width": 1920, "height": 1080, **self._test_scenes[self._test_idx]}
                self.output_manager.update_preview(scene)
                self.handle_take()
                self._test_idx += 1
                QTimer.singleShot(1500, next_test_slide)
            else:
                 QMessageBox.information(self, "Test Complete", "Compositing test finished.")
        next_test_slide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
