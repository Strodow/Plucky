import sys
print(f"DEBUG: scaled_slide_button.py TOP LEVEL, __name__ is {__name__}") # DIAGNOSTIC
import os
from PySide6.QtWidgets import (
    QApplication, QPushButton, QWidget, QSizePolicy, QHBoxLayout, QButtonGroup, QStyle, QMenu
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPalette
)
from PySide6.QtCore import (
    Qt, QSize, Signal, Slot, QRectF, QPoint, QEvent
)
from typing import Optional, List


# Define content dimensions, matching MainWindow's PREVIEW_WIDTH/HEIGHT for the image part
# These constants are no longer strictly needed here as the button will receive an already-sized pixmap.
# However, they can be useful for the test block.
BASE_TEST_PREVIEW_CONTENT_WIDTH = 160
BASE_TEST_PREVIEW_CONTENT_HEIGHT = 90

class ScaledSlideButton(QPushButton):
    """
    A button that displays a scaled version of a QPixmap and an info banner with icons.
    """
    slide_selected = Signal(int) # Emits the slide_id (which is its index in MainWindow)
    edit_requested = Signal(int) # Emits slide_id when edit is requested
    delete_requested = Signal(int) # Emits slide_id when delete is requested
    next_slide_requested_from_menu = Signal(int) # Emits current slide_id
    previous_slide_requested_from_menu = Signal(int) # Emits current slide_id
    apply_template_to_slide_requested = Signal(int, str) # Emits slide_id, template_name
    def __init__(self, slide_id: int, parent=None):
        super().__init__(parent)
        self._pixmap_to_display = QPixmap() # Stores the pixmap (already scaled by MainWindow)
        self._slide_id = slide_id

        self._slide_number: Optional[int] = None
        self._slide_label: Optional[str] = ""
        self._available_template_names: List[str] = [] # Will be set by MainWindow
        self._banner_height = 25
        self.setCheckable(True)
        self.setAutoExclusive(False)

        self._icon_states = {"error": False, "warning": False}
        self._icon_pixmaps = {}
        self._icon_size = self._banner_height - 10
        self._icon_spacing = 5

        error_icon_path = r"c:\Users\Logan\Documents\Plucky\Plucky\resources\error_icon.png"
        error_pixmap_icon = QPixmap(error_icon_path) # Renamed to avoid conflict
        if not error_pixmap_icon.isNull():
            self._icon_pixmaps["error"] = error_pixmap_icon.scaled(self._icon_size, self._icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else: # pragma: no cover
            print(f"Warning: Could not load error icon from {error_icon_path}")

        warning_pixmap_icon = QPixmap(self._icon_size, self._icon_size) # Renamed
        warning_pixmap_icon.fill(QColor("orange"))
        self._icon_pixmaps["warning"] = warning_pixmap_icon

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QPushButton { border: 1px solid #555; padding: 0px; background-color: #333; color: white; text-align: center; }
            QPushButton:checked { border: 2px solid #0078D7; background-color: #444; }
            QPushButton:hover { background-color: #484848; }
            QPushButton:pressed { background-color: #282828; }
        """)
        self.clicked.connect(self._handle_click)

    def set_pixmap(self, pixmap: QPixmap):
        """Sets the pixmap to be displayed and triggers a repaint."""
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self._pixmap_to_display = pixmap # Assume pixmap is already correctly sized
        else:
            # Create a placeholder if an invalid pixmap is provided
            # For safety, create a minimal placeholder. MainWindow should handle better placeholders.
            self._pixmap_to_display = QPixmap(1,1) # Minimal placeholder
            self._pixmap_to_display.fill(Qt.GlobalColor.lightGray)
            # Optionally draw text on placeholder
            # painter = QPainter(self._scaled_pixmap)
            # painter.drawText(self._scaled_pixmap.rect(), Qt.AlignCenter, "No Preview")
            # painter.end()
        self.update()  # Schedule a repaint


    def set_slide_info(self, number: Optional[int], label: Optional[str]):
        """Sets the information to be displayed in the banner."""
        self._slide_number = number
        self._slide_label = label if label is not None else ""
        self.update() # Request repaint

    def set_icon_state(self, icon_name: str, visible: bool):
        """Sets the visibility state for a specific icon."""
        if icon_name in self._icon_states and self._icon_states[icon_name] != visible:
            self._icon_states[icon_name] = visible
            self.update() # Request repaint if state changed

    def sizeHint(self) -> QSize:
        # The button's preferred size includes the pixmap area and the info banner
        content_width = self._pixmap_to_display.width() if not self._pixmap_to_display.isNull() else BASE_TEST_PREVIEW_CONTENT_WIDTH
        content_height = self._pixmap_to_display.height() if not self._pixmap_to_display.isNull() else BASE_TEST_PREVIEW_CONTENT_HEIGHT
        return QSize(content_width, content_height + self._banner_height)


    def paintEvent(self, event):
        """Overrides the paint event to draw the scaled pixmap, banner, and icons."""
        # Call super().paintEvent() if you want the stylesheet's border/hover effects
        # and then draw on top. If you want full control, omit it or draw borders manually.
        super().paintEvent(event) # Draws border, handles hover/pressed from stylesheet

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        button_rect = self.rect() # The entire area of the button

        # --- Draw the Main Scaled Pixmap ---
        # It's already scaled to PREVIEW_CONTENT_WIDTH x PREVIEW_CONTENT_HEIGHT (or smaller if aspect kept)
        if not self._pixmap_to_display.isNull():
            # Calculate target drawing dimensions for the pixmap, respecting button width
            # The pixmap itself is already scaled to PREVIEW_CONTENT_WIDTH x PREVIEW_CONTENT_HEIGHT
            # We just need to center it if the button is wider.
            
            # Effective width for drawing the pixmap (it won't exceed button width)
            draw_width = min(self._pixmap_to_display.width(), button_rect.width())
            # Effective height (it's already scaled for PREVIEW_CONTENT_HEIGHT)
            draw_height = self._pixmap_to_display.height()

            img_x = (button_rect.width() - draw_width) / 2
            # Center vertically within its designated PREVIEW_CONTENT_HEIGHT area
            # The content area height is self._pixmap_to_display.height()
            img_y = (self._pixmap_to_display.height() - draw_height) / 2 # Should be 0 if pixmap fills content height
            
            painter.drawPixmap(QPoint(int(img_x), int(img_y)), self._pixmap_to_display)


        # --- Draw Banner ---
        banner_rect = QRectF(
            0, # Start from the left edge of the button
            self._pixmap_to_display.height() if not self._pixmap_to_display.isNull() else 0, # Positioned directly below the image content area
            button_rect.width(), # Full width of the button
            self._banner_height
        )

        # Banner background
        # Use style's highlight color if checked, otherwise a darker version of button background
        # The stylesheet handles the main button background, so we draw banner on top.
        if self.isChecked():
            # A slightly different color for the banner when checked to distinguish from main highlight
            banner_color = self.palette().color(QPalette.ColorRole.Highlight).darker(110)
            if banner_color == self.palette().color(QPalette.ColorRole.Highlight): # Ensure it's actually darker
                 banner_color = banner_color.darker(105) # Try again
        else:
            # A color that contrasts with the default button background from stylesheet
            banner_color = QColor("#202020") # Darker than the #333 default
        painter.fillRect(banner_rect, banner_color)


        # --- Prepare Banner Content ---
        painter.setPen(QColor(Qt.GlobalColor.white)) # Ensure text is visible on dark banner
        banner_font = QFont(self.font()) # Start with button's font
        banner_font.setPointSize(max(8, int(banner_font.pointSize() * 0.85))) # Slightly smaller
        painter.setFont(banner_font)

        # --- Calculate Text and Icon Rects ---
        text_padding_horizontal = 5 # Horizontal padding for text within the banner
        total_icon_area_width = 0
        visible_icons = []

        # Determine which icons are visible and calculate total width needed
        # Iterate in reverse if you want icons added left-to-right visually but drawn right-to-left
        icon_order = ["error", "warning"] # Define drawing order (rightmost first)
        for icon_name in icon_order:
            if self._icon_states.get(icon_name, False) and icon_name in self._icon_pixmaps:
                visible_icons.append(icon_name)
                total_icon_area_width += self._icon_size + self._icon_spacing

        if total_icon_area_width > 0 and visible_icons: # Check visible_icons to avoid negative if only spacing
            total_icon_area_width -= self._icon_spacing # Remove trailing space if icons exist

        # Adjust text rect to not overlap icon area
        text_rect = banner_rect.adjusted(text_padding_horizontal, 0, -(text_padding_horizontal + total_icon_area_width), 0)

        # --- Draw Banner Text ---
        # Draw slide number left-aligned
        num_str = str(self._slide_number if self._slide_number is not None else (self._slide_id + 1))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, num_str)

        # Draw label centered, elided if necessary
        font_metrics = QFontMetrics(painter.font())
        # Calculate available width for the label (subtracting space for number)
        # Give a bit more space for the number string
        num_str_width_approx = font_metrics.horizontalAdvance(num_str + "  MM") # Approx width for number + some spacing
        available_label_width = text_rect.width() - num_str_width_approx
        elided_label = font_metrics.elidedText(self._slide_label or "", Qt.TextElideMode.ElideRight, max(0, available_label_width))
        if elided_label: # Only draw if there's something to draw
            painter.drawText(text_rect, Qt.AlignCenter | Qt.AlignVCenter, elided_label)

        # --- Draw Visible Icons ---
        current_icon_x = banner_rect.right() - text_padding_horizontal # Start from right edge of banner (with padding)
        for icon_name in visible_icons: # Draw in the order determined earlier (e.g., error then warning from right)
            current_icon_x -= self._icon_size # Position for current icon
            icon_pixmap = self._icon_pixmaps[icon_name]
            icon_y = banner_rect.top() + (banner_rect.height() - icon_pixmap.height()) / 2 # Center vertically
            painter.drawPixmap(int(current_icon_x), int(icon_y), icon_pixmap)
            current_icon_x -= self._icon_spacing # Space for next icon
        painter.end()

    def get_slide_id(self):
        return self._slide_id

    @Slot()
    def _handle_click(self):
        """Emits the slide_selected signal when clicked."""
        # QButtonGroup handles unchecking others if setExclusive(True)
        # self.setChecked(True) # Ensure this button is visually checked
        self.slide_selected.emit(self._slide_id)
        
    def contextMenuEvent(self, event):
        if not self._available_template_names: # Don't show "Apply Template" if no templates known
            # Fallback to a simpler menu or no menu if this happens unexpectedly
            # For now, we'll proceed, but this is a point to consider.
            pass
        """Shows a context menu on right-click."""
        menu = QMenu(self)
        
        edit_action = menu.addAction("Edit Slide Lyrics")
        delete_action = menu.addAction("Delete Slide")
        menu.addSeparator()
        next_slide_action = menu.addAction("Go to Next Slide")
        prev_slide_action = menu.addAction("Go to Previous Slide")
        menu.addSeparator()
        # Future actions can be added here
        
        apply_template_submenu = menu.addMenu("Apply Template")
        if self._available_template_names:
            for template_name in self._available_template_names:
                action = apply_template_submenu.addAction(template_name)
                action.setData(template_name) # Store template name in action's data
        else:
            apply_template_submenu.setEnabled(False)

        action = menu.exec(event.globalPos())

        if action == edit_action:
            self.edit_requested.emit(self._slide_id)
        elif action == delete_action:
            self.delete_requested.emit(self._slide_id)
        elif action and action.parent() == apply_template_submenu: # Check if action is from submenu
            chosen_template_name = action.data()
            if chosen_template_name:
                self.apply_template_to_slide_requested.emit(self._slide_id, chosen_template_name)
        elif action == next_slide_action:
            self.next_slide_requested_from_menu.emit(self._slide_id)
        elif action == prev_slide_action:
            self.previous_slide_requested_from_menu.emit(self._slide_id)

    def set_available_templates(self, template_names: List[str]):
        self._available_template_names = template_names
        
    def keyPressEvent(self, event: QEvent): # QEvent can be imported from PySide6.QtCore
        """Override to prevent default button navigation for arrow keys we want to handle globally."""
        key = event.key()
        # Check for Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down
        if key == Qt.Key_Left or \
           key == Qt.Key_Right or \
           key == Qt.Key_Up or \
           key == Qt.Key_Down:
            event.ignore() # Tell Qt this widget isn't handling it, let it propagate
            return         # Explicitly return to stop further processing by this widget for these keys
        super().keyPressEvent(event) # Handle other keys (like Space for click) normally


if __name__ == "__main__": # pragma: no cover
    print(f"DEBUG: scaled_slide_button.py INSIDE if __name__ == '__main__'") # DIAGNOSTIC
    app = QApplication(sys.argv)

    # --- Create a dummy window to hold the button ---
    window = QWidget()
    layout = QHBoxLayout(window) # Changed to QHBoxLayout
    # Align items added to the layout to the top-left
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    window.setWindowTitle("ScaledSlideButton Test")
    window.setGeometry(100, 100, 800, 400) # x, y, width, height (made taller for banner)

    # --- Create multiple buttons ---
    num_buttons = 10
    loaded_pixmaps = {} # Cache loaded images to avoid reloading

    # --- Add Button Group for Exclusive Selection ---
    button_group = QButtonGroup(window) # Parent to the window
    button_group.setExclusive(True)

    # Create a single placeholder pixmap to reuse for previews in test
    placeholder_pixmap_test = QPixmap(BASE_TEST_PREVIEW_CONTENT_WIDTH, BASE_TEST_PREVIEW_CONTENT_HEIGHT) # Renamed
    placeholder_pixmap_test.fill(QColor("darkcyan"))
    # Ensure painter is ended for placeholder_pixmap
    temp_painter = QPainter(placeholder_pixmap)
    temp_painter.setPen(QColor("white"))
    temp_painter.setFont(QFont("Arial", 10)) # Added font setting for placeholder
    temp_painter.drawText(placeholder_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Test Slide")
    temp_painter.end()


    # --- Connect signal for testing ---
    def on_slide_selected(slide_id_val): # Renamed arg to avoid conflict
        print(f"Button clicked! Slide ID: {slide_id_val}")
        # In a real app, you might uncheck other buttons here

    for i in range(num_buttons):
        # slide_id for the button is its index
        button = ScaledSlideButton(slide_id=i)
        # No need for setFixedSize, sizeHint and sizePolicy should handle it.

        # Try loading a corresponding test render, fallback to placeholder
        # Adjust this path if your test renders are elsewhere or named differently
        test_image_path = f"c:/Users/Logan/Documents/Plucky/Plucky/rendering/test_renders/test_render_{i+1}.png"

        if test_image_path not in loaded_pixmaps:
            pixmap = QPixmap(test_image_path)
            if pixmap.isNull():
                loaded_pixmaps[test_image_path] = placeholder_pixmap_test # Use placeholder if load fails
            else:
                loaded_pixmaps[test_image_path] = pixmap # Cache successful load

        button.set_pixmap(loaded_pixmaps[test_image_path])
        # Set sample banner info
        button.set_slide_info(number=i + 1, label=f"A Long Test Label Name {i+1}")
        # --- Set icon states for some buttons in the test ---
        if (i + 1) % 3 == 0: # Show error on every 3rd button
            button.set_icon_state("error", True)
        if (i + 1) % 4 == 0: # Show warning on every 4th button
            button.set_icon_state("warning", True)
        # Example: Show both on button 6
        if (i + 1) == 6:
             button.set_icon_state("error", True)
             button.set_icon_state("warning", True)


        button.slide_selected.connect(on_slide_selected)
        layout.addWidget(button) # Add button to the layout
        button_group.addButton(button) # Add button to the group

    window.show()

    sys.exit(app.exec())
