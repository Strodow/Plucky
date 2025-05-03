# button_widgets.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton, QLabel, QFrame,
    QSizePolicy, QSpacerItem, QApplication
)
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor
from PySide6.QtCore import Qt, QSize, Signal, QRect

# --- Individual 16x9 Button Widget ---
class AspectRatioButton(QToolButton):
    # Signal emitted when this button is clicked, can pass identifier and associated lyric text
    clicked_with_data = Signal(str, str) # Emit button ID and lyric text

    def __init__(self, button_id, text="", lyric_text="", image_path=None, parent=None):
        super().__init__(parent)
        self.button_id = button_id
        self._lyric_text = lyric_text # Store the lyric text associated with this button
        self._aspect_ratio = 16 / 9.0 # Define the desired aspect ratio

        # --- Changes for Fixed Size ---
        # Define a base width and calculate height based on aspect ratio
        self.base_button_width = 160 # Store base width as an attribute
        base_height = int(self.base_button_width / self._aspect_ratio)
        self.setFixedSize(self.base_button_width, base_height) # Set a fixed size

        # Set size policy to Fixed or Preferred to respect the fixed size/sizeHint
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # --- End Changes for Fixed Size ---


        # Set up the layout and widgets within the button
        # Using a vertical layout to stack image and text
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # Add some padding
        layout.setSpacing(2) # Space between image and text

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True) # Scale image to fit label
        layout.addWidget(self.image_label)

        self.text_label = QLabel(text)
        self_text_label_font = QFont("Arial", 10) # Set a basic font
        self_text_label_font.setBold(True)
        self.text_label.setFont(self_text_label_font)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.setLayout(layout)

        # Set initial content
        self.set_text(text)
        if image_path:
            self.set_image(image_path)
        else:
             # Set a default background color if no image
             self.setStyleSheet("background-color: #555; color: white;") # Added text color


        # --- Stylesheet for Hover Effect ---
        self.setStyleSheet("""
            AspectRatioButton {
                background-color: #555; /* Default background */
                color: white; /* Default text color */
                border: 1px solid #666; /* Default border */
                border-radius: 5px; /* Rounded corners */
            }
            AspectRatioButton:hover {
                background-color: #777; /* Darker background on hover */
                border: 1px solid #fff; /* White border on hover */
            }
            /* Ensure labels inside don't interfere with button styling */
            AspectRatioButton QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        # --- End Stylesheet for Hover Effect ---


        # Connect the button's clicked signal to our custom signal
        self.clicked.connect(lambda: self.clicked_with_data.emit(self.button_id, self._lyric_text))

    def set_text(self, text):
        self.text_label.setText(text)

    def set_image(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.setStyleSheet("""
                AspectRatioButton {
                    background-color: transparent;
                    color: white;
                    border: 1px solid #666;
                    border-radius: 5px;
                }
                AspectRatioButton:hover {
                    background-color: rgba(119, 119, 119, 50);
                    border: 1px solid #fff;
                }
                 AspectRatioButton QLabel {
                    background-color: transparent;
                    border: none;
                }
            """)
        else:
            print(f"Warning: Could not load image from {image_path}")
            self.setStyleSheet("""
                AspectRatioButton {
                    background-color: #555;
                    color: white;
                    border: 1px solid #666;
                    border-radius: 5px;
                }
                AspectRatioButton:hover {
                    background-color: #777;
                    border: 1px solid #fff;
                }
                 AspectRatioButton QLabel {
                    background-color: transparent;
                    border: none;
                }
            """)
            self.image_label.setPixmap(QPixmap())

    def sizeHint(self):
        return self.size()

    def resizeEvent(self, event):
        if not self.image_label.pixmap().isNull():
             current_pixmap = QPixmap(self.image_label.pixmap())
             scaled_pixmap = current_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
             self.image_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)


# --- Container Widget for Buttons ---
class ButtonGridWidget(QFrame):
    # Signal to indicate a button was clicked and pass the lyric data
    button_clicked_with_lyric = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use a grid layout to arrange the items (titles, separators, horizontal layouts of buttons)
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
        self.setLayout(self.grid_layout)

        self.buttons = {} # Dictionary to keep track of buttons by ID
        # max_cols is set to a fixed value in this version
        self.max_cols = 4 # Fixed number of columns

        self.setStyleSheet("QFrame { background-color: #333; border: 1px solid #555; }")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Note: We are not dynamically clearing and repopulating the grid in this version.


    # add_button method creates and returns the button, parent adds to layout
    def add_button(self, button_id, text="", lyric_text="", image_path=None):
        """
        Creates an AspectRatioButton instance.
        Does NOT add it to this widget's grid layout internally.
        Returns the created button instance.
        """
        if button_id in self.buttons:
            print(f"Button with ID {button_id} already exists.")
            return self.buttons[button_id]

        new_button = AspectRatioButton(button_id, text, lyric_text, image_path)
        self.buttons[button_id] = new_button
        new_button.clicked_with_data.connect(self._handle_button_clicked_internal)

        return new_button


    # In this version, clear_grid_layout is not used for dynamic repopulation
    # but might be present for other purposes.
    def clear_grid_layout(self):
        """Removes all items from the grid layout."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                 pass # Don't delete spacers managed elsewhere if any


    def remove_button(self, button_id):
        if button_id in self.buttons:
            button_to_remove = self.buttons.pop(button_id)
            # Note: Removing from the layout needs to be handled by the parent (MainWindow)
            # since the button is added to the layout there.
            print(f"Button {button_id} removed from internal dictionary. Layout removal needs to be handled by parent.")
            button_to_remove.deleteLater() # Safely delete the widget object


    def update_button(self, button_id, text=None, lyric_text=None, image_path=None):
        if button_id in self.buttons:
            button = self.buttons[button_id]
            if text is not None:
                button.set_text(text)
            if lyric_text is not None:
                 button._lyric_text = lyric_text
            if image_path is not None:
                button.set_image(image_path)
        else:
            print(f"Button with ID {button_id} not found.")

    def handle_button_clicked(self, button_id):
        pass

    def _handle_button_clicked_internal(self, button_id, lyric_text):
        print(f"Button clicked internally: {button_id}")
        self.button_clicked_with_lyric.emit(button_id, lyric_text)

