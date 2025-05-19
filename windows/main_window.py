import sys
import os
import json # Needed for saving/loading benchmark history
import copy # Needed for deepcopy when applying templates
# import uuid # For generating unique slide IDs for testing - Unused

from PySide6.QtWidgets import ( # type: ignore
    QApplication, QMainWindow, QFileDialog, QSlider, QMenuBar, # Added QMenuBar
    QMessageBox, QVBoxLayout, QWidget, QPushButton, QInputDialog, QSpinBox,
    QComboBox, QLabel, QHBoxLayout, QSplitter, QScrollArea, QDialog, QMenu
)
from PySide6.QtGui import (
    QScreen, QPixmap, QColor, QContextMenuEvent, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QImage
) # Added specific QDrag...Event types and QImage
from PySide6.QtCore import Qt, QSize, Slot, QEvent, QStandardPaths, QPoint, QRect, QMimeData # Added QRect, QContextMenuEvent, QMimeData

from typing import Optional # Import Optional for type hinting
from PySide6.QtWidgets import QFrame # For the drop indicator
from windows.settings_window import SettingsWindow # Import the new settings window
# --- Local Imports ---
# Make sure these paths are correct relative to where you run main.py
try:
    # Assuming running from the YourProject directory
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData # DEFAULT_TEMPLATE is no longer used here
    from rendering.slide_renderer import SlideRenderer
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
    from core.slide_edit_handler import SlideEditHandler # Import the new handler
    # --- Undo/Redo Command Imports ---
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand
    )
except ImportError:
    # Fallback if running directly from the windows directory (adjust as needed)
    # import sys, os # Already imported at top level
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from windows.output_window import OutputWindow
    from data_models.slide_data import SlideData # DEFAULT_TEMPLATE is no longer used here
    from rendering.slide_renderer import SlideRenderer
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
    from core.slide_edit_handler import SlideEditHandler # Import the new handler
    # --- Undo/Redo Command Imports ---
    from commands.slide_commands import (
        ChangeOverlayLabelCommand, EditLyricsCommand, AddSlideCommand, DeleteSlideCommand, ApplyTemplateCommand
    )

# Import DeckLink handler for sending frames (ensure this is available in your project)
import decklink_handler # Assuming decklink_handler.py is at the Plucky project root
import time


BASE_PREVIEW_WIDTH = 160
# BASE_PREVIEW_HEIGHT is now in core.constants

