import sys
print(f"DEBUG: scaled_slide_button.py TOP LEVEL, __name__ is {__name__}") # DIAGNOSTIC
import os
from PySide6.QtWidgets import (  # type: ignore
    QApplication, QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QButtonGroup, QStyle, QMenu, QStyleOption
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPalette, QPen, QMouseEvent, QContextMenuEvent, QKeyEvent
)
from PySide6.QtCore import (
    Qt, QSize, Signal, Slot, QRectF, QPoint, QEvent
)
from typing import Optional, List, cast

# Import the new InfoBannerWidget
from .scaled_slide_button_infobar import InfoBannerWidget

BASE_TEST_PREVIEW_CONTENT_WIDTH = 160
BASE_TEST_PREVIEW_CONTENT_HEIGHT = 90

class ScaledSlideButton(QWidget): # Changed from QPushButton
    """
    A button that displays a scaled version of a QPixmap and an info banner with icons.
    """
    slide_selected = Signal(int) # Emits the slide_id (which is its index in MainWindow)
    edit_requested = Signal(int) # Emits slide_id when edit is requested
    delete_requested = Signal(int) # Emits slide_id when delete is requested
    next_slide_requested_from_menu = Signal(int) # Emits current slide_id
    previous_slide_requested_from_menu = Signal(int) # Emits current slide_id
    apply_template_to_slide_requested = Signal(int, str) # Emits slide_id, template_name
    center_overlay_label_changed = Signal(int, str) # Emits slide_id, new_label_text
    def __init__(self, slide_id: int, parent=None):
        super().__init__(parent)
        self._pixmap_to_display = QPixmap() # Stores the pixmap (already scaled by MainWindow)
        self._slide_id = slide_id
        self._center_overlay_label: Optional[str] = "" # New: For the prominent centered label
        self._available_template_names: List[str] = [] # Will be set by MainWindow

        self._banner_height = 25
        self._is_checked = False
        self._is_hovered = False 
        self._is_pressed = False 

        self.banner_widget = InfoBannerWidget(banner_height=self._banner_height, parent=self)

        # Main layout for this QWidget
        main_layout = QVBoxLayout(self)
        # Add a margin to the layout so child widgets (like the banner)
        # don't draw over the border painted by ScaledSlideButton's paintEvent.
        # The border width can be up to 2px (or 3px if fixed_inset_for_content is 3).
        main_layout.setContentsMargins(2,2,2,2) # A 2px margin should be enough
        main_layout.setSpacing(0)
        # The image will be drawn in the space managed by ScaledSlideButton's paintEvent,
        # above the banner_widget. We add a stretch item that the banner will push down.
        main_layout.addStretch(1) # This represents the image area
        main_layout.addWidget(self.banner_widget)
        self.setLayout(main_layout)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True) 

        self.setStyleSheet("""
            ScaledSlideButton { /* Style the class itself */
                border: 1px solid #555; /* Default border */
                background-color: #333; /* Default background */
                color: white; 
            }
            ScaledSlideButton[checked="true"] {
                border: 2px solid #0078D7; /* Prominent blue border when checked */
            }
            ScaledSlideButton:hover { 
                border: 2px solid #00A0F0;   /* Was 1px, now 2px light blue */
            }
            /* Pressed state will be handled by changing border color in paintEvent directly */
            ScaledSlideButton[checked="true"]:hover {
                border-color: #50AFEF;   /* Brighter blue for checked + hover */
            }
        """)

    # --- Mimic QPushButton API ---
    def isChecked(self) -> bool:
        return self._is_checked

    def setChecked(self, checked: bool):
        if self._is_checked != checked:
            self._is_checked = checked
            self.setProperty("checked", self._is_checked) # For stylesheet selector [checked="true"]
            self.style().unpolish(self) 
            self.style().polish(self)
            self.update()

    def setCheckable(self, checkable: bool): 
        pass # Always checkable by our logic

    def setAutoExclusive(self, exclusive: bool): 
        pass # Handled by QButtonGroup externally if used with QAbstractButton
    # --- End Mimic QPushButton API ---

    def set_pixmap(self, pixmap: QPixmap):
        """Sets the pixmap to be displayed and triggers a repaint."""
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self._pixmap_to_display = pixmap 
        else:
            self._pixmap_to_display = QPixmap(1,1) 
            self._pixmap_to_display.fill(Qt.GlobalColor.lightGray)
        self.update()
        self.updateGeometry() 

    def set_slide_info(self, number: Optional[int], label: Optional[str]):
        """Sets the information for the banner widget."""
        self.banner_widget.set_info(number, label)

    def set_icon_state(self, icon_name: str, visible: bool):
        """Sets the icon visibility for the banner widget."""
        self.banner_widget.set_icon_state(icon_name, visible)

    def set_center_overlay_label(self, text: Optional[str], emit_signal_on_change: bool = True):
        new_label_value = text if text is not None else ""
        # The ScaledSlideButton still "owns" the concept of this label for data purposes
        if self._center_overlay_label != new_label_value:
            self._center_overlay_label = new_label_value
            if emit_signal_on_change:
                self.center_overlay_label_changed.emit(self._slide_id, self._center_overlay_label)
        self.banner_widget.set_section_label(new_label_value) # Pass to banner for display
        self.update()

    def set_banner_color(self, color: Optional[QColor]):
        """Sets a custom color for the banner widget."""
        self.banner_widget.set_custom_color(color)

    def sizeHint(self) -> QSize:
        content_width = self._pixmap_to_display.width() if not self._pixmap_to_display.isNull() else BASE_TEST_PREVIEW_CONTENT_WIDTH
        content_height = self._pixmap_to_display.height() if not self._pixmap_to_display.isNull() else BASE_TEST_PREVIEW_CONTENT_HEIGHT
        # The banner widget has a fixed height, so we add that.
        return QSize(content_width, content_height + self.banner_widget.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        opt = QStyleOption()
        opt.initFrom(self)
        
        # Draw background based on stylesheet (for QWidget)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        # Determine the area for drawing the image (above the banner)
        image_area_total_rect = self.rect()
        image_area_total_rect.setHeight(max(0, self.height() - self.banner_widget.height()))

        # Determine border properties based on state
        # current_border_color = QColor(self.style().styleHint(QStyle.StyleHint.SH_Button_DefaultBorder, opt, self)) # Fallback - REMOVE THIS
        # Default border from stylesheet if not overridden by state
        if self.isChecked(): # Using our internal state
            current_border_color = QColor("#0078D7") # Checked color
            current_border_width = 2
            if self._is_hovered:
                current_border_color = QColor("#50AFEF") # Checked + Hover
        elif self._is_hovered: # Not checked, but hovered
            current_border_color = QColor("#00A0F0") # Hover color
            current_border_width = 2
        else: # Default unckecked, not hovered
            current_border_color = QColor("#555")
            current_border_width = 1
        
        if self._is_pressed: # Overrides other border colors for visual feedback
            current_border_color = QColor("#FFFFFF") # Pressed color
            current_border_width = 2

        # Draw the border manually
        painter.setPen(QPen(current_border_color, current_border_width))
        half_pen = current_border_width / 2.0
        border_draw_rect = QRectF(self.rect()).adjusted(half_pen, half_pen, -half_pen, -half_pen)
        painter.drawRect(border_draw_rect)

        # Define drawable_area for content (pixmap, overlay) *inside* the border
        fixed_inset_for_content = 3 # This was the value that worked
        drawable_image_content_area = image_area_total_rect.adjusted(
            fixed_inset_for_content, fixed_inset_for_content, 
            -fixed_inset_for_content, -fixed_inset_for_content 
        )

        painter.save() # Save painter state for clipping
        painter.setClipRect(drawable_image_content_area)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        actual_pixmap_rect = QRectF()
        if not self._pixmap_to_display.isNull() and drawable_image_content_area.height() > 0:
            target_w = min(self._pixmap_to_display.width(), drawable_image_content_area.width())
            target_h = min(self._pixmap_to_display.height(), drawable_image_content_area.height())
            actual_pixmap_rect = QRectF(
                drawable_image_content_area.left() + (drawable_image_content_area.width() - target_w) / 2,
                drawable_image_content_area.top() + (drawable_image_content_area.height() - target_h) / 2,
                target_w, target_h
            )
            painter.drawPixmap(actual_pixmap_rect, self._pixmap_to_display, self._pixmap_to_display.rect())
        elif drawable_image_content_area.isValid(): 
            actual_pixmap_rect = QRectF(
                drawable_image_content_area.left(), drawable_image_content_area.top(),
                drawable_image_content_area.width(), max(0, drawable_image_content_area.height())
            )
            painter.fillRect(actual_pixmap_rect, QColor(Qt.GlobalColor.darkGray).lighter(150))

        # Center overlay label drawing on the image is now removed. It's handled by InfoBannerWidget.
        painter.restore() # Restore clipping
        painter.end()

    # --- Mouse event handling ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            if self.rect().contains(event.pos()): # Check if release is within bounds
                current_checked_state = self.isChecked()
                self.setChecked(not current_checked_state) 
                self.slide_selected.emit(self._slide_id) 
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def enterEvent(self, event: QEvent): 
        self._is_hovered = True
        self.update() 
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent): 
        self._is_hovered = False
        self.update() 
        super().leaveEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent): # Changed from QEvent to QContextMenuEvent
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Slide Lyrics")
        delete_action = menu.addAction("Delete Slide")
        menu.addSeparator()
        
        apply_template_submenu = menu.addMenu("Apply Template")
        if self._available_template_names:
            for template_name in self._available_template_names:
                action = apply_template_submenu.addAction(template_name)
                action.setData(template_name)
        else:
            apply_template_submenu.setEnabled(False)

        label_submenu = menu.addMenu("Set Overlay Label")
        predefined_labels = ["Verse 1", "Verse 2", "Verse 3", "Chorus", "Refrain", "Bridge", "Intro", "Outro", "Blank"]
        for label_text in predefined_labels:
            action = label_submenu.addAction(label_text)
            action.setData(label_text)
        
        label_submenu.addSeparator()
        edit_custom_label_action = label_submenu.addAction("Edit Custom Label...")

        menu.addSeparator()
        banner_color_submenu = menu.addMenu("Change Banner Color")
        default_color_action = banner_color_submenu.addAction("Default Color")
        custom_color_action = banner_color_submenu.addAction("Choose Custom Color...")

        action_selected = menu.exec(event.globalPos()) # Renamed 'action' to 'action_selected'

        if action_selected == edit_action:
            self.edit_requested.emit(self._slide_id)
        elif action_selected == delete_action:
            self.delete_requested.emit(self._slide_id)
        elif action_selected and action_selected.parent() == apply_template_submenu:
            chosen_template_name = action_selected.data()
            if chosen_template_name:
                self.apply_template_to_slide_requested.emit(self._slide_id, chosen_template_name)
        elif action_selected and action_selected.parent() == label_submenu:
            if action_selected == edit_custom_label_action:
                from PySide6.QtWidgets import QInputDialog # type: ignore
                current_label = self._center_overlay_label
                new_label, ok = QInputDialog.getText(self, "Set Custom Overlay Label", 
                                                     "Enter label text:", text=current_label)
                if ok:
                    self.set_center_overlay_label(new_label)
            else:
                chosen_label = action_selected.data()
                if chosen_label == "Blank":
                    self.set_center_overlay_label("")
                elif chosen_label:
                    self.set_center_overlay_label(chosen_label)
        elif action_selected and action_selected.parent() == banner_color_submenu:
            if action_selected == default_color_action:
                self.banner_widget.set_custom_color(None) # Delegate to banner widget
            elif action_selected == custom_color_action:
                from PySide6.QtWidgets import QColorDialog # type: ignore
                initial_color = self.banner_widget._custom_banner_color if self.banner_widget._custom_banner_color else QColor("#202020")
                color = QColorDialog.getColor(initial_color, self, "Choose Banner Color")
                if color.isValid():
                    self.banner_widget.set_custom_color(color) # Delegate

    def set_available_templates(self, template_names: List[str]):
        self._available_template_names = template_names
        
    def keyPressEvent(self, event: QKeyEvent): # Changed QEvent to QKeyEvent
        key = event.key()
        if key == Qt.Key_Space or key == Qt.Key_Return: # Emulate button press
            current_checked_state = self.isChecked()
            self.setChecked(not current_checked_state)
            self.slide_selected.emit(self._slide_id)
            event.accept()
        elif key in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]:
            event.ignore() 
        else:
            super().keyPressEvent(event)


