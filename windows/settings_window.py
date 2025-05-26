from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QDialogButtonBox, QTabWidget, QLabel,
    QComboBox, QPushButton, QApplication, QMessageBox, QGroupBox, QFileDialog, QLineEdit,
    QHBoxLayout, QInputDialog # Add QInputDialog
)
from PySide6.QtCore import QDir, QFileInfo, Slot, Signal, Qt # Added Qt
from PySide6.QtGui import QScreen
from PySide6.QtUiTools import QUiLoader
import git # Import GitPython
from git import exc as GitExceptions # For specific Git exceptions
import os, sys # Needed for os.path.basename
import ctypes # For HRESULT S_OK

# Attempt to import from decklink_handler.
try:
    # This assumes decklink_handler.py is in the parent directory of 'windows'
    # Adjust if your project structure is different (e.g. Plucky.decklink_handler)
    from .. import decklink_handler
    from ..core.plucky_standards import PluckyStandards # Import PluckyStandards
    from ..core.app_config_manager import ApplicationConfigManager
    from ..core.template_manager import TemplateManager, SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME
except ImportError:
    # Fallback for different execution contexts or structures
    # This path might need adjustment if running settings_window.py directly for testing
    import decklink_handler
    # This path might need adjustment if running settings_window.py directly for testing
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.plucky_standards import PluckyStandards # Add PluckyStandards import here
    from core.app_config_manager import ApplicationConfigManager
    from core.template_manager import TemplateManager, SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME

class SettingsWindow(QDialog):
    production_mode_changed_signal = Signal(str) # Emits the new mode string


    # Signal to indicate the selected output monitor has changed
    output_monitor_changed = Signal(QScreen)  # Emits the selected QScreen object
    # Emits (fill_device_index, key_device_index)
    decklink_fill_key_devices_selected = Signal(int, int)

    def __init__(self, benchmark_data: dict,
                 current_output_screen: QScreen = None,
                 current_decklink_fill_index: int = -1, # Pass current fill selection
                 current_decklink_key_index: int = -1,   # Pass current key selection
                 current_decklink_video_mode: dict = None, # Pass current video mode
                 config_manager: ApplicationConfigManager = None,
                 template_manager: TemplateManager = None, # Pass TemplateManager
                 parent=None):
        super().__init__(parent)
        self._current_output_screen = current_output_screen
        self._current_decklink_fill_index = current_decklink_fill_index
        self._current_decklink_key_index = current_decklink_key_index
        self._current_decklink_video_mode = current_decklink_video_mode # Store current video mode
        self.config_manager = config_manager
        self.template_manager = template_manager

        if not self.config_manager:
            # This is a fallback if not provided, but ideally it should always be passed.
            # For standalone testing, this might be okay.
            print("SettingsWindow WARNING: ApplicationConfigManager not provided. Prod Toggle will not persist.")
            self.config_manager = ApplicationConfigManager() # Create a temporary one
        self._decklink_api_initialized_by_settings = False # Track if we initialized it
        if not self.template_manager:
            # Fallback, ideally always passed
            print("SettingsWindow WARNING: TemplateManager not provided. Default template selection will be limited.")
            self.template_manager = TemplateManager()


        # Load the UI file
        # Assuming the .ui file is in the same directory as this .py file
        script_file_info = QFileInfo(__file__)
        script_directory_path = script_file_info.absolutePath()
        script_qdir = QDir(script_directory_path)
        ui_file_path = script_qdir.filePath("settings_window.ui")

        loader = QUiLoader()
        # Load the QWidget defined in the UI file
        self.ui = loader.load(ui_file_path) # Load without parent initially

        # Set up the dialog's main layout and add the loaded UI widget
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.ui)
        self.setLayout(main_layout)

        # Access widgets from the loaded UI
        self.button_box: QDialogButtonBox = self.ui.findChild(QDialogButtonBox, "buttonBox")
        self.tab_widget: QTabWidget = self.ui.findChild(QTabWidget, "tabWidget") # Access the tab widget

        # Access benchmarking labels from the loaded UI
        self.label_app_init_time: QLabel = self.ui.findChild(QLabel, "label_app_init_time")
        self.label_mw_init_time: QLabel = self.ui.findChild(QLabel, "label_mw_init_time")
        self.label_mw_show_time: QLabel = self.ui.findChild(QLabel, "label_mw_show_time")
        self.label_last_presentation_path: QLabel = self.ui.findChild(QLabel, "label_last_presentation_path")
        self.label_pm_load_time: QLabel = self.ui.findChild(QLabel, "label_pm_load_time")
        self.label_ui_update_time: QLabel = self.ui.findChild(QLabel, "label_ui_update_time")
        self.label_render_total: QLabel = self.ui.findChild(QLabel, "label_render_total")
        self.label_render_images: QLabel = self.ui.findChild(QLabel, "label_render_images")
        self.label_render_fonts: QLabel = self.ui.findChild(QLabel, "label_render_fonts")
        self.label_render_layout: QLabel = self.ui.findChild(QLabel, "label_render_layout")
        self.label_render_draw: QLabel = self.ui.findChild(QLabel, "label_render_draw")
        self.benchmarking_group_box: QGroupBox = self.ui.findChild(QGroupBox, "benchmarkingGroupBox")

        # Access Output Monitor controls from the loaded UI (General Tab)
        self.monitor_selection_combo: QComboBox = self.ui.findChild(QComboBox, "monitorSelectionComboBox")
        self.refresh_monitors_button: QPushButton = self.ui.findChild(QPushButton, "refreshMonitorsButton")
        # DeckLink Output UI (General Tab) - Find these from the UI file
        self.decklink_fill_device_combo: QComboBox = self.ui.findChild(QComboBox, "decklinkFillDeviceComboBox") # Renamed/Replaced
        self.decklink_key_device_combo: QComboBox = self.ui.findChild(QComboBox, "decklinkKeyDeviceComboBox")   # New
        self.refresh_decklink_devices_button: QPushButton = self.ui.findChild(QPushButton, "refreshDecklinkDevicesButton")
        self.decklink_video_mode_combo: QComboBox = self.ui.findChild(QComboBox, "decklinkVideoModeComboBox")

        # Access Prod Toggle ComboBox (Developer Tab)
        self.prod_toggle_combo_box: QComboBox = self.ui.findChild(QComboBox, "ProdToggleComboBox")

        # Access Default Template ComboBox (Slide Defaults Tab)
        self.default_template_combo_box: QComboBox = self.ui.findChild(QComboBox, "defaultTemplateComboBox")

        # Access Backup & Sharing Tab widgets
        self.backup_status_label: QLabel = self.ui.findChild(QLabel, "backupStatusLabel")
        self.unconfigured_repo_widget: QWidget = self.ui.findChild(QWidget, "unconfiguredRepoWidget")
        # Renamed in UI and here for clarity
        self.setup_new_repo_button: QPushButton = self.ui.findChild(QPushButton, "setupNewRepoButton")
        self.configured_repo_widget: QWidget = self.ui.findChild(QWidget, "configuredRepoWidget")
        self.repo_path_line_edit: QLineEdit = self.ui.findChild(QLineEdit, "repoPathLineEdit")
        self.change_repo_button: QPushButton = self.ui.findChild(QPushButton, "changeRepoButton")
        self.pull_repo_button: QPushButton = self.ui.findChild(QPushButton, "pullRepoButton")
        self.push_repo_button: QPushButton = self.ui.findChild(QPushButton, "pushRepoButton")
        self.commit_repo_button: QPushButton = self.ui.findChild(QPushButton, "commitRepoButton")
        # New widgets for connecting to an existing repository
        self.existing_repo_url_line_edit: QLineEdit = self.ui.findChild(QLineEdit, "existingRepoUrlLineEdit")
        self.connect_existing_repo_button: QPushButton = self.ui.findChild(QPushButton, "connectExistingRepoButton")


        # Set window properties
        self.setWindowTitle("Settings")
        self.resize(500, 450) # Adjusted size for new groupbox

        # Connect standard buttons if they exist
        if self.button_box:
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)

        # Update the display with initial benchmark data
        self.update_benchmarking_display(benchmark_data)

        # Populate and connect monitor controls
        if self.refresh_monitors_button:
            self.refresh_monitors_button.clicked.connect(self.populate_monitor_combo)
        if self.monitor_selection_combo:
            self.monitor_selection_combo.currentIndexChanged.connect(self._handle_monitor_selection_changed)
        self.populate_monitor_combo() # Initial population

        # Connect the toggled signal for the benchmarking group box
        if self.benchmarking_group_box and self.benchmarking_group_box.isCheckable():
            self.benchmarking_group_box.toggled.connect(self._on_benchmarking_group_toggled)
            # Set initial visibility of contents based on the checked state from UI
            self._on_benchmarking_group_toggled(self.benchmarking_group_box.isChecked())

        # DeckLink controls
        if self.refresh_decklink_devices_button:
            self.refresh_decklink_devices_button.clicked.connect(self.populate_decklink_devices_combo)
        if self.decklink_fill_device_combo:
            self.decklink_fill_device_combo.currentIndexChanged.connect(self._handle_decklink_fill_device_selection_changed)
        if self.decklink_key_device_combo:
            self.decklink_key_device_combo.currentIndexChanged.connect(self._handle_decklink_key_device_selection_changed)
        
        self.populate_decklink_devices_combo() # Initial population

        # Populate and connect Prod Toggle ComboBox
        if self.prod_toggle_combo_box:
            self.populate_prod_toggle_combo()
            self.prod_toggle_combo_box.currentTextChanged.connect(self._handle_prod_mode_changed)
        
        # Populate and connect Default Template ComboBox
        if self.default_template_combo_box:
            self.populate_default_template_combo()
            self.default_template_combo_box.currentTextChanged.connect(self._handle_default_template_changed)

        # Initialize Backup & Sharing Tab
        if self.setup_new_repo_button: # Was configure_repo_button
            self.setup_new_repo_button.clicked.connect(self.handle_setup_new_repository) # Renamed handler
        if self.change_repo_button:
            self.change_repo_button.clicked.connect(self.handle_setup_new_repository) # Can reuse setup new logic for reconfigure
        if self.connect_existing_repo_button:
            self.connect_existing_repo_button.clicked.connect(self.handle_connect_existing_repository)
        if self.pull_repo_button:
            self.pull_repo_button.clicked.connect(self.handle_pull_repository)
        if self.push_repo_button:
            self.push_repo_button.clicked.connect(self.handle_push_repository)
        if self.commit_repo_button:
            self.commit_repo_button.clicked.connect(self.handle_commit_repository)

        # Load initial repository configuration for Backup & Sharing
        # self.user_store_path should be reliably obtained, e.g., from config_manager
        self.user_store_path = PluckyStandards.get_user_store_root()
        current_local_repo_path = self.config_manager.get_app_setting("backup_repo_path", None) if self.config_manager else None
        self._update_ui_for_repo_config(current_local_repo_path) # This will also call refresh_repository_status

    def update_benchmarking_display(self, data: dict):
        """Updates the labels in the benchmarking section with provided data."""
        if self.label_app_init_time:
            self.label_app_init_time.setText(f"App Init Time: {data.get('app_init', 'N/A'):.4f}s")
        if self.label_mw_init_time:
            self.label_mw_init_time.setText(f"MainWindow Init Time: {data.get('mw_init', 'N/A'):.4f}s")
        if self.label_mw_show_time:
            self.label_mw_show_time.setText(f"MainWindow Show Time: {data.get('mw_show', 'N/A'):.4f}s")
        if self.label_last_presentation_path:
            # Display just the filename for brevity
            filepath = data.get('last_presentation_path', 'None')
            filename = os.path.basename(filepath) if filepath and filepath != 'None' else 'None'
            self.label_last_presentation_path.setText(f"Last Presentation: {filename}")
        if self.label_pm_load_time:
            self.label_pm_load_time.setText(f"PM Load Time: {data.get('last_presentation_pm_load', 'N/A'):.4f}s")
        if self.label_ui_update_time:
            self.label_ui_update_time.setText(f"UI Update Time: {data.get('last_presentation_ui_update', 'N/A'):.4f}s")
        if self.label_render_total:
             self.label_render_total.setText(f"Render (Total): {data.get('last_presentation_render_total', 'N/A'):.4f}s")
        if self.label_render_images:
             self.label_render_images.setText(f"Render (Images): {data.get('last_presentation_render_images', 'N/A'):.4f}s")
        if self.label_render_fonts:
             self.label_render_fonts.setText(f"Render (Fonts): {data.get('last_presentation_render_fonts', 'N/A'):.4f}s")
        if self.label_render_layout:
             self.label_render_layout.setText(f"Render (Layout): {data.get('last_presentation_render_layout', 'N/A'):.4f}s")
        if self.label_render_draw:
             self.label_render_draw.setText(f"Render (Draw): {data.get('last_presentation_render_draw', 'N/A'):.4f}s")

    @Slot()
    def populate_monitor_combo(self):
        if not self.monitor_selection_combo:
            return

        self.monitor_selection_combo.blockSignals(True)
        self.monitor_selection_combo.clear()
        screens = QApplication.screens()

        if not screens:
            self.monitor_selection_combo.addItem("No monitors found")
            self.monitor_selection_combo.setEnabled(False)
            self.monitor_selection_combo.blockSignals(False)
            return

        self.monitor_selection_combo.setEnabled(True)
        current_selection_index = -1
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            item_text = f"Monitor {i+1}: {screen.name()} ({geometry.width()}x{geometry.height()})"
            self.monitor_selection_combo.addItem(item_text, screen) # Store QScreen object as data
            if self._current_output_screen and self._current_output_screen == screen:
                current_selection_index = i
        
        if current_selection_index != -1:
            self.monitor_selection_combo.setCurrentIndex(current_selection_index)
        elif screens: # Default to first screen if no current selection or current is not found
            self.monitor_selection_combo.setCurrentIndex(0)
            self._current_output_screen = self.monitor_selection_combo.currentData() # Update internal state

        self.monitor_selection_combo.blockSignals(False)
        # Emit signal if the selection effectively changed due to refresh/defaulting
        # or if forced (e.g., on initial population)
        if self.monitor_selection_combo.currentIndex() >= 0:
             self._handle_monitor_selection_changed(self.monitor_selection_combo.currentIndex(), force_emit=True)

    @Slot(int)
    def _handle_monitor_selection_changed(self, index: int, force_emit: bool = False):
        if not self.monitor_selection_combo or index < 0:
            return
        
        selected_screen: QScreen = self.monitor_selection_combo.itemData(index)
        
        # Emit if forced OR if the screen actually changed from the dialog's internal perspective
        if selected_screen and (force_emit or selected_screen != self._current_output_screen):
            self._current_output_screen = selected_screen
            self.output_monitor_changed.emit(selected_screen)
            print(f"SettingsWindow: Output monitor changed to {selected_screen.name()}")

    @Slot(bool)
    def _on_benchmarking_group_toggled(self, checked: bool):
        """Shows or hides the contents of the benchmarking group box."""
        if not self.benchmarking_group_box:
            return
        
        # Iterate over the children of the group box's layout and set their visibility
        # The group box's layout is named "benchmarkingLayout" in the UI
        layout = self.benchmarking_group_box.layout()
        if layout:
            for i in range(layout.count()):
                widget_item = layout.itemAt(i).widget()
                if widget_item: # Check if it's a widget (not a spacer)
                    widget_item.setVisible(checked)
    @Slot()
    def populate_decklink_devices_combo(self):
        print("SettingsWindow: populate_decklink_devices_combo called.") # DEBUG
        if not self.decklink_fill_device_combo or not self.decklink_key_device_combo:
            print("SettingsWindow: DEBUG - Combo box(es) not found, returning.") # DEBUG

            return

        # Block signals for both combos
        self.decklink_fill_device_combo.blockSignals(True)
        self.decklink_key_device_combo.blockSignals(True)

        self.decklink_fill_device_combo.clear()
        self.decklink_key_device_combo.clear()

        if self.decklink_video_mode_combo:
            self.decklink_video_mode_combo.clear() # Clear video modes when devices are refreshed
            self.decklink_video_mode_combo.setEnabled(False)

        if not decklink_handler.decklink_dll:
            if not decklink_handler.load_dll():
                common_error_msg = "DeckLink DLL not loaded"
                self.decklink_fill_device_combo.addItem(common_error_msg); self.decklink_fill_device_combo.setEnabled(False)
                self.decklink_key_device_combo.addItem(common_error_msg); self.decklink_key_device_combo.setEnabled(False)
                self.decklink_fill_device_combo.blockSignals(False); self.decklink_key_device_combo.blockSignals(False)
                QMessageBox.warning(self, "DeckLink Error", "Failed to load DeckLinkWraper.dll.")
                return
        
        hr_init = decklink_handler.S_OK
        # Check if the API level is initialized. decklink_handler.decklink_initialized_successfully
        # refers to a device being initialized, not just the API.
        # We need a way to know if InitializeDLL() itself was successful.
        # For now, we'll assume it's safe to call InitializeDLL() if not sure.
        # The C++ InitializeDLL is idempotent.
        # A better approach would be for decklink_handler to expose an API status.
        if not decklink_handler.decklink_dll.InitializeDLL: # Basic check if function exists
             QMessageBox.critical(self, "DeckLink Error", "InitializeDLL function missing in DLL.")
             return

        # Attempt to initialize API if not already done by main app.
        # This is tricky. Ideally, main app manages this.
        # We'll call InitializeDLL. If it was already called, it should return S_OK.
        hr_init = decklink_handler.decklink_dll.InitializeDLL()
        if hr_init == decklink_handler.S_OK:
            if not self._decklink_api_initialized_by_settings: # If it wasn't us who init'd it before
                 # Check if this call actually did the initialization vs it was already up
                 # This requires more state from decklink_handler or C++ DLL.
                 # For now, assume if S_OK, it's usable.
                 # We'll mark it as "initialized by settings" if the main app hasn't done it.
                 # This is imperfect.
                 if not decklink_handler.decklink_initialized_successfully: # If main app hasn't fully init'd a device
                    self._decklink_api_initialized_by_settings = True
                    print("SettingsWindow: DeckLink API initialized by settings window.")
        else:
            common_error_msg = "Failed to init DeckLink API"
            self.decklink_fill_device_combo.addItem(common_error_msg); self.decklink_fill_device_combo.setEnabled(False)
            self.decklink_key_device_combo.addItem(common_error_msg); self.decklink_key_device_combo.setEnabled(False)
            self.decklink_fill_device_combo.blockSignals(False); self.decklink_key_device_combo.blockSignals(False)
            QMessageBox.warning(self, "DeckLink Error", f"Failed to initialize DeckLink API (HRESULT: {hr_init:#010x}).")
            return

        device_count = ctypes.c_int(0)
        hr = decklink_handler.decklink_dll.GetDeviceCount(ctypes.byref(device_count))

        device_list_for_combos = []
        if hr != decklink_handler.S_OK or device_count.value == 0:
            msg = "No DeckLink devices found." if device_count.value == 0 else f"Error getting device count (HRESULT: {hr:#010x})."
            self.decklink_fill_device_combo.addItem(msg); self.decklink_fill_device_combo.setEnabled(False)
            self.decklink_key_device_combo.addItem(msg); self.decklink_key_device_combo.setEnabled(False)
            if self._decklink_api_initialized_by_settings and device_count.value == 0:
                decklink_handler.decklink_dll.ShutdownDLL()
                self._decklink_api_initialized_by_settings = False
        else:
            self.decklink_fill_device_combo.setEnabled(True)
            self.decklink_key_device_combo.setEnabled(True)

            for i in range(device_count.value):
                name_buffer = ctypes.create_string_buffer(256)
                hr_name = decklink_handler.decklink_dll.GetDeviceName(i, name_buffer, ctypes.sizeof(name_buffer))
                if hr_name == decklink_handler.S_OK:
                    device_name = name_buffer.value.decode('utf-8', errors='replace')
                    device_list_for_combos.append({"text": f"{device_name} (Index {i})", "data": i})
                else:
                    device_list_for_combos.append({"text": f"Unknown Device (Index {i})", "data": i})

            # Populate Fill Device Combo
            current_fill_combo_idx_to_set = -1
            for item in device_list_for_combos:
                self.decklink_fill_device_combo.addItem(item["text"], item["data"])
                if item["data"] == self._current_decklink_fill_index:
                    current_fill_combo_idx_to_set = self.decklink_fill_device_combo.count() - 1
            
            if current_fill_combo_idx_to_set != -1:
                self.decklink_fill_device_combo.setCurrentIndex(current_fill_combo_idx_to_set)
            elif self.decklink_fill_device_combo.count() > 0:
                self.decklink_fill_device_combo.setCurrentIndex(0) # Default to first
                self._current_decklink_fill_index = self.decklink_fill_device_combo.itemData(0)

            # Populate Key Device Combo
            current_key_combo_idx_to_set = -1
            for item in device_list_for_combos:
                self.decklink_key_device_combo.addItem(item["text"], item["data"])
                if item["data"] == self._current_decklink_key_index:
                    current_key_combo_idx_to_set = self.decklink_key_device_combo.count() - 1

            if current_key_combo_idx_to_set != -1:
                self.decklink_key_device_combo.setCurrentIndex(current_key_combo_idx_to_set)
            elif self.decklink_key_device_combo.count() > 0:
                self.decklink_key_device_combo.setCurrentIndex(0) # Default to first
                self._current_decklink_key_index = self.decklink_key_device_combo.itemData(0)

        # Unblock signals
        self.decklink_fill_device_combo.blockSignals(False)
        self.decklink_key_device_combo.blockSignals(False)

        # Manually trigger handlers if valid selections exist to populate video modes and emit initial state
        if self.decklink_fill_device_combo.currentIndex() >= 0:
            self._handle_decklink_fill_device_selection_changed(self.decklink_fill_device_combo.currentIndex())
        # No need to call key handler here as fill handler will emit combined signal

    @Slot(int)
    def _handle_decklink_fill_device_selection_changed(self, index: int):
        if not self.decklink_fill_device_combo or index < 0:
            if self.decklink_video_mode_combo:
                self.decklink_video_mode_combo.clear()
                self.decklink_video_mode_combo.setEnabled(False)
            return

        selected_fill_idx = self.decklink_fill_device_combo.itemData(index)
        if selected_fill_idx is not None:
            self._current_decklink_fill_index = selected_fill_idx
            print(f"SettingsWindow: DeckLink Fill device selection changed to Index {selected_fill_idx}")
            self.populate_decklink_video_modes_combo(selected_fill_idx) # Video modes often tied to fill
            self._emit_fill_key_selection()
        elif self.decklink_video_mode_combo:
            self.decklink_video_mode_combo.clear()
            self.decklink_video_mode_combo.setEnabled(False)

    @Slot(int)
    def _handle_decklink_key_device_selection_changed(self, index: int):
        if not self.decklink_key_device_combo or index < 0:
            return
        selected_key_idx = self.decklink_key_device_combo.itemData(index)
        if selected_key_idx is not None:
            self._current_decklink_key_index = selected_key_idx
            print(f"SettingsWindow: DeckLink Key device selection changed to Index {selected_key_idx}")
            self._emit_fill_key_selection()

    def _emit_fill_key_selection(self):
        """Emits the currently selected fill and key device indices."""
        if self._current_decklink_fill_index is not None and self._current_decklink_key_index is not None:
            self.decklink_fill_key_devices_selected.emit(
                self._current_decklink_fill_index,
                self._current_decklink_key_index
            )

    def populate_decklink_video_modes_combo(self, device_index: int):
        if not self.decklink_video_mode_combo: return
        self.decklink_video_mode_combo.blockSignals(True)
        self.decklink_video_mode_combo.clear()

        if device_index < 0:
            self.decklink_video_mode_combo.setEnabled(False)
        else:
            # Placeholder modes with details as item data
            # These should eventually be populated by querying the DeckLink device via the C++ DLL
            modes = [
                {"name": "1920x1080 @ 59.94", "width": 1920, "height": 1080, "fr_num": 60000, "fr_den": 1001},
                {"name": "1920x1080 @ 30", "width": 1920, "height": 1080, "fr_num": 30000, "fr_den": 1000}, # Added 1080p30
                # Add other common placeholder modes here if needed (e.g., 720p60, 1080i60)
            ]

            # Determine default mode based on passed-in current_decklink_video_mode
            default_mode_name_to_select = "1920x1080 @ 30" # Fallback default
            if self._current_decklink_video_mode and isinstance(self._current_decklink_video_mode.get("name"), str):
                # Check if the current mode's name is in our placeholder list
                for mode_option in modes:
                    if mode_option["name"] == self._current_decklink_video_mode["name"]:
                        default_mode_name_to_select = self._current_decklink_video_mode["name"]
                        break
            default_index_to_set = -1
            for i, mode in enumerate(modes):
                self.decklink_video_mode_combo.addItem(mode["name"], mode) # Store dict as data
                if mode["name"] == default_mode_name_to_select:
                    default_index_to_set = i
            self.decklink_video_mode_combo.setEnabled(True) # Enable for placeholder
            # Set the default selection
            if default_index_to_set != -1:
                self.decklink_video_mode_combo.setCurrentIndex(default_index_to_set)

        self.decklink_video_mode_combo.blockSignals(False)

    def get_selected_decklink_devices(self) -> tuple[int | None, int | None]:
        """Returns the selected fill and key device indices."""
        fill_idx = self.decklink_fill_device_combo.itemData(self.decklink_fill_device_combo.currentIndex()) \
            if self.decklink_fill_device_combo and self.decklink_fill_device_combo.currentIndex() >= 0 else None
        key_idx = self.decklink_key_device_combo.itemData(self.decklink_key_device_combo.currentIndex()) \
            if self.decklink_key_device_combo and self.decklink_key_device_combo.currentIndex() >= 0 else None
        return fill_idx, key_idx

    # No need to emit signal here, the device selection handler already emits the fill/key signal
        # which implies the video mode might have changed and should be re-read by MainWindow.


    def closeEvent(self, event):
        if self._decklink_api_initialized_by_settings:
            if decklink_handler.decklink_dll:
                print("SettingsWindow: Shutting down DeckLink API that was initialized by settings window.")
                decklink_handler.decklink_dll.ShutdownDLL()
                self._decklink_api_initialized_by_settings = False
        super().closeEvent(event)
        
    def get_selected_video_mode(self) -> dict | None:
        """Returns the selected video mode details."""
        if self.decklink_video_mode_combo and self.decklink_video_mode_combo.currentIndex() >= 0:
            return self.decklink_video_mode_combo.itemData(self.decklink_video_mode_combo.currentIndex())
        return None # Return None if no item is selected

    def populate_prod_toggle_combo(self):
        if not self.prod_toggle_combo_box:
            return

        self.prod_toggle_combo_box.blockSignals(True)
        self.prod_toggle_combo_box.clear()

        modes = ["Developer", "Basic", "Premium"] # User-friendly names
        self.prod_toggle_combo_box.addItems(modes)

        current_mode_str = "Developer" # Default
        if self.config_manager:
            current_mode_str = self.config_manager.get_app_setting("production_mode", "Developer")

        if current_mode_str in modes:
            self.prod_toggle_combo_box.setCurrentText(current_mode_str)
        else: # If saved mode is invalid, default to Developer and save it
            self.prod_toggle_combo_box.setCurrentText("Developer")
            if self.config_manager:
                self.config_manager.set_app_setting("production_mode", "Developer")

        self.prod_toggle_combo_box.blockSignals(False)

    @Slot(str)
    def _handle_prod_mode_changed(self, mode_text: str):
        if self.config_manager:
            self.config_manager.set_app_setting("production_mode", mode_text)
            print(f"SettingsWindow: Production mode changed to '{mode_text}' and saved.")
            self.production_mode_changed_signal.emit(mode_text) # Emit signal
        else:
            print(f"SettingsWindow: Production mode changed to '{mode_text}' (config_manager not available, not saved).")

    def populate_default_template_combo(self):
        if not self.default_template_combo_box or not self.template_manager:
            return

        self.default_template_combo_box.blockSignals(True)
        self.default_template_combo_box.clear()

        # Special option to use the system fallback (template_id: None)
        system_fallback_display_text = f"(Use '{SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME}')"
        self.default_template_combo_box.addItem(system_fallback_display_text, None) # Store None as data

        layout_names = self.template_manager.get_layout_names()
        for name in sorted(layout_names):
            if name != SYSTEM_DEFAULT_FALLBACK_LAYOUT_NAME: # Don't list it twice if it exists
                self.default_template_combo_box.addItem(name, name) # Store name as data

        current_default_template_id = None
        if self.config_manager:
            # If "None" is stored as string, convert to Python None
            saved_setting = self.config_manager.get_app_setting("new_slide_default_template_id", None)
            current_default_template_id = None if saved_setting == "None" else saved_setting

        if current_default_template_id is None:
            self.default_template_combo_box.setCurrentText(system_fallback_display_text)
        else:
            index = self.default_template_combo_box.findData(current_default_template_id)
            if index != -1:
                self.default_template_combo_box.setCurrentIndex(index)
            else: # Saved template not found, default to system fallback
                self.default_template_combo_box.setCurrentText(system_fallback_display_text)

        self.default_template_combo_box.blockSignals(False)

    @Slot(str)
    def _handle_default_template_changed(self, text: str):
        if not self.default_template_combo_box or not self.config_manager:
            return
        
        selected_template_id = self.default_template_combo_box.currentData() # This will be None or the template name string
        # Store Python None as string "None" for JSON compatibility, or actual name
        value_to_save = "None" if selected_template_id is None else selected_template_id
        if self.config_manager:
            self.config_manager.set_app_setting("new_slide_default_template_id", value_to_save)
            print(f"SettingsWindow: New slide default template set to '{selected_template_id}' (saved as '{value_to_save}').")

    # --- Backup & Sharing Methods ---

    def _update_ui_for_repo_config(self, local_repo_path: str | None):
        """
        Updates the UI based on whether a local repository path (UserStore) is configured
        for backup and sharing.
        """
        remote_location_configured = False
        if self.config_manager:
            remote_location = self.config_manager.get_app_setting("backup_repo_remote_location", None)
            if remote_location and os.path.isdir(remote_location): # Basic check for remote
                remote_location_configured = True

        if local_repo_path and os.path.isdir(local_repo_path) and remote_location_configured:
            if self.unconfigured_repo_widget: self.unconfigured_repo_widget.hide()
            if self.configured_repo_widget: self.configured_repo_widget.show()
            if self.repo_path_line_edit: self.repo_path_line_edit.setText(local_repo_path)
        else:
            if self.unconfigured_repo_widget: self.unconfigured_repo_widget.show()
            if self.configured_repo_widget: self.configured_repo_widget.hide()
            if self.repo_path_line_edit: self.repo_path_line_edit.setText("N/A")
            if self.config_manager: # Clear any invalid or incomplete stored paths
                self.config_manager.set_app_setting("backup_repo_path", None)
                self.config_manager.set_app_setting("backup_repo_remote_location", None)

        self.refresh_repository_status()

    @Slot()
    def handle_setup_new_repository(self):
        """
        Handles the 'Setup New Backup Location...' or 'Change/Reconfigure...' button click.
        This involves creating/setting up a new (usually bare) remote repository.
        """
        if not self.user_store_path or not os.path.isdir(self.user_store_path):
            QMessageBox.critical(self, "Configuration Error",
                                 "The UserStore path is not defined or invalid. Cannot configure backup.")
            return

        dialog = ConfigureRepositoryDialog(self, user_store_display_name=f"'{os.path.basename(self.user_store_path)}' folder")
        if dialog.exec():
            backup_destination_path = dialog.get_backup_destination_path()
            if not backup_destination_path:
                return # User cancelled or entered no path

            if not os.path.isdir(backup_destination_path):
                reply = QMessageBox.question(self, "Create Folder?",
                                             f"The destination folder '{backup_destination_path}' does not exist. Create it?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    try:
                        os.makedirs(backup_destination_path, exist_ok=True)
                    except Exception as e:
                        QMessageBox.critical(self, "Error Creating Folder", f"Could not create destination folder: {e}")
                        return
                else:
                    return

            try:
                # --- Git Setup Logic using GitPython ---
                user_repo_path = self.user_store_path

                # 1. Initialize UserStore as a Git repository (if not already)
                try:
                    user_repo = git.Repo(user_repo_path)
                    print(f"UserStore at {user_repo_path} is already a Git repository.")
                except GitExceptions.InvalidGitRepositoryError:
                    print(f"Initializing Git repository in UserStore: {user_repo_path}")
                    user_repo = git.Repo.init(user_repo_path)

                # 2. Initialize backup_destination_path as a bare Git repository (if not already)
                is_dest_bare = os.path.exists(os.path.join(backup_destination_path, "HEAD")) and \
                               not os.path.exists(os.path.join(backup_destination_path, ".git"))
                if not is_dest_bare:
                    if os.listdir(backup_destination_path): # Check if not empty
                        try:
                            existing_repo_check = git.Repo(backup_destination_path)
                            if not existing_repo_check.bare:
                                QMessageBox.critical(self, "Configuration Error",
                                                     f"The destination folder '{backup_destination_path}' is an existing non-bare Git repository. "
                                                     "Please choose an empty folder or an existing bare repository.")
                                return
                        except GitExceptions.InvalidGitRepositoryError:
                            reply = QMessageBox.question(self, "Destination Not Empty",
                                                     f"The folder '{backup_destination_path}' is not empty and not a bare Git repository. "
                                                     "Initializing it as a bare repository is recommended for an empty folder. Continue?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.No:
                                return
                    print(f"Initializing bare Git repository at destination: {backup_destination_path}")
                    dest_repo = git.Repo.init(backup_destination_path, bare=True)

                # 3. Add/Update remote 'origin' in UserStore repository
                print(f"Configuring remote 'origin' for UserStore repository.")
                try:
                    origin = user_repo.remote("origin")
                    if origin.exists(): # Should always be true if remote("origin") didn't error
                        if origin.url != backup_destination_path:
                            print(f"Updating 'origin' remote URL to {backup_destination_path}")
                            origin.set_url(backup_destination_path)
                except ValueError: # Raised by GitPython if remote doesn't exist
                    print(f"Creating 'origin' remote with URL {backup_destination_path}")
                    origin = user_repo.create_remote("origin", backup_destination_path)

                # 4. Initial commit (if needed) and push
                print(f"Performing initial add, commit, and push for UserStore.")
                user_repo.git.add(A=True)
                if user_repo.is_dirty(untracked_files=True):
                    user_repo.index.commit("Initial backup configuration of UserStore")
                    print("Committed initial changes.")
                else:
                    try:
                        user_repo.head.commit # Check if any commits exist
                        print("UserStore already has commits and is clean.")
                    except ValueError: # No commits exist
                        print("UserStore has no commits. Making an initial empty commit.")
                        user_repo.index.commit("Initial backup configuration of UserStore", allow_empty=True)
                
                active_branch_name = user_repo.active_branch.name if user_repo.branches else "master"
                print(f"Pushing to origin/{active_branch_name}...")
                user_repo.remotes.origin.push(refspec=f'{active_branch_name}:{active_branch_name}', set_upstream=True)
                # --- End Git Setup Logic ---

                if self.config_manager:
                    self.config_manager.set_app_setting("backup_repo_path", self.user_store_path)
                    self.config_manager.set_app_setting("backup_repo_remote_location", backup_destination_path)

                self._update_ui_for_repo_config(self.user_store_path)
                QMessageBox.information(self, "Backup Configured",
                                        f"'{os.path.basename(self.user_store_path)}' will now be backed up to '{backup_destination_path}'.")

            except GitExceptions.GitCommandError as e:
                QMessageBox.critical(self, "Git Configuration Error", f"A Git command failed: {e}\nStderr: {e.stderr}")
            except Exception as e: 
                QMessageBox.critical(self, "Configuration Error", f"An error occurred during setup: {e}")
                # Optionally, attempt to clean up or revert UI to previous state
                prev_repo_path = self.config_manager.get_app_setting("backup_repo_path", None) if self.config_manager else None
                self._update_ui_for_repo_config(prev_repo_path)
                
    @Slot()
    def handle_connect_existing_repository(self):
        """Handles the 'Connect' button click for an existing remote repository."""
        if not self.existing_repo_url_line_edit:
            QMessageBox.critical(self, "UI Error", "Existing repository URL input field not found.")
            return

        remote_url = self.existing_repo_url_line_edit.text().strip()
        if not remote_url:
            QMessageBox.warning(self, "Input Required", "Please enter the remote repository URL or path.")
            return

        if not self.user_store_path or not os.path.isdir(self.user_store_path):
            QMessageBox.critical(self, "Configuration Error",
                                 "The UserStore path is not defined or invalid. Cannot connect to backup repository.")
            return

        try:
            # 1. Initialize UserStore as a Git repository (if not already)
            user_repo: git.Repo
            try:
                user_repo = git.Repo(self.user_store_path)
                print(f"UserStore at {self.user_store_path} is already a Git repository.")
            except GitExceptions.InvalidGitRepositoryError:
                print(f"Initializing Git repository in UserStore: {self.user_store_path}")
                user_repo = git.Repo.init(self.user_store_path)
            except Exception as e: # Catch other potential errors like permission issues
                QMessageBox.critical(self, "Local Repository Error", f"Failed to access or initialize local UserStore repository: {e}")
                return

            # 2. Add or Update 'origin' remote
            origin: git.Remote | None = None
            try:
                origin = user_repo.remote("origin")
                if origin.url != remote_url:
                    reply = QMessageBox.question(self, "Confirm Remote Update",
                                                 f"The UserStore repository already has a remote 'origin' configured:\n{origin.url}\n\nDo you want to change it to:\n{remote_url}?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        print(f"Updating 'origin' remote URL to {remote_url}")
                        origin.set_url(remote_url)
                    else:
                        QMessageBox.information(self, "Connection Cancelled", "Connection to existing repository cancelled by user.")
                        return
            except ValueError: # Remote "origin" does not exist
                print(f"Creating 'origin' remote with URL {remote_url}")
                origin = user_repo.create_remote("origin", remote_url)
            
            if not origin: # Should ideally not be reached if logic above is correct
                QMessageBox.critical(self, "Remote Configuration Error", "Failed to configure the 'origin' remote.")
                return

            # 3. Fetch from the remote to verify and get refs
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                print(f"Fetching from remote 'origin' ({remote_url})...")
                origin.fetch()
                print("Fetch successful.")
            except GitExceptions.GitCommandError as e:
                QMessageBox.critical(self, "Fetch Error",
                                     f"Could not fetch from the remote repository '{remote_url}'.\n"
                                     f"Error: {e.stderr}\n"
                                     "Please check the URL/path and your network connection or authentication if applicable.")
                return
            finally:
                QApplication.restoreOverrideCursor()

            # 4. If local repo has no commits yet but has content, create an initial commit.
            if not user_repo.head.is_valid() and (user_repo.is_dirty(untracked_files=True) or any(user_repo.untracked_files)):
                print("UserStore has uncommitted content in a repo with no commits. Creating initial commit.")
                user_repo.git.add(A=True) # Stage all changes and untracked files
                user_repo.index.commit("Initial commit of existing UserStore content before syncing with remote.")
                print("Initial local commit created.")

            # 5. Configuration successful, save settings
            if self.config_manager:
                self.config_manager.set_app_setting("backup_repo_path", self.user_store_path)
                self.config_manager.set_app_setting("backup_repo_remote_location", remote_url)

            self._update_ui_for_repo_config(self.user_store_path) # This will call refresh_repository_status
            QMessageBox.information(self, "Connection Successful",
                                    f"Successfully connected UserStore to remote repository:\n{remote_url}\n\n"
                                    "Check the status for any pending pulls or pushes.")
            if self.existing_repo_url_line_edit: self.existing_repo_url_line_edit.clear()

        except GitExceptions.GitCommandError as e:
            QMessageBox.critical(self, "Git Connection Error", f"A Git command failed during connection: {e}\nStderr: {e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"An unexpected error occurred while connecting: {e}")


    def refresh_repository_status(self):
        """
        Checks the Git repository status and updates the UI.
        This is a placeholder for actual Git logic.
        """
        if not self.backup_status_label or not self.repo_path_line_edit:
            return

        local_repo_path = self.config_manager.get_app_setting("backup_repo_path", None) if self.config_manager else None
        remote_location = self.config_manager.get_app_setting("backup_repo_remote_location", None) if self.config_manager else None

        try:
            if not local_repo_path or not remote_location:
                raise GitExceptions.InvalidGitRepositoryError("Local path or remote location not set.")

            try:
                local_repo = git.Repo(local_repo_path)
            except GitExceptions.NoSuchPathError:
                raise GitExceptions.InvalidGitRepositoryError(f"Local repository path does not exist: {local_repo_path}")
            except GitExceptions.InvalidGitRepositoryError:
                 raise GitExceptions.InvalidGitRepositoryError(f"Not a valid Git repository: {local_repo_path}")

            if not local_repo.remotes:
                raise GitExceptions.InvalidGitRepositoryError("No remotes configured.")
            
            origin_remote = local_repo.remote("origin")
            if not origin_remote.exists() or origin_remote.url != remote_location:
                raise GitExceptions.InvalidGitRepositoryError(f"Origin remote misconfigured or URL mismatch. Expected '{remote_location}', got '{origin_remote.url if origin_remote.exists() else 'N/A'}'.")

            print("Refreshing repository status: Fetching from origin...")
            origin_remote.fetch()

            has_uncommitted_changes = local_repo.is_dirty(untracked_files=True)
           
            # Initialize variables that will be determined in the try block
            active_branch_name = None
            commits_ahead = 0
            commits_behind = 0
 
            if not local_repo.head.is_valid(): # No commits yet
                status_text = "Status: No commits yet."
                status_color = "gray"
                if has_uncommitted_changes: # Should be caught by add . in connect/setup
                    status_text = "Status: Uncommitted changes (no commits yet)."
                    status_color = "orange"
                self.backup_status_label.setText(status_text)
                self.backup_status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
                if self.pull_repo_button: self.pull_repo_button.setEnabled(True) # Allow pulling if remote might have content
                if self.push_repo_button: self.push_repo_button.setEnabled(False)
                if self.commit_repo_button: self.commit_repo_button.setEnabled(has_uncommitted_changes)
                return

            try:
                active_branch = local_repo.active_branch
                active_branch_name = active_branch.name
                tracking_branch = active_branch.tracking_branch()

                if tracking_branch:
                    # Ensure the tracking branch ref is valid after fetch
                    if tracking_branch.is_valid():
                        tracking_branch_name_for_compare = tracking_branch.name
                        commits_ahead = len(list(local_repo.iter_commits(f"{tracking_branch_name_for_compare}..{active_branch_name}")))
                        commits_behind = len(list(local_repo.iter_commits(f"{active_branch_name}..{tracking_branch_name_for_compare}")))
                    else: # Tracking a remote branch that no longer exists or was never fetched properly
                        raise GitExceptions.GitCommandError(f"Tracking branch {tracking_branch.name} is not valid.", "")
                else: # Local branch not tracking any remote branch
                    commits_ahead = len(list(local_repo.iter_commits(active_branch_name))) # All commits on this branch are "ahead"
                    commits_behind = 0 # Not tracking anything, so not "behind"
            except (GitExceptions.TypeError, GitExceptions.GitCommandError) as branch_error: # TypeError for detached HEAD, GitCommandError for unborn/other
                print(f"Branch status error: {branch_error}")
                # This case might indicate detached HEAD or an unborn branch if initial commit failed.
                # If head is valid but active_branch access fails, it's likely detached HEAD.
                if local_repo.head.is_detached:
                    status_text = "Status: Detached HEAD"
                    status_color = "purple"
                    has_uncommitted_changes = local_repo.is_dirty(untracked_files=True) # Re-check for detached
                    # For detached HEAD, pull/push are generally not standard operations without more context
                    if self.pull_repo_button: self.pull_repo_button.setEnabled(False)
                    if self.push_repo_button: self.push_repo_button.setEnabled(False)
                    if self.commit_repo_button: self.commit_repo_button.setEnabled(has_uncommitted_changes)
                    self.backup_status_label.setText(status_text)
                    self.backup_status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
                    return
                # If not detached but still error, could be complex. Fallback to general error.
                raise GitExceptions.InvalidGitRepositoryError(f"Could not determine branch status: {branch_error}")


        except (GitExceptions.InvalidGitRepositoryError, GitExceptions.NoSuchPathError, ValueError, GitExceptions.GitCommandError) as e:
            print(f"Error accessing repository or remote: {e}")
            self.backup_status_label.setText("Status: Not Configured")
            self.backup_status_label.setStyleSheet("color: black; font-weight: bold;")
            if self.pull_repo_button: self.pull_repo_button.setEnabled(False)
            if self.push_repo_button: self.push_repo_button.setEnabled(False)
            if self.commit_repo_button: self.commit_repo_button.setEnabled(False)
            return
        except Exception as e: # Catch-all for other unexpected errors
            print(f"Unexpected error during repository status refresh: {e}")
            self.backup_status_label.setText("Status: Error")
            self.backup_status_label.setStyleSheet("color: red; font-weight: bold;")
            if self.pull_repo_button: self.pull_repo_button.setEnabled(False)
            if self.push_repo_button: self.push_repo_button.setEnabled(False)
            if self.commit_repo_button: self.commit_repo_button.setEnabled(False)
            return

        status_text = "Status: Unknown"
        status_color = "black"
        
        active_branch_is_tracking = active_branch.tracking_branch() is not None if 'active_branch' in locals() and active_branch else False


        if has_uncommitted_changes:
            status_text = "Status: Uncommitted changes"
            status_color = "orange"
        elif not active_branch_is_tracking and commits_ahead > 0 : # Local branch with commits, not tracking
            status_text = f"Status: Branch '{active_branch_name}' has {commits_ahead} commit(s) not on remote. Push to publish."
            status_color = "blue" # Suggests push
        # Below assumes active_branch_is_tracking is true for these conditions

        elif commits_ahead > 0 and commits_behind > 0:
            status_text = f"Status: Diverged ({commits_ahead} ahead, {commits_behind} behind)"
            status_color = "purple"
        elif commits_ahead > 0:
            status_text = f"Status: {commits_ahead} commit(s) to push"
            status_color = "blue"
        elif commits_behind > 0:
            status_text = f"Status: {commits_behind} commit(s) to pull"
            status_color = "red"
        elif active_branch_is_tracking: # No uncommitted, not ahead, not behind, and tracking

            status_text = "Status: Up to date"
            status_color = "green"
        else: # No uncommitted, no commits_ahead (e.g. new repo, no commits), and not tracking
            status_text = "Status: Ready (no local changes)" # Or "No commits yet" if that's the case
            status_color = "gray"

        self.backup_status_label.setText(status_text)
        self.backup_status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")

        # Enable/disable buttons based on status
        # Pull enabled if configured and (behind or diverged or simply to allow manual refresh)
        if self.pull_repo_button: self.pull_repo_button.setEnabled(True) # Generally allow pull if configured
        if self.push_repo_button: self.push_repo_button.setEnabled(commits_ahead > 0)
        if self.commit_repo_button: self.commit_repo_button.setEnabled(has_uncommitted_changes)

    @Slot()
    def handle_pull_repository(self):
        local_repo_path = self.config_manager.get_app_setting("backup_repo_path", None)
        if not local_repo_path:
            QMessageBox.warning(self, "Pull Error", "Repository not configured.")
            return
        try:
            repo = git.Repo(local_repo_path)
            origin = repo.remote("origin")
            QMessageBox.information(self, "Pulling...", "Attempting to pull latest changes...")
            # Check for uncommitted changes before pulling
            if repo.is_dirty(untracked_files=True):
                QMessageBox.warning(self, "Uncommitted Changes", 
                                    "You have uncommitted changes. Please commit or stash them before pulling.")
                return
            pull_info_list = origin.pull()
            # Check pull_info for errors or details
            # For example, if pull_info_list is empty or flags indicate failure
            QMessageBox.information(self, "Pull Successful", "Successfully pulled latest changes.")
        except GitExceptions.GitCommandError as e:
            QMessageBox.critical(self, "Pull Error", f"Failed to pull changes: {e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Pull Error", f"An unexpected error occurred during pull: {e}")
        finally:
            self.refresh_repository_status()

    @Slot()
    def handle_push_repository(self):
        local_repo_path = self.config_manager.get_app_setting("backup_repo_path", None)
        if not local_repo_path:
            QMessageBox.warning(self, "Push Error", "Repository not configured.")
            return
        try:
            repo = git.Repo(local_repo_path)
            origin = repo.remote("origin")
            QMessageBox.information(self, "Pushing...", "Attempting to push local changes...")
            push_info_list = origin.push()
            errors = [info for info in push_info_list if info.flags & git.PushInfo.ERROR]
            if errors:
                error_summaries = "\n".join([e.summary for e in errors])
                raise Exception(f"Push error(s):\n{error_summaries}")
            QMessageBox.information(self, "Push Successful", "Successfully pushed local changes.")
        except GitExceptions.GitCommandError as e:
            QMessageBox.critical(self, "Push Error", f"Failed to push changes: {e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Push Error", f"An unexpected error occurred during push: {e}")
        finally:
            self.refresh_repository_status()

    @Slot()
    def handle_commit_repository(self):
        local_repo_path = self.config_manager.get_app_setting("backup_repo_path", None)
        if not local_repo_path:
            QMessageBox.warning(self, "Commit Error", "Repository not configured.")
            return
        
        repo = git.Repo(local_repo_path)
        if not repo.is_dirty(untracked_files=True):
            QMessageBox.information(self, "No Changes", "No changes to commit.")
            self.refresh_repository_status()
            return

        commit_message, ok = QInputDialog.getText(self, "Commit Changes", "Enter commit message:")
        if ok and commit_message:
            try:
                repo.git.add(A=True)
                repo.index.commit(commit_message)
                QMessageBox.information(self, "Commit Successful", "Changes committed.")
            except GitExceptions.GitCommandError as e:
                QMessageBox.critical(self, "Commit Error", f"Failed to commit changes: {e.stderr}")
            except Exception as e:
                QMessageBox.critical(self, "Commit Error", f"An unexpected error occurred during commit: {e}")
            finally:
                self.refresh_repository_status()
        elif ok and not commit_message:
            QMessageBox.warning(self, "Commit Cancelled", "Commit message cannot be empty.")

class ConfigureRepositoryDialog(QDialog):
    def __init__(self, parent=None, user_store_display_name: str = "your data"):
        super().__init__(parent)
        self.setWindowTitle("Configure Backup Destination")
        self.layout = QVBoxLayout(self)
        self.backup_destination_path = None

        self.intro_label = QLabel(
            f"The application will use Git to manage backups of {user_store_display_name}.\n"
            "Please select a folder where these backups will be stored (e.g., a network share or another local folder).\n"
            "This folder will be set up as a Git remote repository.", self
        )
        self.intro_label.setWordWrap(True)
        self.layout.addWidget(self.intro_label)

        path_layout = QHBoxLayout()
        self.destination_path_line_edit = QLineEdit(self)
        self.destination_path_line_edit.setPlaceholderText("Path to backup destination folder")
        path_layout.addWidget(self.destination_path_line_edit)

        self.browse_button = QPushButton("Browse...", self)
        self.browse_button.clicked.connect(self._browse_for_destination)
        path_layout.addWidget(self.browse_button)
        self.layout.addLayout(path_layout)

        # In the future, you could add an "Advanced" section or button here
        # to allow specifying a Git URL directly.

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _browse_for_destination(self):
        path = QFileDialog.getExistingDirectory(self, "Select Backup Destination Folder")
        if path:
            self.destination_path_line_edit.setText(path)

    def _validate_and_accept(self):
        self.backup_destination_path = self.destination_path_line_edit.text().strip()
        if not self.backup_destination_path:
            QMessageBox.warning(self, "Input Required", "Please select or enter a backup destination folder.")
            return
        self.accept()

    def get_backup_destination_path(self):
        return self.backup_destination_path