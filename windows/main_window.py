import sys
import os
import uuid # For generating unique IDs
import json # Needed for saving/loading benchmark history
import copy # Needed for deepcopy when applying templates
# import uuid # For generating unique slide IDs for testing - Unused

from PySide6.QtWidgets import ( # type: ignore
    QApplication, QMainWindow, QFileDialog, QSlider, QMenuBar, # Added QMenuBar
    QMessageBox, QVBoxLayout, QWidget, QPushButton, QInputDialog, QSpinBox,
    QComboBox, QLabel, QHBoxLayout, QSplitter, QScrollArea, QDialog, QMenu,
    QDockWidget # Added QDockWidget
)
from PySide6.QtGui import ( # type: ignore
    QScreen, QPixmap, QColor, QContextMenuEvent, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QImage
) # Added specific QDrag...Event types and QImage
from PySide6.QtCore import Qt, QSize, Slot, QEvent, QStandardPaths, QPoint, QRect, QMimeData, QTimer, QObject, QByteArray # Added QByteArray
from typing import Optional, List, Dict, Any, Set # Import Optional, List, Dict, Any, Set for type hinting
from PySide6.QtWidgets import QFrame # For the drop indicator
from windows.settings_window import SettingsWindow # Import the new settings window
# --- Local Imports ---
# Make sure these paths are correct relative to where you run main.py
try:
    # Assuming running from the YourProject directory
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData 
    from rendering.slide_renderer import LayeredSlideRenderer # Changed to LayeredSlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from windows.template_editor_window import TemplateEditorWindow # Import the new editor
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager
    from dialogs.template_remapping_dialog import TemplateRemappingDialog # Import the new dialog
    from core.template_manager import TemplateManager # Import TemplateManager
    from core.app_config_manager import ApplicationConfigManager # Import new config manager
    from core.slide_drag_drop_handler import SlideDragDropHandler # Import new DND handler
    from core.constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT # Import from new constants file
    from dialogs.edit_slide_content_dialog import EditSlideContentDialog # New Dialog
    from core.section_factory import SectionFactory # Import the new factory
    from core.slide_ui_manager import SlideUIManager # Import the new Slide UI Manager
    from core.slide_edit_handler import SlideEditHandler # Import the new handler    
    from widgets.section_management_panel import SectionManagementPanel # New import
    from core.image_cache_manager import ImageCacheManager # New import
    from core.output_target import OutputTarget # New import for Phase 2
    from PySide6.QtGui import QActionGroup # For mutually exclusive menu items
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand,
        AddSlideBlockToSectionCommand
    )
except ImportError:
    # Fallback if running directly from the windows directory (adjust as needed)
    # import sys, os # Already imported at top level
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData
    from rendering.slide_renderer import LayeredSlideRenderer # Changed to LayeredSlideRenderer
    from widgets.scaled_slide_button import ScaledSlideButton # This should already be there
    from windows.template_editor_window import TemplateEditorWindow # Import the new editor
    from widgets.song_header_widget import SongHeaderWidget # Import the new header widget
    from widgets.flow_layout import FlowLayout # Import the new FlowLayout
    from core.presentation_manager import PresentationManager
    from dialogs.template_remapping_dialog import TemplateRemappingDialog # Import the new dialog
    from core.template_manager import TemplateManager # Import TemplateManager
    from core.app_config_manager import ApplicationConfigManager # Import new config manager
    from core.slide_drag_drop_handler import SlideDragDropHandler # Import new DND handler
    from core.constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT # Import from new constants file
    from dialogs.edit_slide_content_dialog import EditSlideContentDialog # New Dialog
    from core.section_factory import SectionFactory # Import the new factory
    from core.slide_ui_manager import SlideUIManager # Import the new Slide UI Manager
    from core.slide_edit_handler import SlideEditHandler # Import the new handler    
    from widgets.section_management_panel import SectionManagementPanel # New import
    from core.image_cache_manager import ImageCacheManager # New import
    from core.output_target import OutputTarget # New import for Phase 2
    from PySide6.QtGui import QActionGroup # For mutually exclusive menu items
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand,
        AddSlideBlockToSectionCommand
    )

# Import DeckLink handler for sending frames (ensure this is available in your project)
import decklink_handler # Assuming decklink_handler.py is at the Plucky project root
from PySide6.QtGui import QCursor # For MouseHoverDebugger
import time


BASE_PREVIEW_WIDTH = 160
# BASE_PREVIEW_HEIGHT is now in core.constants

# Determine project root dynamically for benchmark history file
SCRIPT_DIR_MW = os.path.dirname(os.path.abspath(__file__)) # /windows
PROJECT_ROOT_MW = os.path.dirname(SCRIPT_DIR_MW) # /Plucky
BENCHMARK_TEMP_DIR_MW = os.path.join(PROJECT_ROOT_MW, "temp")
BENCHMARK_HISTORY_FILE_PATH_MW = os.path.join(BENCHMARK_TEMP_DIR_MW, ".pluckybenches.json")

