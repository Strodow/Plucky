# c:\Users\Logan\Documents\Plucky\song_list_widget.py

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QSizePolicy, QMenu # Removed QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction # Added QAction

class SongListWidget(QTreeWidget):
    """
    A tree widget to display a hierarchical list of songs and their sections.
    Emits a signal when a section item is clicked.
    """
    # Signal arguments: button_id (str), lyric_text (str)
    section_selected = Signal(str, str)
    # Signal argument: button_id (str) of the first section in the song
    song_title_selected = Signal(str)
    # Signal to request editing a song
    edit_song_requested = Signal(str) # Emits the song_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True) # Hide the default header
        self.setMinimumWidth(150) # Give it a reasonable minimum width
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding) # Allow vertical expansion

        # Connect the internal itemClicked signal to our handler
        self.itemClicked.connect(self._handle_item_click)

    def populate(self, songs_data):
        """
        Populates the tree widget with songs and sections from the provided data.
        """
        self.clear() # Clear existing items

        for song_key, song_data in songs_data.items():
            song_title = song_data.get("title", song_key)
            
            first_section_button_id = None # To store the ID of the first section for left-click navigation
            
            # Create top-level item for the song
            song_item = QTreeWidgetItem(self, [song_title])
            song_item.setData(0, Qt.ItemDataRole.UserRole + 2, song_key) # Store song_key for context menu
             # Keep song title selectable for navigation

            if "sections" in song_data and isinstance(song_data["sections"], list):
                found_first_section = False
                for i, section in enumerate(song_data["sections"]):
                    if isinstance(section, dict):
                        section_name = section.get("name", f"Section {i+1}")
                        lyric_text = section.get("lyrics", "")
                        section_name_key = section_name.replace(' ', '_').replace('-', '_').lower()
                        button_id = f"{song_key}__{section_name_key}" # Use double underscore as delimiter

                        # Create child item for the section
                        section_item = QTreeWidgetItem(song_item, [f"  {section_name}"]) # Indent section names slightly
                        # Store the necessary data within the item itself
                        section_item.setData(0, Qt.ItemDataRole.UserRole, (button_id, lyric_text))
                        # Store the button_id of the first valid section found
                        if not found_first_section:
                            first_section_button_id = button_id
                            found_first_section = True

            # Store the first section's button_id in the song item's data (if found)
            if first_section_button_id:
                song_item.setData(0, Qt.ItemDataRole.UserRole + 1, first_section_button_id) # Use a different role

            self.addTopLevelItem(song_item)

    def _handle_item_click(self, item, column):
        """
        Internal slot to handle item clicks and emit the section_selected signal
        if a section item (which has user data) is clicked.
        """
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        first_section_id_data = item.data(0, Qt.ItemDataRole.UserRole + 1)

        if item_data and isinstance(item_data, tuple): # Check if it's a section item (has our tuple stored)
            button_id, lyric_text = item_data
            print(f"Song list item selected: {button_id}")
            self.section_selected.emit(button_id, lyric_text)
        elif first_section_id_data: # Check if it's a song title item with a first section ID
            button_id = first_section_id_data
            print(f"Song list title selected, first section ID: {button_id}")
            self.song_title_selected.emit(button_id)

    def contextMenuEvent(self, event):
        """Handles right-click events on the tree."""
        item = self.itemAt(event.pos())
        if item and item.parent() is None: # Check if it's a top-level item (a song)
            song_key = item.data(0, Qt.ItemDataRole.UserRole + 2) # Retrieve the song_key
            if song_key:
                menu = QMenu(self)
                edit_action = QAction(f"Edit Song: {item.text(0)}", self)
                # Use lambda to emit the signal with the song_key
                edit_action.triggered.connect(lambda checked=False, sk=song_key: self.edit_song_requested.emit(sk))
                menu.addAction(edit_action)
                menu.exec(event.globalPos())
        else:
            # Optional: Call the default context menu event handler if not a song item
            super().contextMenuEvent(event)