if __name__ == "__main__": # pragma: no cover
    print(f"DEBUG: scaled_slide_button.py INSIDE if __name__ == '__main__'") # DIAGNOSTIC
    app = QApplication(sys.argv)

    window = QWidget()
    layout = QHBoxLayout(window) 
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    window.setWindowTitle("ScaledSlideButton Test")
    window.setGeometry(100, 100, 800, 600) 

    num_buttons = 10
    loaded_pixmaps = {} 

    # QButtonGroup won't work directly with QWidget for setExclusive.
    # We'll manage exclusivity manually in the on_slide_selected handler for this test.
    all_slide_buttons_in_test = [] 

    placeholder_pixmap_test = QPixmap(BASE_TEST_PREVIEW_CONTENT_WIDTH, BASE_TEST_PREVIEW_CONTENT_HEIGHT) 
    placeholder_pixmap_test.fill(QColor("darkcyan"))
    temp_painter = QPainter(placeholder_pixmap_test)
    temp_painter.setPen(QColor("white"))
    temp_painter.setFont(QFont("Arial", 10)) 
    temp_painter.drawText(placeholder_pixmap_test.rect(), Qt.AlignmentFlag.AlignCenter, "Test Slide")
    temp_painter.end()

    def on_slide_selected(clicked_button_id): 
        print(f"Button clicked! Slide ID: {clicked_button_id}")
        for btn_id, btn_widget in all_slide_buttons_in_test:
            if btn_id != clicked_button_id:
                btn_widget.setChecked(False) # Manual exclusivity

    for i in range(num_buttons):
        button = ScaledSlideButton(slide_id=i)
        button.set_available_templates(["Template Alpha", "Template Beta"]) # For context menu
        
        test_image_path = f"c:/Users/Logan/Documents/Plucky/Plucky/rendering/test_renders/test_render_{i+1}.png"

        if test_image_path not in loaded_pixmaps:
            pixmap = QPixmap(test_image_path)
            if pixmap.isNull():
                loaded_pixmaps[test_image_path] = placeholder_pixmap_test 
            else:
                loaded_pixmaps[test_image_path] = pixmap.scaled(
                    BASE_TEST_PREVIEW_CONTENT_WIDTH, 
                    BASE_TEST_PREVIEW_CONTENT_HEIGHT, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )

        button.set_pixmap(loaded_pixmaps[test_image_path])
        
        button.set_slide_info(number=i + 1, label=f"Test Label {i+1}")

        if i == 0:
            button.set_center_overlay_label("Verse 1")
        elif i == 2:
            button.set_center_overlay_label("Chorus")
        elif i == 4:
            button.set_center_overlay_label("Bridge") 
            button.set_banner_color(QColor("darkmagenta")) 
        elif i == 5:
             button.set_center_overlay_label("") 

        if (i + 1) % 3 == 0: 
            button.set_icon_state("error", True)
        if (i + 1) % 4 == 0: 
            button.set_icon_state("warning", True)
        if (i + 1) == 6:
             button.set_icon_state("error", True)
             button.set_icon_state("warning", True)
        
        button.slide_selected.connect(on_slide_selected)
        layout.addWidget(button)
        all_slide_buttons_in_test.append((i, button))

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__": # pragma: no cover
    print(f"DEBUG: scaled_slide_button.py INSIDE if __name__ == '__main__'") # DIAGNOSTIC
    app = QApplication(sys.argv)

    window = QWidget()
    layout = QHBoxLayout(window) 
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    window.setWindowTitle("ScaledSlideButton Test")
    window.setGeometry(100, 100, 800, 600) # Made window taller to see more buttons

    num_buttons = 10
    loaded_pixmaps = {} 

    button_group = QButtonGroup(window) 
    button_group.setExclusive(True)

    placeholder_pixmap_test = QPixmap(BASE_TEST_PREVIEW_CONTENT_WIDTH, BASE_TEST_PREVIEW_CONTENT_HEIGHT) 
    placeholder_pixmap_test.fill(QColor("darkcyan"))
    temp_painter = QPainter(placeholder_pixmap_test)
    temp_painter.setPen(QColor("white"))
    temp_painter.setFont(QFont("Arial", 10)) 
    temp_painter.drawText(placeholder_pixmap_test.rect(), Qt.AlignmentFlag.AlignCenter, "Test Slide")
    temp_painter.end()

    def on_slide_selected(slide_id_val): 
        print(f"Button clicked! Slide ID: {slide_id_val}")

    for i in range(num_buttons):
        button = ScaledSlideButton(slide_id=i)
        
        test_image_path = f"c:/Users/Logan/Documents/Plucky/Plucky/rendering/test_renders/test_render_{i+1}.png"

        if test_image_path not in loaded_pixmaps:
            pixmap = QPixmap(test_image_path)
            if pixmap.isNull():
                loaded_pixmaps[test_image_path] = placeholder_pixmap_test 
            else:
                # Ensure test pixmap is scaled to base preview size for consistency in test
                loaded_pixmaps[test_image_path] = pixmap.scaled(
                    BASE_TEST_PREVIEW_CONTENT_WIDTH, 
                    BASE_TEST_PREVIEW_CONTENT_HEIGHT, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )

        button.set_pixmap(loaded_pixmaps[test_image_path])
        
        # Set slide info (number for banner, long label for banner)
        button.set_slide_info(number=i + 1, label=f"Test Label {i+1}")

        # Set center overlay label (now for banner)
        # The set_slide_info above sets a "Test Label X" which will be overridden if section label is set
        if i == 0:
            button.set_center_overlay_label("Verse 1")
        elif i == 2:
            button.set_center_overlay_label("Chorus")
        elif i == 4:
            button.set_center_overlay_label("Bridge") # Label on image
            button.set_banner_color(QColor("darkmagenta")) # Test custom banner color
        elif i == 5:
             button.set_center_overlay_label("") # Test blank overlay label

        # Set icon states
        if (i + 1) % 3 == 0: # Show error on every 3rd button
            button.set_icon_state("error", True)
        if (i + 1) % 4 == 0: # Show warning on every 4th button
            button.set_icon_state("warning", True)
        # Example: Show both on button 6
        if (i + 1) == 6:
             button.set_icon_state("error", True)
             button.set_icon_state("warning", True)
        
        button.slide_selected.connect(on_slide_selected)
        layout.addWidget(button)
        button_group.addButton(button)

    window.show()

    sys.exit(app.exec())
