import copy # For deep copying templates
from PySide6.QtWidgets import (
    QGroupBox, # Added QGroupBox
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox, # QFormLayout removed
    QComboBox, QWidget, QScrollArea, QInputDialog, QMessageBox, QCheckBox, # QFormLayout removed
    QTabWidget, QFontComboBox, QSpinBox, QColorDialog, QLineEdit, 
    QGraphicsObject, # Changed from QGraphicsRectItem
    QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsDropShadowEffect, QGraphicsItem, QApplication # Added QGraphicsItem, QApplication
) # Added QCursor
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QTextCharFormat, QTextCursor, QBrush # For font and color manipulation, and QPainter, Added QPen, QTextCharFormat, QTextCursor, QBrush
from PySide6.QtCore import Qt, Slot, QDir, QFileInfo, Signal # Added Signal
from PySide6.QtUiTools import QUiLoader
# from data_models.slide_data import DEFAULT_TEMPLATE # To access initial defaults - Unused
from PySide6.QtCore import QRectF # For QGraphicsObject bounding rect
from typing import Optional # Import Optional for type hinting
from PySide6.QtGui import QCursor
# Default properties for a new layout definition (used in TemplateEditorWindow)
from PySide6.QtGui import QFontMetrics, QTextOption # For text width calculation, Added QTextOption
from PySide6.QtCore import QPointF # Import QPointF
# from PySide6.QtWidgets import QStyle # For QStyle.State_Selected - Unused

NEW_LAYOUT_DEFAULT_PROPS = {
    "text_boxes": [
        {"id": "main_text", "x_pc": 10, "y_pc": 10, "width_pc": 80, "height_pc": 30, "h_align": "center", "v_align": "center", "style_name": None}
    ], # Default text boxes for a new layout
    "background_color": "" # A dark gray for layout background
}
RESIZE_HANDLE_SIZE = 8 # Size in pixels for the interactive resize area around edges/corners

from PySide6.QtGui import QPainterPath # Import QPainterPath
# --- Custom Zoomable QGraphicsView ---
class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Set the transformation anchor to the mouse position for intuitive zooming
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # Enable drag mode for panning (ScrollHandDrag)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # Set render hints for smoother drawing
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    def wheelEvent(self, event):
        # Get the zoom factor (e.g., 1.1 for zoom in, 1/1.1 for zoom out)
        # event.angleDelta().y() gives the scroll amount (typically 120 or -120)
        zoom_factor = 1.0 + (event.angleDelta().y() / 120.0) * 0.1 # Adjust 0.1 for zoom speed

        # Apply the scale transformation
        self.scale(zoom_factor, zoom_factor)

        # Call the base class implementation to handle other wheel events (like scrolling if not in drag mode)
        # super().wheelEvent(event) # We handle the zoom, so don't pass to super for default scrolling

