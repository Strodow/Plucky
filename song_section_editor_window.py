import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtCore import Signal, Slot # Import Slot

# Import the SectionEditorWidget
from section_editor_widget import SectionEditorWidget # Corrected import name

class SongSectionEditorWindow(QMainWindow):
    # Signal to emit when changes are saved, sends button_id and updated data
    section_data_saved = Signal(str, dict)

    def __init__(self, button_id, section_data, parent=None):
        super().__init__(parent)

        self.button_id = button_id
        # Make a copy to compare against later, preventing modification by reference
        self._initial_section_data = section_data.copy()

        self.setWindowTitle(f"Edit Section: {section_data.get('name', 'New Section')}")
        self.setGeometry(100, 100, 400, 300) # Default window size

        # --- UI Elements ---
        # Pass a copy of the data to the editor as well, so it works independently
        self.editor_widget = SectionEditorWidget(button_id=button_id, section_data=section_data.copy())

        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        # --- Layouts ---
        button_layout = QHBoxLayout()
        button_layout.addStretch(1) # Push buttons to the right
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.editor_widget)
        main_layout.addLayout(button_layout)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- Connections ---
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.close) # Close window on cancel

        # Connect the data_changed signal from the editor widget
        # This allows us to track if changes have been made (optional, but good practice)
        self.editor_widget.data_changed.connect(self._on_editor_data_changed)
        self._has_unsaved_changes = False # Flag to track changes

    @Slot(str, dict) # Use Slot decorator for clarity
    def _on_editor_data_changed(self, button_id, current_editor_data):
        """Slot to track if the editor content has changed."""
        # Compare current editor data with the initial data stored in this window
        if current_editor_data != self._initial_section_data:
             self._has_unsaved_changes = True
             # Optional: Update window title to indicate unsaved changes
             if not self.windowTitle().endswith("*"):
                 self.setWindowTitle(self.windowTitle() + "*")
        elif self.windowTitle().endswith("*"):
             self.setWindowTitle(self.windowTitle().rstrip("*")) # Remove asterisk if changes are undone
             self._has_unsaved_changes = False

    def _on_save_clicked(self):
        """Handles the Save button click."""
        updated_data = self.editor_widget.get_section_data()
        self.section_data_saved.emit(self.button_id, updated_data)
        self._initial_section_data = updated_data.copy() # Update initial data after saving
        self._has_unsaved_changes = False # Reset changes flag
        self.close() # Close the window after saving

    def closeEvent(self, event):
        """Handles the window close event, prompting to save if there are unsaved changes."""
        if self._has_unsaved_changes:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save them?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Save:
                self._on_save_clicked() # Save and then close (close happens in _on_save_clicked)
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept() # Discard changes and close
            else:
                event.ignore() # Do not close the window
        else:
            event.accept() # No unsaved changes, just close