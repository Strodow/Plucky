from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy # Changed QWidget to QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

# Assuming PREVIEW_WIDTH is a known constant, e.g., from MainWindow or a config
# For now, let's use a typical value. If ScaledSlideButton.PREVIEW_CONTENT_WIDTH is accessible, use that.
WIDGET_PREVIEW_WIDTH = 160

class SongHeaderWidget(QFrame): # Inherit from QFrame
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True) # Ensure the widget paints its background
        
        # For QFrame, you might want to control the frame's appearance
        self.setFrameShape(QFrame.Shape.StyledPanel) # This helps with styling
        self.setFrameShadow(QFrame.Shadow.Plain)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 5) # Left, Top, Right, Bottom
        self.main_layout.setSpacing(10)

        self.title_label = QLabel(title)
        font = self.title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1) # Slightly larger
        self.title_label.setFont(font) 
        # Ensure title label text is white, as it's already set
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
                border-radius: 4px;
                /* If using QFrame.NoFrame, you might add border here: */
                /* border: 1px solid #4A5568; */
            }
        """)
        
        # Size policy: Preferred horizontally (will take sizeHint), Fixed vertically
        # The FlowLayout will use its sizeHint.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setTitle(self, title: str):
        self.title_label.setText(title)

    def sizeHint(self) -> QSize:
        # Suggest a width that's reasonably wide, e.g., for 2-3 slide buttons.
        # This helps FlowLayout decide if it should wrap this item to a new line.
        # Height is already fixed by setFixedHeight.
        # Let's make it at least the width of two preview buttons plus some spacing.
        return QSize(WIDGET_PREVIEW_WIDTH * 2 + 20, self.height())