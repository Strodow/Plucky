import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtCore import Signal, Slot

# Import the SongMetadataEditorWidget
from song_metadata_editor_widget import SongMetadataEditorWidget

class SongMetadataEditorWindow(QMainWindow):
    # Signal to emit when changes are saved, sends song_key and updated metadata
    metadata_saved = Signal(str, dict)

    def __init__(self, song_key, song_metadata, parent=None):
        super().__init__(parent)

        self.song_key = song_key
        # Make a copy to compare against later, excluding 'sections'
        self._initial_metadata = {k: v for k, v in song_metadata.items() if k != 'sections'}

        self.setWindowTitle(f"Edit Song: {song_metadata.get('title', song_key)}")
        self.setGeometry(150, 150, 350, 200) # Adjust size as needed

        # --- UI Elements ---
        # Pass a copy of the data to the editor as well
        self.editor_widget = SongMetadataEditorWidget(song_key=song_key, song_metadata=song_metadata.copy())

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
        self.editor_widget.data_changed.connect(self._on_editor_data_changed)
        self._has_unsaved_changes = False # Flag to track changes

    @Slot(str, dict)
    def _on_editor_data_changed(self, song_key, current_editor_data):
        """Slot to track if the editor content has changed."""
        if current_editor_data != self._initial_metadata:
             self._has_unsaved_changes = True
             if not self.windowTitle().endswith("*"):
                 self.setWindowTitle(self.windowTitle() + "*")
        elif self.windowTitle().endswith("*"):
             self.setWindowTitle(self.windowTitle().rstrip("*"))
             self._has_unsaved_changes = False

    def _on_save_clicked(self):
        """Handles the Save button click."""
        updated_metadata = self.editor_widget.get_metadata()
        self.metadata_saved.emit(self.song_key, updated_metadata)
        self._initial_metadata = updated_metadata.copy() # Update initial data after saving
        self._has_unsaved_changes = False # Reset changes flag
        self.close() # Close the window after saving

    def closeEvent(self, event):
        """Handles the window close event, prompting to save if there are unsaved changes."""
        if self._has_unsaved_changes:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save them?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self._on_save_clicked()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()