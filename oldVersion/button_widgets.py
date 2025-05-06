# button_widgets.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton, QLabel, QFrame,
    QSizePolicy, QSpacerItem, QApplication
)
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QDragEnterEvent, QDropEvent, QDragMoveEvent, QPaintEvent, QPen, QBrush, QDragLeaveEvent # Import event types and drawing classes
from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint # Import Signal, QPoint
import os # To check file extensions

# --- Local Import for Type Checking ---
# Use a try-except block in case this file is run standalone or import structure changes
try:
    from button_remake import LyricCardWidget
except ImportError:
    LyricCardWidget = None # Define as None if import fails, check before use

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
    # Signal to indicate a button was clicked (original)
    button_clicked_with_lyric = Signal(str, str)

    # --- Signals for Drag and Drop ---
    image_dropped_on_card = Signal(str, str) # Emits: button_id, image_path
    image_dropped_at_pos = Signal(QPoint, str) # Emits: drop_position (relative to ButtonGridWidget), image_path

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

        # --- Enable Drag and Drop ---
        self.setAcceptDrops(True)

        # --- Indicator State for Drag and Drop ---
        self._indicator_rect = None # QRect of the card to highlight
        self._indicator_line_pos = None # QPoint for insertion line (x, y of top point)
        self._indicator_line_height = 0 # Height for the insertion line

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

    # --- Drag and Drop Event Handlers ---

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept the drag event if it contains URLs pointing to image files."""
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            # Check if at least one URL is an image file
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    _, ext = os.path.splitext(file_path)
                    if ext.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']: # Add more if needed
                        print(f"INFO: Drag Enter Accepted: Found image {file_path}")
                        event.acceptProposedAction()
                        return # Accept as soon as one valid image is found
        # print("Drag Enter Ignored: No valid image URLs found.") # Can comment this out too if desired
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Update the visual indicator based on the current drag position."""
        # Determine target and update indicator state
        self._update_drop_indicator(event.position().toPoint())
        event.acceptProposedAction() # Accept the move to allow dropEvent

    def dropEvent(self, event: QDropEvent):
        """Handle the drop event, determine target, and emit signals."""
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            event.ignore()
            return

        image_path = None
        for url in mime_data.urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                _, ext = os.path.splitext(file_path)
                if ext.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
                    image_path = file_path
                    break # Use the first valid image found

        if not image_path:
            print("Drop Ignored: No valid image file path found in dropped URLs.")
            event.ignore()
            return

        print(f"INFO: Drop Accepted: Image path = {image_path}")
        drop_pos = event.position().toPoint()

        # --- Determine Target ---
        # Use the same logic as dragMoveEvent used, based on the final position
        target_widget = self.childAt(drop_pos) # Find widget at final drop pos
        # print(f"Widget at drop position ({drop_pos}): {target_widget}") # Debug print removed

        # Check if the target widget is one of our AspectRatioButtons
        # Note: This assumes AspectRatioButton is the direct child hit by childAt.
        # If the button has internal widgets (like the QLabel), childAt might return those.
        # A more robust check might involve traversing up the parent hierarchy like before.

        card_widget = None
        widget_at_pos = target_widget
        while widget_at_pos is not None and widget_at_pos is not self:
            # Check if the widget is an AspectRatioButton instance
            if isinstance(widget_at_pos, AspectRatioButton):
                card_widget = widget_at_pos
                break
            widget_at_pos = widget_at_pos.parentWidget() # Move up the hierarchy

        if card_widget:
            # --- Dropped ON an AspectRatioButton ---
            button_id = card_widget.button_id # Get the ID from the button
            # print(f"Drop detected ON card: {button_id}") # Debug print removed
            self.image_dropped_on_card.emit(button_id, image_path)
            event.acceptProposedAction()
        else:
            # --- Dropped NOT on a specific card ---
            # print(f"Drop detected BETWEEN cards (or in empty space) at {drop_pos}. Image: {image_path}") # Debug print removed
            self.image_dropped_at_pos.emit(drop_pos, image_path)
            event.acceptProposedAction() # Accept for now, even if we don't emit perfectly yet

        # --- Clear indicator after drop ---
        self._clear_indicator_state()
        self.update() # Trigger repaint to remove indicator

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """Clear the visual indicator when the drag leaves the widget."""
        # print("Drag Leave Event") # Debug print removed
        self._clear_indicator_state()
        self.update() # Trigger repaint to remove indicator
        event.accept()

    def paintEvent(self, event: QPaintEvent):
        """Draw the widget and the drop indicator if active."""
        # First, draw the default widget content
        super().paintEvent(event)

        # Now, draw the indicator on top if needed
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._indicator_rect:
            # Draw a highlight rectangle over a card
            # print(f"  Painting indicator rectangle: {self._indicator_rect}") # Debug print removed
            highlight_color = QColor(0, 150, 255, 100) # Semi-transparent blue
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(Qt.PenStyle.NoPen) # No border for the highlight itself
            painter.drawRect(self._indicator_rect)
            # Optionally draw a border around it too
            border_color = QColor(0, 150, 255, 200)
            pen = QPen(border_color, 2) # 2px solid border
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._indicator_rect)

        elif self._indicator_line_pos:
            # Draw an insertion line between cards
            # print(f"  Painting indicator line at: {self._indicator_line_pos}, height: {self._indicator_line_height}") # Debug print removed
            line_color = QColor(0, 150, 255, 200) # Solid blue line
            pen = QPen(line_color, 3) # 3px thick line
            painter.setPen(pen)
            x = self._indicator_line_pos.x()
            y = self._indicator_line_pos.y()
            height = self._indicator_line_height
            painter.drawLine(x, y, x, y + height)

        painter.end()

    def _clear_indicator_state(self):
        """Resets the indicator state variables."""
        self._indicator_rect = None
        self._indicator_line_pos = None
        self._indicator_line_height = 0

    def _update_drop_indicator(self, current_pos: QPoint):
        """Determines the drop target and updates indicator state, triggering repaint."""
        # Reset state before checking
        new_rect = None
        new_line_pos = None
        new_line_height = 0

        # --- Check LyricCardWidget is importable ---
        if not LyricCardWidget:
             print("Warning: LyricCardWidget not imported, cannot update drop indicator.")
             return # Cannot proceed without the class definition

        target_widget = self.childAt(current_pos)
        card_widget = None
        widget_at_pos = target_widget
        while widget_at_pos is not None and widget_at_pos is not self:
            if isinstance(widget_at_pos, AspectRatioButton):
                card_widget = widget_at_pos
                break
            widget_at_pos = widget_at_pos.parentWidget()

        if card_widget:
            # --- Over a card: Set indicator rect ---
            # print(f"    Indicator target: Card {card_widget.button_id}") # Debug print removed
            # Get geometry relative to ButtonGridWidget
            card_pos_in_grid = card_widget.mapTo(self, QPoint(0, 0))
            new_rect = QRect(card_pos_in_grid, card_widget.size())
            # print(f"    Calculated card rect: {new_rect}") # Debug print removed
        else:
            # --- Between cards: Find closest gap and set indicator line ---
            # Iterate through the actual layout items to find LyricCardWidgets
            closest_card_left_geom = None
            closest_card_right_geom = None
            min_dist_left = float('inf') # Distance from cursor to right edge of left card
            min_dist_right = float('inf') # Distance from cursor to left edge of right card
            target_row_geom = None # Store geometry of the row containing the cursor vertically
            # print(f"    Indicator target: Between cards (checking layout)") # Debug print removed

            layout = self.grid_layout
            for row in range(layout.rowCount()):
                row_container_item = layout.itemAtPosition(row, 0)
                if row_container_item and isinstance(row_container_item.widget(), QWidget):
                    row_widget = row_container_item.widget()
                    row_layout = row_widget.layout()
                    if isinstance(row_layout, QHBoxLayout):
                        # Check if cursor is vertically within this row's container
                        row_container_geom = row_container_item.geometry()
                        if row_container_geom.top() <= current_pos.y() <= row_container_geom.bottom():
                            target_row_geom = row_container_geom # Found the target row vertically
                            for i in range(row_layout.count()):
                                item = row_layout.itemAt(i)
                                if item and isinstance(item.widget(), LyricCardWidget):
                                    card = item.widget()
                                    card_pos = card.mapTo(self, QPoint(0,0))
                                    card_rect = QRect(card_pos, card.size())

                                    # Check if cursor is left of this card
                                    dist_right = card_rect.left() - current_pos.x()
                                    if 0 < dist_right < min_dist_right:
                                        min_dist_right = dist_right
                                        closest_card_right_geom = card_rect # This card is the closest one to the right

                                    # Check if cursor is right of this card
                                    dist_left = current_pos.x() - card_rect.right()
                                    if 0 < dist_left < min_dist_left:
                                        min_dist_left = dist_left
                                        closest_card_left_geom = card_rect # This card is the closest one to the left
                            # Break after processing the target row
                            break

            # --- Determine line position based on findings ---
            spacing = self.grid_layout.spacing() if self.grid_layout else 10

            if closest_card_right_geom:
                 # Cursor is to the left of a card, draw line before it
                 # print(f"    Found closest card to the right with left edge at {closest_card_right_geom.left()}") # Debug print removed
                 # Draw line just to the left of this card
                 line_x = closest_card_right_geom.left() - spacing // 2 # Mid-spacing
                 new_line_pos = QPoint(line_x, closest_card_right_geom.top())
                 new_line_height = closest_card_right_geom.height()
                 # print(f"    Calculated line pos (before right card): {new_line_pos}, height: {new_line_height}") # Debug print removed
            elif closest_card_left_geom:
                 # Cursor is to the right of a card, draw line after it
                 # print(f"    Found closest card to the left with right edge at {closest_card_left_geom.right()}") # Debug print removed
                 # Draw line just to the right of this card
                 line_x = closest_card_left_geom.right() + spacing // 2 # Mid-spacing
                 new_line_pos = QPoint(line_x, closest_card_left_geom.top())
                 new_line_height = closest_card_left_geom.height()
                 # print(f"    Calculated line pos: {new_line_pos}, height: {new_line_height}") # Debug print removed
            else:
                 pass # No line needed if no adjacent cards found in the row
                 # print("    No adjacent card found in the same vertical range.") # Debug print removed
            # TODO: Add logic for dropping before the first card in a row, or near titles/separators

        # --- Update state only if changed and trigger repaint ---
        if self._indicator_rect != new_rect or self._indicator_line_pos != new_line_pos:
            # print(f"    Indicator state changed. Old: rect={self._indicator_rect}, line={self._indicator_line_pos}. New: rect={new_rect}, line={new_line_pos}. Triggering update.") # Removed final debug print
            self._indicator_rect = new_rect
            self._indicator_line_pos = new_line_pos
            self._indicator_line_height = new_line_height
            self.update() # Request repaint
