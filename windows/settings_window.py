from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QDialogButtonBox, QTabWidget, QLabel,
    QComboBox, QPushButton, QApplication, QMessageBox, QGroupBox
)
from PySide6.QtCore import QDir, QFileInfo, Slot, Signal
from PySide6.QtGui import QScreen
from PySide6.QtUiTools import QUiLoader
import os # Needed for os.path.basename

class SettingsWindow(QDialog):
    # Signal to indicate the selected output monitor has changed
    output_monitor_changed = Signal(QScreen) # Emits the selected QScreen object
    def __init__(self, benchmark_data: dict, current_output_screen: QScreen = None, parent=None):
        super().__init__(parent)

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
        self._current_output_screen = current_output_screen # Store the initially passed screen

        # Set window properties
        self.setWindowTitle("Settings")
        self.resize(400, 300) # Set a default size

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