# Determine project root dynamically for benchmark history file
SCRIPT_DIR_MW = os.path.dirname(os.path.abspath(__file__)) # /windows
PROJECT_ROOT_MW = os.path.dirname(SCRIPT_DIR_MW) # /Plucky
BENCHMARK_TEMP_DIR_MW = os.path.join(PROJECT_ROOT_MW, "temp")
BENCHMARK_HISTORY_FILE_PATH_MW = os.path.join(BENCHMARK_TEMP_DIR_MW, ".pluckybenches.json")




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        mw_init_start_time = time.perf_counter()
        self.mw_init_end_time = 0.0 # Will be set at the end of __init__

        self.setWindowTitle("Plucky Presentation")
        # DeckLink related instance variables
        self.current_decklink_idx = -1 # Default to no device selected or load from config
        # Other DeckLink attributes will be initialized after config_manager

        self.setGeometry(100, 100, 900, 700) # Adjusted size for more controls

        # MainWindow can have focus, but scroll_area is more important for this.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus) 

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
        self.output_window = OutputWindow()
        self.slide_renderer = SlideRenderer(app_settings=self) # Pass MainWindow as settings provider
        self.presentation_manager = PresentationManager() # Assuming this is already here
        self.presentation_manager.presentation_changed.connect(self.update_slide_display_and_selection)
        self.presentation_manager.slide_visual_property_changed.connect(self._handle_slide_visual_property_change) # New connection
        self.presentation_manager.error_occurred.connect(self.show_error_message)

        # Instantiate the SlideEditHandler
        self.slide_edit_handler = SlideEditHandler(self.presentation_manager, self)
        self.button_scale_factor = 1.0 # Default scale
        self._selected_slide_indices: Set[int] = set() # New: Set to store indices of selected slides

        self.current_slide_index = -1 # Tracks the selected slide button's index
        self.output_resolution = QSize(1920, 1080) # Default, updated on monitor select
        self.slide_buttons_list = [] # List to store ScaledSlideButton instances
        self.preview_pixmap_cache: Dict[str, QPixmap] = {} # Cache for scaled preview pixmaps (slide_id -> QPixmap)

        
        self.current_live_background_pixmap: QPixmap | None = None
        self.current_background_slide_id: Optional[str] = None # ID of the active background slide

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

        # Preview Size Spinbox (replaces slider)
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

        # --- Connections ---
        # Connections for load, save, save_as, add_song are now handled by menu actions
        self.edit_template_button.clicked.connect(self.handle_edit_template) # Connect Edit Templates button
        self.undo_button.clicked.connect(self.handle_undo) # New
        self.redo_button.clicked.connect(self.handle_redo) # New
        # self.test_decklink_button.clicked.connect(self._send_decklink_test_frame) # Disconnect DL test button
        self.preview_size_spinbox.valueChanged.connect(self.handle_preview_size_change) # Connect spinbox signal
        self.decklink_output_toggle_button.clicked.connect(self.toggle_decklink_output_stream) # New connection

        self.go_live_button.clicked.connect(self.toggle_live)

        self.update_slide_display_and_selection() # Initial setup of slide display
        
        # Install event filter directly on the QScrollArea.
        self.scroll_area.installEventFilter(self)
        # Ensure QScrollArea can receive focus.
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Enable Drag and Drop on the main window (or a specific widget like scroll_area)
        self.setAcceptDrops(True)

        # Instantiate the SlideDragDropHandler
        self.drag_drop_handler = SlideDragDropHandler(
            main_window=self,
            presentation_manager=self.presentation_manager,
            scroll_area=self.scroll_area,
            slide_buttons_widget=self.slide_buttons_widget,
            slide_buttons_layout=self.slide_buttons_layout,
            drop_indicator=self.drop_indicator,
            parent=self
        )
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

    def set_status_message(self, message: str, timeout: int = 0):
        """
        Displays a message on the status bar.
        A timeout of 0 means the message will remain indefinitely
        until cleared or replaced.
        """
        self.statusBar().showMessage(message, timeout)

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
                return
            
            if not self.current_decklink_video_mode_details:
                QMessageBox.critical(self, "DeckLink Error", "Video mode not configured. Please select a video mode in Settings.")
                self.decklink_output_toggle_button.setChecked(False)
                self._decklink_output_button_state = "error" # Or "off" if preferred
                self._update_decklink_output_button_appearance()
                return
            
            decklink_handler.enumerate_devices()
            
            if not decklink_handler.initialize_selected_devices(self.decklink_fill_device_idx, self.decklink_key_device_idx, self.current_decklink_video_mode_details):
                decklink_handler.shutdown_sdk() # Clean up SDK
                self.decklink_output_toggle_button.setChecked(False) # Revert button state
                self._decklink_output_button_state = "error"
                self._update_decklink_output_button_appearance()
                return
            
            self.is_decklink_output_active = True
            self._decklink_output_button_state = "on"
            print("MainWindow: DeckLink output stream started successfully.")
            # If a slide is currently live on screen, send it to DeckLink
            if self.output_window.isVisible() and 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):
                self._display_slide(self.current_slide_index)
            else: # Send blank to DeckLink
                self._show_blank_on_output() # This will also send blank to DL if active

        else: # User wants to turn DeckLink OFF
            print("MainWindow: Shutting down DeckLink output stream.")
            if self.is_decklink_output_active: # Check if it was actually active
                # Send one last blank frame to DeckLink before shutting down
                black_image = QImage(decklink_handler.DLL_WIDTH, decklink_handler.DLL_HEIGHT, QImage.Format_ARGB32_Premultiplied)
                black_image.fill(QColor(0,0,0,255))
                fill_bytes = decklink_handler.get_image_bytes_from_qimage(black_image)
                if fill_bytes: # Check if conversion was successful
                    decklink_handler.send_external_keying_frames(fill_bytes, fill_bytes) # Send black to both fill and key

                decklink_handler.shutdown_selected_devices()
                decklink_handler.shutdown_sdk()
            self.is_decklink_output_active = False
            self._decklink_output_button_state = "off"
            print("MainWindow: DeckLink output stream stopped.")

        self._update_decklink_output_button_appearance()

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

    def toggle_live(self):
        target_screen = self.config_manager.get_target_output_screen()

        if self.output_window.isVisible():
            self.go_live_button.setChecked(False)
            self._show_blank_on_output() # Good practice to blank it before hiding
            self.output_window.hide() # Explicitly hide the window
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
            self.output_window.showFullScreen()
            if 0 <= self.current_slide_index < len(self.presentation_manager.get_slides()):
                self._display_slide(self.current_slide_index)
            else:
                self._show_blank_on_output()
        self._update_go_live_button_appearance()

    def handle_add_song(self):
        """
        Prompts the user for song lyrics and adds them as new slides.
        Lyrics are split into slides by double newlines.
        """
        song_title_text, ok_title = QInputDialog.getText(
            self,
            "Add New Song - Title",
            "Enter the song title:"
        )

        if not ok_title or not song_title_text.strip():
            # User cancelled or entered an empty title
            if ok_title and not song_title_text.strip(): # User pressed OK but title was empty
                QMessageBox.warning(self, "Empty Title", "Song title cannot be empty.")
            return
        
        cleaned_song_title = song_title_text.strip()

        lyrics_text, ok_lyrics = QInputDialog.getMultiLineText(
            self,
            f"Add Lyrics for \"{cleaned_song_title}\"",
            "Paste or type song lyrics below.\n"
            "Use a blank line (press Enter twice) to separate slides/stanzas."
        )

        if ok_lyrics and lyrics_text:
            # Split by one or more blank lines (effectively \n\n or more \n's)
            stanzas = [s.strip() for s in lyrics_text.split('\n\n') if s.strip()]

            if not stanzas:
                QMessageBox.information(self, "No Stanzas", "No stanzas found. Ensure you use blank lines to separate them.")
                return
            new_slides_data = []
            
            for stanza_lyrics in stanzas:
                # For new songs, apply the "Default Layout" template.
                # Ensure your TemplateManager has a "Default Layout" or handle its absence.
                default_layout_settings = {}
                if hasattr(self.template_manager, 'resolve_layout_template'):
                    default_layout_settings = self.template_manager.resolve_layout_template("Default Layout")
                if not default_layout_settings or not default_layout_settings.get("text_boxes"):
                    print("MainWindow: Warning - Could not resolve 'Default Layout' or it's invalid. New slide will have basic settings.")
                    default_layout_settings = {"layout_name": "Default Layout", "text_boxes": [], "text_content": {}} # Basic fallback
                # Map the stanza lyrics to the first text box of the default layout
                if default_layout_settings.get("text_boxes"):
                    first_tb_id = default_layout_settings["text_boxes"][0].get("id")
                    if first_tb_id:
                        default_layout_settings.setdefault("text_content", {})[first_tb_id] = stanza_lyrics
                new_slide = SlideData(lyrics=stanza_lyrics, 
                                      song_title=cleaned_song_title,
                                      overlay_label="", # Default for new song slides
                                      template_settings=default_layout_settings)
                new_slides_data.append(new_slide)
            
            # For multiple slides, you might create a "MacroCommand" or execute individual AddSlideCommands
            # or we create multiple commands. Here, we'll just call the PM method.
            self.presentation_manager.add_slides(new_slides_data) # This won't be a single undo step

    def handle_load(self, filepath: Optional[str] = None):
        """
        Loads a presentation from a file. Prompts to save unsaved changes.
        If filepath is provided, loads that file directly; otherwise, opens a file dialog.
        """
        if self.presentation_manager.is_dirty and filepath is None: # Only prompt if loading via dialog
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before loading new file?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.handle_save(): # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        if filepath is None: # If no filepath was provided, open the dialog
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Presentation", "", "Plucky Files (*.plucky *.json);;All Files (*)")

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
            self.preview_pixmap_cache.clear() # Clear preview cache when loading a new presentation
            self.presentation_manager.load_presentation(filepath)
            load_pm_duration = time.perf_counter() - load_pm_start_time
            self.benchmark_data_store["last_presentation_pm_load"] = load_pm_duration
            print(f"[BENCHMARK] PresentationManager.load_presentation() took: {load_pm_duration:.4f} seconds for {filepath}")
            # After UI update (triggered by presentation_changed), explicitly mark as not dirty
            # The actual UI update (update_slide_display_and_selection) will be benchmarked separately.
            self.presentation_manager.is_dirty = False
            self.config_manager.add_recent_file(filepath) # Add to recents list on successful load


    def handle_save(self) -> bool:
        if not self.presentation_manager.current_filepath:
            return self.handle_save_as()
        else:
            filepath = self.presentation_manager.current_filepath
            if self.presentation_manager.save_presentation(filepath):
                # Optionally add status bar message: "Presentation saved."
                self.config_manager.add_recent_file(filepath) # Add to recents list on successful save
                return True
            # Error message handled by show_error_message via signal
            # If save failed, don't add to recents
            print(f"Error saving presentation to {filepath}")
            return False

    def handle_save_as(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Presentation As...", self.presentation_manager.current_filepath or os.getcwd(), "Plucky Files (*.plucky *.json);;All Files (*)")
        if filepath:
            if self.presentation_manager.save_presentation(filepath):
                # Optionally add status bar message: "Presentation saved to {filepath}."
                self.config_manager.add_recent_file(filepath) # Add to recents list on successful save as
                return True
            # Error message handled by show_error_message via signal
            return False
        # User cancelled dialog, don't add to recents
        return False # User cancelled dialog

    @Slot() # No longer receives an int directly from the signal
    def handle_preview_size_change(self, value: int):
        """Handles the valueChanged signal from the preview size spinbox."""
        self.button_scale_factor = float(value)  # Use the integer value directly as the scale factor (1x, 2x, etc.)
        self.preview_pixmap_cache.clear() # Preview sizes changed, invalidate cache
        # This will trigger a full rebuild of the slide buttons with the new scale
        self.update_slide_display_and_selection()

    def handle_edit_template(self):
        # TemplateManager ensures "Default" always exists, so no need for the "No Templates" check here.

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

    @Slot()
    def update_slide_display_and_selection(self):
        """
        Clears and repopulates slide buttons. Manages selection.
        Called when presentation_manager.presentation_changed is emitted.
        """
        print("MainWindow: update_slide_display_and_selection called")
        ui_update_start_time = time.perf_counter()
        
        # Preserve the ID of the currently singly selected slide if possible
        # Multi-selection state is reset on UI rebuild for simplicity
        old_single_selected_slide_id_str: Optional[str] = None # Store slide_data.id (string)
        if self.current_slide_index != -1 and len(self._selected_slide_indices) == 1:
            # Get the ID of the currently selected slide *before* clearing slides or buttons
            # This requires getting slides from PM *before* it might change due to other operations
            # For simplicity, let's assume PM.get_slides() is stable here or get it from current_slide_index
            slides_before_rebuild = self.presentation_manager.get_slides()
            if 0 <= self.current_slide_index < len(slides_before_rebuild):
                old_single_selected_slide_id_str = slides_before_rebuild[self.current_slide_index].id

        # Clear existing buttons and selection state
        self._selected_slide_indices.clear() # Clear selection on UI rebuild
        self.current_slide_index = -1 # Reset single selection index
        
        # Initialize accumulators for detailed render timings
        total_aggregated_render_time = 0.0
        total_aggregated_image_time = 0.0
        total_aggregated_font_time = 0.0
        total_aggregated_layout_time = 0.0
        total_aggregated_draw_time = 0.0
        # old_selected_slide_index = self.current_slide_index # No longer needed, using old_single_selected_slide_id_str
        # Clear existing buttons first
        while self.slide_buttons_layout.count():
            item = self.slide_buttons_layout.takeAt(0) # Item from the main QVBoxLayout
            widget_in_vbox = item.widget()
            if widget_in_vbox:
                # If it's a container QWidget holding a FlowLayout for slides
                if isinstance(widget_in_vbox.layout(), FlowLayout):
                    flow_layout_inside = widget_in_vbox.layout()
                    while flow_layout_inside.count():
                        flow_item = flow_layout_inside.takeAt(0)
                        slide_button_widget = flow_item.widget()
                        if slide_button_widget:
                            # No need to remove from QButtonGroup as we are not using it for these
                            # Disconnect signals if they were connected
                            try:
                                slide_button_widget.slide_selected.disconnect(self._handle_manual_slide_selection)
                            except (TypeError, RuntimeError): pass # If not connected or already gone
                            try:
                                slide_button_widget.toggle_selection_requested.disconnect(self._handle_toggle_selection)
                            except (TypeError, RuntimeError): pass
                            # Child widgets of widget_in_vbox will be deleted when widget_in_vbox is deleted
                            # No need to call deleteLater on slide_button_widget explicitly here
                            # as long as it's properly parented to widget_in_vbox or its layout.
                
                # For SongHeaderWidget, QLabel, or the container QWidget itself
                widget_in_vbox.setParent(None)
                widget_in_vbox.deleteLater()
        self.slide_buttons_list.clear() # Clear our manual list

        slides = self.presentation_manager.get_slides()

        if not slides:
            no_slides_label = QLabel("No slides. Use 'Load' or 'Add Song'.")
            no_slides_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slide_buttons_layout.addWidget(no_slides_label)
            self.current_slide_index = -1
            self._show_blank_on_output()
            return

        # Use a sentinel that's guaranteed not to match any actual title (including None)
        last_processed_title: Optional[str] = object() 
        current_song_flow_layout: Optional[FlowLayout] = None

        print(f"  update_slide_display_and_selection: Found {len(slides)} slides to process.")

        # Calculate dynamic preview dimensions based on scale factor
        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)

        for index, slide_data in enumerate(slides):
            current_title = slide_data.song_title # This can be None or a string

            if current_title != last_processed_title:
                # This is a new song, or a transition to/from an untitled block of slides
                last_processed_title = current_title
                
                if current_title is not None: # It's a titled song
                    song_header = SongHeaderWidget(current_title, current_button_width=current_dynamic_preview_width)
                    song_header.edit_song_requested.connect(self.handle_edit_song_title_requested)
                    self.slide_buttons_layout.addWidget(song_header) # Add header to main VBox
                # else:
                    # If current_title is None, we don't add a specific header for "untitled"
                    # but we still create a new FlowLayout container below.

                # Create a new container QWidget and FlowLayout for this group of slides
                song_slides_container = QWidget()
                # Pass the container as the parent to FlowLayout, it will set itself as layout
                current_song_flow_layout = FlowLayout(song_slides_container, margin=5, hSpacing=5, vSpacing=5)
                # song_slides_container.setLayout(current_song_flow_layout) # Not needed if parent passed to FlowLayout
                self.slide_buttons_layout.addWidget(song_slides_container) # Add container to main VBox

            # --- Process and create the ScaledSlideButton ---
            # print(f"    Processing slide {index}, ID: {slide_data.id}, Lyrics: '{slide_data.lyrics[:30].replace('\n', ' ')}...'") # DEBUG
            # (Ensure current_song_flow_layout is valid before adding buttons to it)
            preview_render_width = self.output_resolution.width() if self.output_window.isVisible() else 1920
            preview_render_height = self.output_resolution.height() if self.output_window.isVisible() else 1080
            
            slide_id_str = slide_data.id # Assuming slide_data has a unique 'id' attribute
            has_font_error = False # Default

            if slide_id_str in self.preview_pixmap_cache:
                cached_pixmap = self.preview_pixmap_cache[slide_id_str]
                # Check if cached pixmap size matches current required preview size
                if cached_pixmap.width() == current_dynamic_preview_width and \
                   cached_pixmap.height() == current_dynamic_preview_height:
                    preview_pixmap = cached_pixmap
                    # We don't have font error info from cache, might need to store it too or accept this limitation
                    # For now, assume no error if from cache, or re-evaluate if this is critical
                    print(f"      Using cached preview for slide {index} (ID {slide_id_str})") # DEBUG
                else:
                    # Cached pixmap is stale due to size change, remove it and re-render
                    del self.preview_pixmap_cache[slide_id_str]
                    preview_pixmap = None # Signal to re-render
            else:
                preview_pixmap = None # Not in cache, needs rendering

            if preview_pixmap is None: # Needs rendering
                try:
                    full_res_pixmap, has_font_error, slide_benchmarks = self.slide_renderer.render_slide(
                        slide_data, preview_render_width, preview_render_height, is_final_output=False
                    )
                    total_aggregated_render_time += slide_benchmarks.get("total_render", 0.0)
                    total_aggregated_image_time += slide_benchmarks.get("images", 0.0)
                    total_aggregated_font_time += slide_benchmarks.get("fonts", 0.0)
                    total_aggregated_layout_time += slide_benchmarks.get("layout", 0.0)
                    total_aggregated_draw_time += slide_benchmarks.get("draw", 0.0)
                    
                    preview_pixmap = full_res_pixmap.scaled(current_dynamic_preview_width, current_dynamic_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.preview_pixmap_cache[slide_id_str] = preview_pixmap # Add to cache
                    print(f"      Rendered and cached preview for slide {index} (ID {slide_id_str})") # DEBUG
                except Exception as e: # Catch general rendering exceptions
                    print(f"      ERROR rendering preview for slide {index} (ID {slide_data.id}): {e}")
                    has_font_error = True 
                    preview_pixmap = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height)
                    preview_pixmap.fill(Qt.darkGray)

            button = ScaledSlideButton(slide_id=index, plucky_slide_mime_type=PLUCKY_SLIDE_MIME_TYPE) # Pass MIME type
            button.set_pixmap(preview_pixmap)
            # Explicitly reset icon state for each button before checking for errors
            button.set_icon_state("error", False)
            button.set_icon_state("warning", False) # Also reset warning if you have one
            # Set the slide number and label for the banner
            button.set_is_background_slide(slide_data.is_background_slide) # Tell the button its type first

            # All slides now get a sequential number.
            # Background slides will also have "BG" as their label.
            # Content slides will have an empty label (just showing the number).
            current_label_for_banner = "BG" if slide_data.is_background_slide else ""
            button.set_slide_info(number=index + 1, label=current_label_for_banner)

            button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
            button.toggle_selection_requested.connect(self._handle_toggle_selection) # Connect new signal
            button.slide_selected.connect(self._handle_manual_slide_selection) # Connect to our new manual handler
            button.edit_requested.connect(self.slide_edit_handler.handle_edit_slide_requested) # Connect to the handler
            button.delete_requested.connect(self.handle_delete_slide_requested)

            # For background slides, the "Edit Lyrics" might be less relevant,
            # and "Apply Template" might also behave differently or be disabled.
            # For now, we'll leave them, but this is an area for future refinement.

            # Set the banner color from SlideData
            if hasattr(slide_data, 'banner_color') and slide_data.banner_color:
                button.set_banner_color(QColor(slide_data.banner_color))
            else:
                button.set_banner_color(None) # Reset to default if not set or None
            # Get layout template names for the context menu
            layout_template_names_list = []
            if hasattr(self.template_manager, 'get_layout_names'): # Use existing method
                layout_template_names_list = self.template_manager.get_layout_names()
            else:
                print("MainWindow: WARNING - TemplateManager does not have 'get_layout_template_names'. Context menu for templates will be empty.")

            button.set_available_templates(layout_template_names_list)
            button.apply_template_to_slide_requested.connect(self.handle_apply_template_to_slide)
            # print(f"DEBUG MainWindow: Connected apply_template_to_slide_requested for button {index} to handle_apply_template_to_slide.") # Keep print if desired, remove connection object capture
            # button.next_slide_requested_from_menu.connect(self.handle_next_slide_from_menu) # Removed as per UI change
            button.insert_slide_from_layout_requested.connect(self._handle_insert_slide_from_button_context_menu) # New connection
            # button.previous_slide_requested_from_menu.connect(self.handle_previous_slide_from_menu) # Removed as per UI change
            button.center_overlay_label_changed.connect(self.handle_slide_overlay_label_changed) # New connection
            button.banner_color_change_requested.connect(self.handle_banner_color_change_requested) # New connection

            if has_font_error:
                button.set_icon_state("error", True)
            
            if current_song_flow_layout: # Add button to the current song's FlowLayout
                current_song_flow_layout.addWidget(button)
            # self.slide_button_group.addButton(button, index) # DO NOT ADD TO QButtonGroup
            self.slide_buttons_list.append(button) # Add to our manual list
        # Prune cache: Remove entries for slide IDs that no longer exist
        current_slide_ids = {s.id for s in slides}
        cached_ids_to_remove = [cached_id for cached_id in self.preview_pixmap_cache if cached_id not in current_slide_ids]
        for stale_id in cached_ids_to_remove:
            del self.preview_pixmap_cache[stale_id]
            print(f"      Pruned stale ID {stale_id} from preview cache.") # DEBUG
        
        # Add a stretch at the end of the main QVBoxLayout to push everything up
        self.slide_buttons_layout.addStretch(1)
        # Add a stretch at the end of the main QVBoxLayout to push everything up
        self.slide_buttons_layout.addStretch(1)

        # After creating all buttons, set their overlay labels from SlideData
        self._update_all_button_overlay_labels()
        
        # --- 2. Manage Selection ---
        # Re-establish selection based on the preserved single selection ID

        num_slides = len(slides)
        # Find the index corresponding to the old_single_selected_id
        new_single_selected_index = -1
        if old_single_selected_slide_id_str is not None:
            # Iterate through current slides to find the one with the matching ID
            for index, slide_data in enumerate(slides):
                if slide_data.id == old_single_selected_slide_id_str:
                    new_single_selected_index = index
                    break # Found the slide, stop searching

        # If the old single selection ID was found at a valid new index, select it
        if new_single_selected_index != -1:
            # Find the button in our list
            button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_single_selected_index), None)
            if button_to_select: # If found
                # Trigger our manual selection handler. It will check the button and uncheck others.
                # We don't call the handler directly here because it clears selection.
                # Instead, manually set the state after rebuild.
                self._selected_slide_indices.add(new_single_selected_index)
                self.current_slide_index = new_single_selected_index
                button_to_select.setChecked(True) # Set the button's checked state
                # Update output for the re-selected slide
                if self.output_window.isVisible():
                    self._display_slide(new_single_selected_index)
                # Ensure it's visible
                self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50) # Ensure visibility
            else: # Button for the target index not found (should not happen if list is consistent)
                self.current_slide_index = -1
                self._show_blank_on_output()
        elif num_slides > 0: # No previous selection, but slides exist, select the first one
            self._handle_manual_slide_selection(0) # Select the first slide (ID 0)
            if self.slide_buttons_list:
                 self.scroll_area.ensureWidgetVisible(self.slide_buttons_list[0], 50, 50)
                 # _handle_manual_slide_selection already sets checked state and updates output
        else: # No slides, no selection
            self.current_slide_index = -1
            self._show_blank_on_output()
        
        ui_update_duration = time.perf_counter() - ui_update_start_time
        # Store the UI update and aggregated render times in the global benchmark data
        self.benchmark_data_store["last_presentation_ui_update"] = ui_update_duration
        self.benchmark_data_store["last_presentation_render_total"] = total_aggregated_render_time
        self.benchmark_data_store["last_presentation_render_images"] = total_aggregated_image_time
        self.benchmark_data_store["last_presentation_render_fonts"] = total_aggregated_font_time
        self.benchmark_data_store["last_presentation_render_layout"] = total_aggregated_layout_time
        self.benchmark_data_store["last_presentation_render_draw"] = total_aggregated_draw_time

        print(f"[BENCHMARK] update_slide_display_and_selection() took: {ui_update_duration:.4f} seconds for {len(slides)} slides.")
        if slides: # Only print aggregated if there were slides to render
            print(f"  [BENCHMARK_AGGREGATE] Total time spent in SlideRenderer (all previews):")
            print(f"    Overall Render: {total_aggregated_render_time:.4f}s")
            print(f"    Image Processing: {total_aggregated_image_time:.4f}s")
            print(f"    Font Setup:     {total_aggregated_font_time:.4f}s")
            print(f"    Text Layout:    {total_aggregated_layout_time:.4f}s")
            print(f"    Text Drawing:   {total_aggregated_draw_time:.4f}s")
            
    def get_selected_slide_indices(self) -> list[int]:
        """Returns a list of the indices of currently selected slides."""
        return list(self._selected_slide_indices)

    def _update_button_checked_states(self):
        """Updates the visual checked state of all buttons based on _selected_slide_indices."""
        for button_widget in self.slide_buttons_list:
            button_widget.setChecked(button_widget._slide_id in self._selected_slide_indices)

    @Slot(int)
    def _handle_toggle_selection(self, slide_index: int):
        """
        Handles Ctrl+Click on a slide button to toggle its selection state.
        Does NOT deselect other buttons.
        """
        print(f"MainWindow: _handle_toggle_selection for slide_index {slide_index}")
        
        if slide_index in self._selected_slide_indices:
            self._selected_slide_indices.remove(slide_index)
            print(f"  Deselected slide {slide_index}. Current selection: {self._selected_slide_indices}")
            # If the slide we just deselected was the *only* one selected,
            # the output should probably go blank or show the previously singly selected slide.
            # For simplicity, let's keep the output on the last *singly* selected slide,
            # or blank if nothing is selected. The output doesn't change on multi-select toggle.
        else:
            self._selected_slide_indices.add(slide_index)
            print(f"  Selected slide {slide_index}. Current selection: {self._selected_slide_indices}")
            # Output window does NOT update on multi-select toggle.

        # Update the visual state of all buttons
        self._update_button_checked_states()

    @Slot(int)
    def _handle_manual_slide_selection(self, selected_slide_index: int):
        """
        Handles a single click on a slide button. Clears multi-selection
        and selects only the clicked slide. Updates output.
        """
        print(f"MainWindow: _handle_manual_slide_selection for slide_index {selected_slide_index}")
        
        # Clear any existing multi-selection
        self._selected_slide_indices.clear() # Clear any multi-selection
        self._selected_slide_indices.add(selected_slide_index) # Add the clicked slide
        # Determine if actual changes were made
        # This is a bit more complex now. We need to compare dictionaries.
        # A simple way: check if the new dictionary is different from the old one.
        # Or, if the dialog used the "legacy_lyrics" key, compare that.
        
        content_changed = False
        new_legacy_lyrics_from_dialog: Optional[str] = None
        self.current_slide_index = selected_slide_index # Update our tracking variable

        # Update the visual state of all buttons
        self._update_button_checked_states()

        # Update output window
        if self.output_window.isVisible():
            self._display_slide(selected_slide_index)
        
        # Ensure the scroll area has focus for keyboard navigation
        self.scroll_area.setFocus()
        print(f"MainWindow: UI updated for slide {selected_slide_index}. Focus on scroll_area.")


    def _update_all_button_overlay_labels(self):
        """Sets the overlay label on each button based on its corresponding SlideData."""
        slides = self.presentation_manager.get_slides()
        for index, slide_data in enumerate(slides):
            # Find button in our list
            button = next((btn for btn in self.slide_buttons_list if btn._slide_id == index), None)
            if button and isinstance(button, ScaledSlideButton):
                # Pass the overlay_label from SlideData to the button
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

    # The handle_edit_slide_requested method has been moved to SlideEditHandler

    @Slot(int)
    def handle_delete_slide_requested(self, slide_index: int):
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides()
        if not (0 <= slide_index < len(slides)):
            self.show_error_message(f"Cannot delete slide: Index {slide_index} is invalid.")
            return

        selected_indices_to_delete = list(self._selected_slide_indices) # Get a copy of current selection

        # If the right-clicked slide is part of a multi-selection, delete all selected
        if slide_index in selected_indices_to_delete and len(selected_indices_to_delete) > 1:
            reply = QMessageBox.question(self, 'Delete Slides',
                                         f"Are you sure you want to delete {len(selected_indices_to_delete)} selected slides?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                # Delete in reverse order to avoid index shifts affecting subsequent deletions
                for idx in sorted(selected_indices_to_delete, reverse=True):
                    cmd = DeleteSlideCommand(self.presentation_manager, idx)
                    self.presentation_manager.do_command(cmd) # Each deletion is a separate undo step for now
                self._selected_slide_indices.clear() # Clear selection after deletion
        else: # Single delete (either only one selected, or right-clicked an unselected slide)
            # Ensure slide_data is fetched for the specific slide_index for the confirmation message
            slide_data = slides[slide_index] # This was missing in the multi-delete path
            reply = QMessageBox.question(self, 'Delete Slide',
                                         f"Are you sure you want to delete this slide?\n\nLyrics: \"{slide_data.lyrics[:50]}...\"",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                cmd = DeleteSlideCommand(self.presentation_manager, slide_index)
                self.presentation_manager.do_command(cmd)

    @Slot(str)
    def handle_edit_song_title_requested(self, original_song_title_to_edit: str):
        """Handles request to edit a song's title."""
        if not hasattr(self, '_selected_slide_indices'): # Safety check
            self._selected_slide_indices = set()

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

        # Determine which slides to apply the template to
        selected_indices_to_apply = list(self._selected_slide_indices)
        if slide_index not in selected_indices_to_apply or len(selected_indices_to_apply) <= 1:
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
                    print(f"Warning: Skipping slide index {idx_to_apply} in multi-apply as it's out of bounds.")
                    continue
                
                slide_data_to_apply = slides[idx_to_apply]
                old_settings_for_cmd = slide_data_to_apply.template_settings # This slide's old settings
                
                # Get *this specific slide's* old text content
                current_slide_actual_old_text_content = {}
                if slide_data_to_apply.template_settings and \
                   isinstance(slide_data_to_apply.template_settings.get("text_content"), dict):
                    current_slide_actual_old_text_content = slide_data_to_apply.template_settings["text_content"]
                elif slide_data_to_apply.lyrics: # Fallback for this specific slide
                    current_slide_actual_old_text_content = {"legacy_lyrics": slide_data_to_apply.lyrics}

                new_settings_for_cmd = copy.deepcopy(new_layout_structure)
                new_settings_for_cmd.setdefault("text_content", {})

                if user_mapping_from_dialog is not None: # Dialog was shown and mapping obtained
                    for new_id, old_id_source in user_mapping_from_dialog.items():
                        if old_id_source and old_id_source in current_slide_actual_old_text_content:
                            new_settings_for_cmd["text_content"][new_id] = current_slide_actual_old_text_content[old_id_source]
                elif old_text_content_for_dialog_multi and new_tb_ids: # Auto-map (dialog not shown, but old content structure exists)
                    # Apply auto-mapping rules using current_slide_actual_old_text_content
                    if len(old_text_content_for_dialog_multi) == 1 and len(new_tb_ids) == 1:
                        first_old_key = next(iter(old_text_content_for_dialog_multi.keys())) # Key from the representative slide
                        old_content_value_current_slide = current_slide_actual_old_text_content.get(first_old_key, "")
                        new_settings_for_cmd["text_content"][new_tb_ids[0]] = old_content_value_current_slide
                    else: # Try to map by matching ID using current slide's content
                        for new_id_auto in new_tb_ids:
                            if new_id_auto in current_slide_actual_old_text_content:
                                new_settings_for_cmd["text_content"][new_id_auto] = current_slide_actual_old_text_content[new_id_auto]
                    # Fallback for legacy_lyrics if no content was mapped by ID for *this* slide
                    if not new_settings_for_cmd["text_content"] and \
                       "legacy_lyrics" in current_slide_actual_old_text_content and new_tb_ids:
                        new_settings_for_cmd["text_content"][new_tb_ids[0]] = current_slide_actual_old_text_content["legacy_lyrics"]
                # else: No old content (from first slide perspective) to map, or no new text boxes.
                # new_settings_for_cmd["text_content"] will be empty or partially filled based on above.

                cmd = ApplyTemplateCommand(self.presentation_manager, idx_to_apply, old_settings_for_cmd, new_settings_for_cmd)
                self.presentation_manager.do_command(cmd)
        
        # --- Single-Slide Application ---
        else:
            current_slide_data = slides[slide_index]
            old_settings = current_slide_data.template_settings
            
            old_text_content_for_dialog = {}
            if old_settings and isinstance(old_settings.get("text_content"), dict):
                old_text_content_for_dialog = old_settings["text_content"]
            elif current_slide_data.lyrics: # Fallback to legacy lyrics if no structured content
                old_text_content_for_dialog = {"legacy_lyrics": current_slide_data.lyrics}

            # Prepare final_template_settings (will be populated based on dialog or auto-mapping)
            final_template_settings = copy.deepcopy(new_layout_structure)
            final_template_settings.setdefault("text_content", {}) # Ensure it exists

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
                            final_template_settings["text_content"][new_id] = old_text_content_for_dialog[old_id_source]
                else: # User cancelled
                    QMessageBox.information(self, "Template Change Cancelled", "Template application was cancelled.")
                    return # Abort
            
            elif old_text_content_for_dialog and new_tb_ids: # Auto-map if no dialog needed but old content and new boxes exist
                # Simple auto-mapping:
                if len(old_text_content_for_dialog) == 1 and len(new_tb_ids) == 1:
                    # If only one old content source and one new box, map it.
                    old_content_value = next(iter(old_text_content_for_dialog.values()))
                    final_template_settings["text_content"][new_tb_ids[0]] = old_content_value
                else:
                    # Try to map by matching ID.
                    for new_id in new_tb_ids:
                        if new_id in old_text_content_for_dialog:
                            final_template_settings["text_content"][new_id] = old_text_content_for_dialog[new_id]
                
                # Fallback for legacy_lyrics if no content was mapped by ID:
                # If the old slide only had `slide_data.lyrics` (so `old_text_content_for_dialog` was `{"legacy_lyrics": ...}`)
                # and the new template has text boxes with IDs that don't match "legacy_lyrics",
                # put the legacy_lyrics into the first text box of the new template.
                if not final_template_settings["text_content"] and \
                   "legacy_lyrics" in old_text_content_for_dialog and \
                   new_tb_ids: # new_tb_ids should always be non-empty here
                    final_template_settings["text_content"][new_tb_ids[0]] = old_text_content_for_dialog["legacy_lyrics"]
            # else: No old content to map, or no new text boxes to map to (already checked).
            # final_template_settings["text_content"] will be empty or partially filled.

            cmd = ApplyTemplateCommand(self.presentation_manager, slide_index, old_settings, final_template_settings)
            self.presentation_manager.do_command(cmd)

        # The presentation_changed signal from do_command will update the UI.



    @Slot(int)
    def handle_slide_overlay_label_changed(self, slide_index: int, new_label: str):
        """Handles the center_overlay_label_changed signal from a ScaledSlideButton."""
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides()
        if 0 <= slide_index < len(slides):
            # Determine which slides to apply the label to
            selected_indices_to_apply = list(self._selected_slide_indices)
            # If the right-clicked slide is part of a multi-selection, apply to all selected
            if slide_index not in selected_indices_to_apply or len(selected_indices_to_apply) <= 1:
                 selected_indices_to_apply = [slide_index] # Otherwise, just apply to the clicked one

            # Apply the label change to all determined slides
            # Ideally a MacroCommand, but individual commands for now
            for idx_to_apply in selected_indices_to_apply:
                 if 0 <= idx_to_apply < len(slides):
                     old_label = slides[idx_to_apply].overlay_label
                     cmd = ChangeOverlayLabelCommand(self.presentation_manager, idx_to_apply, old_label, new_label)
                     self.presentation_manager.do_command(cmd)
                     print(f"MainWindow: Overlay label for slide {idx_to_apply} changed to '{new_label}'.")
            # The presentation_changed signal from do_command will update UI.
            # The lines below were redundant if the loop was entered.
            # If the loop wasn't entered (e.g. selected_indices_to_apply was empty, which shouldn't happen here),
            # then 'cmd' might not be defined.
            # self.presentation_manager.do_command(cmd)
            # print(f"MainWindow: Overlay label for slide {slide_index} changed to '{new_label}'. Presentation marked dirty.")

    @Slot(int, QColor)
    def handle_banner_color_change_requested(self, slide_index: int, color: Optional[QColor]):
        """Handles the banner_color_change_requested signal from a ScaledSlideButton."""
        # This slot is called when the context menu action is triggered on a specific button.
        slides = self.presentation_manager.get_slides() # Get slides to check bounds
        # Determine which slides to apply the color to
        selected_indices_to_apply = list(self._selected_slide_indices)
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

    @Slot(int)
    def handle_next_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id + 1
        if new_selection_index >= num_slides: # Wrap to first
            new_selection_index = 0
        
        # Find button in our list
        button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
        if button_to_select:
            # Trigger the full selection logic
            self._handle_manual_slide_selection(new_selection_index)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50) # Ensure visibility

    @Slot(int)
    def handle_previous_slide_from_menu(self, current_slide_id: int):
        num_slides = len(self.presentation_manager.get_slides())
        if num_slides == 0:
            return

        new_selection_index = current_slide_id - 1
        if new_selection_index < 0: # Wrap to last
            new_selection_index = num_slides - 1
        
        # Find button in our list
        button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
        if button_to_select:
            # Trigger the full selection logic
            self._handle_manual_slide_selection(new_selection_index)
            self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50) # Ensure visibility


    def _display_slide(self, index: int): # Original method starts here
        slides = self.presentation_manager.get_slides()
        if not (0 <= index < len(slides)):
            self._show_blank_on_output()
            return
        if not self.output_window.isVisible():
            return

        render_output_start_time = time.perf_counter()
        slide_data = slides[index]
        base_pixmap_for_render = None
        output_width = self.output_resolution.width()
        output_height = self.output_resolution.height()
        
        if slide_data.is_background_slide:
            # This slide IS a background setter. Render it standalone.
            # Its output will become the new self.current_live_background_pixmap.
            base_pixmap_for_render = None # Render standalone
            # Clear the ID of any *content* slide that might have been active
            # (though current_slide_index already points to this BG slide)
        else: # This is a content slide
            # Check if this content slide itself has a transparent background
            is_content_slide_transparent = False
            if not slide_data.background_image_path: # Condition 1: No image path
                if slide_data.background_color is None: # Condition 2a: background_color is explicitly None
                    is_content_slide_transparent = True
                else: # Condition 2b: background_color is a string, check its alpha
                    # Ensure slide_data.background_color is a string before passing to QColor
                    if isinstance(slide_data.background_color, str):
                        slide_bg_qcolor = QColor(slide_data.background_color)
                        if slide_bg_qcolor.isValid() and slide_bg_qcolor.alpha() == 0:
                            is_content_slide_transparent = True
                            
            # Only use the persistent background if the content slide is transparent
            # AND a persistent background is actually set and valid.
            if is_content_slide_transparent and \
               self.current_live_background_pixmap and \
               not self.current_live_background_pixmap.isNull() and \
               self.current_live_background_pixmap.size() == self.output_resolution:
                base_pixmap_for_render = self.current_live_background_pixmap
            else:
                base_pixmap_for_render = None # Render content slide standalone

        try:
            # render_slide now returns (pixmap, has_font_error)
            # For live output, we don't aggregate these individual timings here, but still need to unpack.
            render_result = self.slide_renderer.render_slide(
                 slide_data, output_width, output_height, base_pixmap=base_pixmap_for_render, is_final_output=True
            )
            if len(render_result) == 3: # New renderer with benchmarks
                output_pixmap, has_font_error_on_output, _ = render_result
            else: # Old renderer
                output_pixmap, has_font_error_on_output = render_result
                
            # After rendering, decide if this render should BECOME the new live background
            if slide_data.is_background_slide:
                if output_pixmap and not output_pixmap.isNull():
                    self.current_live_background_pixmap = output_pixmap.copy()
                    self.current_background_slide_id = slide_data.id # Track the ID of the active BG
                else: # Should not happen if rendering was successful
                    self.current_live_background_pixmap = None
                    self.current_background_slide_id = None
            if not output_pixmap.isNull():
                self.output_window.set_pixmap(output_pixmap)
            
            # We don't directly use has_font_error_on_output here, but it's good practice
            # The button icon should already reflect this from the preview rendering.
        except Exception as e:
            print(f"Error rendering slide {index} (ID: {slide_data.id}) for output: {e}")
            error_slide = SlideData(lyrics=f"Error rendering slide:\n{e}", background_color="#AA0000", template_settings={"color": "#FFFFFF"})
            # Render error slide standalone, ignore its font error status and benchmarks for this specific display
            render_result = self.slide_renderer.render_slide(error_slide, output_width, output_height, base_pixmap=None, is_final_output=True)

            if len(render_result) == 3: # New renderer with benchmarks
                error_pixmap, _, _ = render_result
            else: # Old renderer
                error_pixmap, _ = render_result
            if not error_pixmap.isNull():
                self.output_window.set_pixmap(error_pixmap)
            self.show_error_message(f"Error rendering slide {index} (ID: {slide_data.id}): {e}")
        render_output_duration = time.perf_counter() - render_output_start_time

        # --- Send frame to DeckLink if active ---
        if self.is_decklink_output_active and not output_pixmap.isNull():
            # Create a QImage from the pixmap, then make a deep copy
            # to ensure it's independent for DeckLink processing.
            temp_qimage = output_pixmap.toImage()
            decklink_fill_qimage = temp_qimage.copy() # Create a deep copy

            # Ensure the image is scaled to DeckLink's expected resolution
            if (decklink_fill_qimage.width() != decklink_handler.DLL_WIDTH or
                decklink_fill_qimage.height() != decklink_handler.DLL_HEIGHT):
                decklink_fill_qimage = decklink_fill_qimage.scaled(
                    decklink_handler.DLL_WIDTH,
                    decklink_handler.DLL_HEIGHT,
                    Qt.AspectRatioMode.IgnoreAspectRatio, # Or KeepAspectRatioByExpanding and crop
                    Qt.TransformationMode.SmoothTransformation
                )
            
            # Ensure correct format for get_image_bytes_from_qimage
            if decklink_fill_qimage.format() != QImage.Format_ARGB32_Premultiplied:
                decklink_fill_qimage = decklink_fill_qimage.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            
            # --- More detailed check before calling get_image_bytes_from_qimage ---
            if decklink_fill_qimage.isNull():
                print("MainWindow: ERROR - decklink_fill_qimage is NULL before get_image_bytes_from_qimage for slide.")
                fill_bytes = None
            elif decklink_fill_qimage.sizeInBytes() == 0:
                print(f"MainWindow: ERROR - decklink_fill_qimage has zero bytes. Size: {decklink_fill_qimage.width()}x{decklink_fill_qimage.height()}, Format: {decklink_fill_qimage.format()}")
                fill_bytes = None
            else:
                fill_bytes = decklink_handler.get_image_bytes_from_qimage(decklink_fill_qimage)
            
            # --- Generate Key Matte (White text on Black background) ---
            key_bytes = None
            try:
                # Assuming self.slide_renderer has a new method render_key_matte
                # This method should return a QPixmap (white text on black background)
                # at DeckLink resolution.
                key_matte_pixmap = self.slide_renderer.render_key_matte(
                    slide_data, 
                    decklink_handler.DLL_WIDTH, 
                    decklink_handler.DLL_HEIGHT
                )
                if not key_matte_pixmap.isNull():
                    key_matte_qimage = key_matte_pixmap.toImage()
                    if key_matte_qimage.format() != QImage.Format_ARGB32_Premultiplied:
                        key_matte_qimage = key_matte_qimage.convertToFormat(QImage.Format_ARGB32_Premultiplied)
                    
                    if not key_matte_qimage.isNull() and key_matte_qimage.sizeInBytes() > 0:
                        key_bytes = decklink_handler.get_image_bytes_from_qimage(key_matte_qimage)
                    else:
                        print("MainWindow: ERROR - key_matte_qimage is NULL or has zero bytes after conversion/check.")
                else:
                    print("MainWindow: ERROR - render_key_matte returned a NULL pixmap.")
            except AttributeError:
                print("MainWindow: ERROR - self.slide_renderer.render_key_matte method not found. Sending black key.")
            except Exception as e:
                print(f"MainWindow: ERROR during key matte generation: {e}. Sending black key.")

            if key_bytes is None: # Fallback to black key if matte generation failed
                print("MainWindow: Fallback - Key matte generation failed or not implemented, sending black key.")
                black_key_fallback_image = QImage(decklink_handler.DLL_WIDTH, decklink_handler.DLL_HEIGHT, QImage.Format_ARGB32_Premultiplied)
                black_key_fallback_image.fill(QColor(0,0,0,255)) # Opaque black
                key_bytes = decklink_handler.get_image_bytes_from_qimage(black_key_fallback_image)
            
            # This line was duplicated, removing one instance
            # fill_bytes = decklink_handler.get_image_bytes_from_qimage(decklink_fill_qimage) 
            
            if fill_bytes and key_bytes:
                print(f"MainWindow: Attempting to send slide to DeckLink. Fill size: {len(fill_bytes)}, Key size: {len(key_bytes)}")
                if decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
                    print("MainWindow: decklink_handler.send_external_keying_frames reported SUCCESS for slide.")
                else:
                    print("MainWindow: decklink_handler.send_external_keying_frames reported FAILURE for slide.")
            else:
                print(f"MainWindow: ERROR after get_image_bytes - fill_bytes or key_bytes is None. Fill is None: {fill_bytes is None}, Key is None: {key_bytes is None}")

        print(f"[BENCHMARK] _display_slide() for output took: {render_output_duration:.4f} seconds for slide {index}")

    def _show_blank_on_output(self):
        if self.output_window.isVisible():
            blank_slide = SlideData(lyrics="", background_color="#000000")
            # Render blank slide standalone, ignore its font error status and benchmarks
            render_result = self.slide_renderer.render_slide(
                blank_slide, self.output_resolution.width(), self.output_resolution.height(), base_pixmap=None, is_final_output=True
            )
            if len(render_result) == 3: # New renderer
                blank_pixmap, _, _ = render_result
            else: # Old renderer
                blank_pixmap, _ = render_result
            
            if not blank_pixmap.isNull():
                self.output_window.set_pixmap(blank_pixmap)

            # --- Send blank frame to DeckLink if active ---
            if self.is_decklink_output_active:
                # Create a black QImage specifically for DeckLink at its resolution
                decklink_blank_fill_image = QImage(
                    decklink_handler.DLL_WIDTH,
                    decklink_handler.DLL_HEIGHT,
                    QImage.Format_ARGB32_Premultiplied
                )
                decklink_blank_fill_image.fill(QColor(0,0,0,255)) # Opaque black

                if decklink_blank_fill_image.isNull() or decklink_blank_fill_image.sizeInBytes() == 0:
                    print("MainWindow: ERROR - decklink_blank_fill_image is NULL or has zero bytes for BLANK.")
                    fill_bytes = None
                else:
                    fill_bytes = decklink_handler.get_image_bytes_from_qimage(decklink_blank_fill_image)
                
                # Key is also black for a blank output
                if fill_bytes: 
                    key_bytes = fill_bytes 
                else:
                    key_bytes = None 
                
                if fill_bytes and key_bytes:
                    print(f"MainWindow: Attempting to send BLANK to DeckLink. Fill size: {len(fill_bytes)}, Key size: {len(key_bytes)}")
                    if decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
                        print("MainWindow: decklink_handler.send_external_keying_frames reported SUCCESS for BLANK.")
                    else:
                        print("MainWindow: decklink_handler.send_external_keying_frames reported FAILURE for BLANK.")
                else:
                    print(f"MainWindow: ERROR after get_image_bytes - fill_bytes or key_bytes is None for BLANK. Fill is None: {fill_bytes is None}, Key is None: {key_bytes is None}")

        # When showing blank, clear the persistent background
        self.current_live_background_pixmap = None # Clear any persistent background
        self.current_background_slide_id = None
               
    def _show_blank_on_output(self):
        if self.output_window.isVisible():
            blank_slide = SlideData(lyrics="", background_color="#000000")
            # Render blank slide standalone, ignore its font error status and benchmarks
            render_result = self.slide_renderer.render_slide(
                blank_slide, self.output_resolution.width(), self.output_resolution.height(), base_pixmap=None, is_final_output=True
            )
            if len(render_result) == 3: # New renderer
                blank_pixmap, _, _ = render_result
            else: # Old renderer
                blank_pixmap, _ = render_result
            
            if not blank_pixmap.isNull():
                self.output_window.set_pixmap(blank_pixmap)

            # --- Send blank frame to DeckLink if active ---
            if self.is_decklink_output_active:
                # Create a black QImage specifically for DeckLink at its resolution
                decklink_blank_fill_image = QImage(
                    decklink_handler.DLL_WIDTH,
                    decklink_handler.DLL_HEIGHT,
                    QImage.Format_ARGB32_Premultiplied
                )
                decklink_blank_fill_image.fill(QColor(0,0,0,255)) # Opaque black

                if decklink_blank_fill_image.isNull() or decklink_blank_fill_image.sizeInBytes() == 0:
                    print("MainWindow: ERROR - decklink_blank_fill_image is NULL or has zero bytes for BLANK.")
                    fill_bytes = None
                else:
                    fill_bytes = decklink_handler.get_image_bytes_from_qimage(decklink_blank_fill_image)
                
                # Key is also black for a blank output
                # We can reuse fill_bytes if it's guaranteed to be the black frame data
                # or create a separate one for clarity if needed later.
                # For now, if fill_bytes is the black frame, key_bytes can be the same.
                if fill_bytes: # Only assign if fill_bytes was successfully created
                    key_bytes = fill_bytes 
                else:
                    key_bytes = None # Ensure key_bytes is also None if fill_bytes failed
                
                if fill_bytes and key_bytes:
                    print(f"MainWindow: Attempting to send BLANK to DeckLink. Fill size: {len(fill_bytes)}, Key size: {len(key_bytes)}")
                    if decklink_handler.send_external_keying_frames(fill_bytes, key_bytes):
                        print("MainWindow: decklink_handler.send_external_keying_frames reported SUCCESS for BLANK.")
                    else:
                        print("MainWindow: decklink_handler.send_external_keying_frames reported FAILURE for BLANK.")
                else:
                    print(f"MainWindow: ERROR after get_image_bytes - fill_bytes or key_bytes is None for BLANK. Fill is None: {fill_bytes is None}, Key is None: {key_bytes is None}")

        # When showing blank, clear the persistent background
        self.current_live_background_pixmap = None # Clear any persistent background
        self.current_background_slide_id = None

    def show_error_message(self, message: str):
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self.presentation_manager.is_dirty:
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
        self.output_window.close()
        self.config_manager.save_all_configs() # Save settings via config manager
        self._save_benchmark_history() # Save benchmark history on close
        super().closeEvent(event)

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

        super().showEvent(event)

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

    @Slot()
    def on_template_collection_changed(self):
        """
        Called when the TemplateManager signals that the collection of templates has changed.
        This ensures ScaledSlideButtons get the new list of template names for their context menus.
        """
        print("MainWindow: Template collection changed, refreshing slide display.")
        self.update_slide_display_and_selection()

    def eventFilter(self, watched_object, event):
        # This is where key events will go if a child (like a button) doesn't handle them
        # and focus is on the QScrollArea.
        if watched_object == self.scroll_area and event.type() == QEvent.Type.KeyPress:
            if event.type() == QEvent.Type.ContextMenu:
                # Ensure the context menu event is for the slide_buttons_widget area
                # Cast to QContextMenuEvent to access globalPos()
                context_menu_event = QContextMenuEvent(QContextMenuEvent.Type.ContextMenu, event.pos(), event.globalPos(), event.modifiers())
                global_mouse_pos = context_menu_event.globalPos()
                
                # Check if the click is within the bounds of the slide_buttons_widget
                pos_in_viewport = self.scroll_area.viewport().mapFromGlobal(global_mouse_pos)
                if self.scroll_area.viewport().rect().contains(pos_in_viewport):
                    pos_in_slide_buttons_widget = self.slide_buttons_widget.mapFromGlobal(global_mouse_pos)
                    if self.slide_buttons_widget.rect().contains(pos_in_slide_buttons_widget):
                        self._show_insert_slide_context_menu(global_mouse_pos)
                        return True # Event handled
            
            elif event.type() == QEvent.Type.KeyPress:
                # print(f"EventFilter: KeyPress on {watched_object}. Focus: {QApplication.focusWidget()}, Key: {event.key()}") # Can be noisy
                
                if event.isAutoRepeat():
                    return True # Consume auto-repeat events for our navigation keys, do nothing

                key = event.key()

                num_slides = len(self.presentation_manager.get_slides())
                # Ignore navigation keys if Ctrl or Shift is held, to allow default scroll area behavior
                # or future multi-selection range behavior.
                if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                     return super().eventFilter(watched_object, event)

                if num_slides == 0:
                    return super().eventFilter(watched_object, event) # Pass on if no slides

                current_selection_index = self.current_slide_index
                new_selection_index = current_selection_index

                if key == Qt.Key_Right:
                    if current_selection_index == -1 and num_slides > 0:
                        new_selection_index = 0 # Select first if nothing selected
                    elif current_selection_index < num_slides - 1:
                        new_selection_index = current_selection_index + 1
                    elif current_selection_index == num_slides - 1: # Wrap
                        new_selection_index = 0
                    else: # No change in selection logic based on this key, let default happen
                        return super().eventFilter(watched_object, event)
                elif key == Qt.Key_Left:
                    # If current_slide_index is -1, it means no slide is selected.
                    if current_selection_index == -1 and num_slides > 0: # If nothing selected, select last
                        new_selection_index = num_slides - 1
                        print(f"EventFilter ArrowKeyDebug: Left - Was: None, Next: {new_selection_index}")
                    elif current_selection_index > 0:
                        new_selection_index = current_selection_index - 1
                        print(f"EventFilter ArrowKeyDebug: Left - Was: {current_selection_index}, Next: {new_selection_index}")
                    elif current_selection_index == 0 and num_slides > 0: # Wrap
                        new_selection_index = num_slides - 1
                        print(f"EventFilter ArrowKeyDebug: Left - Was: {current_selection_index} (first), Next: {new_selection_index} (wrap)")
                    else: # No change
                        return super().eventFilter(watched_object, event)
                else:
                    # For other keys (like Up/Down for scrolling, Tab), let the scroll area handle them
                    return super().eventFilter(watched_object, event)

                if new_selection_index != current_selection_index or \
                   (current_selection_index == -1 and new_selection_index != -1): # Ensure selection actually changes or initializes
                    # Find button in our list
                    button_to_select = next((btn for btn in self.slide_buttons_list if btn._slide_id == new_selection_index), None)
                    if button_to_select:
                        print(f"EventFilter: Navigating to slide index {new_selection_index} from {current_selection_index}") # DEBUG
                        
                        # Directly call the method that handles all aspects of slide selection.
                        self._handle_manual_slide_selection(new_selection_index)
                        # The handler above already calls setChecked(True) on the target button.
                        self.scroll_area.ensureWidgetVisible(button_to_select, 50, 50)
                    return True # Event handled

        return super().eventFilter(watched_object, event) # Pass on unhandled events/objects
    
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        # Set a theme-aware background color for the menu bar to make it more distinct
        menu_bar.setStyleSheet("QMenuBar { background-color: palette(button); }")
        
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
        
        add_song_action = presentation_menu.addAction("Add Song")
        add_song_action.triggered.connect(self.handle_add_song)
        # Keep it disabled as in the toolbar
        add_song_action.setEnabled(False)
        add_song_action.setToolTip("Temporarily disabled pending multi-textbox feature.")

        # Settings Menu (New)
        settings_menu = menu_bar.addMenu("Settings")
        open_settings_action = settings_menu.addAction("Open Settings...")
        open_settings_action.triggered.connect(self.handle_open_settings)

        return menu_bar
    
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
    
    def handle_new(self):
        """
        Starts a new presentation.  If there are unsaved changes, prompts the user to save.
        """
        if self.presentation_manager.is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before starting a new presentation?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.handle_save():  # If save fails or is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return

        # Clear the current presentation (or load a blank one)
        self.preview_pixmap_cache.clear() # Clear preview cache for a new presentation
        self.presentation_manager.clear_presentation()
        # Reset the window title to reflect a new, unsaved presentation
        self.setWindowTitle("Plucky Presentation - New Presentation")
        # If you wish to force a save immediately to a new file you could do the following (uncomment).
        # But I do not recommend forcing it. Let the user decide when to save:
    
    @Slot(list)
    def _handle_slide_visual_property_change(self, updated_indices: list[int]):
        """
        Handles changes to visual properties of specific slides without a full UI rebuild.
        'updated_indices' is a list of slide indices that were modified.
        """
        print(f"MainWindow: _handle_slide_visual_property_change for indices: {updated_indices}")
        slides = self.presentation_manager.get_slides()
        # Calculate dynamic preview dimensions based on current scale factor
        # This is needed if we are re-rendering previews.
        current_dynamic_preview_width = int(BASE_PREVIEW_WIDTH * self.button_scale_factor)
        current_dynamic_preview_height = int(BASE_PREVIEW_HEIGHT * self.button_scale_factor)
        preview_render_width = self.output_resolution.width() if self.output_window.isVisible() else 1920
        preview_render_height = self.output_resolution.height() if self.output_window.isVisible() else 1080
        for index in updated_indices:
            if 0 <= index < len(self.slide_buttons_list) and 0 <= index < len(slides):
                button = self.slide_buttons_list[index]
                slide_data = slides[index]
                if not isinstance(button, ScaledSlideButton):
                    continue

                # --- Re-render preview pixmap (necessary for template changes) ---
                # This part assumes a template change might have occurred.
                # For simple banner color changes, re-rendering the pixmap is often overkill but included for robustness
                # if this handler is also used for template changes.
                try:
                    full_res_pixmap, has_font_error, _ = self.slide_renderer.render_slide(
                        slide_data, preview_render_width, preview_render_height, is_final_output=False
                    )
                    preview_pixmap = full_res_pixmap.scaled(
                        current_dynamic_preview_width,
                        current_dynamic_preview_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    button.set_pixmap(preview_pixmap)
                    # Update cache with the newly rendered preview
                    self.preview_pixmap_cache[slide_data.id] = preview_pixmap
                    button.set_icon_state("error", has_font_error)
                    # If you have a warning icon, reset/update it too
                    # button.set_icon_state("warning", some_warning_condition_from_slide_data)
                except Exception as e:
                    print(f"Error re-rendering preview for slide {index} in _handle_slide_visual_property_change: {e}")
                    error_preview = QPixmap(current_dynamic_preview_width, current_dynamic_preview_height)
                    error_preview.fill(Qt.GlobalColor.magenta) # Or a less intrusive error indicator
                    button.set_pixmap(error_preview)
                    button.set_icon_state("error", True)

                # --- Update banner color ---
                if hasattr(slide_data, 'banner_color'): # Check if the attribute exists
                    new_color = QColor(slide_data.banner_color) if slide_data.banner_color else None
                    button.set_banner_color(new_color)

                # --- Update overlay label display on the banner ---
                button.set_center_overlay_label(slide_data.overlay_label, emit_signal_on_change=False)

                # --- Update other button states ---
                button.setToolTip(f"Slide {index + 1}: {slide_data.lyrics.splitlines()[0] if slide_data.lyrics else 'Empty'}")
                button.set_is_background_slide(slide_data.is_background_slide)
                current_label_for_banner = "BG" if slide_data.is_background_slide else ""
                button.set_slide_info(number=index + 1, label=current_label_for_banner)

                button.update() # Ensure the button repaints with all changes

                # If the updated slide is the currently live one, re-display it on the output
                if self.current_slide_index == index and self.output_window.isVisible():
                    self._display_slide(index)

        # if not self.handle_save_as():
        #     # Optionally, warn the user if even the 'Save As...' was cancelled.
        #     QMessageBox.warning(self, "Action Cancelled", "New presentation cancelled.")

        # The event filter on QScrollArea should handle Left/Right.
        #super().keyPressEvent(event)

    def _determine_insertion_context(self, global_pos: QPoint) -> tuple[int, Optional[str]]:
        pos_in_slide_buttons_widget = self.slide_buttons_widget.mapFromGlobal(global_pos)
        
        # Default: append to the end of the presentation, no specific song title (new block)
        target_insertion_index = len(self.presentation_manager.get_slides())
        target_song_title: Optional[str] = None

        # Handle case of no slides: insert at index 0, no song title
        if not self.presentation_manager.get_slides():
            return 0, None

        # Find the widget directly under the mouse cursor
        clicked_widget = self.slide_buttons_widget.childAt(pos_in_slide_buttons_widget)
        
        widget_iterator = clicked_widget
        # Traverse up from clicked_widget to find relevant parent 
        # (ScaledSlideButton, SongHeaderWidget, or FlowContainer QWidget)
        while widget_iterator and widget_iterator != self.slide_buttons_widget:
            if isinstance(widget_iterator, ScaledSlideButton):
                slide_idx = widget_iterator._slide_id # Access directly
                slides = self.presentation_manager.get_slides()
                if 0 <= slide_idx < len(slides):
                    target_song_title = slides[slide_idx].song_title
                    target_insertion_index = slide_idx + 1 # Insert after this slide
                    return target_insertion_index, target_song_title
                break # Should not happen if button exists

            # Check if widget_iterator is a direct child of slide_buttons_layout 
            # (i.e., a SongHeader or a FlowContainer)
            if widget_iterator.parentWidget() == self.slide_buttons_widget:
                if isinstance(widget_iterator, SongHeaderWidget):
                    target_song_title = widget_iterator.get_song_title()
                    # Calculate insertion index for start of this song
                    current_cumulative_idx = 0
                    for i in range(self.slide_buttons_layout.count()):
                        item = self.slide_buttons_layout.itemAt(i)
                        if not item or not item.widget(): continue
                        vbox_child = item.widget()
                        if vbox_child == widget_iterator: # This is the header
                            target_insertion_index = current_cumulative_idx
                            return target_insertion_index, target_song_title
                        if isinstance(vbox_child.layout(), FlowLayout): # Count slides in preceding flow layouts
                            current_cumulative_idx += vbox_child.layout().count()
                    break 

                elif isinstance(widget_iterator.layout(), FlowLayout): # A FlowContainer QWidget
                    target_song_title = self.drag_drop_handler._get_song_title_for_flow_widget(widget_iterator)
                    # Click was on the container but not a specific button. Insert at end of this song.
                    current_cumulative_idx = 0
                    found_container = False
                    for i in range(self.slide_buttons_layout.count()):
                        item = self.slide_buttons_layout.itemAt(i)
                        if not item or not item.widget(): continue
                        vbox_child = item.widget()
                        if isinstance(vbox_child.layout(), FlowLayout):
                            current_cumulative_idx += vbox_child.layout().count()
                        if vbox_child == widget_iterator: # Found the container
                            target_insertion_index = current_cumulative_idx # Index is after all slides in this flow
                            found_container = True
                            break 
                    if found_container:
                        return target_insertion_index, target_song_title
                    break 
            
            widget_iterator = widget_iterator.parentWidget()

        # If clicked_widget is None or traversal didn't identify a specific context,
        # it implies a click on the empty background of slide_buttons_widget.
        # Determine if it's between songs or at the very end.
        if clicked_widget is None:
            y_click = pos_in_slide_buttons_widget.y()
            cumulative_idx_at_item_top = 0
            for i in range(self.slide_buttons_layout.count()):
                item = self.slide_buttons_layout.itemAt(i)
                if not item or not item.widget(): continue
                vbox_child = item.widget()
                
                if y_click < vbox_child.geometry().top(): # Click is above this item
                    target_insertion_index = cumulative_idx_at_item_top
                    # Determine song title for this insertion point (could be start of next song, or end of prev)
                    if isinstance(vbox_child, SongHeaderWidget):
                        target_song_title = vbox_child.get_song_title()
                    elif isinstance(vbox_child.layout(), FlowLayout):
                        target_song_title = self.drag_drop_handler._get_song_title_for_flow_widget(vbox_child)
                    else: # Unlikely, but if it's a spacer, use previous song's title or None
                        if i > 0:
                            prev_item_widget = self.slide_buttons_layout.itemAt(i-1).widget()
                            if isinstance(prev_item_widget.layout(), FlowLayout): # prev was flow
                                target_song_title = self.drag_drop_handler._get_song_title_for_flow_widget(prev_item_widget)
                    return target_insertion_index, target_song_title

                # Update cumulative index based on type of vbox_child
                if isinstance(vbox_child.layout(), FlowLayout):
                    cumulative_idx_at_item_top += vbox_child.layout().count()
            # If loop finishes, click is below all items, so append (default is already set)
            target_song_title = None # New block at the very end
            return target_insertion_index, target_song_title

        # Fallback if specific item not identified through traversal, use default (append)
        return target_insertion_index, target_song_title

    def _show_insert_slide_context_menu(self, global_pos: QPoint):
        insertion_index, song_title_for_new_slide = self._determine_insertion_context(global_pos)
        
        context_menu = QMenu(self)
        insert_submenu = context_menu.addMenu("Insert Slide from Layout")

        layout_template_names = self.template_manager.get_layout_names()
        if not layout_template_names:
            no_layouts_action = insert_submenu.addAction("No Layout Templates Available")
            no_layouts_action.setEnabled(False)
        else:
            for layout_name in layout_template_names:
                action = insert_submenu.addAction(layout_name)
                action.triggered.connect(
                    lambda checked=False, name=layout_name, index=insertion_index, title=song_title_for_new_slide: 
                    self._handle_insert_slide_from_layout(name, index, title)
                )
        
        context_menu.addSeparator()
        insert_blank_action = context_menu.addAction("Insert Blank Slide (Default Layout)")
        if "Default Layout" in layout_template_names:
            insert_blank_action.triggered.connect(
                lambda checked=False, index=insertion_index, title=song_title_for_new_slide:
                self._handle_insert_slide_from_layout("Default Layout", index, title)
            )
        else:
            insert_blank_action.setEnabled(False)
            insert_blank_action.setToolTip("Default Layout template not found.")

        context_menu.exec(global_pos)

    def _handle_insert_slide_from_layout(self, layout_name: str, insertion_index: int, song_title: Optional[str]):
        resolved_template_settings = self.template_manager.resolve_layout_template(layout_name)
        if not resolved_template_settings:
            self.show_error_message(f"Could not resolve layout template '{layout_name}'. Cannot insert slide.")
            return

        # print(f"DEBUG: Resolved template settings for '{layout_name}': {resolved_template_settings}")

        # Get background color from template
        bg_color_hex_from_template = resolved_template_settings.get("background_color")
        print(f"DEBUG: bg_color_hex_from_template for '{layout_name}': {bg_color_hex_from_template}")

        # If the template specifies fully transparent black ("#00000000"),
        # or if no background color is specified at all, treat it as no background color (use None for SlideData).
        # Otherwise, use the color specified.
        bg_color_for_slide_data = None # Default to None (transparent texture)
        if bg_color_hex_from_template and bg_color_hex_from_template.lower() != "#00000000":
            bg_color_for_slide_data = bg_color_hex_from_template

        new_slide_data = SlideData(
            lyrics="", song_title=song_title, template_settings=resolved_template_settings, background_color=bg_color_for_slide_data
        )
        # Ensure text_content is empty for a new slide
        new_slide_data.template_settings.setdefault("text_content", {})
        for tb in new_slide_data.template_settings.get("text_boxes", []):
            tb_id = tb.get("id")
            if tb_id:
                 new_slide_data.template_settings["text_content"][tb_id] = ""

        cmd = AddSlideCommand(self.presentation_manager, new_slide_data, at_index=insertion_index)
        self.presentation_manager.do_command(cmd)
        
        # Ensure the newly added slide's area is visible
        # Note: The actual button for the new slide is created by update_slide_display_and_selection
        # This ensures visibility of the *area* where it will appear.
        if self.slide_buttons_list: # Check if list is not empty
            # Determine a button to scroll to. If inserting in middle, use that index. If at end, use last.
            scroll_to_idx = min(insertion_index, len(self.slide_buttons_list) -1)
            if scroll_to_idx >= 0:
                 button_to_ensure_visible = self.slide_buttons_list[scroll_to_idx]
                 self.scroll_area.ensureWidgetVisible(button_to_ensure_visible, 50, 50)

    @Slot(int, str)
    def _handle_insert_slide_from_button_context_menu(self, after_slide_id: int, layout_name: str):
        """Handles inserting a slide when requested from a ScaledSlideButton's context menu."""
        slides = self.presentation_manager.get_slides()
        if not (0 <= after_slide_id < len(slides)):
            self.show_error_message(f"Cannot insert slide: Reference slide ID {after_slide_id} is invalid.")
            return

        insertion_index = after_slide_id + 1
        song_title_for_new_slide = slides[after_slide_id].song_title
        print(f"MainWindow: Inserting slide from button context menu. Layout: '{layout_name}', After Slide ID: {after_slide_id}, Index: {insertion_index}, Song Title: '{song_title_for_new_slide}'")
        self._handle_insert_slide_from_layout(layout_name, insertion_index, song_title_for_new_slide)

    @Slot()
    def handle_undo(self):
        print("MainWindow: Undo action triggered.")
        self.presentation_manager.undo()

    @Slot()
    def handle_redo(self):
        print("MainWindow: Redo action triggered.")
        self.presentation_manager.redo()
        
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

            parent=self
        )
        settings_dialog.output_monitor_changed.connect(self._handle_settings_monitor_changed)
        # Connect to the new signal that emits both fill and key indices
        # We will get all settings when the dialog is accepted.
        # settings_dialog.decklink_fill_key_devices_selected.connect(self._handle_decklink_devices_changed_from_settings)

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
            # settings_dialog.decklink_fill_key_devices_selected.disconnect(self._handle_decklink_devices_changed_from_settings) # No longer connected
        except RuntimeError: # In case signals were already disconnected or dialog closed unexpectedly
            pass

    @Slot(dict)
    def _load_recent_file_action(self, filepath: str):
        """Handler for clicking a recent file action in the menu."""
        print(f"Loading recent file: {filepath}")
        # Call the handle_load method with the specific filepath
        self.handle_load(filepath=filepath)
    def _handle_editor_save_request(self, templates_collection: dict):
        """
        Handles the templates_save_requested signal from the TemplateEditorWindow.
        This allows saving templates without closing the editor.
        """
        print(f"MainWindow: Received save request from template editor with data: {templates_collection.keys()}")
        self.template_manager.update_from_collection(templates_collection)
        # Optionally, provide feedback to the user, e.g., via a status bar or a brief message.
        # For now, the print statement and the TemplateManager's own save confirmation (if any) will suffice.

    @Slot(QScreen)
    def _handle_settings_monitor_changed(self, selected_screen: QScreen):
        """Handles the output_monitor_changed signal from the SettingsWindow."""
        self.config_manager.set_target_output_screen(selected_screen)
        print(f"MainWindow: Target output monitor setting updated to {selected_screen.name()} via settings dialog.")
        # If already live, you might want to move the output window, or just apply on next "Go Live"
        
    # The _handle_decklink_devices_changed_from_settings slot is removed as settings are applied on dialog accept.


    # def reinitialize_decklink_output(self):
    #     """Shuts down and re-initializes DeckLink output with current settings."""
    #     print("MainWindow: Re-initializing DeckLink output...")
    #     decklink_handler.shutdown_output() # Ensure existing is off

    #     if self.current_decklink_idx == -1 or self.current_decklink_video_mode_details is None:
    #         print("MainWindow: Cannot re-initialize DeckLink, device or video mode not selected.")
    #         return

    #     # Modify decklink_handler.initialize_output to accept these parameters
    #     # or create a new function like initialize_output_with_settings
    #     success = decklink_handler.initialize_output(
    #         device_index=self.current_decklink_idx,
    #         width=self.current_decklink_video_mode_details['width'],
    #         height=self.current_decklink_video_mode_details['height'],
    #         frame_rate_num=self.current_decklink_video_mode_details['fr_num'],
    #         frame_rate_denom=self.current_decklink_video_mode_details['fr_den']
    #     )
    #     # Update UI or status based on success

    def get_setting(self, key: str, default_value=None):
        """
        Provides a way for other components (like SlideRenderer) to get settings
        managed or known by MainWindow.
        """
        if key == "display_checkerboard_for_transparency":
            return self.config_manager.get_app_setting(key, True) # Default to True
        return self.config_manager.get_app_setting(key, default_value)
        
    # --- Drag and Drop for Background Slides ---
    def dragEnterEvent(self, event: QDragEnterEvent): # Added type hint
        # The SlideDragDropHandler will inspect mimeData and decide to accept.
        # MainWindow simply delegates. The handler should call event.acceptProposedAction()
        # if it can handle the data (either PLUCKY_SLIDE_MIME_TYPE or image URLs).
        if self.drag_drop_handler:
            self.drag_drop_handler.dragEnterEvent(event)
        else:
            event.ignore() # No handler, ignore.

    def dragMoveEvent(self, event: QDragMoveEvent): # Added type hint
        # Delegate to the handler. It's responsible for:
        # 1. Checking if it can handle the event.mimeData().
        # 2. Calling event.acceptProposedAction() or event.ignore().
        # 3. Updating the self.drop_indicator if a slide (PLUCKY_SLIDE_MIME_TYPE) is being reordered.
        if self.drag_drop_handler:
            self.drag_drop_handler.dragMoveEvent(event)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent): # Added type hint
        # Delegate to the handler. It should hide the drop_indicator.
        if self.drag_drop_handler:
            self.drag_drop_handler.dragLeaveEvent(event)
        # MainWindow's self.drop_indicator is managed by the handler

    def dropEvent(self, event: QDropEvent): # Added type hint
        # Delegate to the handler. It's responsible for:
        # 1. Processing the drop (reordering slide or adding image).
        # 2. Hiding the self.drop_indicator.
        if self.drag_drop_handler:
            self.drag_drop_handler.dropEvent(event)
        # MainWindow's self.drop_indicator is managed by the handler


# Example of how to run this if it's the main entry point for testing
# (Your main.py would typically handle this)
if __name__ == '__main__': # This block is for direct testing of MainWindow
    # Simulate what main.py does for benchmarks
    app_start_time_for_mw_test = time.perf_counter()
    app = QApplication(sys.argv)
    QApplication.instance().setProperty("app_start_time", app_start_time_for_mw_test)

    main_win = MainWindow()
    main_win.show()

    app_ready_duration_for_mw_test = time.perf_counter() - app_start_time_for_mw_test
    print(f"[BENCHMARK_MW_TEST] Application ready (after show) took: {app_ready_duration_for_mw_test:.4f} seconds")
    sys.exit(app.exec())