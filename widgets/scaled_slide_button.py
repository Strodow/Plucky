import sys
import os
from PySide6.QtWidgets import (  # type: ignore
    QApplication, QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QButtonGroup, QStyle, QMenu, QStyleOption
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontMetrics, QPalette, QPen, QMouseEvent, QContextMenuEvent, QKeyEvent, QDrag, QRegion


)
from PySide6.QtCore import (
    Qt, QSize, Signal, Slot, QRectF, QPoint, QEvent, QMimeData, QByteArray, QPointF
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
    toggle_selection_requested = Signal(int) # New: Emits slide_id when Ctrl+Click toggles selection
    """next_slide_requested_from_menu = Signal(int) # Emits current slide_id
    previous_slide_requested_from_menu = Signal(int) # Emits current slide_id"""
    apply_template_to_slide_requested = Signal(int, str) # Emits slide_id, template_name
    center_overlay_label_changed = Signal(int, str) # Emits slide_id, new_label_text
    banner_color_change_requested = Signal(int, QColor) # Emits slide_id, new_color (None for default)

    # New signal for inserting slide from layout
    insert_slide_from_layout_requested = Signal(int, str) # slide_id (to insert after), layout_name
    insert_new_section_requested = Signal(int) # slide_id (to insert section AFTER this one)

    def __init__(self, **kwargs):
        # Pop our custom arguments from the kwargs dictionary.
        # This removes them, so they won't be passed to the superclass.
        slide_id = kwargs.pop('slide_id')
        instance_id = kwargs.pop('instance_id')
        plucky_slide_mime_type = kwargs.pop('plucky_slide_mime_type')

        # Now, call the parent constructor with the REMAINING kwargs.
        # If 'parent' was in the original call, it's still in kwargs and will be handled correctly.
        # If not, it's fine. 'slide_id' and the others are guaranteed to be gone.
        super().__init__(**kwargs)

        # --- The rest of your original __init__ method continues from here ---
        self._pixmap_to_display = QPixmap()
        self._slide_id = slide_id
        self._instance_id = instance_id
        self.plucky_slide_mime_type = plucky_slide_mime_type

        self._center_overlay_label: Optional[str] = ""
        self._available_template_names: List[str] = []
        self._is_background_slide: bool = False
        self._is_arrangement_enabled: bool = True

        self._is_template_missing: bool = False # New: Track if the template is missing
        self._original_template_name: Optional[str] = None # New: Store original name if missing

        self._banner_height = 25
        self._is_checked = False
        self._is_hovered = False
        self._is_pressed = False
        self._drag_start_position: Optional[QPoint] = None

        self.banner_widget = InfoBannerWidget(banner_height=self._banner_height, parent=self)

        # ... and so on for the rest of the method (layouts, stylesheet, etc.) ...
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)
        main_layout.addStretch(1)
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
        self.banner_widget.update() # Explicitly tell the banner to repaint
        self.update() # Also tell the ScaledSlideButton to repaint

    def set_template_missing_error(self, is_missing: bool, original_template_name: Optional[str] = None):
        self._is_template_missing = is_missing
        self._original_template_name = original_template_name
        # The banner text might also need updating depending on how it's used
        self.update() # Also tell the ScaledSlideButton to repaint

    def set_center_overlay_label(self, text: Optional[str], emit_signal_on_change: bool = True):
        new_label_value = text if text is not None else ""
        # The ScaledSlideButton still "owns" the concept of this label for data purposes
        if self._center_overlay_label != new_label_value:
            self._center_overlay_label = new_label_value
            if emit_signal_on_change:
                self.center_overlay_label_changed.emit(self._slide_id, self._center_overlay_label)

        # Only set the section_label on the banner if this is NOT a background slide.
        # For background slides, the banner's primary label is "BG", set via set_info.
        if not self._is_background_slide:
            self.banner_widget.set_section_label(new_label_value) # Pass to banner for display
        self.update()

    def set_arrangement_enabled_state(self, is_enabled: bool):
        """Sets the visual state based on whether the slide is enabled in the current arrangement."""
        if self._is_arrangement_enabled != is_enabled:
            self._is_arrangement_enabled = is_enabled
            self.update() # Trigger a repaint to reflect the change

    def set_banner_color(self, color: Optional[QColor]):
        """Sets a custom color for the banner widget."""
        self.banner_widget.set_custom_color(color)

    def sizeHint(self) -> QSize:
        # If this button is for a background slide, it might not have a pixmap from lyrics.
        # Ensure we use the base preview dimensions if _pixmap_to_display is small/default.
        # This logic might need refinement based on how background slide previews are generated.
        # For now, assume _pixmap_to_display is correctly sized by MainWindow.

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
        current_border_color: QColor
        current_border_width: float

        if self._is_template_missing:
            current_border_color = QColor("red") # Distinct red border for error
            current_border_width = 3.0 # Thicker border
            # Error state overrides other states for border color
        elif self.isChecked(): # Using our internal state
            current_border_color = QColor("#0078D7") # Checked color (blue)
            current_border_width = 2.0
            if self._is_hovered:
                current_border_color = QColor("#50AFEF") # Checked + Hover (brighter blue)
        elif self._is_hovered: # Not checked, but hovered
            current_border_color = QColor("#00A0F0") # Hover color (light blue)
            current_border_width = 2.0
        else: # Default unchecked, not hovered
            current_border_color = QColor("#555") # Default gray
            current_border_width = 1.0
        
        if self._is_pressed: # Overrides other border colors for visual feedback
            current_border_color = QColor("#FFFFFF") # Pressed color
            current_border_width = 2.0

        # Draw the border manually
        painter.setPen(QPen(current_border_color, current_border_width))
        half_pen = current_border_width / 2.0
        border_draw_rect = QRectF(self.rect()).adjusted(half_pen, half_pen, -half_pen, -half_pen)
        painter.drawRect(border_draw_rect)

        # Define drawable_area for content (pixmap, overlay) *inside* the border
        inset = current_border_width
        drawable_image_content_area = image_area_total_rect.adjusted(
            inset, inset,
            -inset, -inset
        )

        painter.save() # Save painter state for clipping
        painter.setClipRect(drawable_image_content_area)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        # Apply opacity if the slide is not enabled in the arrangement
        if not self._is_arrangement_enabled:
            painter.setOpacity(0.5) # Adjust opacity value as needed (e.g., 0.5 for 50%)

        actual_pixmap_rect = QRectF()
        if not self._pixmap_to_display.isNull() and drawable_image_content_area.width() > 0 and drawable_image_content_area.height() > 0:
            # _pixmap_to_display is already scaled by SlideUIManager. Center it.
            px = drawable_image_content_area.left() + (drawable_image_content_area.width() - self._pixmap_to_display.width()) / 2
            py = drawable_image_content_area.top() + (drawable_image_content_area.height() - self._pixmap_to_display.height()) / 2
            painter.drawPixmap(QPointF(px, py), self._pixmap_to_display)
        elif drawable_image_content_area.isValid(): 
            # Fallback drawing if pixmap is null or area is invalid
            # actual_pixmap_rect = QRectF( # This variable is no longer used after the change
            #     drawable_image_content_area.left(), drawable_image_content_area.top(),
            #     drawable_image_content_area.width(), max(0, drawable_image_content_area.height())
            # ) # Removed this line as actual_pixmap_rect is not used here
            
            # Draw a fallback background if pixmap is null
            painter.fillRect(drawable_image_content_area, QColor(Qt.GlobalColor.darkGray).lighter(150))

        # --- Draw Error Overlay if Template is Missing ---
        if self._is_template_missing:
            painter.setOpacity(1.0) # Ensure overlay is fully opaque
            painter.fillRect(drawable_image_content_area, QColor(255, 0, 0, 80)) # Semi-transparent red overlay
            
            # Draw error text on the overlay
            painter.setPen(QColor(Qt.GlobalColor.white))
            error_font = QFont("Arial", 10 * (drawable_image_content_area.height() / BASE_TEST_PREVIEW_CONTENT_HEIGHT)) # Scale font
            painter.setFont(error_font)
            text_option = QTextOption(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
            error_text = f"Template Missing:\n'{self._original_template_name or 'Unknown'}'"
            painter.drawText(drawable_image_content_area, error_text, text_option)

        # Center overlay label drawing on the image is now removed. It's handled by InfoBannerWidget.
        
        # Restore opacity if it was changed
        if not self._is_arrangement_enabled:
            painter.setOpacity(1.0)
        painter.restore() # Restore clipping
        painter.end()

    # --- Mouse event handling ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self._drag_start_position = event.pos() # Store position for drag detection
            self.update()
            # Don't accept yet, mouseMoveEvent might start a drag or mouseReleaseEvent will handle click
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_position is None: # Should not happen if press was captured
            super().mouseMoveEvent(event)
            return

        # Check if drag distance exceeds threshold
        if (event.pos() - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        # --- Start Drag Operation ---
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Use the stored MIME type and instance_id
        slide_id_bytes = QByteArray(str(self._instance_id).encode('utf-8'))
        mime_data.setData(self.plucky_slide_mime_type, slide_id_bytes)
        
        # Create a semi-transparent pixmap of the button itself for drag visual
        # Ensure the pixmap captures the current look, including banner
        preview_pixmap = QPixmap(self.size())
        preview_pixmap.fill(Qt.GlobalColor.transparent) # Ensure transparent background for the drag pixmap
        temp_painter = QPainter(preview_pixmap)
        temp_painter.setOpacity(0.75) # Make it slightly transparent
        # Render the entire widget (including children like the banner) to the pixmap
        self.render(temp_painter, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
        temp_painter.end()
        
        drag.setPixmap(preview_pixmap)
        drag.setHotSpot(event.pos()) # Hotspot relative to the button's top-left
        drag.setMimeData(mime_data)

        # Execute the drag
        # print(f"ScaledSlideButton {self._slide_id}: Starting drag exec...") # DEBUG
        drop_action = drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction) # Suggest MoveAction primarily

        # Reset states after drag attempt, regardless of outcome
        self._is_pressed = False # Ensure pressed state is cleared
        self._drag_start_position = None # Clear drag start position
        self.update() # Repaint to clear pressed state visual

        # if drop_action == Qt.DropAction.MoveAction:
        #     print(f"ScaledSlideButton {self._slide_id}: Drag resulted in MoveAction.") # DEBUG
        # else:
        #     print(f"ScaledSlideButton {self._slide_id}: Drag cancelled or resulted in NoAction/CopyAction.") # DEBUG

            
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            # If _drag_start_position is still set, it means a drag didn't initiate (it was a click)
            if self._drag_start_position is not None and \
               (event.pos() - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
                if self.rect().contains(event.pos()): # Click was within the button
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self.toggle_selection_requested.emit(self._slide_id)
                    else:
                        self.slide_selected.emit(self._slide_id)
            self._is_pressed = False # Reset pressed state
            self._drag_start_position = None # Reset drag start position
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
        # Check if this button is part of a multi-selection
        is_multi_selection_active = False
        # Get the top-level window (MainWindow) and check if it has the method
        main_window = self.window()
        if main_window and hasattr(main_window, 'get_selected_slide_indices'):
            selected_indices = main_window.get_selected_slide_indices() # type: ignore
            is_multi_selection_active = len(selected_indices) > 1 and self._slide_id in selected_indices

        menu = QMenu(self)
        edit_action = menu.addAction("Edit Contents")
        delete_action = menu.addAction("Delete Slide")
        menu.addSeparator() # Separator before Template/Label/Color

        # --- Insert Slide from Layout Submenu ---
        insert_slide_submenu = menu.addMenu("Insert Slide from Layout")
        if self._available_template_names:
            for layout_name in self._available_template_names:
                action = insert_slide_submenu.addAction(layout_name)
                # Emit with self._slide_id (to insert AFTER this one) and layout_name
                action.triggered.connect(
                    lambda checked=False, name=layout_name: self.insert_slide_from_layout_requested.emit(self._slide_id, name)
                )
            insert_slide_submenu.addSeparator()
            insert_blank_action = insert_slide_submenu.addAction("Insert Blank Slide (Default Layout)")
            if "Default Layout" in self._available_template_names:
                 insert_blank_action.triggered.connect(
                    lambda: self.insert_slide_from_layout_requested.emit(self._slide_id, "Default Layout")
                )
            else:
                insert_blank_action.setEnabled(False)
                insert_blank_action.setToolTip("Default Layout template not found.")
        else: # No layout templates available
            insert_slide_submenu.setEnabled(False)
        
        menu.addSeparator() # Separator before "Insert New Section"
        insert_new_section_action = menu.addAction("Insert New Section After This...")
        insert_new_section_action.triggered.connect(lambda: self.insert_new_section_requested.emit(self._slide_id))
        menu.addSeparator() # Separator after "Insert New Section"

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

        # Disable Edit and Label actions if multi-selection is active
        if is_multi_selection_active:
            edit_action.setEnabled(False) # Gray out "Edit Contents"
            label_submenu.setEnabled(False) # Disable the whole label submenu

        menu.addSeparator()
        banner_color_submenu = menu.addMenu("Change Banner Color")
        default_color_action = banner_color_submenu.addAction("Default Color")
        custom_color_action = banner_color_submenu.addAction("Choose Custom Color...")
        """menu.addSeparator() # Separator before Next/Previous
        next_slide_action = menu.addAction("Next Slide")
        previous_slide_action = menu.addAction("Previous Slide")"""
        print(f"DEBUG ScaledSlideButton: Context menu opened for slide {self._slide_id}") # DEBUG

        action_selected = menu.exec(event.globalPos()) # Renamed 'action' to 'action_selected'

        if action_selected == edit_action:
            self.edit_requested.emit(self._slide_id)
            # Delete, Apply Template, and Change Banner Color actions will operate on the selection
            # if multi-select is active and the right-clicked button is part of it.
            # MainWindow will handle checking the selection state when receiving the signal.
            print(f"DEBUG ScaledSlideButton: Context menu action selected: {action_selected}") # DEBUG
        elif action_selected == delete_action:
            self.delete_requested.emit(self._slide_id)
        elif action_selected and action_selected.parent() == apply_template_submenu:
            # This is for applying a template to the *current* slide(s)
            chosen_template_name = action_selected.data()
            if chosen_template_name: # Check if data is not None or empty
                print(f"DEBUG ScaledSlideButton: Emitting apply_template_to_slide_requested for slide {self._slide_id}, template '{chosen_template_name}'") # ADD THIS DEBUG
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
                # This branch is disabled if is_multi_selection_active is true
                chosen_label = action_selected.data()
                if chosen_label == "Blank":
                    self.set_center_overlay_label("")
                elif chosen_label:
                    self.set_center_overlay_label(chosen_label)
        elif action_selected and action_selected.parent() == banner_color_submenu:
            if action_selected == default_color_action:
                # Signal MainWindow to change color for selected slides
                self.banner_color_change_requested.emit(self._slide_id, None) # Pass clicked ID and None for default
            elif action_selected == custom_color_action:
                from PySide6.QtWidgets import QColorDialog # type: ignore
                initial_color = self.banner_widget._custom_banner_color if self.banner_widget._custom_banner_color else QColor("#202020")
                color = QColorDialog.getColor(initial_color, self, "Choose Banner Color")
                # Signal MainWindow to change color for selected slides
                if color.isValid():
                    self.banner_color_change_requested.emit(self._slide_id, color) # Pass clicked ID and chosen color
        # Note: The insert_slide_from_layout_requested signal is emitted directly by the action's triggered.connect
        # in the submenu creation, so no explicit handling for it is needed here in the main menu's exec result.

        """elif action_selected == next_slide_action:
            self.next_slide_requested_from_menu.emit(self._slide_id)
        elif action_selected == previous_slide_action:
            self.previous_slide_requested_from_menu.emit(self._slide_id)"""

    def set_available_templates(self, template_names: List[str]):
        self._available_template_names = template_names
        
    def set_is_background_slide(self, is_background: bool):
        self._is_background_slide = is_background
        self.update() # May want to trigger a style change or icon update

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


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    window = QWidget()
    layout = QHBoxLayout(window) 
    layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    window.setWindowTitle("ScaledSlideButton Test")
    window.setGeometry(100, 100, 800, 600) 

    num_buttons = 10
    loaded_pixmaps = {}
    all_slide_buttons_in_test = []

    placeholder_pixmap_test = QPixmap(BASE_TEST_PREVIEW_CONTENT_WIDTH, BASE_TEST_PREVIEW_CONTENT_HEIGHT) 
    placeholder_pixmap_test.fill(QColor("darkcyan"))
    temp_painter = QPainter(placeholder_pixmap_test)
    temp_painter.setPen(QColor("white"))
    temp_painter.setFont(QFont("Arial", 10)) 
    temp_painter.drawText(placeholder_pixmap_test.rect(), Qt.AlignmentFlag.AlignCenter, "Test Slide")
    temp_painter.end()

    # Simulate MainWindow's selection handling for testing
    selected_slide_ids_test = set()

    def update_button_checked_states_test():
        for btn_id, btn_widget in all_slide_buttons_in_test:
             btn_widget.setChecked(btn_id in selected_slide_ids_test)

    def on_slide_selected_test(clicked_button_id):
        print(f"Test: Button clicked! Slide ID: {clicked_button_id}")
        # Simulate MainWindow clearing other selections and selecting this one
        selected_slide_ids_test.clear()
        selected_slide_ids_test.add(clicked_button_id)
        update_button_checked_states_test()

    def on_toggle_selection_test(clicked_button_id):
        print(f"Test: Ctrl+Click! Slide ID: {clicked_button_id}")
        # Simulate MainWindow toggling this button's selection
        if clicked_button_id in selected_slide_ids_test:
            selected_slide_ids_test.remove(clicked_button_id)
        else:
            selected_slide_ids_test.add(clicked_button_id)
        update_button_checked_states_test()

    # Add a dummy get_selected_slide_indices method to the window for the button's context menu (if it needs it later)
    # For this step, it's not strictly necessary but good for future steps.
    def get_selected_slide_indices_test():
        return list(selected_slide_ids_test)
    window.get_selected_slide_indices = get_selected_slide_indices_test # Monkey patch for testing

    for i in range(num_buttons):
        button = ScaledSlideButton(
            slide_id=i,
            instance_id=f"test_instance_{i}", # Provide a dummy instance_id
            plucky_slide_mime_type="application/x-plucky-slide-test" # Provide a dummy mime type
        )
        button.set_available_templates(["Template Alpha", "Template Beta", "Default Master"])

        test_image_path = f"c:/Users/Logan/Documents/Plucky/Plucky/rendering/test_renders/test_render_{i + 1}.png"

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
        
        button.slide_selected.connect(on_slide_selected_test)
        button.toggle_selection_requested.connect(on_toggle_selection_test) # Connect the new signal
        layout.addWidget(button)
        all_slide_buttons_in_test.append((i, button))

    window.show()

    sys.exit(app.exec())
