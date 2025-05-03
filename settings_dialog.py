# settings_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QComboBox, QLabel, QDialogButtonBox, QApplication,
    QPushButton, QMessageBox, QSpacerItem, QSizePolicy # Added imports
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, current_screen_index, load_stats, parent=None): # Added load_stats parameter
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self._initial_screen_index = current_screen_index
        self._load_stats = load_stats # Store the passed stats
        self._selected_screen_index = current_screen_index

        layout = QVBoxLayout(self)

        # --- Screen Selection ---
        screen_label = QLabel("Output Display Screen:")
        layout.addWidget(screen_label)

        self.screen_combo = QComboBox()
        self.populate_screen_combo()
        layout.addWidget(self.screen_combo)

        # Add a spacer before the stats button
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Load Stats Button ---
        self.stats_button = QPushButton("Show Load Stats")
        self.stats_button.clicked.connect(self._show_load_stats_message)
        layout.addWidget(self.stats_button)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept) # Connect Ok to accept
        button_box.rejected.connect(self.reject) # Connect Cancel to reject
        layout.addWidget(button_box)

        self.setLayout(layout)

    def populate_screen_combo(self):
        """Fills the combo box with available screens."""
        screens = QApplication.screens()
        self.screen_combo.clear()
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            screen_name = f"Screen {i}: {geometry.width()}x{geometry.height()}"
            # Add item with display text and store the index as data
            self.screen_combo.addItem(screen_name, userData=i)

        # Set the current selection based on the initial index
        current_combo_index = self.screen_combo.findData(self._initial_screen_index)
        if current_combo_index != -1:
            self.screen_combo.setCurrentIndex(current_combo_index)

    def get_selected_screen_index(self):
        """Returns the index of the screen selected in the combo box."""
        # Retrieve the index stored in the item's data
        return self.screen_combo.currentData()

    def _show_load_stats_message(self):
        """Displays the collected loading statistics in a message box."""
        if not self._load_stats:
            QMessageBox.information(self, "Load Stats", "No loading statistics collected yet.")
            return

        stats_message = "Initial Load Times:\n\n"
        stats_message += f"- Template Load: {self._load_stats.get('template_load_time', 0):.4f} seconds\n"
        stats_message += f"- Song Data Load: {self._load_stats.get('song_data_load_time', 0):.4f} seconds\n"
        stats_message += f"- Grid Population: {self._load_stats.get('grid_population_time', 0):.4f} seconds\n"
        stats_message += f"  - Image Loading (within grid): {self._load_stats.get('image_load_time', 0):.4f} seconds\n"

        # Use 'self' as the parent for the message box so it appears centered over the dialog
        QMessageBox.information(self, "Load Stats", stats_message)