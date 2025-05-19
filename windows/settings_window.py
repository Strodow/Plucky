from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QDialogButtonBox, QTabWidget, QLabel,
    QComboBox, QPushButton, QApplication, QMessageBox, QGroupBox
)
from PySide6.QtCore import QDir, QFileInfo, Slot, Signal
from PySide6.QtGui import QScreen
from PySide6.QtUiTools import QUiLoader
import os # Needed for os.path.basename
import ctypes # For HRESULT S_OK

# Attempt to import from decklink_handler.
try:
    # This assumes decklink_handler.py is in the parent directory of 'windows'
    # Adjust if your project structure is different (e.g. Plucky.decklink_handler)
    from .. import decklink_handler
except ImportError:
    # Fallback for different execution contexts or structures
    import decklink_handler

class SettingsWindow(QDialog):
    # Signal to indicate the selected output monitor has changed
    output_monitor_changed = Signal(QScreen)  # Emits the selected QScreen object
    # Emits (fill_device_index, key_device_index)
    decklink_fill_key_devices_selected = Signal(int, int)

    def __init__(self, benchmark_data: dict,
                 current_output_screen: QScreen = None,
                 current_decklink_fill_index: int = -1, # Pass current fill selection
                 current_decklink_key_index: int = -1,   # Pass current key selection
                 current_decklink_video_mode: dict = None, # Pass current video mode
                 parent=None):
        super().__init__(parent)
        self._current_output_screen = current_output_screen
        self._current_decklink_fill_index = current_decklink_fill_index
        self._current_decklink_key_index = current_decklink_key_index
        self._current_decklink_video_mode = current_decklink_video_mode # Store current video mode
        self._decklink_api_initialized_by_settings = False # Track if we initialized it


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