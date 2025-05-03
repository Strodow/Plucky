import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel
)
from PySide6.QtCore import Signal, Slot

class SongMetadataEditorWidget(QWidget):
    """
    A widget containing fields to edit the metadata of a song (e.g., title, artist).
    Emits a signal whenever the data is changed by the user.
    """
    # Signal arguments: song_key (str), current_metadata (dict)
    data_changed = Signal(str, dict)

    def __init__(self, song_key, song_metadata, parent=None):
        super().__init__(parent)
        self.song_key = song_key
        # Store a copy of the initial metadata to work with
        # Exclude 'sections' as we only edit metadata here
        self._current_metadata = {k: v for k, v in song_metadata.items() if k != 'sections'}

        # --- UI Elements ---
        self.title_input = QLineEdit()
        # Add more fields as needed (e.g., artist, key, default_tempo)
        # self.artist_input = QLineEdit()
        # self.key_input = QLineEdit()

        # --- Layout ---
        form_layout = QFormLayout()
        form_layout.addRow("Song Title:", self.title_input)
        # form_layout.addRow("Artist:", self.artist_input)
        # form_layout.addRow("Key:", self.key_input)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        self.setLayout(main_layout)

        # --- Load Initial Data ---
        self.title_input.setText(self._current_metadata.get("title", ""))
        # self.artist_input.setText(self._current_metadata.get("artist", ""))
        # self.key_input.setText(self._current_metadata.get("key", ""))

        # --- Connections ---
        self.title_input.textChanged.connect(self._emit_data_changed)
        # Connect textChanged for other fields if added

    def get_metadata(self):
        """Returns the current metadata from the input fields."""
        self._current_metadata["title"] = self.title_input.text()
        # Update other fields if added
        # self._current_metadata["artist"] = self.artist_input.text()
        # self._current_metadata["key"] = self.key_input.text()
        return self._current_metadata.copy() # Return a copy

    def _emit_data_changed(self):
        """Gathers current data and emits the data_changed signal."""
        current_data = self.get_metadata()
        self.data_changed.emit(self.song_key, current_data)