# --- Custom QGraphicsRectItem for Layout Text Boxes ---
class LayoutRectItem(QGraphicsObject): # Inherit from QGraphicsObject
    # Signal: item_id, new_x_pc, new_y_pc, new_width_pc, new_height_pc
    geometry_changed_pc = Signal(str, float, float, float, float)
    SNAP_INCREMENT_PC = 1.0  # Snap to nearest 1.0 percent for position and size

    def __init__(self, tb_id: str, x: float, y: float, w: float, h: float,
                 scene_w: float, scene_h: float,
                 style_definitions_ref: dict, # New: reference to all style definitions
                 initial_h_align: str = "center", # New: initial horizontal alignment
                 initial_v_align: str = "center", # New: initial vertical alignment
                 initial_style_name: Optional[str] = None, # New: initial style for this item
                 parent=None):
        super().__init__(parent) # Call QGraphicsObject's init
        self.tb_id = tb_id
        self.scene_width = scene_w # Scene dimensions for percentage calculations
        self.scene_height = scene_h
        
        # Snap initial geometry
        initial_x_pc = (x / self.scene_width) * 100.0
        initial_y_pc = (y / self.scene_height) * 100.0
        initial_w_pc = (w / self.scene_width) * 100.0
        initial_h_pc = (h / self.scene_height) * 100.0

        snapped_x_pc = self._snap_value(initial_x_pc, self.SNAP_INCREMENT_PC)
        snapped_y_pc = self._snap_value(initial_y_pc, self.SNAP_INCREMENT_PC)
        snapped_w_pc = self._snap_value(initial_w_pc, self.SNAP_INCREMENT_PC)
        snapped_h_pc = self._snap_value(initial_h_pc, self.SNAP_INCREMENT_PC)

        final_x_pixels = (snapped_x_pc / 100.0) * self.scene_width
        final_y_pixels = (snapped_y_pc / 100.0) * self.scene_height
        final_w_pixels = (snapped_w_pc / 100.0) * self.scene_width
        final_h_pixels = (snapped_h_pc / 100.0) * self.scene_height
        
        # Allow moving and selecting
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges, True) # Important for itemChange
        
        self._resize_mode = None # None, 'top', 'bottom', 'left', 'right', 'top-left', etc.
        self._mouse_press_pos = None # Store mouse position on press for resizing
        self._item_initial_pos_at_drag = None # Item's scene position at start of drag
        self._item_initial_rect_at_drag = None # Item's local rect at start of drag
        self._item_initial_pos_at_drag = None # Item's scene position at start of drag
        self._item_initial_rect_at_drag = None # Item's local rect at start of drag

        self._pen = QPen(Qt.GlobalColor.yellow, 2)
        self._brush = QBrush(QColor(255, 255, 0, 30)) # Semi-transparent yellow fill

        # For displaying styled text within the LayoutRectItem
        self.style_definitions_ref = style_definitions_ref
        self.assigned_style_name: Optional[str] = None # Will be set by assign_style
        self.assigned_h_align: str = initial_h_align
        self.assigned_v_align: str = initial_v_align

        self.text_item = QGraphicsTextItem(self) # Child item for displaying styled text
        # Ensure text_item does not affect parent's selection/movability by itself
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self._rect = QRectF(0, 0, final_w_pixels, final_h_pixels) # Store dimensions relative to item's origin
        self.setPos(final_x_pixels, final_y_pixels) # Set position in the scene

        # self.assign_horizontal_alignment(initial_h_align) # Called by assign_style if it calls _update_text_item_appearance
        # self.assign_vertical_alignment(initial_v_align) # Also called by assign_style
        self.assign_style(initial_style_name) # Apply initial style (which calls _update_text_item_appearance)

    def boundingRect(self) -> QRectF: # Must implement for QGraphicsObject
        # Calculate the margin needed to encompass everything drawn outside self._rect
        
        # Margin for resize handles (they extend half their size outside _rect)
        handle_margin = RESIZE_HANDLE_SIZE / 2.0
        
        # Margin for percentage text
        # Approximating text dimensions for bounding rect calculation
        text_offset_from_rect_edge = RESIZE_HANDLE_SIZE * 1.5 
        # Use a temporary font similar to what's used in paint for measurements
        measurement_font_approx = QFont()
        measurement_font_approx.setPointSize(max(6, int(RESIZE_HANDLE_SIZE * 1.2)))
        fm = QFontMetrics(measurement_font_approx)
        
        # Estimate width needed for "100.0%" text plus padding
        percent_text_width_approx = fm.horizontalAdvance("100.0%") + 10 # 5px padding each side
        measurement_text_height_approx = fm.height()

        # For text above/below, consider its height + offset
        text_vertical_clearance = text_offset_from_rect_edge + measurement_text_height_approx
        # For text left/right, consider its width (approx 40px box) + offset
        text_horizontal_clearance = text_offset_from_rect_edge + percent_text_width_approx
        margin = max(handle_margin, text_vertical_clearance, text_horizontal_clearance) + self._pen.widthF() # Add pen width for safety
        return self._rect.adjusted(-margin, -margin, margin, margin)

    def paint(self, painter: QPainter, option, widget=None): # Must implement for QGraphicsObject
        painter.setPen(self._pen) # Draw the main rectangle border
        painter.setBrush(self._brush)
        painter.drawRect(self._rect) # Draw the rectangle
        
        # The self.text_item (QGraphicsTextItem child) will handle drawing the text.
        # Its properties are set in _update_text_item_appearance()

        # Draw percentage measurements if selected
        # Using self.isSelected() is often more direct for the item's own state
        if self.isSelected(): # Changed from option.state for clarity
            painter.setPen(QColor(Qt.GlobalColor.cyan)) # Measurement text color
            measurement_font = painter.font()
            measurement_font.setPointSize(max(6, int(RESIZE_HANDLE_SIZE * 1.2))) # Small font for measurements
            painter.setFont(measurement_font)

            # Get item's position and size in scene coordinates
            item_scene_pos = self.pos() # Top-left of the item in scene coordinates
            item_rect_width_scene = self._rect.width()  # Width of the item's internal rect
            item_rect_height_scene = self._rect.height() # Height of the item's internal rect

            # Percentages relative to the scene dimensions
            # These are the distances from the scene edges to the item's edges
            percent_from_left = (item_scene_pos.x() / self.scene_width) * 100.0
            percent_from_top = (item_scene_pos.y() / self.scene_height) * 100.0
            
            item_right_edge_scene = item_scene_pos.x() + item_rect_width_scene
            percent_to_right = ((self.scene_width - item_right_edge_scene) / self.scene_width) * 100.0
            
            item_bottom_edge_scene = item_scene_pos.y() + item_rect_height_scene
            percent_to_bottom = ((self.scene_height - item_bottom_edge_scene) / self.scene_height) * 100.0

            # Item's own width and height as percentages of the scene (optional to display)
            # item_width_pc = (item_rect_width_scene / self.scene_width) * 100.0
            # item_height_pc = (item_rect_height_scene / self.scene_height) * 100.0

            # Draw text relative to the item's local coordinates (_rect)
            text_offset = RESIZE_HANDLE_SIZE * 1.5 # Offset from the item's edge
            text_box_height = painter.fontMetrics().height() 
            text_box_width_for_top_bottom_text = painter.fontMetrics().horizontalAdvance("100.0%") + 10 
            text_box_width_for_side_text = painter.fontMetrics().horizontalAdvance("100.0%") + 10 

            # Distance from scene top to item top
            painter.drawText(QRectF(self._rect.center().x() - text_box_width_for_top_bottom_text / 2, self._rect.top() - text_offset - text_box_height, text_box_width_for_top_bottom_text, text_box_height), Qt.AlignmentFlag.AlignCenter, f"{percent_from_top:.1f}%")
            # Distance from scene left to item left
            painter.drawText(QRectF(self._rect.left() - text_offset - text_box_width_for_side_text, self._rect.center().y() - (text_box_height/2), text_box_width_for_side_text, text_box_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{percent_from_left:.1f}%")
            # Distance from item right to scene right
            painter.drawText(QRectF(self._rect.right() + text_offset, self._rect.center().y() - (text_box_height/2), text_box_width_for_side_text, text_box_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{percent_to_right:.1f}%")
            # Distance from item bottom to scene bottom
            painter.drawText(QRectF(self._rect.center().x() - text_box_width_for_top_bottom_text / 2, self._rect.bottom() + text_offset, text_box_width_for_top_bottom_text, text_box_height), Qt.AlignmentFlag.AlignCenter, f"{percent_to_bottom:.1f}%")
        
    # Optionally draw resize handles when selected
        if self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.setBrush(QBrush(Qt.GlobalColor.black))
            handle_size = RESIZE_HANDLE_SIZE
            half_handle = handle_size / 2.0
            
            # Corners
            painter.drawRect(self._rect.topLeft().x() - half_handle, self._rect.topLeft().y() - half_handle, handle_size, handle_size)
            painter.drawRect(self._rect.topRight().x() - half_handle, self._rect.topRight().y() - half_handle, handle_size, handle_size)
            painter.drawRect(self._rect.bottomLeft().x() - half_handle, self._rect.bottomLeft().y() - half_handle, handle_size, handle_size)
            painter.drawRect(self._rect.bottomRight().x() - half_handle, self._rect.bottomRight().y() - half_handle, handle_size, handle_size)
            
            # Mid-points
            painter.drawRect(self._rect.center().x() - half_handle, self._rect.top() - half_handle, handle_size, handle_size) # Top-mid
            painter.drawRect(self._rect.center().x() - half_handle, self._rect.bottom() - half_handle, handle_size, handle_size) # Bottom-mid
            painter.drawRect(self._rect.left() - half_handle, self._rect.center().y() - half_handle, handle_size, handle_size) # Left-mid
            painter.drawRect(self._rect.right() - half_handle, self._rect.center().y() - half_handle, handle_size, handle_size) # Right-mid

    def hoverShape(self) -> QPainterPath:
        # Override hoverShape to provide a larger interactive area for resizing
        path = QPainterPath()
        # Add the main rectangle plus a margin for easier grabbing
        path.addRect(self._rect.adjusted(-RESIZE_HANDLE_SIZE/2, -RESIZE_HANDLE_SIZE/2, RESIZE_HANDLE_SIZE/2, RESIZE_HANDLE_SIZE/2))
        return path
    
    def hoverMoveEvent(self, event):
        # Change cursor based on hover position for resizing
        pos = event.pos() # Position in item coordinates
        handle_size = RESIZE_HANDLE_SIZE # This is 8 pixels by default
        
        determined_cursor_shape = None # None means unset/defer to view
        
        left_edge = abs(pos.x() - self._rect.left()) < handle_size
        right_edge = abs(pos.x() - self._rect.right()) < handle_size
        top_edge = abs(pos.y() - self._rect.top()) < handle_size
        bottom_edge = abs(pos.y() - self._rect.bottom()) < handle_size
        
        if left_edge and top_edge: determined_cursor_shape = Qt.CursorShape.SizeFDiagCursor
        elif right_edge and bottom_edge: determined_cursor_shape = Qt.CursorShape.SizeFDiagCursor
        elif left_edge and bottom_edge: determined_cursor_shape = Qt.CursorShape.SizeBDiagCursor
        elif right_edge and top_edge: determined_cursor_shape = Qt.CursorShape.SizeBDiagCursor
        elif left_edge or right_edge: determined_cursor_shape = Qt.CursorShape.SizeHorCursor
        elif top_edge or bottom_edge: determined_cursor_shape = Qt.CursorShape.SizeVerCursor
        
        if determined_cursor_shape is not None:
            # If a specific resize cursor is determined, set it
            if self.cursor().shape() != determined_cursor_shape:
                self.setCursor(QCursor(determined_cursor_shape))
        else:
            # Not on a handle; if item has a cursor set (e.g. from previous move on handle), unset it
            # This allows the view's ScrollHandDrag cursor (OpenHand) to show.
            if self.hasCursor():
                self.unsetCursor()
        
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor() # Ensure view's cursor is restored when mouse leaves item
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos() # Position in item coordinates
            handle_size = RESIZE_HANDLE_SIZE
            
            left_edge = abs(pos.x() - self._rect.left()) < handle_size
            right_edge = abs(pos.x() - self._rect.right()) < handle_size
            top_edge = abs(pos.y() - self._rect.top()) < handle_size
            bottom_edge = abs(pos.y() - self._rect.bottom()) < handle_size
            
            # Determine resize mode
            if left_edge and top_edge: self._resize_mode = 'top-left'
            elif right_edge and bottom_edge: self._resize_mode = 'bottom-right'
            elif left_edge and bottom_edge: self._resize_mode = 'bottom-left'
            elif right_edge and top_edge: self._resize_mode = 'top-right'
            elif left_edge: self._resize_mode = 'left'
            elif right_edge: self._resize_mode = 'right'
            elif top_edge: self._resize_mode = 'top'
            elif bottom_edge: self._resize_mode = 'bottom'
            else: self._resize_mode = None # Not resizing, allow moving
            
            if self._resize_mode:
                self._mouse_press_pos = event.scenePos() # Store scene position for calculating delta
                self._item_initial_pos_at_drag = self.pos() # Store item's current scene position
                self._item_initial_rect_at_drag = QRectF(self._rect) # Store copy of item's current local rect
                self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, False) # Disable moving while resizing
                self.setSelected(True) # Ensure item is selected when resizing starts
                event.accept() # Accept the event to start drag
            else:
                super().mousePressEvent(event) # Not resizing, pass to base class for moving

    def mouseMoveEvent(self, event):
        if self._resize_mode and self._mouse_press_pos is not None:
            # Calculate how much the mouse has moved IN SCENE COORDINATES from its initial press position
            mouse_delta_scene = event.scenePos() - self._mouse_press_pos

            # Start with the item's initial geometry at the beginning of the drag
            new_item_pos_scene = QPointF(self._item_initial_pos_at_drag)
            new_item_local_rect = QRectF(self._item_initial_rect_at_drag)

            if 'left' in self._resize_mode:
                new_item_pos_scene.setX(self._item_initial_pos_at_drag.x() + mouse_delta_scene.x())
                new_item_local_rect.setWidth(self._item_initial_rect_at_drag.width() - mouse_delta_scene.x())
            if 'right' in self._resize_mode:
                new_item_local_rect.setWidth(self._item_initial_rect_at_drag.width() + mouse_delta_scene.x())
            if 'top' in self._resize_mode:
                new_item_pos_scene.setY(self._item_initial_pos_at_drag.y() + mouse_delta_scene.y())
                new_item_local_rect.setHeight(self._item_initial_rect_at_drag.height() - mouse_delta_scene.y())
            if 'bottom' in self._resize_mode:
                new_item_local_rect.setHeight(self._item_initial_rect_at_drag.height() + mouse_delta_scene.y())

            # Ensure minimum size
            min_size = 10.0
            if new_item_local_rect.width() < min_size:
                if 'left' in self._resize_mode: 
                    # If dragging left edge and width becomes too small,
                    # the item's X position needs to be adjusted to maintain min_width
                    # relative to the original right edge.
                    original_right_x = self._item_initial_pos_at_drag.x() + self._item_initial_rect_at_drag.width()
                    new_item_pos_scene.setX(original_right_x - min_size)
                # else: right edge is fixed by mouse, width is just set to min_size
                new_item_local_rect.setWidth(min_size)
            
            if new_item_local_rect.height() < min_size:
                if 'top' in self._resize_mode:
                    original_bottom_y = self._item_initial_pos_at_drag.y() + self._item_initial_rect_at_drag.height()
                    new_item_pos_scene.setY(original_bottom_y - min_size)
                new_item_local_rect.setHeight(min_size)
            
            # Normalize the rectangle if width/height became negative (e.g. dragging left edge past right edge)
            new_item_local_rect = new_item_local_rect.normalized()

            # --- Conditional Snapping logic for resize ---
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
                prop_x_pc = (new_item_pos_scene.x() / self.scene_width) * 100.0
                prop_y_pc = (new_item_pos_scene.y() / self.scene_height) * 100.0
                prop_w_pc = (new_item_local_rect.width() / self.scene_width) * 100.0
                prop_h_pc = (new_item_local_rect.height() / self.scene_height) * 100.0

                snapped_x_pc = self._snap_value(prop_x_pc, self.SNAP_INCREMENT_PC)
                snapped_y_pc = self._snap_value(prop_y_pc, self.SNAP_INCREMENT_PC)
                snapped_w_pc = self._snap_value(prop_w_pc, self.SNAP_INCREMENT_PC)
                snapped_h_pc = self._snap_value(prop_h_pc, self.SNAP_INCREMENT_PC)

                final_item_pos_x_pixels = (snapped_x_pc / 100.0) * self.scene_width
                final_item_pos_y_pixels = (snapped_y_pc / 100.0) * self.scene_height
                final_item_rect_w_pixels = (snapped_w_pc / 100.0) * self.scene_width
                final_item_rect_h_pixels = (snapped_h_pc / 100.0) * self.scene_height
                
                new_item_pos_scene = QPointF(final_item_pos_x_pixels, final_item_pos_y_pixels)
                new_item_local_rect = QRectF(0, 0, final_item_rect_w_pixels, final_item_rect_h_pixels)
            # --- End of conditional snapping logic for resize ---
            
            self.prepareGeometryChange() # Notify scene about geometry change
            self.setPos(new_item_pos_scene) # Update item's position in the scene
            self._rect = new_item_local_rect # Update internal rect (local coords)
            self._update_text_item_appearance() # Update text based on new rect size
            # DO NOT update self._mouse_press_pos here. It's the anchor for the current drag operation.
            self.update() # Request repaint
            event.accept()
        else:
            super().mouseMoveEvent(event) # Not resizing, pass to base class for moving

    def mouseReleaseEvent(self, event):
        if self._resize_mode:
            self._resize_mode = None
            self._mouse_press_pos = None
            self._item_initial_pos_at_drag = None
            self._item_initial_rect_at_drag = None
            self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True) # Re-enable moving
            
            # Calculate final geometry and emit signal after resize
            final_x_pc = (self.pos().x() / self.scene_width) * 100.0
            final_y_pc = (self.pos().y() / self.scene_height) * 100.0
            final_w_pc = (self._rect.width() / self.scene_width) * 100.0
            final_h_pc = (self._rect.height() / self.scene_height) * 100.0

            # Emit the values as they are (snapped if Ctrl was held during move, otherwise not)
            self.geometry_changed_pc.emit(self.tb_id, final_x_pc, final_y_pc, final_w_pc, final_h_pc)
            event.accept()
        else:
            super().mouseReleaseEvent(event) # Not resizing, pass to base class


    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() and not self._resize_mode:
            # 'value' is the new proposed QPointF position in scene coordinates
            new_pos_pixels = value
            
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
                potential_x_pc = (new_pos_pixels.x() / self.scene_width) * 100.0
                potential_y_pc = (new_pos_pixels.y() / self.scene_height) * 100.0

                snapped_x_pc = self._snap_value(potential_x_pc, self.SNAP_INCREMENT_PC)
                snapped_y_pc = self._snap_value(potential_y_pc, self.SNAP_INCREMENT_PC)

                final_snapped_x_pixels = (snapped_x_pc / 100.0) * self.scene_width
                final_snapped_y_pixels = (snapped_y_pc / 100.0) * self.scene_height
                
                snapped_pos_pixels = QPointF(final_snapped_x_pixels, final_snapped_y_pixels)
                
                if snapped_pos_pixels != new_pos_pixels:
                    value = snapped_pos_pixels # Modify the proposed position to the snapped one
            # If Ctrl not held, value remains the raw proposed position

        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() and not self._resize_mode:
            # Item has finished moving. 'value' is the new position (which should be the snapped one).
            # Use self.pos() for definitive current position.
            current_pos_pixels = self.pos() 

            final_x_pc = (current_pos_pixels.x() / self.scene_width) * 100.0
            final_y_pc = (current_pos_pixels.y() / self.scene_height) * 100.0
            
            current_w_pc = (self._rect.width() / self.scene_width) * 100.0
            current_h_pc = (self._rect.height() / self.scene_height) * 100.0
            
            # Emit the values as they are (snapped if Ctrl was held during move, otherwise not)
            self.geometry_changed_pc.emit(self.tb_id, final_x_pc, final_y_pc, current_w_pc, current_h_pc)


        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange and self.scene():
            # Selection state has changed, trigger an update to redraw with/without handles/text
            self.update()

        return super().itemChange(change, value)

    def assign_style(self, style_name: Optional[str]):
        self.assigned_style_name = style_name
        self._update_text_item_appearance()

    def assign_horizontal_alignment(self, h_align: str):
        self.assigned_h_align = h_align
        self._update_text_item_appearance()

    def assign_vertical_alignment(self, v_align: str):
        self.assigned_v_align = v_align
        self._update_text_item_appearance()

    def _snap_value(self, value: float, increment: float) -> float:
        """Snaps a value to the nearest multiple of the increment."""
        if increment <= 0:
            return value
        return round(value / increment) * increment

    def _update_text_item_appearance(self):
        self.prepareGeometryChange() # Important if text changes could affect bounding rect

        text_to_display = self.tb_id
        font = QFont() # Default font (e.g., Arial or system default)
        text_color = QColor(Qt.GlobalColor.black) # Default text color

        if self.assigned_style_name and self.assigned_style_name in self.style_definitions_ref:
            style_props = self.style_definitions_ref[self.assigned_style_name]
            
            font.setFamily(style_props.get("font_family", font.family())) # Fallback to current font's family
            
            point_size_from_style = style_props.get("font_size")
            if point_size_from_style is not None:
                font.setPointSize(point_size_from_style)
            else:
                # Style is assigned, but font_size is missing in its definition (should be rare)
                # Use a small, fixed default to indicate an issue with the style def.
                font.setPointSize(8) # Small fixed default
                
            text_color = QColor(style_props.get("font_color", text_color.name())) # Fallback to default text_color
            
            if style_props.get("force_all_caps", False):
                text_to_display = text_to_display.upper()
        else:
            # No style assigned, or assigned style_name not found in definitions.
            # Use dynamic sizing for the text.
            # Font family remains QFont() default.
            # Text color remains default black.
            dynamic_point_size = max(6, int(self._rect.height() / 6)) # Original dynamic sizing
            font.setPointSize(dynamic_point_size)

        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(text_color)
        self.text_item.setPlainText(text_to_display)

        # Apply horizontal alignment
        doc_option = self.text_item.document().defaultTextOption()
        if self.assigned_h_align == "left":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        elif self.assigned_h_align == "center":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        elif self.assigned_h_align == "right":
            doc_option.setAlignment(Qt.AlignmentFlag.AlignRight)
        else: # Default or fallback
            doc_option.setAlignment(Qt.AlignmentFlag.AlignLeft) # Default to left if unspecified
        self.text_item.document().setDefaultTextOption(doc_option)

        # --- Horizontal Positioning and Width ---
        h_padding = self._pen.widthF() + 2 # Horizontal padding from the edge of the yellow box
        text_rect_width = self._rect.width() - 2 * h_padding
        if text_rect_width < 1: text_rect_width = 1 # Ensure positive width for setTextWidth
        self.text_item.setTextWidth(text_rect_width) # This affects the text_item's bounding rect height

        # --- Vertical Positioning ---
        v_padding = self._pen.widthF() + 2 # Vertical padding
        text_item_height = self.text_item.boundingRect().height()
        available_height_for_text = self._rect.height() - 2 * v_padding

        text_y_pos = self._rect.top() + v_padding
        if self.assigned_v_align == "center":
            if text_item_height < available_height_for_text: # Only center if there's space
                text_y_pos = self._rect.top() + v_padding + (available_height_for_text - text_item_height) / 2
        elif self.assigned_v_align == "bottom":
            if text_item_height < available_height_for_text: # Only align bottom if there's space
                text_y_pos = self._rect.top() + v_padding + (available_height_for_text - text_item_height)

        self.text_item.setPos(self._rect.left() + h_padding, text_y_pos)
        self.update() # Request repaint of the LayoutRectItem

class OutlinedGraphicsTextItem(QGraphicsTextItem):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._outline_pen = QPen(Qt.PenStyle.NoPen)
        self._text_fill_color = QColor(Qt.GlobalColor.black)
        self._has_outline = False
        self._current_font = QFont() # Store the current font

        # Initialize with default font and color to ensure _apply_format_to_document works
        super().setFont(self._current_font)
        super().setDefaultTextColor(self._text_fill_color)

        if text:
            self.setPlainText(text) # This will call _apply_format_to_document

    def setOutline(self, color: QColor, thickness: int):
        if thickness > 0 and color.isValid():
            # The pen width for setTextOutline is the actual stroke width.
            self._outline_pen = QPen(color, float(thickness))
            self._outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin) # Makes corners look better
            self._has_outline = True
        else:
            self._outline_pen = QPen(Qt.PenStyle.NoPen)
            self._has_outline = False
        self._apply_format_to_document()

    def setTextFillColor(self, color: QColor):
        self._text_fill_color = color
        # Also call super's method if it's used for default text color elsewhere
        super().setDefaultTextColor(color)
        self._apply_format_to_document()

    def setFont(self, font: QFont):
        self._current_font = font
        super().setFont(font)
        # When font changes, we need to re-apply the whole format
        self._apply_format_to_document()

    def setPlainText(self, text: str):
        super().setPlainText(text)
        # After text is set/changed, re-apply the format
        self._apply_format_to_document()

    def setHtml(self, html: str):
        super().setHtml(html)
        # After html is set/changed, re-apply the format
        self._apply_format_to_document()

    def _apply_format_to_document(self):
        if not self.document():  # Document might not exist if no text/HTML has been set
            return

        self.prepareGeometryChange() # Important if formatting affects bounding rect

        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)

        text_format = QTextCharFormat()
        # Apply all relevant properties in one go
        text_format.setFont(self._current_font)
        text_format.setForeground(self._text_fill_color) # This is the brush for the text fill

        if self._has_outline:
            text_format.setTextOutline(self._outline_pen)
        else:
            # Explicitly remove outline by setting a NoPen
            text_format.setTextOutline(QPen(Qt.PenStyle.NoPen))

        cursor.mergeCharFormat(text_format)
        # self.update() # mergeCharFormat usually triggers necessary updates

