from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QMenu
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QPalette, QContextMenuEvent

# This will be the base width for calculations.
BASE_BUTTON_WIDTH = 160

class SongHeaderWidget(QFrame): # Inherit from QFrame
    # Signal to emit the section_id when title edit is requested
    edit_title_requested = Signal(str) # Emits section_id
    # Signal to emit the section_id when full section properties edit is requested
    edit_properties_requested = Signal(str) # Emits section_id

    def __init__(self, title: str, section_id: str, current_button_width: int = BASE_BUTTON_WIDTH, parent=None):
        super().__init__(parent)
        self._current_button_width = current_button_width
        self.setAutoFillBackground(True) # Ensure the widget paints its background

        # For QFrame, you might want to control the frame's appearance
        self.setFrameShape(QFrame.Shape.StyledPanel) # This helps with styling
        self.setFrameShadow(QFrame.Shadow.Plain)

        self.section_id = section_id
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 5) # Left, Top, Right, Bottom
        self.main_layout.setSpacing(10)

        self.title_label = QLabel(title)
        font = self.title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1) # Slightly larger
        self.title_label.setFont(font)
        # Ensure label background is transparent so frame background shows through
        self.title_label.setStyleSheet("color: white; background-color: transparent;")

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addStretch(1) # Pushes future buttons to the right

        # Example: Placeholder for a future loop button
        # self.loop_button = QPushButton("Loop")
        # self.loop_button.setFixedSize(QSize(60, 24))
        # self.loop_button.setStyleSheet("QPushButton { background-color: #5A67D8; color: white; border-radius: 3px; padding: 2px 5px; }")
        # self.main_layout.addWidget(self.loop_button)

        self.setFixedHeight(35) # Define a fixed height for the header
        self.setStyleSheet("""
            SongHeaderWidget {
                background-color: #2D3748; /* Darker color (Tailwind gray-800 equivalent) */
                margin-top: 8px; /* Add space above the header */
                border-radius: 4px;
                /* If using QFrame.NoFrame, you might add border here: */
                /* border: 1px solid #4A5568; */
            }
        """)
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setTitle(self, title: str):
        self.title_label.setText(title)
    
    def get_song_title(self) -> str:
        """Returns the current song title displayed by the header."""
        return self.title_label.text() # Or however you store/access the title string

    def set_reference_button_width(self, width: int):
        self._current_button_width = width
        self.updateGeometry() # May be needed if sizeHint changes

    def sizeHint(self) -> QSize:
        return QSize(self._current_button_width * 2 + 20, self.height())
    
    def contextMenuEvent(self, event):
        """Shows a context menu on right-click."""
        menu = QMenu(self)
        
        edit_song_action = menu.addAction(f"Edit Song Title: \"{self.title_label.text()}\"")
        menu.addSeparator()
        edit_this_section_action = menu.addAction(f"Edit Section: \"{self.title_label.text()}\"")
        # Add more song-level actions here in the future if needed
        # menu.addSeparator()
        # delete_song_action = menu.addAction("Delete Entire Song")

        # Show the menu once with all actions added
        action_selected = menu.exec(event.globalPos())

        if action_selected == edit_song_action:
            print(f"DEBUG: Emitting edit_title_requested for section_id: {self.section_id}") # Diagnostic
            self.edit_title_requested.emit(self.section_id)
        elif action_selected == edit_this_section_action:
            print(f"DEBUG: Emitting edit_properties_requested for section_id: {self.section_id}") # Diagnostic
            self.edit_properties_requested.emit(self.section_id)