# --- Mouse Hover Debug Event Filter Class ---
# TODO: Move this class to a more appropriate utility module (e.g., core/debug_utils.py)
# so it can be imported by MainWindow if needed, and potentially by main.py for other startup debugging.
class MouseHoverDebugger(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("DEBUG (MainWindow): MouseHoverDebugger instance CREATED.")
        sys.stdout.flush()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            global_mouse_pos = QCursor.pos()
            widget_under_mouse = QApplication.widgetAt(global_mouse_pos)
            if widget_under_mouse:
                print(f"Mouse at {global_mouse_pos}: Hovering over {widget_under_mouse.__class__.__name__} (ObjectName: '{widget_under_mouse.objectName()}')")
                sys.stdout.flush()
            else:
                print(f"Mouse at {global_mouse_pos}: Hovering over None (No Qt widget at this global position)")
                sys.stdout.flush()
        # CRITICAL: Return False to ensure event propagation for an observing filter
        return False
# --- End Mouse Hover Debug Event Filter Class ---


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        mw_init_start_time = time.perf_counter()
        self.mw_init_end_time = 0.0 # Will be set at the end of __init__

        # Initialize these attributes early, before any methods that might use them are called
        self.hover_debugger_instance = None # To store the hover debugger if active
        self.enable_hover_debug_action = None # To store the menu action

        self.setWindowTitle("Plucky Presentation")
        # DeckLink related instance variables
        # self.current_decklink_idx = -1 # This seems unused; fill/key indices are used directly.
        # Other DeckLink attributes will be initialized after config_manager

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Ensure MainWindow can receive focus
        self.setGeometry(100, 100, 900, 700) # Adjusted size for more controls

        # Instantiate the ApplicationConfigManager
        self.config_manager = ApplicationConfigManager(parent=self)
        self.config_manager.recent_files_updated.connect(self._update_recent_files_menu)

        # Load DeckLink device indices from config, then initialize related attributes
        self.decklink_fill_device_idx = self.config_manager.get_app_setting("decklink_fill_device_index", 0) # Default 0
        self.decklink_key_device_idx = self.config_manager.get_app_setting("decklink_key_device_index", 2)  # Default 2
        print(f"MainWindow: Loaded DeckLink settings - Fill: {self.decklink_fill_device_idx}, Key: {self.decklink_key_device_idx}")
        self.current_decklink_name = "" # This might be deprecated or re-evaluated        
        self.current_decklink_video_mode_details = self.config_manager.get_app_setting("decklink_video_mode_details", None) # Load saved video mode
        if self.current_decklink_video_mode_details:
            print(f"MainWindow: Loaded DeckLink video mode: {self.current_decklink_video_mode_details.get('name', 'Unknown')}")

        self.is_decklink_output_active = False # Track if DeckLink output is live
        self._decklink_output_button_state = "off" # "off", "on", "error" for the new button

        self.setMenuBar(self.create_menu_bar()) # Create menu bar AFTER recent files list is initialized

        # Initialize benchmark data store as an instance attribute
        # This will hold current session data + loaded history for the last presentation
        self.benchmark_data_store = {
            "app_init": 0.0,  # Time from app start until MainWindow is shown (calculated in showEvent)
            "mw_init": 0.0,   # Time for MainWindow.__init__ (calculated at end of __init__)
            "mw_show": 0.0,   # Time from MainWindow.__init__ end until it's shown (calculated in showEvent)
            "last_presentation_path": "None",
            "last_presentation_pm_load": 0.0,
            "last_presentation_ui_update": 0.0,
            "last_presentation_render_total": 0.0,
            "last_presentation_render_images": 0.0,
            "last_presentation_render_fonts": 0.0,
            "last_presentation_render_layout": 0.0,
            "last_presentation_render_draw": 0.0,
        }
        # self.setFocus() # Attempt to give focus to MainWindow initially

        # Instantiate the TemplateManager
        self.template_manager = TemplateManager()
        self.template_manager.templates_changed.connect(self.on_template_collection_changed)
        
        # --- Core Components ---
        self.image_cache_manager = ImageCacheManager() # Create the image cache manager
        self.output_window = OutputWindow()
        self.slide_renderer = LayeredSlideRenderer(app_settings=self, image_cache_manager=self.image_cache_manager)
        self.presentation_manager = PresentationManager(template_manager=self.template_manager) # Pass TemplateManager
        self.presentation_manager.presentation_changed.connect(self.update_slide_display_and_selection)
        self.presentation_manager.slide_visual_property_changed.connect(self._handle_slide_visual_property_change) # New connection
        # self.presentation_manager.presentation_changed.connect(self._refresh_section_management_panel) # SlideUIManager will handle its refresh
        self.presentation_manager.error_occurred.connect(self.show_error_message)
        # Instantiate the SlideEditHandler
        self.slide_edit_handler = SlideEditHandler(self.presentation_manager, self)

        self.current_slide_index = -1 # Tracks the selected slide button's index
        self.output_resolution = QSize(1920, 1080) # Default, updated on monitor select
        # Old way of managing live background, will be superseded by OutputTarget logic
        # but kept for now for UI elements that might depend on knowing the "persistent" background.


        
        self.current_live_background_pixmap: QPixmap | None = None
        self.current_background_slide_id: Optional[str] = None # ID of the active background slide
        self.main_output_target: Optional[OutputTarget] = None
        self.decklink_output_target: Optional[OutputTarget] = None


        # --- UI Elements ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Top controls: Live button (Monitor selection moved to settings)
        self.go_live_button = QPushButton("") # Text removed, will be a circle
        self.go_live_button.setFixedSize(24, 24) # Make it smaller
        self.go_live_button.setCheckable(True) # To manage its state
        self._decklink_keyer_state = "off" # "off", "on", "error"
        self._update_go_live_button_appearance() # Initial appearance

        # Top controls: Undo/Redo (File ops moved to menu)
        self.undo_button = QPushButton("Undo") # New
        self.redo_button = QPushButton("Redo") # New

        # DeckLink Test Button (Removing this from the main toolbar)
        # self.test_decklink_button = QPushButton("DL Test Frame")
        # self.test_decklink_button.setToolTip("Send a test frame to DeckLink output.")

        # DeckLink Output On/Off Button (repurposed from keyer button)
        self.decklink_output_toggle_button = QPushButton("") # Text removed, will be a circle
        self.decklink_output_toggle_button.setFixedSize(24, 24)
        self.decklink_output_toggle_button.setCheckable(True) # To manage its state
        self._update_decklink_output_button_appearance() # Initial appearance

        # Edit Template button (Restoring this button)
        self.edit_template_button = QPushButton("Edit Templates") 
        self.edit_template_button.setEnabled(True) 
        self.edit_template_button.setToolTip("Open the template editor.") 

        # Preview Size Spinbox
        self.preview_size_spinbox = QSpinBox()
        self.preview_size_spinbox.setMinimum(1)
        self.preview_size_spinbox.setMaximum(4)
        self.preview_size_spinbox.setSuffix("x") # Add 'x' suffix
        self.preview_size_spinbox.setToolTip("Adjust Slide Preview Size (1x-4x)") # Changed to spinbox and updated tooltip
        

        # Slide Button Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.slide_buttons_widget = QWidget()
        # This is now the main vertical layout for song headers and their slide containers
        self.slide_buttons_layout = QVBoxLayout(self.slide_buttons_widget)
        self.slide_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.slide_buttons_layout.setSpacing(0) # Let widgets/layouts inside manage their own margins/spacing
        self.scroll_area.setWidget(self.slide_buttons_widget)


        # Drop Indicator (child of slide_buttons_widget for correct positioning)
        self.drop_indicator = QFrame(self.slide_buttons_widget)
        self.drop_indicator.setFrameShape(QFrame.Shape.VLine) # Change to Vertical Line
        self.drop_indicator.setFrameShadow(QFrame.Shadow.Plain) # Plain for a solid line
        self.drop_indicator.setStyleSheet("QFrame { border: 2px solid #00A0F0; }") # Bright blue
        self.drop_indicator.setFixedWidth(4) # Thickness of the vertical line
        self.drop_indicator.hide()

        # --- Layouts ---
        main_layout = QHBoxLayout(self.central_widget)
        left_panel_widget = QWidget()
        left_layout = QVBoxLayout(left_panel_widget)
        # Remove default margins to prevent extra space above the first elements
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Monitor layout is removed as Go Live button is moved

        # File operations layout
        file_ops_layout = QHBoxLayout()

        # Add Preview Size controls to the far left
        file_ops_layout.addWidget(QLabel("Preview Size:"))
        file_ops_layout.addWidget(self.preview_size_spinbox)
        file_ops_layout.addSpacing(10) # Space after preview size

        # Add middle buttons
        file_ops_layout.addWidget(self.edit_template_button) # Add Edit Templates button back
        file_ops_layout.addWidget(self.undo_button)
        file_ops_layout.addWidget(self.redo_button)
        # file_ops_layout.addWidget(self.test_decklink_button) # Remove DeckLink test button from layout

        file_ops_layout.addStretch(1) # Add stretch to push Output control to the far right

        # DeckLink Keyer control button with label
        decklink_keyer_control_layout = QVBoxLayout()
        decklink_keyer_label = QLabel("DL Output") # Renamed label
        decklink_keyer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        decklink_keyer_control_layout.addWidget(decklink_keyer_label)
        decklink_keyer_control_layout.addWidget(self.decklink_output_toggle_button, 0, Qt.AlignmentFlag.AlignHCenter) # Use new button name
        file_ops_layout.addLayout(decklink_keyer_control_layout)
        file_ops_layout.addSpacing(5) # Small space between DL Keyer and Output

        # Output (Go Live) button with label
        output_control_layout = QVBoxLayout()
        output_label = QLabel("Output")
        output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        output_control_layout.addWidget(output_label)
        output_control_layout.addWidget(self.go_live_button, 0, Qt.AlignmentFlag.AlignHCenter) # Add Go Live button here, centered
        file_ops_layout.addLayout(output_control_layout)
        left_layout.addLayout(file_ops_layout) # Add the file_ops_layout which now contains all top buttons and preview size

        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("Slides:"))
        left_layout.addWidget(self.scroll_area)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel_widget)
        # splitter.addWidget(right_panel_widget) # If you add a right panel later
        splitter.setSizes([350]) # Adjust initial size of left panel
        main_layout.addWidget(splitter)

        # --- Section Management Panel (as a Dock Widget) ---
        self.section_management_dock = QDockWidget("Section Manager", self)
        self.section_management_panel = SectionManagementPanel(self.presentation_manager, self)
        self.section_management_dock.setObjectName("SectionManagementDock") # <--- ADD THIS LINE
        self.section_management_dock.setWidget(self.section_management_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.section_management_dock) # Or LeftDockWidgetArea
        self.section_management_dock.hide() # Hidden by default

        # --- Instantiate SlideUIManager ---
        self.slide_ui_manager = SlideUIManager(
            presentation_manager=self.presentation_manager,
            template_manager=self.template_manager,
            slide_renderer=self.slide_renderer,
            slide_edit_handler=self.slide_edit_handler,
            config_manager=self.config_manager,
            output_window_ref=self.output_window,
            scroll_area=self.scroll_area,
            slide_buttons_widget=self.slide_buttons_widget,
            slide_buttons_layout=self.slide_buttons_layout,
            drop_indicator=self.drop_indicator,
            parent_main_window=self,
            parent=self # QWidget parent
        )
        # Load preview size from config and initialize button_scale_factor in SlideUIManager
        initial_preview_size = self.config_manager.get_app_setting("preview_size", 1) # Default to 1x
        self.slide_ui_manager.set_preview_scale_factor(float(initial_preview_size))
        self.preview_size_spinbox.setValue(initial_preview_size) # Set spinbox value

        # --- Connections ---
        # Connections for load, save, save_as, add_song are now handled by menu actions
        self.edit_template_button.clicked.connect(self.handle_edit_template) # Connect Edit Templates button
        self.undo_button.clicked.connect(self.handle_undo) # New
        self.redo_button.clicked.connect(self.handle_redo) # New
        self.preview_size_spinbox.valueChanged.connect(self.handle_preview_size_change) # Connect spinbox signal
        self.decklink_output_toggle_button.clicked.connect(self.toggle_decklink_output_stream) # New connection
        self.go_live_button.clicked.connect(self.toggle_live)

        self.slide_ui_manager.active_slide_changed_signal.connect(self._handle_active_slide_changed_from_ui)
        self.slide_ui_manager.request_show_error_message_signal.connect(self.show_error_message)
        self.slide_ui_manager.request_set_status_message_signal.connect(self.set_status_message)

        # Connect signals from SectionManagementPanel
        self._connect_section_management_panel_signals()

        # Enable Drag and Drop on the main window (or a specific widget like scroll_area)
        self.setAcceptDrops(True)

        # The SlideDragDropHandler is now owned by SlideUIManager.
        # self.drag_drop_handler in MainWindow is no longer needed.
        # Store initial app benchmark data
        app_start_time = QApplication.instance().property("app_start_time")
        # Store app_start_time (timestamp) temporarily for calculation in showEvent

        # --- Status Bar ---
        self.statusBar().showMessage("Ready") # Initial status message

        self._app_start_time = app_start_time 

        # Target output screen is now managed by config_manager
        # self._target_output_screen: Optional[QScreen] = self.config_manager.get_target_output_screen()
        
        mw_init_duration = time.perf_counter() - mw_init_start_time
        self.benchmark_data_store["mw_init"] = mw_init_duration
        self.mw_init_end_time = time.perf_counter() # Store for calculating mw_show in showEvent

        if app_start_time is not None: # Check if it was set
            # app_init and mw_show will be calculated and printed in showEvent, using self._app_start_time
            pass 
        else:
            print(f"[BENCHMARK] MainWindow.__init__ took: {self.benchmark_data_store['mw_init']:.4f} seconds (app_start_time not found)")

        self.slide_ui_manager.refresh_slide_display() # Initial setup of slide display

        # Restore window state (including dock widgets)
        # Do this after all UI elements, including docks, are created but before showEvent typically.
        saved_window_state_str = self.config_manager.get_app_setting("main_window_state")
        if saved_window_state_str:
            # Ensure dock widgets are created before restoring state
            if not self.section_management_dock: # Should not happen if init order is correct
                print("MainWindow: Warning - Section management dock not created before restoreState.")

            try:
                self.restoreState(QByteArray.fromBase64(saved_window_state_str.encode('utf-8')))
                print("MainWindow: Restored window state.")
            except Exception as e:
                print(f"MainWindow: Error restoring window state: {e}")


    def _connect_section_management_panel_signals(self):
        self.section_management_panel.request_reorder_section.connect(self._handle_request_reorder_section)
        self.section_management_panel.request_remove_section.connect(self._handle_request_remove_section)
        self.section_management_panel.request_add_existing_section.connect(self._handle_request_add_existing_section)
        self.section_management_panel.request_create_new_section.connect(self._handle_request_create_new_section_from_panel)
        self.presentation_manager.presentation_changed.connect(self._refresh_section_management_panel)
    #Main Window Controls
    def set_status_message(self, message: str, timeout: int = 0):
        """
        Displays a message on the status bar.
        A timeout of 0 means the message will remain indefinitely
        until cleared or replaced.
        """
        self.statusBar().showMessage(message, timeout)

    #Main Window Effects 
    def _update_go_live_button_appearance(self):
        if self.go_live_button.isChecked(): # Live
            self.go_live_button.setToolTip("Output is LIVE")
            self.go_live_button.setStyleSheet("QPushButton { background-color: red; border-radius: 12px; border: 1px solid darkred; } QPushButton:hover { background-color: #FF4C4C; }")
        else: # Not live
            self.go_live_button.setToolTip("Go Live")
            self.go_live_button.setStyleSheet("QPushButton { background-color: palette(button); border-radius: 12px; border: 2px solid gray; } QPushButton:hover { border: 2px solid darkgray; }")

    def _update_decklink_output_button_appearance(self):
        if self.decklink_output_toggle_button.isChecked(): # DeckLink Output is ON
            self.decklink_output_toggle_button.setToolTip("DeckLink Output is LIVE. Click to turn OFF.")
            self.decklink_output_toggle_button.setStyleSheet("QPushButton { background-color: #4CAF50; /* Green */ border-radius: 12px; border: 1px solid darkgreen; } QPushButton:hover { background-color: #66BB6A; }")
        elif self._decklink_output_button_state == "error": # Error state
            self.decklink_output_toggle_button.setToolTip("DeckLink Output Error. Click to attempt reset to OFF.")
            self.decklink_output_toggle_button.setStyleSheet("QPushButton { background-color: yellow; border-radius: 12px; border: 1px solid #B8860B; } QPushButton:hover { background-color: #FFFFE0; }")
        else: # Off or uninitialized
            self.decklink_output_toggle_button.setToolTip("DeckLink Output is OFF. Click to turn ON.")
            self.decklink_output_toggle_button.setStyleSheet("QPushButton { background-color: palette(button); border-radius: 12px; border: 2px solid gray; } QPushButton:hover { border: 2px solid darkgray; }")

    #Main window Send - maybe move ()
    def toggle_decklink_output_stream(self):
        if self.decklink_output_toggle_button.isChecked(): # User wants to turn DeckLink ON
            print("MainWindow: Initializing DeckLink for output stream...")
            self._decklink_output_button_state = "pending" # Intermediate state
            sdk_init_success, _ = decklink_handler.initialize_sdk()
            if not sdk_init_success:
                QMessageBox.critical(self, "DeckLink Error", "Failed to initialize DeckLink SDK.")
                self.decklink_output_toggle_button.setChecked(False) # Revert button state
                self._decklink_output_button_state = "error"
                self._update_decklink_output_button_appearance()
                # Ensure DeckLink target is not active if initialization fails
                if self.decklink_output_target:
                    self.decklink_output_target.update_slide(None) # Blank it
                    # Consider deleting or nullifying self.decklink_output_target here
                return
            
            if not self.current_decklink_video_mode_details:
                QMessageBox.critical(self, "DeckLink Error", "Video mode not configured. Please select a video mode in Settings.")
                self.decklink_output_toggle_button.setChecked(False)
                self._decklink_output_button_state = "error" # Or "off" if preferred
                self._update_decklink_output_button_appearance()
                if self.decklink_output_target:
                    self.decklink_output_target.update_slide(None)
                    # Consider deleting or nullifying self.decklink_output_target here
                return
            
            decklink_handler.enumerate_devices()
            
            if not decklink_handler.initialize_selected_devices(self.decklink_fill_device_idx, self.decklink_key_device_idx, self.current_decklink_video_mode_details):
                decklink_handler.shutdown_sdk() # Clean up SDK
                self.decklink_output_toggle_button.setChecked(False) # Revert button state
                self._decklink_output_button_state = "error"
                self._update_decklink_output_button_appearance()
                if self.decklink_output_target:
                    self.decklink_output_target.update_slide(None)
                    # Consider deleting or nullifying self.decklink_output_target here
                return
            
            self.is_decklink_output_active = True
            self._decklink_output_button_state = "on"
            self._init_decklink_output_target() # Initialize or re-initialize DeckLink OutputTarget
            print("MainWindow: DeckLink output stream started successfully.")
            # If a slide is currently live on screen, send it to DeckLink
            # The _display_slide call will now update the decklink_output_target
            if 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):

                self._display_slide(self.current_slide_index)
            else: # Send blank to DeckLink
                self._show_blank_on_output() # This will also send blank to DL if active

        else: # User wants to turn DeckLink OFF
            print("MainWindow: Shutting down DeckLink output stream.")
            if self.is_decklink_output_active: # Check if it was actually active
                # Blank the DeckLink target first
                if self.decklink_output_target:
                    self.decklink_output_target.update_slide(None) 
                    # The _handle_decklink_target_update will send the blank frame

                decklink_handler.shutdown_selected_devices()
                decklink_handler.shutdown_sdk()
            self.is_decklink_output_active = False
            self._decklink_output_button_state = "off"
            print("MainWindow: DeckLink output stream stopped.")
            # Clean up DeckLink target
            if self.decklink_output_target:
                self.decklink_output_target.pixmap_updated.disconnect(self._handle_decklink_target_update)
                self.decklink_output_target.deleteLater() # Schedule for deletion
                self.decklink_output_target = None

        self._update_decklink_output_button_appearance()

    #  Old prob delete
    def _send_decklink_test_frame(self):
        """Sends a test frame to the DeckLink output."""
        if not self.is_decklink_output_active:
            print("DeckLink output is not active. Cannot send test frame.")
            QMessageBox.warning(self, "DeckLink Error", "DeckLink output is not active. Please go live first.")
            return

        # Create a QImage for the test frame
        # Using dimensions from the decklink_handler
        test_image = QImage(decklink_handler.DLL_WIDTH, decklink_handler.DLL_HEIGHT, QImage.Format_ARGB32_Premultiplied)
        test_image.fill(QColor(0, 255, 255, 255))  # Opaque Cyan (RGBA for QColor)

        # For DeckLink, we need separate fill and key. For a simple test, key can be black.
        fill_bytes = decklink_handler.get_image_bytes_from_qimage(test_image)
        
        black_image = QImage(decklink_handler.DLL_WIDTH, decklink_handler.DLL_HEIGHT, QImage.Format_ARGB32_Premultiplied)
        black_image.fill(QColor(0,0,0,255)) # Opaque black
        key_bytes = decklink_handler.get_image_bytes_from_qimage(black_image)

        expected_size = decklink_handler.DLL_WIDTH * decklink_handler.DLL_HEIGHT * 4

        if fill_bytes and key_bytes and len(fill_bytes) == expected_size and len(key_bytes) == expected_size:
            print(f"Sending DeckLink test frame (Fill Size: {len(fill_bytes)} bytes, Key Size: {len(key_bytes)} bytes)")
            if not decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
                print("Failed to send DeckLink test frame.", file=sys.stderr)
                QMessageBox.critical(self, "DeckLink Error", "Failed to send test frame to DeckLink output.")
            else:
                print("DeckLink test frame sent successfully.")
                QMessageBox.information(self, "DeckLink Test", "Test frame sent successfully to DeckLink output.")
        else:
            print(f"Error: Test image data size mismatch or creation failed.", file=sys.stderr)
            QMessageBox.critical(self, "Image Error", f"Test image data size mismatch or creation failed.")
    
    #Main window Send - Follow Decklink output ^
    def toggle_live(self):
        target_screen = self.config_manager.get_target_output_screen()

        if self.output_window.isVisible(): # Turning OFF
            self.go_live_button.setChecked(False)
            self._show_blank_on_output() # Good practice to blank it before hiding
            self.output_window.hide() # Explicitly hide the window
            if self.main_output_target: # Clean up main output target
                self.main_output_target.pixmap_updated.disconnect(self.output_window.set_pixmap)
                self.main_output_target.deleteLater()
                self.main_output_target = None

            # Note: DeckLink output is now controlled by its own button
        else: # Going LIVE (Screen Output)
            if not target_screen:
                QMessageBox.warning(self, "No Output Selected", "Please select an output monitor or DeckLink device in Settings.")
                self.go_live_button.setChecked(False) # Ensure button state is correct
                self._update_go_live_button_appearance()
                return
            self.go_live_button.setChecked(True)
            output_geometry = target_screen.geometry()
            self.output_resolution = output_geometry.size()
            self.output_window.setGeometry(output_geometry)
            self._init_main_output_target() # Initialize or re-initialize Main OutputTarget

            self.output_window.showFullScreen()
            if 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):
                self._display_slide(self.current_slide_index)
            else:
                self._show_blank_on_output()
        self._update_go_live_button_appearance()

    #Strip to external probably (core.addSection())
    def handle_add_new_section(self):
        """
        Prompts for a new section title, creates a new section file
        in the central store, and adds it to the current presentation.
        """
        section_title_text, ok_title = QInputDialog.getText(
            self,
            "Add New Section",
            "Enter the title for the new section (e.g., song name, sermon part):"
        )

        if not ok_title or not song_title_text.strip():
            if ok_title and not song_title_text.strip(): # User pressed OK but title was empty
                QMessageBox.warning(self, "Empty Title", "Section title cannot be empty.")
            return
        
        cleaned_section_title = section_title_text.strip() # Renamed for clarity

        section_file_id = f"section_{uuid.uuid4().hex}"

        # Use SectionFactory to create the data
        new_section_data = SectionFactory.create_new_section_data(
            title=cleaned_section_title,
            section_file_id=section_file_id,
            section_type="Generic" # Or prompt for type if this menu item is generic
        )

        try:
            from core.plucky_standards import PluckyStandards
        except ImportError:
            from plucky_standards import PluckyStandards

        central_sections_dir = PluckyStandards.get_sections_dir()
        
        full_filepath, section_filename = SectionFactory.save_new_section_file(
            new_section_data, cleaned_section_title, self.presentation_manager.io_handler, central_sections_dir
        )

        if full_filepath and section_filename:
            self.set_status_message(f"New section '{cleaned_section_title}' created.", 3000)

        # 5. Add the section to the current presentation (append to the end)
        # Determine insertion index (append to end of current presentation)
        num_current_sections = 0
        if self.presentation_manager.presentation_manifest_data and "sections" in self.presentation_manager.presentation_manifest_data:
            num_current_sections = len(self.presentation_manager.presentation_manifest_data["sections"])
        
        # Pass the simple filename to PresentationManager
        self.presentation_manager.add_section_to_presentation(section_filename, num_current_sections, desired_arrangement_name="Default")
        # PresentationManager will emit presentation_changed, updating the UI.
    
    #Main Window Controls
    #double check if it should just check if it's dirty reguardless (check where this goes and make it load all slides with updated templates)
    def handle_load(self, filepath: Optional[str] = None):
        """
        Loads a presentation from a file. Prompts to save unsaved changes.
        If filepath is provided, loads that file directly; otherwise, opens a file dialog.
        """
        if self.presentation_manager.is_overall_dirty() and filepath is None: # Only prompt if loading via dialog
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before loading new file?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.handle_save(): # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        if filepath is None: # If no filepath was provided, open the dialog
            default_load_path = self.config_manager.get_default_presentations_path()
            filepath, _ = QFileDialog.getOpenFileName(
                self, 
                "Load Presentation", 
                default_load_path, 
                "Plucky Presentation Files (*.plucky_pres);;All Files (*)")

        if filepath: # Proceed if we have a filepath (either provided or from dialog)
            # Reset presentation-specific benchmarks before loading
            self.benchmark_data_store["last_presentation_path"] = filepath
            self.benchmark_data_store["last_presentation_pm_load"] = 0.0
            self.benchmark_data_store["last_presentation_ui_update"] = 0.0
            self.benchmark_data_store["last_presentation_render_total"] = 0.0
            self.benchmark_data_store["last_presentation_render_images"] = 0.0
            self.benchmark_data_store["last_presentation_render_fonts"] = 0.0
            self.benchmark_data_store["last_presentation_render_layout"] = 0.0
            self.benchmark_data_store["last_presentation_render_draw"] = 0.0

            load_pm_start_time = time.perf_counter()
            if self.slide_ui_manager: # Access cache through SlideUIManager
                self.slide_ui_manager.preview_pixmap_cache.clear()
            if self.presentation_manager.load_presentation(filepath): # This will trigger presentation_changed
                load_pm_duration = time.perf_counter() - load_pm_start_time
                self.benchmark_data_store["last_presentation_pm_load"] = load_pm_duration
                print(f"[BENCHMARK] PresentationManager.load_presentation() took: {load_pm_duration:.4f} seconds for {filepath}")
                
                # Update window title
                presentation_title = self.presentation_manager.get_presentation_title()
                if presentation_title:
                    self.setWindowTitle(f"Plucky Presentation - {presentation_title}")
                else:
                    self.setWindowTitle(f"Plucky Presentation - {os.path.basename(filepath)}")
                
                self.config_manager.add_recent_file(filepath) # Add to recents list on successful load
            # Error messages are handled by PresentationManager's error_occurred signal

    #Main Window Controls
    def handle_save(self) -> bool:
        if not self.presentation_manager.current_manifest_filepath:
            return self.handle_save_as()
        else:
            # current_manifest_filepath is already set, so save_presentation will use it.
            if self.presentation_manager.save_presentation():
                self.set_status_message(f"Presentation saved to {os.path.basename(self.presentation_manager.current_manifest_filepath)}", 3000)
                
                # Update window title based on the saved presentation's title
                presentation_title = self.presentation_manager.get_presentation_title()
                if presentation_title:
                    self.setWindowTitle(f"Plucky Presentation - {presentation_title}")
                elif self.presentation_manager.current_manifest_filepath: # Fallback to filename if title is missing
                    self.setWindowTitle(f"Plucky Presentation - {os.path.basename(self.presentation_manager.current_manifest_filepath)}")
                
                if self.presentation_manager.current_manifest_filepath: # Ensure path exists before adding
                    self.config_manager.add_recent_file(self.presentation_manager.current_manifest_filepath)
                return True
            # Error message handled by show_error_message via signal
            self.set_status_message(f"Error saving presentation to {self.presentation_manager.current_manifest_filepath}", 5000)
            return False

    #Main Window Controls
    def handle_save_as(self) -> bool:
        default_save_path = self.config_manager.get_default_presentations_path()
        current_filename = os.path.basename(self.presentation_manager.current_manifest_filepath) if self.presentation_manager.current_manifest_filepath else "Untitled.plucky_pres"
        new_manifest_filepath, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Presentation As...", 
            os.path.join(default_save_path, current_filename), 
            "Plucky Presentation Files (*.plucky_pres);;All Files (*)"
        )
        if new_manifest_filepath:
            if self.presentation_manager.save_presentation_as(new_manifest_filepath):
                self.set_status_message(f"Presentation saved as {os.path.basename(new_manifest_filepath)}", 3000)
                
                # Update window title based on the saved presentation's title
                # save_presentation_as updates the title in manifest_data, get_presentation_title will reflect it.
                presentation_title = self.presentation_manager.get_presentation_title()
                if presentation_title:
                    self.setWindowTitle(f"Plucky Presentation - {presentation_title}")
                else: # Fallback to filename if title is somehow missing after save_as
                    self.setWindowTitle(f"Plucky Presentation - {os.path.basename(new_manifest_filepath)}")
                
                self.config_manager.add_recent_file(new_manifest_filepath)
                return True
            self.set_status_message(f"Error saving presentation as {os.path.basename(new_manifest_filepath)}", 5000)
            return False
        return False # User cancelled dialog

    #Main Window Controls
    @Slot() # No longer receives an int directly from the signal
    def handle_preview_size_change(self, value: int):
        """Delegates preview size change to SlideUIManager."""
        if self.slide_ui_manager:
            self.slide_ui_manager.set_preview_scale_factor(float(value))

    #Sub window opener
    def handle_edit_template(self):
        # TemplateManager ensures "Default Layout" always exists, so no need for the "No Templates" check here.

        # Pass all current named templates to the editor
        current_templates_snapshot = self.template_manager.get_all_templates()
        editor = TemplateEditorWindow(all_templates=current_templates_snapshot, parent=self)
        # Connect the editor's save request signal to a handler in MainWindow
        editor.templates_save_requested.connect(self._handle_editor_save_request)
        
        if editor.exec() == QDialog.DialogCode.Accepted:
            updated_templates_collection = editor.get_updated_templates()
            self.template_manager.update_from_collection(updated_templates_collection)
            # If the signal from template_manager.update_from_collection is not reliably
            # triggering on_template_collection_changed after the dialog is accepted,
            # or if we want to be absolutely sure that closing the editor with "OK"
            # refreshes the main window's view of templates, we can manually call the slot.
            # This ensures at least one refresh reflecting the editor's final state.
            print("MainWindow: Template editor was accepted. Manually triggering UI refresh for templates.")
            self.on_template_collection_changed() # Manually call the slot that handles the refresh
        else:
            # If the user cancels, we might want to reload the templates from the manager
            # to discard any un-OK'd changes if they didn't use the intermediate "Save" button.
            # This depends on how "dirty" state is managed within TemplateEditorWindow itself.
            # For now, we'll assume TemplateManager holds the last saved state.
            # If the editor was complex and had its own dirty tracking, you might reload here.
            print("Template editor was cancelled.")

    #Main Window Controls
    @Slot()
    def update_slide_display_and_selection(self):
        """
        This slot is connected to presentation_manager.presentation_changed.
        The actual UI update is now handled by SlideUIManager.refresh_slide_display(),
        which is also connected to presentation_manager.presentation_changed.
        This method can be kept for any MainWindow specific updates needed on presentation change,
        or removed if SlideUIManager handles everything. For now, it's a pass-through.
        """
        # print("MainWindow: presentation_changed signal received. SlideUIManager will handle UI refresh.")
        pass # SlideUIManager.refresh_slide_display is already connected and will handle it.
    
    #Main window controls
    def get_selected_slide_indices(self) -> list[int]:
        """Returns a list of the indices of currently selected slides."""
        if self.slide_ui_manager:
            return self.slide_ui_manager.get_selected_slide_indices()
        return []

    @Slot(int)
    def _handle_active_slide_changed_from_ui(self, new_active_slide_index: int):
        """Handles the signal from SlideUIManager when the active slide changes."""
        self.current_slide_index = new_active_slide_index
        if self.output_window.isVisible():
            if new_active_slide_index != -1:
                self._display_slide(new_active_slide_index)
            else:
                self._show_blank_on_output()

    #Main Window Utility
    @Slot(int)
    def handle_delete_slide_requested(self, slide_index: int):
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot delete slide: Index {slide_index} is invalid.")
            return

        selected_indices_to_delete = self.get_selected_slide_indices() # Get current selection

        # If the right-clicked slide is part of a multi-selection, delete all selected
        if slide_index in selected_indices_to_delete and len(selected_indices_to_delete) > 1:
            reply = QMessageBox.question(self, 'Delete Slides',
                                         f"Are you sure you want to delete {len(selected_indices_to_delete)} selected slides?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                # Delete in reverse order to avoid index shifts affecting subsequent deletions
                for idx in sorted(selected_indices_to_delete, reverse=True):
                    # --- Illustrative: Accessing new identifiers ---
                    slide_data_to_delete = slides[idx]
                    instance_id_to_delete = slide_data_to_delete.id # Get the unique instance ID
                    print(f"MainWindow: Preparing to delete slide at global index {idx}, "
                          f"instance_id '{instance_id_to_delete}'.")
                    # --- End Illustrative ---
                    cmd = DeleteSlideCommand(self.presentation_manager, instance_id_to_delete)
                    self.presentation_manager.do_command(cmd) # Each deletion is a separate undo step for now
                # Selection will be updated by SlideUIManager on presentation_changed
                # self.slide_ui_manager._selected_slide_indices.clear() # This would be internal to SlideUIManager
        else: # Single delete (either only one selected, or right-clicked an unselected slide)
            # Ensure slide_data is fetched for the specific slide_index for the confirmation message
            slide_data = slides[slide_index] # This was missing in the multi-delete path

            # --- Illustrative: Accessing new identifiers ---
            section_id = slide_data.section_id_in_manifest # ID of the section instance in the manifest
            block_id = slide_data.slide_block_id # ID of the slide_block within the section file
            arrangement_name = slide_data.active_arrangement_name_for_section # The arrangement this instance is from
            print(f"MainWindow: Preparing to delete single slide at global index {slide_index}, "
                  f"which is slide_block '{block_id}' in section_manifest_id '{section_id}'.")
            # --- End Illustrative ---

            # TODO (Refinement): If deleting the last reference to a slide_block,
            # should we prompt to delete the block itself from the section file? (Phase 5?)
            reply = QMessageBox.question(self, 'Delete Slide',
                                         f"Are you sure you want to delete this slide?\n\nLyrics: \"{slide_data.lyrics[:50]}...\"",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                instance_id_to_delete = slide_data.id # Get the correct instance ID
                cmd = DeleteSlideCommand(self.presentation_manager, instance_id_to_delete)
                self.presentation_manager.do_command(cmd)

    # doubble check to make sure that it doesn't search by song title (if 2 are the same it should just edit the one?)
    @Slot(str)
    def handle_edit_song_title_requested(self, original_song_title_to_edit: str):
        """Handles request to edit a song's title."""
        # This method might need to be re-evaluated if song titles are part of section data
        # rather than individual slide data. For now, keeping original logic.

        # Fetch current lyrics for the song
        current_slides_for_song = [
            s.lyrics for s in self.presentation_manager.get_slides() if s.song_title == original_song_title_to_edit
        ]

        if not current_slides_for_song:
            self.show_error_message(f"Could not find slides for song: \"{original_song_title_to_edit}\" to edit its title.")
            return

        new_title, ok_title = QInputDialog.getText(
            self,
            "Edit Song Title",
            f"Current title: \"{original_song_title_to_edit}\"\nEnter new title (leave blank for no title):",
            text=original_song_title_to_edit
        )

        if not ok_title:
            return # User cancelled title edit
        
        # If user pressed OK, proceed with the title change, keeping existing lyrics
        # The update_entire_song method expects a list of stanzas.
        # We use the already fetched current_slides_for_song which are the lyrics stanzas.
        # This is a complex operation, potentially multiple commands or a macro command.
        # For now, not making it undoable as a single step through the command system,
        # but PresentationManager itself will handle the change.
        # If new_title is empty, update_entire_song will treat it as an untitled song.
        self.presentation_manager.update_entire_song(original_song_title_to_edit, new_title, current_slides_for_song)
    
    # --- OutputTarget Initialization ---
    def _init_main_output_target(self):
        if self.main_output_target: # Disconnect and delete if exists
            try: self.main_output_target.pixmap_updated.disconnect(self.output_window.set_pixmap)
            except RuntimeError: pass # Already disconnected
            self.main_output_target.deleteLater()
            self.main_output_target = None

        target_screen = self.config_manager.get_target_output_screen()
        # The decision to initialize should be based on configuration and intent to go live,
        # not the current visibility of output_window, as this method is called *before* showFullScreen.
        if target_screen: 
            output_res = target_screen.geometry().size()
            if output_res.width() > 0 and output_res.height() > 0:
                self.main_output_target = OutputTarget("MainScreen", output_res, self.slide_renderer, self)
                self.main_output_target.pixmap_updated.connect(self.output_window.set_pixmap)
                print(f"MainWindow: Main output target initialized for screen: {target_screen.name()} at {output_res.width()}x{output_res.height()}")
            else:
                print(f"MainWindow: Invalid resolution for main output target: {output_res}")
        else:
            # This message will now only appear if no target_screen is configured.
            # The "output window not visible" part is removed from the condition.
            print("MainWindow: No target screen configured for main output target.")

    def _init_decklink_output_target(self):
        if self.decklink_output_target: # Disconnect and delete if exists
            try: self.decklink_output_target.pixmap_updated.disconnect(self._handle_decklink_target_update)
            except RuntimeError: pass
            self.decklink_output_target.deleteLater()
            self.decklink_output_target = None

        if self.is_decklink_output_active and self.current_decklink_video_mode_details:
            dl_width = self.current_decklink_video_mode_details.get('width')
            dl_height = self.current_decklink_video_mode_details.get('height')
            if dl_width and dl_height and dl_width > 0 and dl_height > 0:
                decklink_res = QSize(dl_width, dl_height)
                self.decklink_output_target = OutputTarget("DeckLink", decklink_res, self.slide_renderer, self)
                self.decklink_output_target.pixmap_updated.connect(self._handle_decklink_target_update)
                print(f"MainWindow: DeckLink output target initialized at {dl_width}x{dl_height}")
            else:
                print(f"MainWindow: Invalid DeckLink dimensions for output target: W={dl_width}, H={dl_height}")
        else:
            print("MainWindow: DeckLink not active or video mode not set for DeckLink output target.")


    # The checkup might need to be updated because it's happening everytime?
    @Slot(int, str)
    def handle_apply_template_to_slide(self, slide_index: int, template_name: str):
        """
        Applies a named layout template to the selected slide(s), handling text content remapping.
        """
        print(f"DEBUG MainWindow: handle_apply_template_to_slide called for slide_index: {slide_index}, template_name: '{template_name}'")

        if not hasattr(self.template_manager, 'resolve_layout_template'):
            self.show_error_message("Error: Template system (resolve_layout_template) is not available.")
            return

        new_layout_structure = self.template_manager.resolve_layout_template(template_name)
        if not new_layout_structure:
            self.show_error_message(f"Could not resolve Layout Template '{template_name}'.")
            return
        
        # Check if the new template defines any text boxes. This is crucial.
        # new_layout_structure.get("text_boxes") might be None or an empty list.
        if not new_layout_structure.get("text_boxes"): # Also covers if "text_boxes" key is missing
            self.show_error_message(f"Layout Template '{template_name}' defines no text boxes. Cannot apply.")
            return

        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot apply template: Slide index {slide_index} is invalid.")
            return
        
        # Get the instance_id for the primary slide being affected (for single or first of multi)
        # This will be used by the command.
        target_slide_data_for_command = slides[slide_index]
        instance_id_for_command = target_slide_data_for_command.id

        # Determine which slides to apply the template to
        selected_indices_to_apply = self.get_selected_slide_indices()
        if not selected_indices_to_apply or slide_index not in selected_indices_to_apply:
            selected_indices_to_apply = [slide_index] # Apply to the clicked one if not part of multi-selection

        # Get new_tb_ids from the resolved layout structure
        new_tb_ids = [tb.get("id") for tb in new_layout_structure.get("text_boxes", []) if tb.get("id")]
        # new_tb_ids should not be empty here due to the check above, but defensive programming is good.
        if not new_tb_ids: # Should be caught by the earlier check on new_layout_structure.get("text_boxes")
             self.show_error_message(f"Layout Template '{template_name}' has text box entries but no valid IDs. Cannot apply lyrics.")
             return

        # --- Multi-Slide Application ---
        if len(selected_indices_to_apply) > 1:
            # Check if all selected slides currently use the same layout template.
            first_slide_data_for_check = slides[selected_indices_to_apply[0]]
            # Get the layout name from the first selected slide's template_settings.
            # It's None if template_settings is None or 'layout_name' key is missing.
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
                return # Abort the operation

            # --- If all slides share the same layout, proceed with remapping dialog or auto-map for the batch ---
            # Get old_text_content from the *first* selected slide for dialog setup purposes.
            # Its structure is representative of all selected slides in this scenario.
            first_selected_slide_data = slides[selected_indices_to_apply[0]]
            old_settings_first_slide = first_selected_slide_data.template_settings
            old_text_content_for_dialog_multi = {}
            if old_settings_first_slide and isinstance(old_settings_first_slide.get("text_content"), dict):
                old_text_content_for_dialog_multi = old_settings_first_slide["text_content"]
            elif first_selected_slide_data.lyrics: # Fallback for the first slide if it has legacy lyrics
                old_text_content_for_dialog_multi = {"legacy_lyrics": first_selected_slide_data.lyrics}

            old_tb_ids_set_multi = set(old_text_content_for_dialog_multi.keys())
            # new_tb_ids_set is already calculated from new_tb_ids at the start of the function
            new_tb_ids_set = set(new_tb_ids)

            show_remapping_dialog_multi = False
            user_mapping_from_dialog = None # To store mapping from dialog: {"new_id": "old_id_source"}

            if old_text_content_for_dialog_multi: # Only if there's something to remap (based on the first slide)
                if old_tb_ids_set_multi != new_tb_ids_set:
                    show_remapping_dialog_multi = True
            
            if show_remapping_dialog_multi:
                print(f"DEBUG MainWindow: Multi-slide - Showing TemplateRemappingDialog based on first selected slide.")
                remapping_dialog = TemplateRemappingDialog(old_text_content_for_dialog_multi, new_tb_ids, self)
                if remapping_dialog.exec():
                    user_mapping_from_dialog = remapping_dialog.get_remapping()
                else: # User cancelled dialog
                    QMessageBox.information(self, "Template Change Cancelled", "Template application was cancelled for multiple slides.")
                    return # Abort

            # Now, iterate through each selected slide and apply the template
            # using user_mapping_from_dialog (if dialog was shown) or auto-mapping rules.
            for idx_to_apply in selected_indices_to_apply:
                if not (0 <= idx_to_apply < len(slides)):
                    print(f"MW Warning: Skipping slide index {idx_to_apply} in multi-apply as it's out of bounds.")
                    continue
                
                slide_data_to_apply = slides[idx_to_apply]
                current_instance_id = slide_data_to_apply.id
                old_template_id_for_cmd = slide_data_to_apply.template_settings.get('layout_name')
                old_content_for_cmd = slide_data_to_apply.template_settings.get('text_content', {})
                
                # Get *this specific slide's* old text content
                current_slide_actual_old_text_content = {}
                if slide_data_to_apply.template_settings and \
                   isinstance(slide_data_to_apply.template_settings.get("text_content"), dict):
                    current_slide_actual_old_text_content = slide_data_to_apply.template_settings["text_content"]
                elif slide_data_to_apply.lyrics: # Fallback for this specific slide
                    current_slide_actual_old_text_content = {"legacy_lyrics": slide_data_to_apply.lyrics}

                # new_template_id is template_name
                final_new_content_for_block = {}

                if user_mapping_from_dialog is not None: # Dialog was shown and mapping obtained
                    for new_id, old_id_source in user_mapping_from_dialog.items():
                        if old_id_source and old_id_source in current_slide_actual_old_text_content:
                            new_settings_for_cmd["text_content"][new_id] = current_slide_actual_old_text_content[old_id_source]
                elif old_text_content_for_dialog_multi and new_tb_ids: # Auto-map (dialog not shown, but old content structure exists)
                    # Apply auto-mapping rules using current_slide_actual_old_text_content
                    if len(old_text_content_for_dialog_multi) == 1 and len(new_tb_ids) == 1:
                        first_old_key = next(iter(old_text_content_for_dialog_multi.keys())) # Key from the representative slide
                        old_content_value_current_slide = current_slide_actual_old_text_content.get(first_old_key, "")
                        final_new_content_for_block[new_tb_ids[0]] = old_content_value_current_slide
                    else: # Try to map by matching ID using current slide's content
                        for new_id_auto in new_tb_ids:
                            if new_id_auto in current_slide_actual_old_text_content:
                                final_new_content_for_block[new_id_auto] = current_slide_actual_old_text_content[new_id_auto]
                    # Fallback for legacy_lyrics if no content was mapped by ID for *this* slide
                    if not final_new_content_for_block and \
                       "legacy_lyrics" in current_slide_actual_old_text_content and new_tb_ids:
                        final_new_content_for_block[new_tb_ids[0]] = current_slide_actual_old_text_content["legacy_lyrics"]
                # else: No old content (from first slide perspective) to map, or no new text boxes.

                print(f"DEBUG_MW_APPLY_TEMPLATE (Multi for instance {current_instance_id}): final_new_content_for_block: {final_new_content_for_block}")
                sys.stdout.flush()
                cmd = ApplyTemplateCommand(
                    self.presentation_manager,
                    current_instance_id,
                    old_template_id_for_cmd,
                    template_name, # new_template_id
                    old_content_for_cmd,
                    final_new_content_for_block
                )
                self.presentation_manager.do_command(cmd)
        
        # --- Single-Slide Application ---
        else:
            current_slide_data = slides[slide_index]
            # For the command
            instance_id_for_single_command = current_slide_data.id
            old_template_id_for_single_command = current_slide_data.template_settings.get('layout_name')
            old_content_for_single_command = current_slide_data.template_settings.get('text_content', {})
            
            old_text_content_for_dialog = {}
            # Use current_slide_data.template_settings here instead of the undefined 'old_settings'
            if current_slide_data.template_settings and isinstance(current_slide_data.template_settings.get("text_content"), dict):
                old_text_content_for_dialog = current_slide_data.template_settings["text_content"]
            elif current_slide_data.lyrics: # Fallback to legacy lyrics if no structured content
                old_text_content_for_dialog = {"legacy_lyrics": current_slide_data.lyrics}

            # Prepare final_template_settings (will be populated based on dialog or auto-mapping)
            final_new_content_dict_single = {}

            # Determine if remapping dialog is needed
            old_tb_ids_set = set(old_text_content_for_dialog.keys())
            new_tb_ids_set = set(new_tb_ids) # new_tb_ids already calculated

            show_remapping_dialog = False
            if old_text_content_for_dialog: # Only if there's something to remap
                # Show dialog if old content exists and the IDs don't perfectly match.
                if old_tb_ids_set != new_tb_ids_set:
                    show_remapping_dialog = True
            
            if show_remapping_dialog:
                remapping_dialog = TemplateRemappingDialog(old_text_content_for_dialog, new_tb_ids, self)
                if remapping_dialog.exec():
                    user_mapping = remapping_dialog.get_remapping()
                    for new_id, old_id_source in user_mapping.items():
                        if old_id_source and old_id_source in old_text_content_for_dialog:
                            final_new_content_dict_single[new_id] = old_text_content_for_dialog[old_id_source]
                else: # User cancelled
                    QMessageBox.information(self, "Template Change Cancelled", "Template application was cancelled.")
                    return # Abort
            # If dialog was not shown (e.g., old_tb_ids_set == new_tb_ids_set, or no old_text_content_for_dialog)
            # We should still try to preserve content if IDs match, or map if it's a simple 1-to-1.
            elif new_tb_ids: # Ensure there are new text boxes to map to
                if old_text_content_for_dialog:
                    # If IDs are the same, just copy the content
                    if old_tb_ids_set == new_tb_ids_set:
                        final_new_content_dict_single = old_text_content_for_dialog.copy()
                    # Simple auto-mapping for 1-to-1 if IDs differ but counts are 1
                    elif len(old_text_content_for_dialog) == 1 and len(new_tb_ids) == 1:
                        old_content_value = next(iter(old_text_content_for_dialog.values()))
                        final_new_content_dict_single[new_tb_ids[0]] = old_content_value
                    else: # More complex, try to map by matching ID if any exist
                        for new_id in new_tb_ids:
                            if new_id in old_text_content_for_dialog:
                                final_new_content_dict_single[new_id] = old_text_content_for_dialog[new_id]
                            # else: no direct match for this new_id, it will be empty

                    # Fallback for "legacy_lyrics" if no content was mapped by ID and it exists
                    if not final_new_content_dict_single and "legacy_lyrics" in old_text_content_for_dialog:
                        final_new_content_dict_single[new_tb_ids[0]] = old_text_content_for_dialog["legacy_lyrics"]
                else: # No old_text_content_for_dialog, so new content will be empty for all new_tb_ids
                    for new_id in new_tb_ids:
                        final_new_content_dict_single[new_id] = ""

            print(f"DEBUG_MW_APPLY_TEMPLATE (Single): final_new_content_dict_single: {final_new_content_dict_single}")
            sys.stdout.flush()

            # new_template_id is template_name
            cmd = ApplyTemplateCommand(
                self.presentation_manager,
                instance_id_for_single_command,
                old_template_id_for_single_command,
                template_name, # new_template_id
                old_content_for_single_command,
                final_new_content_dict_single
            )
            self.presentation_manager.do_command(cmd)

        # The presentation_changed signal from do_command will update the UI.

    #Main Window Utility
    @Slot(int)
    def handle_slide_overlay_label_changed(self, slide_index: int, new_label: str):
        """Handles the center_overlay_label_changed signal from a ScaledSlideButton."""
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            # Determine which slides to apply the label to
            selected_indices_to_apply = self.get_selected_slide_indices()
            # If the right-clicked slide is part of a multi-selection, apply to all selected
            if slide_index not in selected_indices_to_apply or len(selected_indices_to_apply) <= 1:
                 selected_indices_to_apply = [slide_index] # Otherwise, just apply to the clicked one

            # Apply the label change to all determined slides
            # Ideally a MacroCommand, but individual commands for now
            for idx_to_apply in selected_indices_to_apply:
                 if 0 <= idx_to_apply < len(slides):
                     old_label = slides[idx_to_apply].overlay_label
                     instance_id = slides[idx_to_apply].id # Get instance_id
                     cmd = ChangeOverlayLabelCommand(self.presentation_manager, instance_id, old_label, new_label)
                     self.presentation_manager.do_command(cmd)
                     print(f"MainWindow: Overlay label for slide {idx_to_apply} changed to '{new_label}'.")
            # The presentation_changed signal from do_command will update UI.
            # The lines below were redundant if the loop was entered.
            # If the loop wasn't entered (e.g. selected_indices_to_apply was empty, which shouldn't happen here),
            # then 'cmd' might not be defined.
            # self.presentation_manager.do_command(cmd)
            # print(f"MainWindow: Overlay label for slide {slide_index} changed to '{new_label}'. Presentation marked dirty.")

    #Main Window Utility
    @Slot(int, QColor)
    def handle_banner_color_change_requested(self, slide_index: int, color: Optional[QColor]):
        """Handles the banner_color_change_requested signal from a ScaledSlideButton."""
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides() # Get slides to check bounds
        # Determine which slides to apply the color to
        selected_indices_to_apply = self.get_selected_slide_indices()
        # If the right-clicked slide is part of a multi-selection, apply to all selected
        if slide_index not in selected_indices_to_apply or len(selected_indices_to_apply) <= 1:
             selected_indices_to_apply = [slide_index] # Otherwise, just apply to the clicked one

        # Determine if we should suppress signals during the loop
        suppress_signals_during_loop = len(selected_indices_to_apply) > 1

        # Apply the color change to all determined slides
        for idx_to_apply in selected_indices_to_apply:
            if 0 <= idx_to_apply < len(slides): # Check bounds for each index
                # Assuming PresentationManager has a method to set this.
                # This might need to be a command for undo/redo.
                # Pass _suppress_signal=True if we are processing multiple slides
                # When _suppress_signal is True, PM will emit slide_visual_property_changed for each.
                self.presentation_manager.set_slide_banner_color(idx_to_apply, color, _suppress_signal=suppress_signals_during_loop)
        # The PresentationManager already emits slide_visual_property_changed for each slide
        # when _suppress_signal is True. No need for a final generic emit here for banner color.

    #Main Window Utility (might be bad because _from_menu but description is ok but doubble check)
    @Slot(int)
    def handle_next_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id + 1
        if new_selection_index >= num_slides: # Wrap to first
            new_selection_index = 0
        
        if self.slide_ui_manager:
            # SlideUIManager will handle selection and ensuring visibility
            self.slide_ui_manager._handle_manual_slide_selection(new_selection_index)

    #Main Window Utility (might be bad because _from_menu but description is ok but doubble check)
    @Slot(int)
    def handle_previous_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id - 1
        if new_selection_index < 0: # Wrap to last
            new_selection_index = num_slides - 1
        
        if self.slide_ui_manager:
            # SlideUIManager will handle selection and ensuring visibility
            self.slide_ui_manager._handle_manual_slide_selection(new_selection_index)

    def _display_slide(self, index: int):
        slides = self.presentation_manager.get_slides()
        slide_data_to_display: Optional[SlideData] = None

        if 0 <= index < len(slides):
            slide_data_to_display = slides[index]
        else: # Invalid index, effectively blanking
            self._show_blank_on_output()
            return
        # If output window is not visible, but DeckLink might be, still update DeckLink.
        # The OutputTarget's update_slide will handle its own logic.
        # The main_output_target's pixmap_updated is connected to output_window.set_pixmap,
        # so if output_window is hidden, set_pixmap might do nothing or be optimized by Qt.

        print(f"MainWindow: _display_slide called for index {index}, slide_id: {slide_data_to_display.id if slide_data_to_display else 'None'}")

        # Update Main Output Target (if it exists and its window is visible)
        if self.main_output_target and self.output_window.isVisible():
            self.main_output_target.update_slide(slide_data_to_display)
            # Its pixmap_updated signal will call self.output_window.set_pixmap

        # Update DeckLink Output Target (if it exists and DeckLink is active)
        if self.decklink_output_target and self.is_decklink_output_active:
            self.decklink_output_target.update_slide(slide_data_to_display)
            # Its pixmap_updated signal will call self._handle_decklink_target_update

        # Update MainWindow's internal tracking of the "persistent" background
        # This is for UI elements or logic within MainWindow that might need to know
        # what the conceptual background is, separate from what OutputTargets are doing.
        if slide_data_to_display and slide_data_to_display.is_background_slide:
            # To get a representative pixmap for self.current_live_background_pixmap,
            # we can render it once using the main output target's resolution.
            # This is a bit redundant if main_output_target is active, but ensures
            # self.current_live_background_pixmap is correctly sized and rendered.
            width = self.output_resolution.width() # Default to screen output res
            height = self.output_resolution.height()
            if self.main_output_target: # Prefer main target's size if available
                width = self.main_output_target.target_size.width()
                height = self.main_output_target.target_size.height()
            
            # Render standalone to get the background pixmap
            bg_pixmap, _, _ = self.slide_renderer.render_slide(
                slide_data_to_display, width, height, base_pixmap=None, is_final_output=True
            )
            self.current_live_background_pixmap = bg_pixmap.copy() if bg_pixmap and not bg_pixmap.isNull() else None
            self.current_background_slide_id = slide_data_to_display.id
        # If it's a content slide, self.current_live_background_pixmap remains unchanged.
        # If slide_data_to_display is None (blanking), _show_blank_on_output handles clearing these.

    def _show_blank_on_output(self):
        print("MainWindow: _show_blank_on_output called.")
        # Update Main Output Target to blank
        if self.main_output_target and self.output_window.isVisible():
            self.main_output_target.update_slide(None)

        # Update DeckLink Output Target to blank
        if self.decklink_output_target and self.is_decklink_output_active:
            self.decklink_output_target.update_slide(None)

        # Clear MainWindow's internal persistent background tracking
        self.current_live_background_pixmap = None
        self.current_background_slide_id = None

        # If the output window itself needs to be explicitly blanked (e.g., if no target was active)
        if not self.main_output_target and self.output_window.isVisible():
            blank_pixmap = QPixmap(self.output_resolution.width(), self.output_resolution.height())
            blank_pixmap.fill(Qt.GlobalColor.black)
            self.output_window.set_pixmap(blank_pixmap)

    @Slot(QPixmap)
    def _handle_decklink_target_update(self, fill_pixmap: QPixmap):
        """Slot connected to decklink_output_target.pixmap_updated."""
        if not self.is_decklink_output_active or not self.decklink_output_target:
            return

        # The fill_pixmap is the composited output from decklink_output_target
        key_matte_pixmap = self.decklink_output_target.get_key_matte()

        if fill_pixmap.isNull() or not key_matte_pixmap or key_matte_pixmap.isNull():
            print("MainWindow: Error - Fill or Key pixmap is null for DeckLink in _handle_decklink_target_update.")
            return

        # Convert QPixmaps to QImages, then to bytes (existing logic)
        # Ensure correct format for DeckLink
        fill_qimage = fill_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        key_qimage = key_matte_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

        fill_bytes = decklink_handler.get_image_bytes_from_qimage(fill_qimage)
        key_bytes = decklink_handler.get_image_bytes_from_qimage(key_qimage)

        if fill_bytes and key_bytes:
            # print(f"MainWindow: Sending to DeckLink via OutputTarget. Fill size: {len(fill_bytes)}, Key size: {len(key_bytes)}")
            if not decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
                print("MainWindow: decklink_handler.send_external_keying_frames reported FAILURE (via OutputTarget).")
        else:
            print("MainWindow: Error converting pixmaps to bytes for DeckLink (via OutputTarget).")

    
    #Main window Utility 
    def show_error_message(self, message: str):
        QMessageBox.critical(self, "Error", message)

    #Main Window Utility
    def closeEvent(self, event):
        if self.presentation_manager.is_overall_dirty():
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Save)
            if reply == QMessageBox.Save:
                if not self.handle_save(): # handle_save calls handle_save_as if needed
                    event.ignore() # Save failed or was cancelled
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        # Ensure DeckLink is shut down if it was active
        if self.is_decklink_output_active:
            print("MainWindow: Shutting down DeckLink on close.")
            decklink_handler.shutdown_selected_devices()
            decklink_handler.shutdown_sdk()
            self.is_decklink_output_active = False
        # Clean up OutputTargets
        if self.main_output_target:
            self.main_output_target.deleteLater()
        if self.decklink_output_target:
            self.decklink_output_target.deleteLater()
        self.output_window.close()
        self.config_manager.save_all_configs() # Save settings via config manager
        self._save_benchmark_history() # Save benchmark history on close

        # Save window state (including dock widgets)
        window_state = self.saveState().toBase64().data().decode('utf-8')
        self.config_manager.set_app_setting("main_window_state", window_state)
        print("MainWindow: Saved window state.")


        super().closeEvent(event)

    #Main Window Utility
    def showEvent(self, event):
        """Override showEvent to capture benchmark timings when the window is actually shown."""
        # Calculate app_init and mw_show times when the window is first shown
        if self._app_start_time is not None:
            app_start_time = self._app_start_time
            self.benchmark_data_store['app_init'] = time.perf_counter() - app_start_time
            self.benchmark_data_store['mw_show'] = time.perf_counter() - self.mw_init_end_time # Time from end of __init__ to show
            print(f"[BENCHMARK] Application ready (MainWindow.showEvent): {self.benchmark_data_store['app_init']:.4f}s")
            print(f"[BENCHMARK] MainWindow show (from init end to showEvent): {self.benchmark_data_store['mw_show']:.4f}s")
            self._app_start_time = None # Clear temporary storage
        
        # Settings and recent files are loaded by ApplicationConfigManager's constructor.
        # We just need to ensure the UI reflects the loaded state.
        self._update_recent_files_menu() # Ensure menu is up-to-date
        self._load_benchmark_history()

        # Attempt to fix macOS menu bar unresponsiveness on startup by activating in showEvent
        # Use QTimer.singleShot to delay activation slightly, allowing event loop to process show.
        def activate_and_focus_main_window():
            self.raise_()
            self.activateWindow()
            self.setFocus() # Explicitly try to set focus to the MainWindow
            # self.menuBar().update() # Keep this commented for now, can re-introduce if needed

        QTimer.singleShot(50, activate_and_focus_main_window) # Increased delay slightly

        super().showEvent(event)

    #Main Window Utility (maybe extract Benchmarking things to external program)
    def _save_benchmark_history(self):
        """Saves the last presentation benchmark data to a file."""
        data_to_save = {key: self.benchmark_data_store[key] for key in self.benchmark_data_store if key.startswith("last_presentation_")}
        try:
            os.makedirs(BENCHMARK_TEMP_DIR_MW, exist_ok=True) # Ensure the temp directory exists
            with open(BENCHMARK_HISTORY_FILE_PATH_MW, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Saved benchmark history to {BENCHMARK_HISTORY_FILE_PATH_MW}")
        except IOError as e:
            print(f"Error saving benchmark history to {BENCHMARK_HISTORY_FILE_PATH_MW}: {e}")
        except Exception as e:
            print(f"Unexpected error saving benchmark history: {e}")

    #Main Window Utility (maybe extract Benchmarking things to external program)
    def _load_benchmark_history(self):
        """Loads the last presentation benchmark data from a file."""
        if os.path.exists(BENCHMARK_HISTORY_FILE_PATH_MW):
            try:
                with open(BENCHMARK_HISTORY_FILE_PATH_MW, 'r') as f:
                    loaded_data = json.load(f)
                if not isinstance(loaded_data, dict): # Basic validation
                    print(f"Error: Benchmark history file {BENCHMARK_HISTORY_FILE_PATH_MW} does not contain a valid dictionary.")
                    return
                # Update only the relevant keys in the current store
                for key, value in loaded_data.items():
                    if key in self.benchmark_data_store:
                        self.benchmark_data_store[key] = value
                print(f"Loaded benchmark history from {BENCHMARK_HISTORY_FILE_PATH_MW}")
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error loading benchmark history from {BENCHMARK_HISTORY_FILE_PATH_MW}: {e}")
            except Exception as e: # Catch any other unexpected errors during loading/processing
                 print(f"Unexpected error loading benchmark history: {e}")
        else:
            print(f"Benchmark history file not found: {BENCHMARK_HISTORY_FILE_PATH_MW}")

    # Needs to be updated so that when tempates are updated it will retroactively refresh all of the templates in the presentation
    @Slot()
    def on_template_collection_changed(self):
        """
        Called when the TemplateManager signals that the collection of templates has changed.
        This ensures ScaledSlideButtons get the new list of template names for their context menus.
        """
        print("MainWindow: Template collection changed, refreshing slide display.")
        if self.slide_ui_manager:
            self.slide_ui_manager.refresh_slide_display()

    # This was modified alot when making could be funky
    def eventFilter(self, watched_object, event):
        # This is where key events will go if a child (like a button) doesn't handle them
        # and focus is on the QScrollArea (for keyboard navigation).
        if watched_object == self.scroll_area:
            if event.type() == QEvent.Type.KeyPress:
                # Delegate to SlideUIManager's event filter if it's managing the scroll_area
                if self.slide_ui_manager and hasattr(self.slide_ui_manager, 'eventFilter'):
                    return self.slide_ui_manager.eventFilter(watched_object, event)

        return super().eventFilter(watched_object, event) # Pass on unhandled events/objects
    
    @Slot(QPoint)
    def _handle_slide_panel_custom_context_menu(self, local_pos: QPoint):
        """Delegates to SlideUIManager."""
        if self.slide_ui_manager:
            self.slide_ui_manager._handle_slide_panel_custom_context_menu(local_pos)

    #Main Window Structure
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        # Set a theme-aware background color for the menu bar to make it more distinct
        # menu_bar.setStyleSheet("QMenuBar { background-color: palette(button); }") # EXPERIMENT: Comment out
        
        # File Menu
        file_menu = menu_bar.addMenu("File")
        load_action = file_menu.addAction("Load")
        load_action.triggered.connect(lambda: self.handle_load(filepath=None)) # Ensure filepath is None
        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.handle_save)
        save_as_action = file_menu.addAction("Save As...")
        save_as_action.triggered.connect(self.handle_save_as)
        
        new_action = file_menu.addAction("New")
        new_action.triggered.connect(self.handle_new)
        # Edit Menu
        # Removed Import submenu and ProPresenter import action

        file_menu.addSeparator()
        self.recent_files_menu = file_menu.addMenu("Recents") # Store as instance member
        self._update_recent_files_menu() # Initial population
        file_menu.addSeparator()
        edit_menu = menu_bar.addMenu("Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.triggered.connect(self.handle_undo)
        undo_action.setShortcut("Ctrl+Z") # Add standard shortcut
        redo_action = edit_menu.addAction("Redo")
        redo_action.triggered.connect(self.handle_redo)
        
        # Presentation Menu
        presentation_menu = menu_bar.addMenu("Presentation")
        go_live_action = presentation_menu.addAction("Go Live")
        go_live_action.triggered.connect(self.toggle_live)
        # Renamed "Add Song" to "Add New Section"
        add_song_action = presentation_menu.addAction("Add New Section")
        add_song_action.triggered.connect(self.handle_add_new_section) # Connect to new handler
        # Keep it disabled as in the toolbar
        add_song_action.setEnabled(True) # Enable this feature now
        add_song_action.setToolTip("Add a new song or content section to the presentation.")

        # Settings Menu (New)
        settings_menu = menu_bar.addMenu("Settings")
        open_settings_action = settings_menu.addAction("Open Settings...")
        open_settings_action.triggered.connect(self.handle_open_settings)

        # View Menu (for toggling panels)
        view_menu = menu_bar.addMenu("View")
        toggle_section_manager_action = view_menu.addAction("Section Manager")
        toggle_section_manager_action.triggered.connect(self._toggle_section_manager_panel)

        # Developer Menu (New)
        current_prod_mode = self.config_manager.get_app_setting("production_mode", "Developer")

        # Only show the Developer menu if in Developer mode
        if current_prod_mode == "Developer":
            dev_menu = menu_bar.addMenu("Developer")

            # The "Mode" submenu is removed as it's handled in SettingsWindow.
            # If you had other Developer-specific menu items that selected the mode,
            # they would also be removed or rethought.

            # Add "Enable Hover Debug" directly to the Developer menu
            dev_menu.addSeparator()
            self.enable_hover_debug_action = dev_menu.addAction("Enable Hover Debug")
            self.enable_hover_debug_action.setCheckable(True)
            # Set checked state based on whether debugger is already active
            self.enable_hover_debug_action.setChecked(self.hover_debugger_instance is not None)
            self.enable_hover_debug_action.toggled.connect(self._toggle_hover_debugger)
        return menu_bar
    #Main Window Utility (add function to clear recents)
    def _update_recent_files_menu(self):
        """Clears and repopulates the 'Recents' submenu."""
        if not hasattr(self, 'recent_files_menu') or self.recent_files_menu is None:
            # This can happen if called before create_menu_bar (e.g., during init if load_recent_files is too early)
            # Or if the menu bar structure changes unexpectedly.
            print("Warning: 'recent_files_menu' attribute not found or is None. Cannot update recents menu.")
            return

        self.recent_files_menu.clear() # Clear existing actions
        current_recent_files = self.config_manager.get_recent_files()
        if not current_recent_files:
            self.recent_files_menu.setEnabled(False)
            return

        self.recent_files_menu.setEnabled(True)
        for filepath in current_recent_files:
            action = self.recent_files_menu.addAction(os.path.basename(filepath)) # Display just the filename
            action.triggered.connect(lambda checked, path=filepath: self._load_recent_file_action(path)) # Use lambda to pass argument
    
    #doubble check to see if it does the dirty check 
    def handle_new(self):
        """
        Starts a new presentation.  If there are unsaved changes, prompts the user to save.
        """
        if self.presentation_manager.is_overall_dirty():
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before starting a new presentation?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save) # Default to Save
            if reply == QMessageBox.Save:
                if not self.handle_save():  # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return

        # Clear the current presentation (or load a blank one)
        if self.slide_ui_manager:
            self.slide_ui_manager.preview_pixmap_cache.clear()
        self.presentation_manager.clear_presentation()
        # Reset the window title to reflect a new, unsaved presentation
        self.setWindowTitle("Plucky Presentation - New Presentation")
        # If you wish to force a save immediately to a new file you could do the following (uncomment).
        # But I do not recommend forcing it. Let the user decide when to save:

    #Fancy speed boost function make sure it's well structures to keep it fast
    @Slot(list)
    def _handle_slide_visual_property_change(self, updated_indices: list[int]):
        """
        Handles changes to visual properties of specific slides without a full UI rebuild.
        'updated_indices' is a list of slide indices that were modified.
        """
        # This is now handled by SlideUIManager's own slot connected to this signal.
        # print(f"MainWindow: _handle_slide_visual_property_change for indices: {updated_indices} - (Delegated to SlideUIManager)")
        pass

        # if not self.handle_save_as():
        #     # Optionally, warn the user if even the 'Save As...' was cancelled.
        #     QMessageBox.warning(self, "Action Cancelled", "New presentation cancelled.")

        # The event filter on QScrollArea should handle Left/Right.
        #super().keyPressEvent(event)
        
    @Slot(bool)
    def _toggle_hover_debugger(self, checked: bool):
        if checked and not self.hover_debugger_instance:
            self.hover_debugger_instance = MouseHoverDebugger(parent=QApplication.instance())
            QApplication.instance().installEventFilter(self.hover_debugger_instance)
            print("MainWindow: Hover debugger ENABLED.")
        elif not checked and self.hover_debugger_instance:
            QApplication.instance().removeEventFilter(self.hover_debugger_instance)
            self.hover_debugger_instance.deleteLater() # Proper cleanup
            self.hover_debugger_instance = None
            print("MainWindow: Hover debugger DISABLED.")
        sys.stdout.flush()

    def _determine_insertion_context(self, global_pos: QPoint) -> Dict[str, Any]:
        """Delegates to SlideUIManager."""
        if self.slide_ui_manager:
            return self.slide_ui_manager._determine_insertion_context(global_pos)
        # Fallback if SlideUIManager is not available (should not happen in normal operation)
        return {"action_on_slide_instance_id": None, "target_section_id_for_slide_insert": None,
                "target_arrangement_name_for_slide_insert": None, "index_in_arrangement_for_slide_insert": 0,
                "manifest_index_for_new_section_insert": 0}

    # Probably needs to be updated to the new ways (make a generalized function for making slides and sections)
    def _prompt_for_song_title_and_insert_blank_slide(self, insertion_index: int):
        """Prompts for a song title and inserts a new blank slide (using Default Layout)."""
        song_title, ok = QInputDialog.getText(self, "Start New Song",
                                              "Enter title for the new song (leave blank for untitled):",
                                              text="")
        if ok:
            final_song_title = song_title.strip() if song_title.strip() else None
            # Check if "Default Layout" is available
            if "Default Layout" not in self.template_manager.get_layout_names():
                QMessageBox.warning(self, "Template Missing",
                                    "'Default Layout' template not found. Cannot add new song slide.")
                return
            # This needs to be adapted. The old method inserted into a flat list.
            # Now we need section context. This method is likely deprecated or needs significant rework.
            self.show_error_message("Function '_prompt_for_song_title_and_insert_blank_slide' needs update for section-based structure.")

    # Main window utility
    def _handle_insert_slide_from_layout(self,
                                         layout_name_to_apply: str,
                                         target_section_id_in_manifest: str,
                                         target_arrangement_name: str,
                                         insert_at_index_in_arrangement: int):
        """Delegates to SlideUIManager."""
        print(f"MW: _handle_insert_slide_from_layout(layout='{layout_name_to_apply}', section_id='{target_section_id_in_manifest}', arr='{target_arrangement_name}', index={insert_at_index_in_arrangement})")
        if self.slide_ui_manager:
            self.slide_ui_manager._handle_insert_slide_from_layout_action(
                layout_name_to_apply, target_section_id_in_manifest,
                target_arrangement_name, insert_at_index_in_arrangement
            )

    #Main window utility
    @Slot(int, str)
    def _handle_insert_slide_from_button_context_menu(self, after_slide_id: int, layout_name: str):
        """Delegates to SlideUIManager."""
        if self.slide_ui_manager:
            self.slide_ui_manager._handle_insert_slide_from_button_context_menu(after_slide_id, layout_name)

    #Probably remove due to new generic and song setup
    @Slot(int)
    def _handle_insert_new_section_from_button_context_menu(self, after_slide_id: int):
        """Delegates to SlideUIManager."""
        if self.slide_ui_manager:
            self.slide_ui_manager._handle_insert_new_section_from_button_context_menu(after_slide_id)

    #Main window Structure
    def _show_insert_slide_context_menu(self, global_pos: QPoint):
        """Delegates to SlideUIManager if the context menu is for the slide panel background."""
        # This was originally connected to slide_buttons_widget.customContextMenuRequested
        # SlideUIManager now handles this directly.
        # If MainWindow needs to show other global context menus, this method could be adapted.
        # For now, assuming SlideUIManager handles its own context menu.
        pass

    # probably remove or change due to new generic and song setup
    def _prompt_and_insert_new_section(self, manifest_insertion_index: int):
        """
        Prompts for a new section title, creates a new section file using SectionFactory,
        and adds it to the presentation manifest at the specified index.
        """
        new_section_title_str, ok = QInputDialog.getText(
            self,
            "Create New Section",
            "Enter title for the new section (leave blank for an untitled section):",
            text=""  # Start with empty text
        )

        if ok:
            cleaned_section_title = new_section_title_str.strip()
            if not cleaned_section_title: # If title is empty after stripping, make it "Untitled Section"
                cleaned_section_title = f"Untitled Section {uuid.uuid4().hex[:4]}"

            section_file_id = f"section_{uuid.uuid4().hex}"
            
            # Use SectionFactory to create the data
            new_section_data = SectionFactory.create_new_section_data(
                title=cleaned_section_title,
                section_file_id=section_file_id,
                section_type="Generic" # Context menu is generic
            )
            try:
                from core.plucky_standards import PluckyStandards
            except ImportError:
                from plucky_standards import PluckyStandards
            central_sections_dir = PluckyStandards.get_sections_dir()
            
            full_filepath, section_filename = SectionFactory.save_new_section_file(
                new_section_data, cleaned_section_title, self.presentation_manager.io_handler, central_sections_dir
            )

            if full_filepath and section_filename:
                self.presentation_manager.add_section_to_presentation(
                    section_filename, manifest_insertion_index, desired_arrangement_name="Default"
                )
                self.set_status_message(f"New section '{cleaned_section_title}' created and added at specified position.", 3000)
            else:
                self.show_error_message(f"Failed to create and save new section '{cleaned_section_title}'.")


    #Main Window Utility
    @Slot()
    def handle_undo(self):
        print("MainWindow: Undo action triggered.")
        self.presentation_manager.undo()

    #Main Window Utility
    @Slot()
    def handle_redo(self):
        print("MainWindow: Redo action triggered.")
        self.presentation_manager.redo()
    
    #Main Window window spawn
    @Slot()
    def handle_open_settings(self):
        """Opens the settings dialog."""
        current_target_screen = self.config_manager.get_target_output_screen()
        # Pass current DeckLink selection to the settings window
        settings_dialog = SettingsWindow(
            benchmark_data=self.benchmark_data_store,
            current_output_screen=current_target_screen,
            current_decklink_fill_index=self.decklink_fill_device_idx, # Pass current fill index
            current_decklink_key_index=self.decklink_key_device_idx,   # Pass current key index
            current_decklink_video_mode=self.current_decklink_video_mode_details, # Pass current video mode
            config_manager=self.config_manager, # Pass the config manager
            template_manager=self.template_manager, # Pass the template manager

            parent=self
        )
        settings_dialog.output_monitor_changed.connect(self._handle_settings_monitor_changed)
        # Connect to the new signal that emits both fill and key indices
        # We will get all settings when the dialog is accepted.
        # settings_dialog.decklink_fill_key_devices_selected.connect(self._handle_decklink_devices_changed_from_settings)
        settings_dialog.production_mode_changed_signal.connect(self._handle_production_mode_setting_changed)

        if settings_dialog.exec() == QDialog.DialogCode.Accepted:
            print("MainWindow: Settings dialog accepted.")
            # Retrieve and apply DeckLink device settings
            fill_idx, key_idx = settings_dialog.get_selected_decklink_devices()
            if fill_idx is not None and key_idx is not None:
                self.decklink_fill_device_idx = fill_idx
                self.decklink_key_device_idx = key_idx
                self.config_manager.set_app_setting("decklink_fill_device_index", fill_idx)
                self.config_manager.set_app_setting("decklink_key_device_index", key_idx)
                print(f"  Applied DeckLink devices - Fill: {fill_idx}, Key: {key_idx}")

            # Retrieve and apply DeckLink video mode
            video_mode = settings_dialog.get_selected_video_mode()
            if video_mode:
                self.current_decklink_video_mode_details = video_mode
                self.config_manager.set_app_setting("decklink_video_mode_details", video_mode)
                print(f"  Applied DeckLink video mode: {video_mode.get('name', 'Unknown')}")
            else: # No video mode selected or available
                self.current_decklink_video_mode_details = None
                self.config_manager.set_app_setting("decklink_video_mode_details", None)
                print("  No DeckLink video mode applied/selected.")
        else:
            print("MainWindow: Settings dialog cancelled. No changes applied from dialog.")
            # Optionally, could reload from config_manager here to ensure state consistency if needed,
            # but current attributes should still hold their pre-dialog values.
        
        # Disconnect after use to prevent issues if dialog is reopened or multiple instances exist
        try:
            settings_dialog.output_monitor_changed.disconnect(self._handle_settings_monitor_changed)
            
            settings_dialog.production_mode_changed_signal.disconnect(self._handle_production_mode_setting_changed)
            # settings_dialog.decklink_fill_key_devices_selected.disconnect(self._handle_decklink_devices_changed_from_settings) # No longer connected
        except RuntimeError: # In case signals were already disconnected or dialog closed unexpectedly
            pass

    #Main Window Utility
    @Slot(dict)
    def _load_recent_file_action(self, filepath: str):
        """Handler for clicking a recent file action in the menu."""
        print(f"Loading recent file: {filepath}")
        # Call the handle_load method with the specific filepath
        self.handle_load(filepath=filepath)

    #Main Window Utility
    def _handle_editor_save_request(self, templates_collection: dict):
        
        """
        Handles the templates_save_requested signal from the TemplateEditorWindow.
        This allows saving templates without closing the editor.
        """
        print(f"MainWindow: Received save request from template editor with data: {templates_collection.keys()}")
        self.template_manager.update_from_collection(templates_collection)
        # Optionally, provide feedback to the user, e.g., via a status bar or a brief message.
        # For now, the print statement and the TemplateManager's own save confirmation (if any) will suffice.

    #Main Window Utility (Maybe integrate with plucky standards)
    @Slot(QScreen)
    def _handle_settings_monitor_changed(self, selected_screen: QScreen):
        """Handles the output_monitor_changed signal from the SettingsWindow."""
        
        self.config_manager.set_target_output_screen(selected_screen)
        print(f"MainWindow: Target output monitor setting updated to {selected_screen.name()} via settings dialog.")
        # If already live, you might want to move the output window, or just apply on next "Go Live"
        
    #Main Window Utility
    def get_setting(self, key: str, default_value=None):
        """
        Provides a way for other components (like SlideRenderer) to get settings
        managed or known by MainWindow.
        """
        if key == "display_checkerboard_for_transparency":
            return self.config_manager.get_app_setting(key, True) # Default to True
        return self.config_manager.get_app_setting(key, default_value)
        
    @Slot(str)
    def _handle_production_mode_setting_changed(self, new_mode: str):
        """
        Slot to react to production mode changes from the settings window.
        MainWindow can update its behavior or inform other components if needed.
        Rebuilds the menu bar to reflect changes in available developer tools.
        """
        print(f"MainWindow: Detected production mode change to '{new_mode}'.")
        # Rebuild the menu bar to show/hide developer options
        # This is crucial for the "Enable Hover Debug" to appear/disappear
        self.setMenuBar(self.create_menu_bar())

    # This slot is no longer needed as the mode selection is not in MainWindow's menu bar.
    # @Slot(str)
    # def _handle_prod_mode_menu_selection(self, mode_name: str):
    #     pass # Functionality moved to SettingsWindow

    
    # --- Drag and Drop for Background Slides ---
    def dragEnterEvent(self, event: QDragEnterEvent): # Added type hint
        # The SlideDragDropHandler will inspect mimeData and decide to accept.
        # MainWindow delegates to SlideUIManager's drag_drop_handler.
        if self.slide_ui_manager and self.slide_ui_manager.drag_drop_handler:
            self.slide_ui_manager.drag_drop_handler.dragEnterEvent(event)
        else:
            event.ignore() # No handler, ignore.


    def dragMoveEvent(self, event: QDragMoveEvent): # Added type hint
        # Delegate to the handler. It's responsible for:
        # 1. Checking if it can handle the event.mimeData().
        # 2. Calling event.acceptProposedAction() or event.ignore().
        # 3. Updating the self.drop_indicator if a slide (PLUCKY_SLIDE_MIME_TYPE) is being reordered.
        if self.slide_ui_manager and self.slide_ui_manager.drag_drop_handler:
            self.slide_ui_manager.drag_drop_handler.dragMoveEvent(event)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent): # Added type hint
        # Delegate to the handler. It should hide the drop_indicator.
        if self.slide_ui_manager and self.slide_ui_manager.drag_drop_handler:
            self.slide_ui_manager.drag_drop_handler.dragLeaveEvent(event)
        # No else: event.ignore() here, as the default behavior is usually fine for leave events.

    def dropEvent(self, event: QDropEvent): # Added type hint
        # Delegate to the handler. It's responsible for:
        # 1. Processing the drop (reordering slide or adding image).
        # 2. Hiding the self.drop_indicator.
        if self.slide_ui_manager and self.slide_ui_manager.drag_drop_handler:
            self.slide_ui_manager.drag_drop_handler.dropEvent(event)
        else:
            event.ignore()
    # --- Slots for SectionManagementPanel signals ---
    @Slot()
    def _refresh_section_management_panel(self):
        if hasattr(self, 'section_management_panel') and self.section_management_panel:
            self.section_management_panel.refresh_sections_list()

    @Slot(str, int)
    def _handle_request_reorder_section(self, section_id_in_manifest: str, direction: int):
        # Find current index
        current_idx = -1
        manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
        for i, sec_entry in enumerate(manifest_sections):
            if sec_entry["id"] == section_id_in_manifest:
                current_idx = i
                break
        if current_idx == -1: return

        new_idx = current_idx + direction
        if 0 <= new_idx < len(manifest_sections):
            # TODO: Create ReorderSectionCommand
            self.presentation_manager.reorder_sections_in_manifest(section_id_in_manifest, new_idx)

    @Slot(str)
    def _handle_request_remove_section(self, section_id_in_manifest: str):
        reply = QMessageBox.question(self, "Remove Section",
                                     "Are you sure you want to remove this section from the presentation?\n(The section file itself will not be deleted from your computer.)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # TODO: Create RemoveSectionCommand
            self.presentation_manager.remove_section_from_presentation(section_id_in_manifest)

    @Slot()
    def _handle_request_add_existing_section(self):
        default_load_path = self.config_manager.get_default_sections_path()
        filepath, _ = QFileDialog.getOpenFileName(self, "Add Existing Section", default_load_path, "Plucky Section Files (*.plucky_section);;All Files (*)")
        if filepath:
            section_filename = os.path.basename(filepath) # PM expects simple filename for central store
            # TODO: Create AddExistingSectionCommand or adapt add_section_to_presentation
            num_current_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
            self.presentation_manager.add_section_to_presentation(section_filename, num_current_sections)

    def _toggle_section_manager_panel(self):
        if self.section_management_dock.isVisible():
            self.section_management_dock.hide()
        else:
            self.section_management_dock.show()

    @Slot()
    def _handle_request_create_new_section_from_panel(self):
        """Handles request from SectionManagementPanel to create and add a new section."""
        section_types = ["Song", "Generic Content"]
        chosen_type, ok_type = QInputDialog.getItem(self, "Select Section Type", "What type of section do you want to create?", section_types, 0, False)

        if not ok_type:
            return # User cancelled type selection

        section_title_text, ok_title = QInputDialog.getText(
            self,
            f"Create New {chosen_type} Section",
            f"Enter the title for the new {chosen_type.lower()} section:"
        )

        id_prefix = "song" if chosen_type == "Song" else "generic"

        if not ok_title or not section_title_text.strip():
            if ok_title and not section_title_text.strip():
                QMessageBox.warning(self, "Empty Title", "Section title cannot be empty.")
            return
        
        cleaned_section_title = section_title_text.strip()

        section_file_id = f"{id_prefix}_{uuid.uuid4().hex}" # Use type prefix for ID

        # Use SectionFactory to create the data
        new_section_data = SectionFactory.create_new_section_data(
            title=cleaned_section_title,
            section_file_id=section_file_id,
            section_type=chosen_type
        )

        try:
            from core.plucky_standards import PluckyStandards
        except ImportError:
            from plucky_standards import PluckyStandards

        central_sections_dir = PluckyStandards.get_sections_dir()
        
        full_filepath, section_filename = SectionFactory.save_new_section_file(
            new_section_data, cleaned_section_title, self.presentation_manager.io_handler, central_sections_dir
        )

        if full_filepath and section_filename:
            num_current_sections = len(self.presentation_manager.presentation_manifest_data.get("sections", [])) if self.presentation_manager.presentation_manifest_data else 0
            self.presentation_manager.add_section_to_presentation(section_filename, num_current_sections, desired_arrangement_name="Default")