class TemplateEditorWindow(QDialog):
    # Signal to indicate that the current templates (styles, etc.) should be saved
    templates_save_requested = Signal(dict)

    def __init__(self, all_templates: dict, parent=None):
        super().__init__(parent)

        # Load the UI file
        # Assuming the .ui file is in the same directory as this .py file
        script_file_info = QFileInfo(__file__) # Get info about the current script file
        script_directory_path = script_file_info.absolutePath() # Get the absolute path of the directory
        script_qdir = QDir(script_directory_path) # Create a QDir object for that directory
        ui_file_path = script_qdir.filePath("template_editor_window.ui") # Construct path to .ui file

        loader = QUiLoader()
        # Register custom widgets before loading the UI
        loader.registerCustomWidget(ZoomableGraphicsView)
        self.ui = loader.load(ui_file_path, self)

        # --- Access widgets from the loaded UI (Styles Tab) ---
        self.style_selector_combo: QComboBox = self.ui.findChild(QComboBox, "style_selector_combo")
        self.add_style_button: QPushButton = self.ui.findChild(QPushButton, "add_style_button")
        self.remove_style_button: QPushButton = self.ui.findChild(QPushButton, "remove_style_button")
        
        self.preview_text_input_edit: QLineEdit = self.ui.findChild(QLineEdit, "preview_text_input_edit")
        self.font_family_combo: QFontComboBox = self.ui.findChild(QFontComboBox, "font_family_combo")
        self.font_size_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "font_size_spinbox")
        self.font_color_button: QPushButton = self.ui.findChild(QPushButton, "font_color_button")
        self.font_color_preview_label: QLabel = self.ui.findChild(QLabel, "font_color_preview_label")
        
        self.force_caps_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "force_caps_checkbox")
        self.text_shadow_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "text_shadow_checkbox")
        self.text_outline_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "text_outline_checkbox")
        
        # Shadow Detail Controls
        self.shadow_properties_group = self.ui.findChild(QWidget, "shadow_properties_group") # QGroupBox is a QWidget
        self.shadow_x_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_x_spinbox")
        self.shadow_y_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_y_spinbox")
        self.shadow_blur_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "shadow_blur_spinbox")
        self.shadow_color_button: QPushButton = self.ui.findChild(QPushButton, "shadow_color_button")
        self.shadow_color_preview_label: QLabel = self.ui.findChild(QLabel, "shadow_color_preview_label")
        
        # Outline Detail Controls
        self.outline_properties_group = self.ui.findChild(QWidget, "outline_properties_group") # QGroupBox is a QWidget
        self.outline_thickness_spinbox: QSpinBox = self.ui.findChild(QSpinBox, "outline_thickness_spinbox")
        self.outline_color_button: QPushButton = self.ui.findChild(QPushButton, "outline_color_button")
        self.outline_color_preview_label: QLabel = self.ui.findChild(QLabel, "outline_color_preview_label")
        
        # --- Access widgets from the loaded UI (Layouts Tab) ---
        self.layout_selector_combo: QComboBox = self.ui.findChild(QComboBox, "layout_selector_combo")
        self.add_layout_button: QPushButton = self.ui.findChild(QPushButton, "add_layout_button")
        self.remove_layout_button: QPushButton = self.ui.findChild(QPushButton, "remove_layout_button")
        self.rename_layout_button: QPushButton = self.ui.findChild(QPushButton, "rename_layout_button")
        self.layout_preview_graphics_view: ZoomableGraphicsView = self.ui.findChild(ZoomableGraphicsView, "layout_preview_graphics_view") # Use custom class
        self.add_textbox_to_layout_button: QPushButton = self.ui.findChild(QPushButton, "add_textbox_to_layout_button")
        self.remove_selected_textbox_button: QPushButton = self.ui.findChild(QPushButton, "remove_selected_textbox_button")
        self.textbox_properties_group: QGroupBox = self.ui.findChild(QGroupBox, "textbox_properties_group")
        self.selected_textbox_id_edit: QLineEdit = self.ui.findChild(QLineEdit, "selected_textbox_id_edit")
        self.selected_textbox_style_combo: QComboBox = self.ui.findChild(QComboBox, "selected_textbox_style_combo")
        self.selected_textbox_halign_combo: QComboBox = self.ui.findChild(QComboBox, "selected_textbox_halign_combo") # New
        self.selected_textbox_valign_combo: QComboBox = self.ui.findChild(QComboBox, "selected_textbox_valign_combo") # New
        # Layout Background Color Controls
        self.layout_bg_enable_checkbox: QCheckBox = self.ui.findChild(QCheckBox, "layout_bg_enable_checkbox")
        self.layout_bg_color_button: QPushButton = self.ui.findChild(QPushButton, "layout_bg_color_button")
        self.layout_bg_color_swatch_label: QLabel = self.ui.findChild(QLabel, "layout_bg_color_swatch_label")
        self.remove_selected_textbox_button: QPushButton = self.ui.findChild(QPushButton, "remove_selected_textbox_button")
        self.layout_preview_scene = QGraphicsScene(self)
        self.layout_preview_graphics_view.setScene(self.layout_preview_scene)

        # Graphics View for Style Preview
        self.style_preview_graphics_view: QGraphicsView = self.ui.findChild(QGraphicsView, "style_preview_graphics_view")
        self.style_preview_scene = QGraphicsScene(self)
        self.style_preview_graphics_view.setScene(self.style_preview_scene) # Still use standard QGraphicsView for style preview
        self.style_preview_text_item = OutlinedGraphicsTextItem() # Use the new custom item
        self.style_preview_text_item.setFont(QFont()) # Initialize with a default font
        self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black)) # Initialize fill
        self.style_preview_scene.addItem(self.style_preview_text_item) # Add item to scene
        self.style_preview_graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style_preview_graphics_view.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Initialize a variable to store the current font color
        self._current_style_font_color = QColor(Qt.GlobalColor.black) 
        self._current_shadow_color = QColor(0,0,0,180) # Default shadow: semi-transparent black
        self._current_outline_color = QColor(Qt.GlobalColor.black) # Default outline: solid black
        self._current_layout_bg_color: Optional[QColor] = None # For layout background color

        # Set the layout for the QDialog itself if not handled by QUiLoader correctly for top-level
        if self.layout() is None: # Check if a layout is already set
            main_layout_from_ui = self.ui.layout()
            if main_layout_from_ui:
                self.setLayout(main_layout_from_ui)
            else: # Fallback if the .ui file's top widget doesn't have a layout for the dialog
                fallback_layout = QVBoxLayout(self)
                fallback_layout.addWidget(self.ui)
                self.setLayout(fallback_layout)

        self.setWindowTitle(self.ui.windowTitle()) # Set window title from UI file
        self.resize(self.ui.size()) # Set initial size from UI file

        # --- Initialize data structures for styles, layouts, and master templates ---
        # Make deep copies to avoid modifying the original dict directly until "OK" or "Save"
        self.style_definitions = copy.deepcopy(all_templates.get("styles", {}))
        self.layout_definitions = copy.deepcopy(all_templates.get("layouts", {}))

        self._currently_editing_style_name: str | None = None
        self._currently_editing_layout_name: str | None = None
        # TODO: Add similar tracking variables for currently editing layout/master template when those tabs are implemented


        # If, after loading, there are no styles, create a default one.
        if not self.style_definitions: # Check if it's still empty
            default_style_props = {
                "font_family": self.font_family_combo.font().family(), # Get default from combo
                "font_size": self.font_size_spinbox.value(),
                "font_color": self._current_style_font_color.name(), # Store as hex string
                "preview_text": "Sample Text Aa Bb Cc", # Initial text
                "force_all_caps": False,
                "text_shadow": False,
                "text_outline": False,
                "shadow_x": self.shadow_x_spinbox.value(), "shadow_y": self.shadow_y_spinbox.value(), 
                "shadow_blur": self.shadow_blur_spinbox.value(), "shadow_color": self._current_shadow_color.name(QColor.NameFormat.HexArgb),
                "outline_thickness": self.outline_thickness_spinbox.value(), "outline_color": self._current_outline_color.name(),
            }
            self.style_definitions["Default Style"] = default_style_props
            
        # TODO: Add similar default creation logic for layouts and master_templates
        # if not self.layout_definitions:
        #     self.layout_definitions["Default Layout"] = copy.deepcopy(DEFAULT_LAYOUT_PROPS_FROM_MANAGER_OR_HERE)
        # If, after loading, there are no layouts, create a default one.
        if not self.layout_definitions:
            self.layout_definitions["Default Layout"] = copy.deepcopy(NEW_LAYOUT_DEFAULT_PROPS)
            

        # --- Populate UI for each tab ---
        # Layouts Tab
        self._populate_layout_selector()

        # Styles Tab (already implemented)
        self._populate_style_selector()
        # TODO: Call similar population methods for Layouts and Master Templates tabs when implemented

        # --- Connect signals from the loaded UI ---
        self.ui.button_box.accepted.connect(self.accept)
        self.ui.button_box.rejected.connect(self.reject)

        # Add a "Save" button to the dialog's button box
        self.save_button = QPushButton("Save")
        self.ui.button_box.addButton(self.save_button, QDialogButtonBox.ButtonRole.ApplyRole) # ApplyRole is good for "save and continue"
        self.save_button.clicked.connect(self._handle_save_action)
        # Tooltip for clarity
        self.save_button.setToolTip("Save current changes and continue editing.")

        # --- Style Tab Connections ---
        self.add_style_button.clicked.connect(self.add_new_style_definition)
        self.remove_style_button.clicked.connect(self.remove_selected_style_definition)
        self.style_selector_combo.currentTextChanged.connect(self.on_style_selected)

        self.preview_text_input_edit.textChanged.connect(self.update_style_from_preview_text_input)
        self.font_family_combo.currentFontChanged.connect(self.update_style_from_font_controls)
        self.font_size_spinbox.valueChanged.connect(self.update_style_from_font_controls)
        self.font_color_button.clicked.connect(self.choose_style_font_color)
        
        self.force_caps_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        self.text_shadow_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        self.text_outline_checkbox.toggled.connect(self.update_style_from_formatting_controls)
        
        # Shadow detail connections
        self.shadow_x_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_y_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_blur_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.shadow_color_button.clicked.connect(self.choose_shadow_color)
        # Outline detail connections
        self.outline_thickness_spinbox.valueChanged.connect(self.update_style_from_formatting_controls)
        self.outline_color_button.clicked.connect(self.choose_outline_color)
        
        # --- Layout Tab Connections ---
        self.add_layout_button.clicked.connect(self.add_new_layout_definition)
        self.remove_layout_button.clicked.connect(self.remove_selected_layout_definition)
        self.rename_layout_button.clicked.connect(self.rename_selected_layout_definition)
        self.layout_selector_combo.currentTextChanged.connect(self.on_layout_selected)
        self.add_textbox_to_layout_button.clicked.connect(self.add_textbox_to_current_layout)
        self.remove_selected_textbox_button.clicked.connect(self._remove_selected_textbox_from_layout)
        self.selected_textbox_id_edit.editingFinished.connect(self._handle_selected_textbox_id_changed)
        self.selected_textbox_style_combo.currentTextChanged.connect(self._handle_selected_textbox_style_changed)
        self.selected_textbox_halign_combo.currentTextChanged.connect(self._handle_selected_textbox_halign_changed) # New
        self.selected_textbox_valign_combo.currentTextChanged.connect(self._handle_selected_textbox_valign_changed) # New
        # Layout Background Color Connections
        self.layout_bg_enable_checkbox.toggled.connect(self._on_layout_bg_enable_toggled)
        self.layout_bg_color_button.clicked.connect(self._choose_layout_bg_color)
        self.layout_preview_scene.selectionChanged.connect(self._update_layout_buttons_state) # Update on selection change
        self.ui.main_tab_widget.currentChanged.connect(self._on_main_tab_changed) # New connection

        if self.style_selector_combo.count() > 0:
            # Set the index first
            self.style_selector_combo.setCurrentIndex(0)
            # Manually call on_style_selected to ensure it runs for the initial item,
            # in case setCurrentIndex(0) doesn't trigger currentTextChanged if the
            # text was somehow considered unchanged by Qt's internal state.
            print(f"DEBUG: __init__ - Manually calling on_style_selected with: '{self.style_selector_combo.currentText()}'") # DEBUG
            self.on_style_selected(self.style_selector_combo.currentText())
        else:
            self._clear_style_controls() # No styles, clear controls
            self._update_style_remove_button_state()
            
        if self.layout_selector_combo.count() > 0:
            self.layout_selector_combo.setCurrentIndex(0) # Triggers on_layout_selected
            # Manually call on_layout_selected to ensure it runs for the initial item
            print(f"DEBUG: __init__ - Manually calling on_layout_selected with: '{self.layout_selector_combo.currentText()}'")
            self.on_layout_selected(self.layout_selector_combo.currentText())
        else:
            self._clear_layout_preview()
            self._update_layout_buttons_state()
            
        # Initial state for detail groups
        self._toggle_shadow_detail_group()
        self._toggle_outline_detail_group()
        
    @Slot(int)
    def _on_main_tab_changed(self, index: int):
        """Called when the current tab in the main QTabWidget changes."""
        # Assuming Layouts tab is at index 0, Styles at 1
        # You can get the tab text to be more robust:
        # tab_text = self.ui.main_tab_widget.tabText(index)
        # if tab_text == "Layouts":
        
        if index == 0: # Switched to the "Layouts" tab
            print("DEBUG: Switched to Layouts tab. Refreshing layout items.")
            if self._currently_editing_layout_name and self.layout_preview_scene:
                for item in self.layout_preview_scene.items():
                    if isinstance(item, LayoutRectItem):
                        # Re-apply its current style to refresh appearance
                        # This will pick up any changes made in the Styles tab
                        item.assign_style(item.assigned_style_name)
                        # Also re-apply alignment as style changes might affect text metrics
                        item.assign_horizontal_alignment(item.assigned_h_align)
                        item.assign_vertical_alignment(item.assigned_v_align)

    # --- Layout Tab Methods ---
    def _populate_layout_selector(self):
        self.layout_selector_combo.blockSignals(True)
        current_text = self.layout_selector_combo.currentText()
        self.layout_selector_combo.clear()
        self.layout_selector_combo.addItems(self.layout_definitions.keys())
        if current_text in self.layout_definitions:
            self.layout_selector_combo.setCurrentText(current_text)
        elif self.layout_selector_combo.count() > 0:
            self.layout_selector_combo.setCurrentIndex(0)
        self.layout_selector_combo.blockSignals(False)

    @Slot()
    def add_new_layout_definition(self):
        layout_name, ok = QInputDialog.getText(self, "New Layout", "Enter name for the new layout definition:")
        if ok and layout_name:
            layout_name = layout_name.strip()
            if not layout_name:
                QMessageBox.warning(self, "Invalid Name", "Layout name cannot be empty.")
                return
            if layout_name in self.layout_definitions:
                QMessageBox.warning(self, "Name Exists", f"A layout named '{layout_name}' already exists.")
                return

            self.layout_definitions[layout_name] = copy.deepcopy(NEW_LAYOUT_DEFAULT_PROPS)
            self._populate_layout_selector()
            self.layout_selector_combo.setCurrentText(layout_name) # Triggers on_layout_selected
        elif ok and not layout_name.strip():
            QMessageBox.warning(self, "Invalid Name", "Layout name cannot be empty.")

    @Slot()
    def remove_selected_layout_definition(self):
        if not self._currently_editing_layout_name:
            return
        if len(self.layout_definitions) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "Cannot remove the last layout definition.")
            return

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Are you sure you want to remove the layout '{self._currently_editing_layout_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.layout_definitions[self._currently_editing_layout_name]
            self._currently_editing_layout_name = None
            self._populate_layout_selector()
            if self.layout_selector_combo.count() > 0:
                self.layout_selector_combo.setCurrentIndex(0)
            else:
                self._clear_layout_preview()

    @Slot()
    def rename_selected_layout_definition(self):
        if not self._currently_editing_layout_name:
            QMessageBox.information(self, "No Layout Selected", "Please select a layout to rename.")
            return

        old_layout_name = self._currently_editing_layout_name
        new_layout_name, ok = QInputDialog.getText(self, "Rename Layout",
                                                   f"Enter the new name for layout '{old_layout_name}':",
                                                   QLineEdit.EchoMode.Normal, # QLineEdit.Normal for PySide2
                                                   old_layout_name) # Pre-fill with current name

        if ok and new_layout_name:
            new_layout_name = new_layout_name.strip()
            if not new_layout_name:
                QMessageBox.warning(self, "Invalid Name", "Layout name cannot be empty.")
                return

            if new_layout_name == old_layout_name:
                # Name hasn't changed, do nothing
                return

            if new_layout_name in self.layout_definitions:
                QMessageBox.warning(self, "Name Exists", f"A layout named '{new_layout_name}' already exists.")
                return

            # Perform the rename
            layout_properties = self.layout_definitions.pop(old_layout_name)
            self.layout_definitions[new_layout_name] = layout_properties
            self._currently_editing_layout_name = new_layout_name # Update the tracked name
            self._populate_layout_selector() # Refresh the combo box
            self.layout_selector_combo.setCurrentText(new_layout_name) # Select the new name, triggers on_layout_selected
            print(f"DEBUG: Renamed layout from '{old_layout_name}' to '{new_layout_name}'")
        elif ok and not new_layout_name.strip(): # User pressed OK but the input was empty or just whitespace
            QMessageBox.warning(self, "Invalid Name", "Layout name cannot be empty.")

    @Slot(str)
    def on_layout_selected(self, layout_name: str):
        print(f"DEBUG: on_layout_selected: '{layout_name}'")
        if not layout_name or layout_name not in self.layout_definitions:
            self._clear_layout_preview()
            self._currently_editing_layout_name = None
            self._update_textbox_properties_panel() # Clear/disable panel
            return

        self._currently_editing_layout_name = layout_name
        layout_props = self.layout_definitions[layout_name]
        
        self.layout_preview_scene.clear()

        # Load and set layout background color from layout_props
        bg_color_hex = layout_props.get("background_color")
        self.layout_bg_enable_checkbox.blockSignals(True) # Block signals during programmatic update
        if bg_color_hex:
            self._current_layout_bg_color = QColor(bg_color_hex)
            self.layout_bg_enable_checkbox.setChecked(True)
            self.layout_bg_color_button.setEnabled(True)
        else:
            # If no color is in layout_props, it means transparent.
            # Set checkbox to false, and internal color to transparent black.
            self._current_layout_bg_color = QColor(0, 0, 0, 0) # Transparent black
            self.layout_bg_enable_checkbox.setChecked(False)
            self.layout_bg_color_button.setEnabled(False)
        self._update_layout_bg_color_swatch()
        self.layout_bg_enable_checkbox.blockSignals(False) # Unblock signals

        # Define a scene rect, e.g., 16:9 aspect ratio
        scene_width = 1600
        scene_height = 900
        self.layout_preview_scene.setSceneRect(0, 0, scene_width, scene_height)
        
        # Draw background for the scene (representing slide background)
        if self.layout_bg_enable_checkbox.isChecked() and self._current_layout_bg_color:
            bg_color = self._current_layout_bg_color
        else: # Transparent if checkbox is off or color is None
            bg_color = QColor(Qt.GlobalColor.transparent) # Or a default like darkGray if you prefer a visual placeholder
        self.layout_preview_scene.setBackgroundBrush(QBrush(bg_color))

        # Draw a border rectangle to clearly indicate the slide bounds
        border_pen = QPen(QColor(Qt.GlobalColor.gray), 1) # A thin gray border
        border_pen.setStyle(Qt.PenStyle.SolidLine)
        # Create a rectangle that is slightly inset to ensure the border is fully visible
        # and doesn't get clipped by the view's edges if fitInView is exact.
        self.layout_preview_scene.addRect(self.layout_preview_scene.sceneRect(), border_pen)

        for tb_props in layout_props.get("text_boxes", []):
            x = scene_width * (tb_props.get("x_pc", 0) / 100.0)
            y = scene_height * (tb_props.get("y_pc", 0) / 100.0)
            w = scene_width * (tb_props.get("width_pc", 10) / 100.0)
            h = scene_height * (tb_props.get("height_pc", 10) / 100.0)
            
            rect_item = LayoutRectItem(
                tb_id=tb_props.get("id", "unknown"), x=x, y=y, w=w, h=h,
                scene_w=scene_width, scene_h=scene_height,
                style_definitions_ref=self.style_definitions, # Pass reference to all styles
                initial_v_align=tb_props.get("v_align", "center"), # Pass v_align
                initial_h_align=tb_props.get("h_align", "center"), # Pass h_align
                initial_style_name=tb_props.get("style_name") # Pass current style name
            )
            # Connect the item's signal to a handler in the editor window
            rect_item.geometry_changed_pc.connect(self._handle_layout_item_geometry_changed)
            self.layout_preview_scene.addItem(rect_item)
            
            # Store a reference if needed, e.g., for selecting/editing properties later
            # self.current_layout_items[tb_props.get("id")] = rect_item 
        self.layout_preview_graphics_view.fitInView(self.layout_preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._update_layout_buttons_state()
        self._update_textbox_properties_panel() # Update panel based on new selection (likely none initially)

    @Slot(bool)
    def _on_layout_bg_enable_toggled(self, checked: bool):
        self.layout_bg_color_button.setEnabled(checked)
        self._update_layout_bg_color_swatch()

        if self._currently_editing_layout_name:
            layout_props = self.layout_definitions[self._currently_editing_layout_name]
            if checked:
                # If enabling, and _current_layout_bg_color is transparent (from being disabled),
                # set it to a default opaque color (e.g., black) before saving.
                if self._current_layout_bg_color is None or self._current_layout_bg_color.alpha() == 0:
                    self._current_layout_bg_color = QColor(Qt.GlobalColor.black) # Default to opaque black when enabling
                layout_props["background_color"] = self._current_layout_bg_color.name(QColor.NameFormat.HexArgb)
                self.layout_preview_scene.setBackgroundBrush(QBrush(self._current_layout_bg_color))
            else: # Not checked (disabled)
                self._current_layout_bg_color = QColor(0,0,0,0) # Store as transparent black
                layout_props["background_color"] = self._current_layout_bg_color.name(QColor.NameFormat.HexArgb) # Save #00000000
                self.layout_preview_scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
            # self._current_layout_dirty = True
            # self._update_save_button_state()

    @Slot()
    def _choose_layout_bg_color(self):
        initial_color = self._current_layout_bg_color if self._current_layout_bg_color else QColor(Qt.GlobalColor.black)
        dialog = QColorDialog(initial_color, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True) # Enable Alpha
        
        if dialog.exec():
            new_color = dialog.currentColor()
            if new_color.isValid() and (not self._current_layout_bg_color or new_color != self._current_layout_bg_color):
                self._current_layout_bg_color = new_color
                self._update_layout_bg_color_swatch()
                if self._currently_editing_layout_name and self.layout_bg_enable_checkbox.isChecked():
                    # Save with Alpha
                    self.layout_definitions[self._currently_editing_layout_name]["background_color"] = new_color.name(QColor.NameFormat.HexArgb)
                    self.layout_preview_scene.setBackgroundBrush(QBrush(new_color))
                    # Mark layout as dirty

    def _update_layout_bg_color_swatch(self):
        display_color_name = 'transparent'
        if self.layout_bg_enable_checkbox.isChecked() and self._current_layout_bg_color:
            # If enabled, use the stored color, including its alpha for the swatch
            display_color_name = self._current_layout_bg_color.name(QColor.NameFormat.HexArgb)
        elif not self.layout_bg_enable_checkbox.isChecked():
            # If disabled, explicitly show transparent for the swatch
            display_color_name = QColor(0,0,0,0).name(QColor.NameFormat.HexArgb) # #00000000

        self.layout_bg_color_swatch_label.setStyleSheet(f"background-color: {display_color_name}; border: 1px solid grey;")
        # Reset view transform after loading a new layout
        self.layout_preview_graphics_view.resetTransform()
        self.layout_preview_graphics_view.fitInView(self.layout_preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    @Slot()
    def add_textbox_to_current_layout(self):
        if not self._currently_editing_layout_name:
            QMessageBox.information(self, "No Layout Selected", "Please select or create a layout first.")
            return
        
        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        num_existing_boxes = len(layout_props.get("text_boxes", []))
        new_box_id = f"textbox_{num_existing_boxes + 1}"
        
        # Add a new default text box definition
        new_box_props = {
            "id": new_box_id, 
            "x_pc": 5, "y_pc": 5, 
            "width_pc": 30, "height_pc": 15, 
            "h_align": "left", # Default h_align for new boxes
            "v_align": "top",  # Default v_align for new boxes
            "style_name": None # Default style for new boxes
        }
        layout_props.setdefault("text_boxes", []).append(new_box_props)
        
        # Refresh the preview for the current layout
        self.on_layout_selected(self._currently_editing_layout_name)
        print(f"DEBUG: Added new text box '{new_box_id}' to layout '{self._currently_editing_layout_name}'")

    @Slot()
    def _remove_selected_textbox_from_layout(self):
        if not self._currently_editing_layout_name:
            return

        selected_items = self.layout_preview_scene.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a text box in the preview to remove.")
            return

        item_to_remove = None
        for item in selected_items:
            if isinstance(item, LayoutRectItem):
                item_to_remove = item
                break
        
        if item_to_remove:
            layout_props = self.layout_definitions[self._currently_editing_layout_name]
            # Remove from data model
            layout_props["text_boxes"] = [tb for tb in layout_props.get("text_boxes", []) if tb.get("id") != item_to_remove.tb_id]
            # Remove from scene
            self.layout_preview_scene.removeItem(item_to_remove)
            print(f"DEBUG: Removed text box '{item_to_remove.tb_id}' from layout '{self._currently_editing_layout_name}'")
            # self.on_layout_selected(self._currently_editing_layout_name) # Optionally refresh everything, or just update button state
            self._update_layout_buttons_state() # Update button state after removal

    def _clear_layout_preview(self):
        self.layout_preview_scene.clear()
        # Optionally set a placeholder background or text
        self.layout_preview_scene.setBackgroundBrush(QBrush(Qt.GlobalColor.darkGray))
        # placeholder_text = self.layout_preview_scene.addText("No layout selected or defined.")
        # placeholder_text.setDefaultTextColor(Qt.GlobalColor.lightGray)
        self.layout_preview_graphics_view.fitInView(self.layout_preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._update_textbox_properties_panel() # Clear/disable panel
        self.layout_preview_graphics_view.resetTransform() # Reset zoom/pan

    def _update_layout_buttons_state(self):
        can_remove = self.layout_selector_combo.count() > 1 and self._currently_editing_layout_name is not None
        self.remove_layout_button.setEnabled(can_remove)
        
        layout_selected = self._currently_editing_layout_name is not None
        self.add_textbox_to_layout_button.setEnabled(layout_selected)

        can_remove_textbox = False
        if layout_selected and self.layout_preview_scene.selectedItems():
            can_remove_textbox = any(isinstance(item, LayoutRectItem) for item in self.layout_preview_scene.selectedItems())
        self.remove_selected_textbox_button.setEnabled(can_remove_textbox)
        self._update_textbox_properties_panel() # Also update properties panel based on selection

    @Slot(str, float, float, float, float)
    def _handle_layout_item_geometry_changed(self, item_id: str, new_x_pc: float, new_y_pc: float, new_w_pc: float, new_h_pc: float):
        if not self._currently_editing_layout_name or self._currently_editing_layout_name not in self.layout_definitions:
            return

        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        updated = False
        for tb_props in layout_props.get("text_boxes", []):
            if tb_props.get("id") == item_id:
                tb_props["x_pc"] = round(new_x_pc, 2) # Store with some precision
                tb_props["y_pc"] = round(new_y_pc, 2)
                # For now, width and height are not changed by this signal (only position)
                # tb_props["width_pc"] = round(new_w_pc, 2)
                # tb_props["height_pc"] = round(new_h_pc, 2)
                tb_props["width_pc"] = round(new_w_pc, 2) # Now update width/height
                tb_props["height_pc"] = round(new_h_pc, 2)
                updated = True
                break
        
        if updated:
            print(f"DEBUG: Layout item '{item_id}' in '{self._currently_editing_layout_name}' updated to X:{new_x_pc:.2f}%, Y:{new_y_pc:.2f}%")
            # No need to call self.on_layout_selected, as the item itself has moved.
            # However, if the ID changed, we might need to update the properties panel if it was based on the old ID.
            # For now, assume ID doesn't change via geometry signal.

    def _get_selected_layout_rect_item(self) -> Optional[LayoutRectItem]:
        """Helper to get the currently selected LayoutRectItem, if any."""
        selected_items = self.layout_preview_scene.selectedItems()
        for item in selected_items:
            if isinstance(item, LayoutRectItem):
                return item
        return None

    def _update_textbox_properties_panel(self):
        """Updates the 'Selected Text Box Properties' panel based on the current selection."""
        selected_item = self._get_selected_layout_rect_item()

        if selected_item and self._currently_editing_layout_name:
            self.textbox_properties_group.setEnabled(True)
            
            # Block signals while populating to avoid feedback loops
            self.selected_textbox_id_edit.blockSignals(True)
            self.selected_textbox_style_combo.blockSignals(True)
            self.selected_textbox_valign_combo.blockSignals(True) # New
            self.selected_textbox_halign_combo.blockSignals(True) # New

            self.selected_textbox_id_edit.setText(selected_item.tb_id)
            
            # Populate style combo
            self.selected_textbox_style_combo.clear()
            self.selected_textbox_style_combo.addItems(["None"] + list(self.style_definitions.keys()))

            # Populate h_align combo
            self.selected_textbox_halign_combo.clear()
            self.selected_textbox_halign_combo.addItems(["left", "center", "right"])

            # Populate v_align combo
            self.selected_textbox_valign_combo.clear()
            self.selected_textbox_valign_combo.addItems(["top", "center", "bottom"])
            
            # Find the style assigned to this text box in the layout definition
            layout_props = self.layout_definitions[self._currently_editing_layout_name]
            assigned_style_name = None
            assigned_h_align = "left" # Default if not found
            assigned_v_align = "top"  # Default if not found
            for tb_def in layout_props.get("text_boxes", []):
                if tb_def.get("id") == selected_item.tb_id:
                    assigned_style_name = tb_def.get("style_name") # Assuming "style_name" key
                    assigned_v_align = tb_def.get("v_align", "top")
                    assigned_h_align = tb_def.get("h_align", "left")
                    break
            
            if assigned_style_name and assigned_style_name in self.style_definitions:
                self.selected_textbox_style_combo.setCurrentText(assigned_style_name)
            else:
                self.selected_textbox_style_combo.setCurrentText("None")

            self.selected_textbox_halign_combo.setCurrentText(assigned_h_align) # New
            self.selected_textbox_valign_combo.setCurrentText(assigned_v_align) # New

            self.selected_textbox_id_edit.blockSignals(False)
            self.selected_textbox_style_combo.blockSignals(False)
            self.selected_textbox_valign_combo.blockSignals(False) # New
            self.selected_textbox_halign_combo.blockSignals(False) # New
        else:
            self.textbox_properties_group.setEnabled(False)
            self.selected_textbox_id_edit.blockSignals(True)
            self.selected_textbox_style_combo.blockSignals(True)
            self.selected_textbox_valign_combo.blockSignals(True) # New
            self.selected_textbox_halign_combo.blockSignals(True) # New
            self.selected_textbox_id_edit.clear()
            self.selected_textbox_style_combo.clear()
            self.selected_textbox_valign_combo.clear() # New
            self.selected_textbox_halign_combo.clear() # New
            self.selected_textbox_id_edit.blockSignals(False)
            self.selected_textbox_style_combo.blockSignals(False)
            self.selected_textbox_valign_combo.blockSignals(False) # New
            self.selected_textbox_halign_combo.blockSignals(False) # New

    @Slot()
    def _handle_selected_textbox_id_changed(self):
        selected_item = self._get_selected_layout_rect_item()
        if not selected_item or not self._currently_editing_layout_name:
            return
        
        new_id = self.selected_textbox_id_edit.text().strip()
        old_id = selected_item.tb_id

        if not new_id:
            QMessageBox.warning(self, "Invalid ID", "Text box ID cannot be empty.")
            self.selected_textbox_id_edit.setText(old_id) # Revert
            return
        
        # Check for ID uniqueness within the current layout definition
        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        for tb_props in layout_props.get("text_boxes", []):
            if tb_props.get("id") == new_id and tb_props.get("id") != old_id:
                QMessageBox.warning(self, "Duplicate ID", f"A text box with ID '{new_id}' already exists in this layout.")
                self.selected_textbox_id_edit.setText(old_id) # Revert
                return

        # Update the ID in self.layout_definitions
        for tb_props in layout_props.get("text_boxes", []):
            if tb_props.get("id") == old_id:
                tb_props["id"] = new_id
                selected_item.tb_id = new_id  # Update the ID on the LayoutRectItem
                selected_item._update_text_item_appearance() # Refresh text display
                print(f"DEBUG: Text box ID changed from '{old_id}' to '{new_id}'. Data model and item updated.")
                return

    @Slot(str)
    def _handle_selected_textbox_style_changed(self, style_name_from_combo: str):
        selected_item = self._get_selected_layout_rect_item()
        if not selected_item or not self._currently_editing_layout_name:
            return
        
        # Determine the actual style name to store (None if "None" is selected)
        style_name_to_store = style_name_from_combo if style_name_from_combo != "None" else None

        # Find the style definition properties to apply to the Styles tab preview
        style_props_to_preview = None
        if style_name_to_store and style_name_to_store in self.style_definitions:
            style_props_to_preview = self.style_definitions[style_name_to_store]

        # Update the preview area in the *Styles tab* (optional, but can be useful)
        # self._apply_style_to_preview_area(style_props_to_preview) # Pass the specific style props
        # For now, let's not automatically switch the Styles tab preview, to keep focus.
        # The user can navigate to the Styles tab if they want to see full details.
            
        # Update the style_name for this text box ID in self.layout_definitions
        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        for tb_def in layout_props.get("text_boxes", []):
            if tb_def.get("id") == selected_item.tb_id:
                # Store None if "None" is selected in the combo box
                tb_def["style_name"] = style_name_to_store
                print(f"DEBUG: Text box '{selected_item.tb_id}' style changed to '{style_name_to_store}'. Data model updated.")
                # Now, update the LayoutRectItem's appearance
                selected_item.assign_style(style_name_to_store)
                return

    @Slot(str)
    def _handle_selected_textbox_halign_changed(self, h_align_value: str):
        selected_item = self._get_selected_layout_rect_item()
        if not selected_item or not self._currently_editing_layout_name or not h_align_value:
            return

        # Update h_align for this text box ID in self.layout_definitions
        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        for tb_def in layout_props.get("text_boxes", []):
            if tb_def.get("id") == selected_item.tb_id:
                tb_def["h_align"] = h_align_value
                print(f"DEBUG: Text box '{selected_item.tb_id}' h_align changed to '{h_align_value}'. Data model updated.")
                # Now, update the LayoutRectItem's appearance
                selected_item.assign_horizontal_alignment(h_align_value)
                return

    @Slot(str)
    def _handle_selected_textbox_valign_changed(self, v_align_value: str):
        selected_item = self._get_selected_layout_rect_item()
        if not selected_item or not self._currently_editing_layout_name or not v_align_value:
            return

        # Update v_align for this text box ID in self.layout_definitions
        layout_props = self.layout_definitions[self._currently_editing_layout_name]
        for tb_def in layout_props.get("text_boxes", []):
            if tb_def.get("id") == selected_item.tb_id:
                tb_def["v_align"] = v_align_value
                print(f"DEBUG: Text box '{selected_item.tb_id}' v_align changed to '{v_align_value}'. Data model updated.")
                # Now, update the LayoutRectItem's appearance
                selected_item.assign_vertical_alignment(v_align_value)
                return


    # --- Style Tab Methods ---
    def _populate_style_selector(self):
        self.style_selector_combo.blockSignals(True)
        self.style_selector_combo.clear()
        self.style_selector_combo.addItems(self.style_definitions.keys())
        self.style_selector_combo.blockSignals(False)

    @Slot()
    def add_new_style_definition(self):
        style_name, ok = QInputDialog.getText(self, "New Style", "Enter name for the new style:")
        if ok and style_name:
            style_name = style_name.strip()
            if not style_name:
                QMessageBox.warning(self, "Invalid Name", "Style name cannot be empty.")
                return
            if style_name in self.style_definitions:
                QMessageBox.warning(self, "Name Exists", f"A style named '{style_name}' already exists.")
                return

            new_style_props = {
                "font_family": self.font_family_combo.font().family(),
                "font_size": self.font_size_spinbox.value(),
                "font_color": QColor(Qt.GlobalColor.black).name(), # Default to black
                "preview_text": "New Style Text",
                "force_all_caps": False,
                "text_shadow": False,
                "text_outline": False,
                "shadow_x": 1, "shadow_y": 1, "shadow_blur": 2, "shadow_color": QColor(0,0,0,180).name(QColor.NameFormat.HexArgb),
                "outline_thickness": 1, "outline_color": QColor(Qt.GlobalColor.black).name(),

            }
            self.style_definitions[style_name] = new_style_props
            self._populate_style_selector()
            self.style_selector_combo.setCurrentText(style_name) # Triggers on_style_selected
        elif ok and not style_name.strip():
            QMessageBox.warning(self, "Invalid Name", "Style name cannot be empty.")

    @Slot()
    def remove_selected_style_definition(self):
        if not self._currently_editing_style_name:
            return
        if len(self.style_definitions) <= 1: # Prevent deleting the last style
            QMessageBox.warning(self, "Cannot Remove", "Cannot remove the last style definition.")
            return

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Are you sure you want to remove the style '{self._currently_editing_style_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.style_definitions[self._currently_editing_style_name]
            self._currently_editing_style_name = None
            self._populate_style_selector()
            if self.style_selector_combo.count() > 0:
                self.style_selector_combo.setCurrentIndex(0)
            else: # Should not happen due to the "last style" check
                self._clear_style_controls()

    @Slot(str)
    def on_style_selected(self, style_name: str):
        print(f"DEBUG: on_style_selected called with style_name: '{style_name}'") # DEBUG
        if not style_name or style_name not in self.style_definitions:
            self._clear_style_controls()
            self._currently_editing_style_name = None
            print(f"DEBUG: on_style_selected - style_name invalid or not found. _currently_editing_style_name set to None.") # DEBUG
            return

        self._currently_editing_style_name = style_name # This sets it
        style_props = self.style_definitions[style_name]

        # Block signals while setting UI to prevent feedback loops
        self.preview_text_input_edit.blockSignals(True)
        self.font_family_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)
        self.force_caps_checkbox.blockSignals(True)
        self.text_shadow_checkbox.blockSignals(True)
        self.text_outline_checkbox.blockSignals(True)
        self.shadow_x_spinbox.blockSignals(True)
        self.shadow_y_spinbox.blockSignals(True)
        self.shadow_blur_spinbox.blockSignals(True)
        self.shadow_color_button.blockSignals(True) # Not strictly necessary but good practice
        self.outline_thickness_spinbox.blockSignals(True)
        self.outline_color_button.blockSignals(True) # Not strictly necessary

        self.preview_text_input_edit.setText(style_props.get("preview_text", "Sample Text"))
        self.font_family_combo.setCurrentFont(QFont(style_props.get("font_family", "Arial")))
        self.font_size_spinbox.setValue(style_props.get("font_size", 12))
        
        self._current_style_font_color = QColor(style_props.get("font_color", "#000000"))
        self._update_font_color_preview_label()
        
        self.force_caps_checkbox.setChecked(style_props.get("force_all_caps", False))
        self.text_shadow_checkbox.setChecked(style_props.get("text_shadow", False))
        self.text_outline_checkbox.setChecked(style_props.get("text_outline", False))
        
        self.shadow_x_spinbox.setValue(style_props.get("shadow_x", 1))
        self.shadow_y_spinbox.setValue(style_props.get("shadow_y", 1))
        self.shadow_blur_spinbox.setValue(style_props.get("shadow_blur", 2))
        self._current_shadow_color = QColor(style_props.get("shadow_color", QColor(0,0,0,180).name(QColor.NameFormat.HexArgb)))
        self._update_shadow_color_preview_label()
        
        self.outline_thickness_spinbox.setValue(style_props.get("outline_thickness", 1))
        self._current_outline_color = QColor(style_props.get("outline_color", QColor(Qt.GlobalColor.black).name()))
        self._update_outline_color_preview_label()

        self.preview_text_input_edit.blockSignals(False)
        self.font_family_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.force_caps_checkbox.blockSignals(False)
        self.text_shadow_checkbox.blockSignals(False)
        self.text_outline_checkbox.blockSignals(False)
        self.shadow_x_spinbox.blockSignals(False)
        self.shadow_y_spinbox.blockSignals(False)
        self.shadow_blur_spinbox.blockSignals(False)
        self.shadow_color_button.blockSignals(False) # Unblock shadow color button
        self.outline_thickness_spinbox.blockSignals(False)
        self.outline_color_button.blockSignals(False) # Unblock outline color button

        print(f"DEBUG: on_style_selected - _currently_editing_style_name is now: '{self._currently_editing_style_name}'") # DEBUG
        self._apply_style_to_preview_area()
        self._update_style_remove_button_state()
        self._toggle_shadow_detail_group() # Update enabled state of shadow group
        self._toggle_outline_detail_group() # Update enabled state of outline group

    @Slot(str)
    def update_style_from_preview_text_input(self, text: str): # This is for the Styles Tab preview text
        print(f"DEBUG: update_style_from_preview_text_input called with text: '{text}'") # DEBUG
        print(f"DEBUG: At start of update_style_from_preview_text_input, _currently_editing_style_name is: '{self._currently_editing_style_name}'") # DEBUG
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            # This method updates the "preview_text" property of a style definition,
            # which is then used by _apply_style_to_preview_area for the Styles tab.
            # It does not directly affect LayoutRectItem's display text, which uses its tb_id.
            print(f"DEBUG: Condition PASSED. Updating preview for '{self._currently_editing_style_name}'.") # DEBUG
            self.style_definitions[self._currently_editing_style_name]["preview_text"] = text
            self._apply_style_to_preview_area() # Update the preview label's text
            print(f"DEBUG: Updated style_definitions for '{self._currently_editing_style_name}', preview_text is now: '{self.style_definitions[self._currently_editing_style_name]['preview_text']}'") # DEBUG
        else: # DEBUG
            print(f"DEBUG: Condition FAILED. _currently_editing_style_name: '{self._currently_editing_style_name}', in definitions: {self._currently_editing_style_name in self.style_definitions if self._currently_editing_style_name else 'N/A'}") # DEBUG

    @Slot()
    def update_style_from_font_controls(self):
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            style_props = self.style_definitions[self._currently_editing_style_name]
            style_props["font_family"] = self.font_family_combo.currentFont().family()
            style_props["font_size"] = self.font_size_spinbox.value()
            # Color is handled by choose_style_font_color
            self._apply_style_to_preview_area()
            
    @Slot()
    def update_style_from_formatting_controls(self):
        if self._currently_editing_style_name and self._currently_editing_style_name in self.style_definitions:
            style_props = self.style_definitions[self._currently_editing_style_name]
            style_props["force_all_caps"] = self.force_caps_checkbox.isChecked()
            style_props["text_shadow"] = self.text_shadow_checkbox.isChecked()
            style_props["text_outline"] = self.text_outline_checkbox.isChecked()
            
            style_props["shadow_x"] = self.shadow_x_spinbox.value()
            style_props["shadow_y"] = self.shadow_y_spinbox.value()
            style_props["shadow_blur"] = self.shadow_blur_spinbox.value()
            # Shadow color is updated by its own picker
            style_props["outline_thickness"] = self.outline_thickness_spinbox.value()
            # Outline color is updated by its own picker
            self._apply_style_to_preview_area()
            self._toggle_shadow_detail_group() # Enable/disable based on checkbox
            print(f"DEBUG: Shadow group enabled: {self.shadow_properties_group.isEnabled()}, shadow_color_button enabled: {self.shadow_color_button.isEnabled()}") # DEBUG
            self._toggle_outline_detail_group() # Enable/disable based on checkbox
            print(f"DEBUG: Outline group enabled: {self.outline_properties_group.isEnabled()}, outline_color_button enabled: {self.outline_color_button.isEnabled()}") # DEBUG


    def load_template_settings(self):
        # TODO: This method needs a complete rewrite.
        # It will involve populating the controls within the active tab of self.ui.main_tab_widget
        # based on the selected Layout, Style, or Master Template.
        print(f"Template Editor: load_template_settings() called - needs rewrite for new UI.")

    @Slot()
    def choose_style_font_color(self):
        if not self._currently_editing_style_name: return

        initial_color = self._current_style_font_color
        color = QColorDialog.getColor(initial_color, self, "Choose Font Color")
        if color.isValid():
            self._current_style_font_color = color
            self.style_definitions[self._currently_editing_style_name]["font_color"] = color.name() # Store as hex
            self._update_font_color_preview_label()
            self._apply_style_to_preview_area()

    @Slot()
    def choose_shadow_color(self):
        if not self._currently_editing_style_name: return
        initial_color = self._current_shadow_color
        # Allow choosing alpha for shadow color
        color = QColorDialog.getColor(initial_color, self, "Choose Shadow Color", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self._current_shadow_color = color
            self.style_definitions[self._currently_editing_style_name]["shadow_color"] = color.name(QColor.NameFormat.HexArgb)
            self._update_shadow_color_preview_label()
            self._apply_style_to_preview_area()
            
    @Slot()
    def choose_outline_color(self):
        if not self._currently_editing_style_name: return
        initial_color = self._current_outline_color
        color = QColorDialog.getColor(initial_color, self, "Choose Outline Color") # No alpha for basic outline usually
        if color.isValid():
            self._current_outline_color = color
            self.style_definitions[self._currently_editing_style_name]["outline_color"] = color.name()
            self._update_outline_color_preview_label()
            self._apply_style_to_preview_area()

    def _update_font_color_preview_label(self):
        palette = self.font_color_preview_label.palette()
        palette.setColor(QPalette.ColorRole.Window, self._current_style_font_color) # QPalette.Window is background for QLabel
        self.font_color_preview_label.setPalette(palette)
        # Ensure the label updates its display if its background is transparent by default
        self.font_color_preview_label.setAutoFillBackground(True) 
        self.font_color_preview_label.update()

    def _update_shadow_color_preview_label(self):
        self.shadow_color_preview_label.setStyleSheet(f"background-color: {self._current_shadow_color.name(QColor.NameFormat.HexArgb)};")

    def _update_outline_color_preview_label(self):
        self.outline_color_preview_label.setStyleSheet(f"background-color: {self._current_outline_color.name()};")

    def _apply_style_to_preview_area(self, style_props_override: Optional[dict] = None):
        # This method is for the PREVIEW AREA IN THE STYLES TAB.
        # It uses OutlinedGraphicsTextItem for a detailed preview.
        # If style_props_override is provided, it uses those instead of _currently_editing_style_name.
        print(f"DEBUG: _apply_style_to_preview_area called. Current style: '{self._currently_editing_style_name}'") # DEBUG
        if not self._currently_editing_style_name or self._currently_editing_style_name not in self.style_definitions:
            default_font = QFont()
            self.style_preview_text_item.setFont(default_font)
            self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black))
            self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # No outline
            self.style_preview_text_item.setPlainText("Select a style to preview.")
            self.style_preview_text_item.setGraphicsEffect(None) # Remove effects
            self.style_preview_text_item.setPlainText("Select a style to preview.") # Set text after other properties
            self.style_preview_scene.update()
            return # Exit the method if no style is selected
        print(f"DEBUG: Applying style for '{self._currently_editing_style_name}'") # DEBUG

        if style_props_override:
            style_props = style_props_override
        else:
            style_props = self.style_definitions.get(self._currently_editing_style_name)

        if not style_props: # Should not happen if _currently_editing_style_name is valid, but good check
            print(f"DEBUG: _apply_style_to_preview_area - Could not find style_props for '{self._currently_editing_style_name}'")
            return

        font_family = style_props.get("font_family", "Arial")
        font_size = style_props.get("font_size", 12)
        font_color_hex = style_props.get("font_color", "#000000")
        force_caps = style_props.get("force_all_caps", False)
        has_shadow = style_props.get("text_shadow", False)
        has_outline = style_props.get("text_outline", False)
        
        shadow_x = style_props.get("shadow_x", 1)
        shadow_y = style_props.get("shadow_y", 1)
        shadow_blur = style_props.get("shadow_blur", 2)
        shadow_color_hexargb = style_props.get("shadow_color", QColor(0,0,0,180).name(QColor.NameFormat.HexArgb))
        outline_thickness = style_props.get("outline_thickness", 1)
        outline_color_hex = style_props.get("outline_color", "#000000")
        preview_text = style_props.get("preview_text", "Sample Text")

        # ---- ADDING MORE DEBUG PRINTS HERE ----
        print(f"DEBUG: _apply_style_to_preview_area - has_shadow: {has_shadow}, has_outline: {has_outline}")
        print(f"DEBUG: _apply_style_to_preview_area - shadow_color: {shadow_color_hexargb}, shadow_x: {shadow_x}, shadow_y: {shadow_y}, shadow_blur: {shadow_blur}")
        print(f"DEBUG: _apply_style_to_preview_area - font_family: {font_family}, font_size: {font_size}, font_color_hex: {font_color_hex}")
        print(f"DEBUG: _apply_style_to_preview_area - preview_text (before caps): '{preview_text}'")
        print(f"DEBUG: _apply_style_to_preview_area - outline_color: {outline_color_hex}, outline_thickness: {outline_thickness}")
        if force_caps:
            preview_text = preview_text.upper()

        # Apply to OutlinedGraphicsTextItem
        current_font = QFont(font_family, font_size)
        self.style_preview_text_item.setFont(current_font)
        print(f"  DEBUG: Called item.setFont({font_family}, {font_size})")
        self.style_preview_text_item.setTextFillColor(QColor(font_color_hex))
        self.style_preview_text_item.setPlainText(preview_text)

        # --- Outline ---
        # This needs to be applied after font and color, or ensure _apply_format_to_document
        # correctly re-applies everything. Our OutlinedGraphicsTextItem is designed to do so.
        if has_outline:
            outline_qcolor = QColor(outline_color_hex)
            actual_thickness = max(1, outline_thickness) # Ensure thickness is at least 1 if outline is enabled
            self.style_preview_text_item.setOutline(outline_qcolor, actual_thickness)
            print(f"  DEBUG: Called item.setOutline(Color {outline_color_hex}, Thickness {actual_thickness})")
        else:
            # Remove outline by setting thickness to 0
            self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # Color doesn't matter if pen is NoPen4
            print("  DEBUG: Called item.setOutline(Transparent, 0) to remove outline")
        
        # Explicitly update the item after all formatting calls, before shadow effect
        self.style_preview_text_item.update() # Try explicit update of the item

        # --- Shadow Effect ---
        current_effect = self.style_preview_text_item.graphicsEffect()
        if has_shadow:
            if not isinstance(current_effect, QGraphicsDropShadowEffect):
                shadow_effect = QGraphicsDropShadowEffect(self)
                self.style_preview_text_item.setGraphicsEffect(shadow_effect)
            else:
                shadow_effect = current_effect
            
            shadow_effect.setXOffset(shadow_x)
            shadow_effect.setYOffset(shadow_y)
            shadow_effect.setBlurRadius(shadow_blur * 2) # QGraphicsDropShadowEffect blur is different from CSS
            shadow_effect.setColor(QColor(shadow_color_hexargb))
            print(f"DEBUG: Applied QGraphicsDropShadowEffect: X:{shadow_x}, Y:{shadow_y}, Blur:{shadow_blur*2}, Color:{shadow_color_hexargb}")
        else:
            if isinstance(current_effect, QGraphicsDropShadowEffect): # Remove only if it's our shadow
                self.style_preview_text_item.setGraphicsEffect(None)
                print("DEBUG: Removed QGraphicsDropShadowEffect")

        # Adjust view / item position if necessary
        # For simplicity, let's ensure the item is at the top-left of the scene.
        # And then fit the view to the item.
        self.style_preview_text_item.setPos(0, 0) 

        # Set text width for wrapping (important for QGraphicsTextItem)
        # Use the view's width as a basis, minus some padding
        available_width = self.style_preview_graphics_view.viewport().width() - 20 # 10px padding each side
        print(f"DEBUG: _apply_style_to_preview_area - Viewport width: {self.style_preview_graphics_view.viewport().width()}, available_width for text: {available_width}") # DEBUG
        print(f"DEBUG: _apply_style_to_preview_area - TextItem boundingRect BEFORE setTextWidth: {self.style_preview_text_item.boundingRect()}") # DEBUG

        if available_width > 0 :
            self.style_preview_text_item.setTextWidth(available_width)
        else:
            self.style_preview_text_item.setTextWidth(-1) # No wrapping if view not sized yet

        self.style_preview_scene.update() # Ensure scene redraws
        # It's good to allow the scene to process updates which might affect bounding rect after setTextWidth
        print(f"DEBUG: _apply_style_to_preview_area - TextItem boundingRect AFTER setTextWidth: {self.style_preview_text_item.boundingRect()}") # DEBUG
        self.style_preview_graphics_view.fitInView(self.style_preview_text_item, Qt.AspectRatioMode.KeepAspectRatio)
        print(f"  DEBUG: _apply_style_to_preview_area FINISHED for '{self._currently_editing_style_name}'")

    @Slot()
    def add_new_template(self):
        # TODO: This is for adding old-style templates.
        # You'll need separate logic for adding Layouts, Styles, and Master Templates
        # triggered by buttons within their respective tabs.
        new_template_name, ok = QInputDialog.getText(self, "New Template", "Enter name for the new template:")
        if ok and new_template_name:
            new_template_name = new_template_name.strip()
            # This method is now largely deprecated in favor of add_new_style_definition, etc.
            # For now, just print a message.
            print(f"Template Editor: add_new_template called with '{new_template_name}' - this is for old system.")

        elif ok and not new_template_name.strip():
             QMessageBox.warning(self, "Invalid Name", "Template name cannot be empty.")

    @Slot()
    def remove_selected_template(self):
        # TODO: This is for removing old-style templates.
        # Needs to be adapted for Layouts, Styles, Master Templates.
        print(f"Template Editor: remove_selected_template called - this is for old system.")

    def _clear_style_controls(self):
        self.preview_text_input_edit.blockSignals(True)
        self.font_family_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)
        self.force_caps_checkbox.blockSignals(True)
        self.text_shadow_checkbox.blockSignals(True)
        self.text_outline_checkbox.blockSignals(True)
        self.shadow_x_spinbox.blockSignals(True)
        self.shadow_y_spinbox.blockSignals(True)
        self.shadow_blur_spinbox.blockSignals(True)
        self.shadow_color_button.blockSignals(True)
        self.outline_thickness_spinbox.blockSignals(True)
        self.outline_color_button.blockSignals(True)

        self.preview_text_input_edit.clear()
        self.font_family_combo.setCurrentIndex(-1) # Or set to a default font
        self.font_size_spinbox.setValue(self.font_size_spinbox.minimum()) # Or a default size
        
        self._current_style_font_color = QColor(Qt.GlobalColor.black)
        self._update_font_color_preview_label()
        
        self.style_preview_text_item.setFont(QFont()) # Reset font
        self.style_preview_text_item.setTextFillColor(QColor(Qt.GlobalColor.black)) # Reset fill
        self.style_preview_text_item.setOutline(QColor(Qt.GlobalColor.transparent), 0) # Reset outline
        self.style_preview_text_item.setPlainText("No style selected or defined.") # Set text last
        
        self.force_caps_checkbox.setChecked(False)
        self.text_shadow_checkbox.setChecked(False)
        self.text_outline_checkbox.setChecked(False)
        
        self.shadow_x_spinbox.setValue(1)
        self.shadow_y_spinbox.setValue(1)
        self.shadow_blur_spinbox.setValue(2)
        self._current_shadow_color = QColor(0,0,0,180)
        self._update_shadow_color_preview_label()
        
        self.outline_thickness_spinbox.setValue(1)
        self._current_outline_color = QColor(Qt.GlobalColor.black)
        self._update_outline_color_preview_label()
        
        # Remove any graphics effects
        self.style_preview_text_item.setGraphicsEffect(None)
        self.style_preview_scene.update()

        self.preview_text_input_edit.blockSignals(False)
        self.font_family_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)
        self.force_caps_checkbox.blockSignals(False)
        self.text_shadow_checkbox.blockSignals(False)
        self.text_outline_checkbox.blockSignals(False)
        self.shadow_x_spinbox.blockSignals(False)
        self.shadow_y_spinbox.blockSignals(False)
        self.shadow_blur_spinbox.blockSignals(False)
        self.outline_thickness_spinbox.blockSignals(False)
        self.shadow_color_button.blockSignals(False) # Ensure unblocked here too
        self.outline_color_button.blockSignals(False)# Ensure unblocked here too
        
        self._toggle_shadow_detail_group()
        self._toggle_outline_detail_group()

    @Slot()
    def _handle_save_action(self):
        """Handles the action when the 'Save' button is clicked."""
        current_template_data = self.get_updated_templates()
        self.templates_save_requested.emit(current_template_data)
        print("Template Editor: 'Save' button clicked. templates_save_requested signal emitted.")
        # self._toggle_outline_detail_group() # This call seems out of place here

    def _update_style_remove_button_state(self):
        can_remove = self.style_selector_combo.count() > 1 and self._currently_editing_style_name is not None
        self.remove_style_button.setEnabled(can_remove)

    def get_updated_templates(self): # Renamed method
        """
        Gathers the current state of styles, layouts, and master templates
        from the editor's internal data structures.
        """
        print(f"Template Editor: get_updated_templates() called. Packaging styles, layouts, master_templates.")
        return {
            "styles": copy.deepcopy(self.style_definitions),
            "layouts": copy.deepcopy(self.layout_definitions), # Will be populated when Layouts tab is built
            # "master_templates": copy.deepcopy(self.master_template_definitions) # Removed
        }

    def _update_remove_button_state(self):
        """Enable/disable the remove button based on the selected template."""
        # TODO: This is for the old remove button.
        # Each tab (Layouts, Styles, Master Templates) will need its own logic
        # for enabling/disabling its respective remove button.
        # This method is now superseded by _update_style_remove_button_state for the styles tab.
        print(f"Template Editor: _update_remove_button_state() called - largely deprecated.")
        self._update_style_remove_button_state() # Call the new specific one for styles

    def _toggle_shadow_detail_group(self):
        is_enabled = self.text_shadow_checkbox.isChecked()
        self.shadow_properties_group.setEnabled(is_enabled)

    def _toggle_outline_detail_group(self):
        is_enabled = self.text_outline_checkbox.isChecked()
        self.outline_properties_group.setEnabled(is_enabled)
