# settings_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QColorDialog, QGroupBox,
    QMessageBox, QSpacerItem, QSizePolicy, QDialogButtonBox, QApplication # Added imports
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette # Added imports


class SettingsDialog(QDialog):
    def __init__(self, current_screen_index, current_card_bg_color, load_stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self._initial_screen_index = current_screen_index
        self._selected_card_bg_color = current_card_bg_color # Store initial color
        self._load_stats = load_stats # Store the passed stats
        self._selected_screen_index = current_screen_index

        layout = QVBoxLayout(self)

        # --- Screen Selection ---
        screen_group = QGroupBox("Output Screen")
        screen_layout = QHBoxLayout(screen_group)
        screen_layout.addWidget(QLabel("Output Display Screen:"))

        self.screen_combo = QComboBox()
        self.populate_screen_combo()
        screen_layout.addWidget(self.screen_combo)
        layout.addWidget(screen_group)

        # --- Card Background Color Group ---
        card_bg_group = QGroupBox("Card Appearance")
        card_bg_layout = QHBoxLayout(card_bg_group)
        card_bg_layout.addWidget(QLabel("Default Card Background:"))
        self.card_bg_button = QPushButton("Choose Color")
        self.card_bg_button.clicked.connect(self._choose_card_bg_color) # Connect button
        self.card_bg_preview = QLabel() # Label to show the color
        self.card_bg_preview.setMinimumWidth(40)
        self.card_bg_preview.setAutoFillBackground(True)
        self._update_color_preview(self.card_bg_preview, self._selected_card_bg_color) # Show initial color
        card_bg_layout.addWidget(self.card_bg_button)
        card_bg_layout.addWidget(self.card_bg_preview)
        card_bg_layout.addStretch()
        layout.addWidget(card_bg_group)

        # Add a spacer before the stats button (optional, adjust as needed)
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

    def get_selected_card_background_color(self):
        """Returns the selected card background color hex string."""
        return self._selected_card_bg_color

    def _choose_card_bg_color(self):
        """Opens a color dialog to choose the card background color."""
        initial_color = QColor(self._selected_card_bg_color) # Use current selection
        color = QColorDialog.getColor(initial_color, self, "Choose Card Background Color")
        if color.isValid():
            hex_color = color.name(QColor.NameFormat.HexRgb) # Get #RRGGBB format
            self._selected_card_bg_color = hex_color # Update internal state
            self._update_color_preview(self.card_bg_preview, hex_color) # Update preview label

    def _update_color_preview(self, label_widget, hex_color):
        """Updates the background color of a QLabel to show a color preview."""
        palette = label_widget.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(hex_color)) # Set background role
        label_widget.setPalette(palette)

    def _show_load_stats_message(self):
        """Displays the collected loading statistics in a message box."""
        if not self._load_stats:
            QMessageBox.information(self, "Load Stats", "No loading statistics collected yet.")
            return

        stats_message = "Initial Load Times:\n\n"
        stats_message += f"- App Settings Load: {self._load_stats.get('app_settings_load_time', 0):.4f} seconds\n" # Added this line
        stats_message += f"- Template Load: {self._load_stats.get('template_load_time', 0):.4f} seconds\n"
        stats_message += f"- Song Data Load: {self._load_stats.get('song_data_load_time', 0):.4f} seconds\n"
        stats_message += f"- Grid Population: {self._load_stats.get('grid_population_time', 0):.4f} seconds\n"
        stats_message += f"  - Image Loading (within grid): {self._load_stats.get('image_load_time', 0):.4f} seconds\n"

        # Use 'self' as the parent for the message box so it appears centered over the dialog
        QMessageBox.information(self, "Load Stats", stats_message)