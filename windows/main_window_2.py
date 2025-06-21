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
from core.plucky_standards import PluckyStandards # Added PluckyStandards import
from core.image_cache_manager import ImageCacheManager
from widgets.section_management_panel import SectionManagementPanel
# from dialogs.template_remapping_dialog import TemplateRemappingDialog # Not used in main_window_2.py directly yet
from windows.settings_window import SettingsWindow
from dialogs.template_remapping_dialog import TemplateRemappingDialog # Import the new dialog
from windows.template_editor_window import TemplateEditorWindow
from windows.template_pair_window import TemplatePairingWindow # Import TemplatePairingWindow
from windows.main_editor_window import MainEditorWindow, _open_editor_windows
from windows.resource_manager_window import ResourceManagerWindow
from core.section_factory import SectionFactory
from commands.slide_commands import (
    ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand,
    AddSlideBlockToSectionCommand
)
import decklink_handler # type: ignore

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
        self.output_manager.register_screen_output_window(self.output_window) # Register it
        # --- UI Windows ---
        self.output_window = OutputWindow()
        self._resource_manager_window_instance = None
        self._template_pairing_window_instance = None # To store the pairing window instance
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
        
        # --- DeckLink Error Indicator ---
        self.decklink_error_indicator_label = QLabel()
        self.decklink_error_indicator_label.setFixedSize(16, 16)
        self.decklink_error_indicator_label.setToolTip("DeckLink Status: OK")
        self.decklink_error_indicator_label.setStyleSheet("background-color: transparent; border-radius: 8px;")
        self.decklink_error_indicator_label.hide() # Hidden by default

        # --- Final Setup ---
        self._connect_signals()
        self._init_benchmarking()
        self.output_manager.clear_all()
        self.slide_ui_manager.refresh_slide_display()
        self._update_dirty_indicator()
        self.setAcceptDrops(True) # Enable Drag & Drop
        self.statusBar().addPermanentWidget(self.decklink_error_indicator_label)
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
        # Assuming OutputManager will have a direct signal for its program output pixmap
        self.output_manager.program_pixmap_updated.connect(self.output_window.set_pixmap)

        # --- UI Buttons -> Handlers ---
        self.go_live_button.clicked.connect(self.handle_take) # The 'Output' circle button
        self.decklink_output_toggle_button.toggled.connect(self.toggle_decklink_output_stream)
        self.undo_button.clicked.connect(self.handle_undo)
        self.redo_button.clicked.connect(self.handle_redo) # This was correct
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
        self.actionEdit_Templates.triggered.connect(self.handle_edit_template) # Connect new menu item
        self.actionTemplate_Pairing.triggered.connect(self.handle_template_pairing) # Connect new menu item
        self.actionShow_Environment_Variables.triggered.connect(self._show_environment_variables)

        # --- Core Components -> UI/Handlers ---
        self.presentation_manager.presentation_changed.connect(self.slide_ui_manager.refresh_slide_display)
        self.presentation_manager.presentation_changed.connect(self._update_dirty_indicator)
        self.presentation_manager.error_occurred.connect(self.show_error_message)
        self.output_manager.decklink_error_occurred.connect(self._handle_decklink_error_from_output_manager) # NEW: Connect DeckLink error signal
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

    # Methods _build_scene_from_active_slides and _convert_slidedata_to_layers are now moved to OutputManager.


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
            if not target_screen:
                QMessageBox.warning(self, "No Output Selected", "Please select an output monitor in Settings.")
                self.go_live_button.setChecked(False)  # Revert button state as action failed
                self._update_go_live_button_appearance() # Update button style
                return
            self.output_manager.set_screen_output_target_visibility(True, target_screen.geometry())
            self.output_manager.take()
        else:  # Button is now OFF
            logging.info("TAKE button: Output OFF. Hiding output window.")
            self.output_manager.set_screen_output_target_visibility(False)
            self.output_manager.clear_program() # Also clear program content when going off-air
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
        # Add detailed slide data logging
        if self.active_background_slide:
            logging.debug(f"  BG SlideData: {vars(self.active_background_slide)}")
        if self.active_content_slide:
            logging.debug(f"  Content SlideData: {vars(self.active_content_slide)}")

        # Delegate scene building and preview update to OutputManager
        self.output_manager.update_preview_slides(
            background_slide=self.active_background_slide,
            content_slide=self.active_content_slide
        )

    @Slot()
    def handle_clear(self):
        """Clears selection and sends a blank scene to preview, which can then be taken."""
        logging.info("Clearing active slide selection.")
        self.slide_ui_manager.clear_selection()
        self.active_content_slide = None # Explicitly clear here too
        self.output_manager.update_preview_slides(
            background_slide=self.active_background_slide, # Keep current background
            content_slide=None # Clear content
        )

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

    def _prompt_and_insert_new_section(self, manifest_insertion_index: int):
        """
        Prompts for a new section title, creates a new section file using SectionFactory,
        and adds it to the presentation manifest at the specified index.
        (Adapted from original main_window.py)
        """
        new_section_title_str, ok = QInputDialog.getText(
            self,
            "Create New Section",
            "Enter title for the new section (leave blank for an untitled section):",
            text=""
        )

        if ok:
            cleaned_section_title = new_section_title_str.strip()
            if not cleaned_section_title:
                cleaned_section_title = f"Untitled Section {uuid.uuid4().hex[:4]}"

            section_file_id = f"section_{uuid.uuid4().hex}"
            
            new_section_data = SectionFactory.create_new_section_data(
                title=cleaned_section_title,
                section_file_id=section_file_id,
                section_type="Generic" # Context menu is generic
            )
            # PluckyStandards is already imported
            central_sections_dir = PluckyStandards.get_sections_dir()
            
            full_filepath, section_filename = SectionFactory.save_new_section_file(
                new_section_data, cleaned_section_title, self.presentation_manager.io_handler, central_sections_dir
            )

            if full_filepath and section_filename:
                self.presentation_manager.add_section_to_presentation(
                    section_filename, manifest_insertion_index, desired_arrangement_name="Default"
                )
                self.statusBar().showMessage(f"New section '{cleaned_section_title}' created and added.", 3000)
            else:
                self.show_error_message(f"Failed to create and save new section '{cleaned_section_title}'.")

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

    def handle_template_pairing(self):
        """Opens the Template Pairing window."""
        if self._template_pairing_window_instance is None or not self._template_pairing_window_instance.isVisible():
            self._template_pairing_window_instance = TemplatePairingWindow(template_manager=self.template_manager, parent=None) # Changed parent to None
            self._template_pairing_window_instance.show()
        else:
            self._template_pairing_window_instance.activateWindow()

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
            self.go_live_button.setStyleSheet("QPushButton { background-color: #FF0000; color: white; font-weight: bold; border-radius: 12px; border: 2px solid #CC0000; } QPushButton:hover { background-color: #FF3333; }")
        else:
            self.go_live_button.setToolTip("Screen Output is OFF. Click to TAKE Preview to Program and turn ON.")
            self.go_live_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 12px; border: 2px solid #388E3C; } QPushButton:hover { background-color: #66BB6A; }")

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
            fill_idx = self.config_manager.get_app_setting("decklink_fill_device_index", 0) # Default 0
            key_idx = self.config_manager.get_app_setting("decklink_key_device_index", 2)  # Default 2
            mode_details = self.config_manager.get_app_setting("decklink_video_mode_details", None)

            # Delegate to OutputManager
            success = self.output_manager.enable_decklink_output(fill_idx, key_idx, mode_details)
            if success:
                self.is_decklink_output_active = True
                self.decklink_output_toggle_button.setStyleSheet("background-color: #4CAF50; border-radius: 12px;")
                # OutputManager will handle sending the current program frame when its DeckLink target becomes active
            else:
                self.show_error_message("Failed to initialize DeckLink output via OutputManager.")
                self.decklink_output_toggle_button.setChecked(False)
                self.is_decklink_output_active = False # Ensure state is correct
                self.decklink_output_toggle_button.setStyleSheet("") # Revert style
        else:
            # Delegate to OutputManager
            self.output_manager.disable_decklink_output()
            self.is_decklink_output_active = False
            self.decklink_output_toggle_button.setStyleSheet("")
            logging.info("MainWindow: DeckLink output stream stopped.")

    # This method will be removed as its logic moves to OutputManager's DeckLinkTarget
    # @Slot(QPixmap)
    # def _handle_decklink_frame(self, pixmap: QPixmap):
    #     pass # Logic moved to OutputManager
    
    @Slot(str)
    def _handle_decklink_error_from_output_manager(self, error_message: str):
        """Handles DeckLink errors reported by OutputManager and updates the status bar icon."""
        if error_message:
            # An error occurred
            self.decklink_error_indicator_label.setStyleSheet("background-color: red; border-radius: 8px; border: 1px solid darkred;")
            self.decklink_error_indicator_label.setToolTip(f"DeckLink Error: {error_message}")
            self.decklink_error_indicator_label.show()
            logging.error(f"MainWindow: DeckLink error received: {error_message}")
        else:
            # This can be called with an empty string to clear the error state
            self.decklink_error_indicator_label.setStyleSheet("background-color: transparent; border-radius: 8px;")
            self.decklink_error_indicator_label.setToolTip("DeckLink Status: OK")
            self.decklink_error_indicator_label.hide()
            logging.info("MainWindow: DeckLink error state cleared.")

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
        """
        Applies a named layout template to the selected slide(s), handling text content remapping.
        """
        logging.info(f"MainWindow: handle_apply_template_to_slide called for slide_index: {slide_index}, template_name: '{template_name}'")

        if not hasattr(self.template_manager, 'resolve_layout_template'):
            self.show_error_message("Error: Template system (resolve_layout_template) is not available.")
            return

        new_layout_structure = self.template_manager.resolve_layout_template(template_name)
        if not new_layout_structure:
            self.show_error_message(f"Could not resolve Layout Template '{template_name}'.")
            return
        
        if not new_layout_structure.get("text_boxes"):
            self.show_error_message(f"Layout Template '{template_name}' defines no text boxes. Cannot apply.")
            return

        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot apply template: Slide index {slide_index} is invalid.")
            return
        
        target_slide_data_for_command = slides[slide_index]
        instance_id_for_command = target_slide_data_for_command.id

        selected_indices_to_apply = self.slide_ui_manager.get_selected_slide_indices()
        if not selected_indices_to_apply or slide_index not in selected_indices_to_apply:
            selected_indices_to_apply = [slide_index]

        new_tb_ids = [tb.get("id") for tb in new_layout_structure.get("text_boxes", []) if tb.get("id")]
        if not new_tb_ids:
             self.show_error_message(f"Layout Template '{template_name}' has text box entries but no valid IDs. Cannot apply lyrics.")
             return

        # --- Multi-Slide Application ---
        if len(selected_indices_to_apply) > 1:
            first_slide_data_for_check = slides[selected_indices_to_apply[0]]
            expected_layout_name = first_slide_data_for_check.template_settings.get('layout_name') \
                                   if first_slide_data_for_check.template_settings else None

            all_slides_share_layout = True
            for i in range(1, len(selected_indices_to_apply)):
                current_slide_data_for_check = slides[selected_indices_to_apply[i]]
                current_layout_name = current_slide_data_for_check.template_settings.get('layout_name') \
                                      if current_slide_data_for_check.template_settings else None
                if current_layout_name != expected_layout_name:
                    all_slides_share_layout = False
                    break
            
            if not all_slides_share_layout:
                QMessageBox.warning(self, "Mixed Layouts",
                                    "Cannot apply template to multiple slides that have different current layouts.\n"
                                    "Please select slides that already share the same layout template, or apply individually.")
                return

            first_selected_slide_data = slides[selected_indices_to_apply[0]]
            old_settings_first_slide = first_selected_slide_data.template_settings
            old_text_content_for_dialog_multi = {}
            if old_settings_first_slide and isinstance(old_settings_first_slide.get("text_content"), dict):
                old_text_content_for_dialog_multi = old_settings_first_slide["text_content"]
            elif first_selected_slide_data.lyrics:
                old_text_content_for_dialog_multi = {"legacy_lyrics": first_selected_slide_data.lyrics}

            old_tb_ids_set_multi = set(old_text_content_for_dialog_multi.keys())
            new_tb_ids_set = set(new_tb_ids)

            show_remapping_dialog_multi = False
            user_mapping_from_dialog = None

            if old_text_content_for_dialog_multi:
                if old_tb_ids_set_multi != new_tb_ids_set:
                    show_remapping_dialog_multi = True
            
            if show_remapping_dialog_multi:
                logging.debug(f"MainWindow: Multi-slide - Showing TemplateRemappingDialog based on first selected slide.")
                remapping_dialog = TemplateRemappingDialog(old_text_content_for_dialog_multi, new_tb_ids, self)
                if remapping_dialog.exec():
                    user_mapping_from_dialog = remapping_dialog.get_remapping()
                else:
                    QMessageBox.information(self, "Template Change Cancelled", "Template application was cancelled for multiple slides.")
                    return

            for idx_to_apply in selected_indices_to_apply:
                if not (0 <= idx_to_apply < len(slides)):
                    logging.warning(f"MW Warning: Skipping slide index {idx_to_apply} in multi-apply as it's out of bounds.")
                    continue
                
                slide_data_to_apply = slides[idx_to_apply]
                current_instance_id = slide_data_to_apply.id
                old_template_id_for_cmd = slide_data_to_apply.template_settings.get('layout_name')
                old_content_for_cmd = slide_data_to_apply.template_settings.get('text_content', {})
                
                current_slide_actual_old_text_content = {}
                if slide_data_to_apply.template_settings and \
                   isinstance(slide_data_to_apply.template_settings.get("text_content"), dict):
                    current_slide_actual_old_text_content = slide_data_to_apply.template_settings["text_content"]
                elif slide_data_to_apply.lyrics:
                    current_slide_actual_old_text_content = {"legacy_lyrics": slide_data_to_apply.lyrics}

                final_new_content_for_block = {}

                if user_mapping_from_dialog is not None:
                    for new_id, old_id_source in user_mapping_from_dialog.items():
                        if old_id_source and old_id_source in current_slide_actual_old_text_content:
                            final_new_content_for_block[new_id] = current_slide_actual_old_text_content[old_id_source]
                elif old_text_content_for_dialog_multi and new_tb_ids:
                    if len(old_text_content_for_dialog_multi) == 1 and len(new_tb_ids) == 1:
                        first_old_key = next(iter(old_text_content_for_dialog_multi.keys()))
                        old_content_value_current_slide = current_slide_actual_old_text_content.get(first_old_key, "")
                        final_new_content_for_block[new_tb_ids[0]] = old_content_value_current_slide
                    else:
                        for new_id_auto in new_tb_ids:
                            if new_id_auto in current_slide_actual_old_text_content:
                                final_new_content_for_block[new_id_auto] = current_slide_actual_old_text_content[new_id_auto]
                    if not final_new_content_for_block and \
                       "legacy_lyrics" in current_slide_actual_old_text_content and new_tb_ids:
                        final_new_content_for_block[new_tb_ids[0]] = current_slide_actual_old_text_content["legacy_lyrics"]

                logging.debug(f"DEBUG_MW_APPLY_TEMPLATE (Multi for instance {current_instance_id}): final_new_content_for_block: {final_new_content_for_block}")
                sys.stdout.flush()
                cmd = ApplyTemplateCommand(
                    self.presentation_manager,
                    current_instance_id,
                    old_template_id_for_cmd,
                    template_name,
                    old_content_for_cmd,
                    final_new_content_for_block
                )
                self.presentation_manager.do_command(cmd)
        
        # --- Single-Slide Application ---
        else:
            current_slide_data = slides[slide_index]
            instance_id_for_single_command = current_slide_data.id
            old_template_id_for_single_command = current_slide_data.template_settings.get('layout_name')
            old_content_for_single_command = current_slide_data.template_settings.get('text_content', {})
            
            old_text_content_for_dialog = {}
            if current_slide_data.template_settings and isinstance(current_slide_data.template_settings.get("text_content"), dict):
                old_text_content_for_dialog = current_slide_data.template_settings["text_content"]
            elif current_slide_data.lyrics:
                old_text_content_for_dialog = {"legacy_lyrics": current_slide_data.lyrics}

            final_new_content_dict_single = {}

            show_remapping_dialog = False
            old_tb_ids_set = set(old_text_content_for_dialog.keys()) # Define old_tb_ids_set for single-slide path
            new_tb_ids_set = set(new_tb_ids) # Define new_tb_ids_set for single-slide path
            if old_text_content_for_dialog:
                if old_tb_ids_set != new_tb_ids_set:
                    show_remapping_dialog = True
            
            if show_remapping_dialog:
                remapping_dialog = TemplateRemappingDialog(old_text_content_for_dialog, new_tb_ids, self)
                if remapping_dialog.exec():
                    user_mapping = remapping_dialog.get_remapping()
                    for new_id, old_id_source in user_mapping.items():
                        if old_id_source and old_id_source in old_text_content_for_dialog:
                            final_new_content_dict_single[new_id] = old_text_content_for_dialog[old_id_source]
                else:
                    QMessageBox.information(self, "Template Change Cancelled", "Template application was cancelled.")
                    return
            elif new_tb_ids:
                if old_text_content_for_dialog:
                    if old_tb_ids_set == new_tb_ids_set:
                        final_new_content_dict_single = old_text_content_for_dialog.copy()
                    elif len(old_text_content_for_dialog) == 1 and len(new_tb_ids) == 1:
                        old_content_value = next(iter(old_text_content_for_dialog.values()))
                        final_new_content_dict_single[new_tb_ids[0]] = old_content_value
                    else:
                        for new_id in new_tb_ids:
                            if new_id in old_text_content_for_dialog:
                                final_new_content_dict_single[new_id] = old_text_content_for_dialog[new_id]

                    if not final_new_content_dict_single and "legacy_lyrics" in old_text_content_for_dialog:
                        final_new_content_dict_single[new_tb_ids[0]] = old_text_content_for_dialog["legacy_lyrics"]
                else:
                    for new_id in new_tb_ids:
                        final_new_content_dict_single[new_id] = ""

            logging.debug(f"DEBUG_MW_APPLY_TEMPLATE (Single): final_new_content_dict_single: {final_new_content_dict_single}")
            sys.stdout.flush()

            cmd = ApplyTemplateCommand(
                self.presentation_manager,
                instance_id_for_single_command,
                old_template_id_for_single_command,
                template_name,
                old_content_for_single_command,
                final_new_content_dict_single
            )
            self.presentation_manager.do_command(cmd)

        # The presentation_changed signal from do_command will update the UI.

    @Slot()
    def handle_add_new_section(self):
        """Handles the 'Add New Section' menu action by adding a section to the end of the presentation."""
        num_current_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
        self._prompt_and_insert_new_section(num_current_sections)

    def _prompt_and_insert_new_section(self, manifest_insertion_index: int):
        """
        Prompts for a new section title, creates a new section file using SectionFactory,
        and adds it to the presentation manifest at the specified index.
        (Adapted from original main_window.py)
        """
        new_section_title_str, ok = QInputDialog.getText(
            self,
            "Create New Section",
            "Enter title for the new section (leave blank for an untitled section):",
            text=""
        )

        if ok:
            cleaned_section_title = new_section_title_str.strip()
            if not cleaned_section_title:
                cleaned_section_title = f"Untitled Section {uuid.uuid4().hex[:4]}"

            section_file_id = f"section_{uuid.uuid4().hex}"

            new_section_data = SectionFactory.create_new_section_data(
                title=cleaned_section_title,
                section_file_id=section_file_id,
                section_type="Generic"
            )

            central_sections_dir = PluckyStandards.get_sections_dir()

            full_filepath, section_filename = SectionFactory.save_new_section_file(
                new_section_data, cleaned_section_title, self.presentation_manager.io_handler, central_sections_dir
            )

            if full_filepath and section_filename:
                self.presentation_manager.add_section_to_presentation(
                    section_filename, manifest_insertion_index, desired_arrangement_name="Default"
                )
                self.statusBar().showMessage(f"New section '{cleaned_section_title}' created and added.", 3000)
            else:
                self.show_error_message(f"Failed to create and save new section '{cleaned_section_title}'.")


    @Slot(str)
    def _open_section_editor_window(self, section_id_in_manifest: str):
        """Opens the MainEditorWindow for the specified section."""
        if not section_id_in_manifest or section_id_in_manifest not in self.presentation_manager.loaded_sections:
            self.show_error_message(f"Cannot open editor: Section ID '{section_id_in_manifest}' not found or not loaded.")
            return

        # Check if an editor for this section is already open and activate it
        for editor in self._open_editor_windows:
            if hasattr(editor, '_test_section_id') and editor._test_section_id == section_id_in_manifest:
                editor.activateWindow()
                editor.raise_()
                return

        editor_window = MainEditorWindow(
            presentation_manager_ref=self.presentation_manager,
            section_id_to_edit=section_id_in_manifest,
            parent=self
        )
        editor_window.section_content_saved.connect(self._handle_section_content_saved_in_editor)
        self._open_editor_windows.append(editor_window) # Keep a reference
        editor_window.show()

    @Slot(str)
    def _handle_section_content_saved_in_editor(self, section_id: str):
        """
        Called when a MainEditorWindow signals that it has saved content for a section.
        Refreshes the main UI to reflect potential changes.
        """
        logging.info(f"MainWindow: Section '{section_id}' was saved in its editor. Refreshing main UI.")
        # Invalidate the preview cache for this section in SlideUIManager
        self.slide_ui_manager.invalidate_cache_for_section(section_id)
        # The PresentationManager's data for this section was updated directly by the editor.
        # We just need to tell SlideUIManager to rebuild its view based on PM's current state.
        self.slide_ui_manager.refresh_slide_display()

    @Slot(str)
    def handle_rename_section_dialog(self, section_id_in_manifest: str):
        """Handles the request to rename a section via a dialog."""
        if not section_id_in_manifest or section_id_in_manifest not in self.presentation_manager.loaded_sections:
            self.show_error_message(f"Cannot rename section: ID '{section_id_in_manifest}' not found or not loaded.")
            return

        section_wrapper = self.presentation_manager.loaded_sections.get(section_id_in_manifest)
        if not section_wrapper:
            self.show_error_message(f"Internal error: Section wrapper not found for ID '{section_id_in_manifest}'.")
            return

        current_title = section_wrapper.get("section_content_data", {}).get("title", "")

        new_title, ok = QInputDialog.getText(
            self,
            "Rename Section",
            f"Enter new title for section (current: \"{current_title}\"):",
            text=current_title
        )

        if ok and new_title.strip():
            cleaned_new_title = new_title.strip()
            if cleaned_new_title != current_title:
                success = self.presentation_manager.update_section_title(section_id_in_manifest, cleaned_new_title)
                if success:
                    self.statusBar().showMessage(f"Section '{current_title}' renamed to '{cleaned_new_title}'.", 3000)
                else:
                    self.show_error_message(f"Failed to rename section '{current_title}'.")
        elif ok and not new_title.strip():
            QMessageBox.warning(self, "Empty Title", "Section title cannot be empty.")

    # --- Section Panel Handlers (Placeholders) ---
    @Slot(str, int)
    def _handle_request_reorder_section(self, section_id_in_manifest: str, direction: int):
        """Handles the request from the SectionManagementPanel to reorder a section."""
        if not self.presentation_manager.presentation_manifest_data:
            return

        manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
        current_idx = -1
        for i, sec_entry in enumerate(manifest_sections):
            if sec_entry.get("id") == section_id_in_manifest:
                current_idx = i
                break

        if current_idx == -1:
            self.show_error_message(f"Could not find section with ID {section_id_in_manifest} to reorder.")
            return

        new_idx = current_idx + direction
        if 0 <= new_idx < len(manifest_sections):
            self.presentation_manager.reorder_sections_in_manifest(section_id_in_manifest, new_idx)
    @Slot(str)
    def _handle_request_remove_section(self, section_id_in_manifest: str):
        """Handles the request from the SectionManagementPanel to remove a section."""
        reply = QMessageBox.question(self, "Remove Section",
                                     "Are you sure you want to remove this section from the presentation?\n"
                                     "(The section file itself will not be deleted from your computer.)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.presentation_manager.remove_section_from_presentation(section_id_in_manifest)

    @Slot()
    def _handle_request_add_existing_section(self):
        """Handles the request from the SectionManagementPanel to add an existing section file."""
        default_load_path = self.config_manager.get_default_sections_path()
        filepath, _ = QFileDialog.getOpenFileName(self, "Add Existing Section", default_load_path, "Plucky Section Files (*.plucky_section)")
        if filepath:
            section_filename = os.path.basename(filepath)
            num_current_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
            self.presentation_manager.add_section_to_presentation(section_filename, num_current_sections)

    @Slot()
    def _handle_request_create_new_section_from_panel(self):
        """Handles the request from the SectionManagementPanel to create a new section."""
        num_current_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
        self._prompt_and_insert_new_section(num_current_sections)


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
        """
        Runs a test sequence to demonstrate the compositing render pipeline using SlideData.
        """
        if not self.go_live_button.isChecked() and not self.is_decklink_output_active:
            QMessageBox.information(self, "Output Not Active",
                                    "Please activate an output (Screen or DeckLink) before running the compositing test.")
            return

        # Define a minimal text template for the test
        minimal_text_template = {"layout_name": "MinimalText", "text_boxes": [{"id": "test_text", "x_pc": 5, "y_pc": 45, "width_pc": 90, "height_pc": 10, "h_align": "center", "v_align": "center"}]}

        # Sequence of (SlideData, duration_ms) tuples
        self._test_slide_sequence = [
            (SlideData(id="test_bg_blue", background_color="#0000FF", is_background_slide=True), 1500),
            (SlideData(id="test_content_1", template_settings={**minimal_text_template, "text_content": {"test_text": "Content Over Blue"}}), 1500),
            (SlideData(id="test_bg_green", background_color="#00FF00", is_background_slide=True), 1500),
            (SlideData(id="test_content_2", template_settings={**minimal_text_template, "text_content": {"test_text": "Content Over Green"}}), 1500),
            (None, 1500), # Clear content, keep background
            (SlideData(id="test_bg_clear", is_background_slide=True), 1500), # Clear background to black
        ]
        self._current_test_slide_idx = 0
        self._execute_next_test_slide()

    def _execute_next_test_slide(self):
        if self._current_test_slide_idx < len(self._test_slide_sequence):
            slide_data, duration_ms = self._test_slide_sequence[self._current_test_slide_idx]

            if slide_data is None: # Clear content command
                self.active_content_slide = None
            elif slide_data.is_background_slide:
                self.active_background_slide = slide_data
                self.active_content_slide = slide_data # Background can also be content
            else: # Content slide
                self.active_content_slide = slide_data

            # Update the preview with the new slide combination
            self.output_manager.update_preview_slides(self.active_background_slide, self.active_content_slide)
            # Take the new preview to the live program output
            self.output_manager.take()

            self._current_test_slide_idx += 1
            QTimer.singleShot(duration_ms, self._execute_next_test_slide)
        else:
            QMessageBox.information(self, "Compositing Test Complete", "The compositing test sequence has finished.")
            # Clear outputs and active slide tracking after test
            self.output_manager.update_preview_slides(None, None)
            self.output_manager.take()
            self.active_background_slide = None
            self.active_content_slide = None
            logging.info("Compositing Test: Sequence finished.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
