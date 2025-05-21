import os
from PySide6.QtCore import QObject, QPoint, Qt, QRect, QByteArray
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from typing import Optional, TYPE_CHECKING

from data_models.slide_data import SlideData
from widgets.flow_layout import FlowLayout # Assuming FlowLayout is in widgets
from widgets.song_header_widget import SongHeaderWidget # Assuming SongHeaderWidget is in widgets
from widgets.scaled_slide_button import ScaledSlideButton

# Import constants from the new constants file
from .constants import PLUCKY_SLIDE_MIME_TYPE, BASE_PREVIEW_HEIGHT

if TYPE_CHECKING:
    from windows.main_window import MainWindow # For type hinting
    from core.presentation_manager import PresentationManager


class SlideDragDropHandler(QObject):
    def __init__(self, main_window: 'MainWindow', presentation_manager: 'PresentationManager',
                 scroll_area: QScrollArea, slide_buttons_widget: QWidget,
                 slide_buttons_layout: QVBoxLayout, drop_indicator: QFrame, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.main_window = main_window # For mapToGlobal, etc.
        self.presentation_manager = presentation_manager
        self.scroll_area = scroll_area
        self.slide_buttons_widget = slide_buttons_widget # The content widget of scroll_area
        self.slide_buttons_layout = slide_buttons_layout # The QVBoxLayout within slide_buttons_widget
        self.drop_indicator = drop_indicator

        self._potential_drop_index: int = 0
        self._current_drop_target_song_title: Optional[str] = None
        self._dragged_slide_source_index: int = -1 # For slide reordering


    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasFormat(PLUCKY_SLIDE_MIME_TYPE):
            try:
                self._dragged_slide_source_index = int(mime_data.data(PLUCKY_SLIDE_MIME_TYPE).data().decode('utf-8'))
                event.acceptProposedAction()
                # print(f"SlideDragDropHandler: dragEnter accepted for slide reorder, source index: {self._dragged_slide_source_index}") # DEBUG
            except ValueError:
                self._dragged_slide_source_index = -1
                event.ignore()
        elif mime_data.hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        event.acceptProposedAction()
                        # print("SlideDragDropHandler: dragEnter accepted for image drop") # DEBUG
                        return
            event.ignore()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event: QDragMoveEvent):
        mime_data = event.mimeData()
        if mime_data.hasFormat(PLUCKY_SLIDE_MIME_TYPE):
            if self._dragged_slide_source_index != -1:
                self._update_drop_indicator_position(event.position().toPoint(), is_slide_reorder=True)
                event.acceptProposedAction()
            else: # Should have been caught in dragEnter, but as a safeguard
                self.drop_indicator.hide()
                event.ignore()
        elif mime_data.hasUrls():
            is_image_file = False
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    is_image_file = True
                    break
            
            if is_image_file:
                self._update_drop_indicator_position(event.position().toPoint(), is_slide_reorder=False)
                event.acceptProposedAction()
                return
            else: # Has URLs but not image files we handle
                    self.drop_indicator.hide()
                    event.ignore()
        else:
            self.drop_indicator.hide()
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.drop_indicator.hide()
        self._dragged_slide_source_index = -1 # Reset
        event.accept()

    def dropEvent(self, event: QDropEvent):
        new_bg_slides_data = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    bg_slide = SlideData(
                        lyrics="",
                        background_image_path=file_path,
                        background_color="#00000000",
                        is_background_slide=True,
                        song_title=self._current_drop_target_song_title,
                        overlay_label=os.path.basename(file_path),
                    )
                    new_bg_slides_data.append(bg_slide)
        
        if new_bg_slides_data:
            if hasattr(self.presentation_manager, 'insert_slides'):
                self.presentation_manager.insert_slides(new_bg_slides_data, self._potential_drop_index)
            else:
                print("Warning: PresentationManager does not have 'insert_slides'. Appending background slide(s).")
                self.presentation_manager.add_slides(new_bg_slides_data) # Fallback
            event.acceptProposedAction()
        else:
            # Check for slide reorder
            if event.mimeData().hasFormat(PLUCKY_SLIDE_MIME_TYPE) and self._dragged_slide_source_index != -1:
                # Recalculate target_drop_index based on the actual drop position
                # Map drop event position to the coordinate system of slide_buttons_widget
                # QDropEvent.position() is QPointF relative to the widget that received the event (MainWindow)
                global_drop_pos = self.main_window.mapToGlobal(event.position().toPoint())
                pos_in_sbg_widget = self.slide_buttons_widget.mapFromGlobal(global_drop_pos)
                
                # Use a method similar to _update_drop_indicator_position's logic to find the index
                # For simplicity, let's assume _calculate_target_drop_index exists and works.
                # You might need to adapt parts of _update_drop_indicator_position's logic here
                target_drop_index = self._calculate_logical_drop_index(pos_in_sbg_widget)
                source_slide_index = self._dragged_slide_source_index

                # print(f"SlideDragDropHandler: dropEvent - Reordering slide. Source: {source_slide_index}, Target: {target_drop_index}") # DEBUG

                # Adjust target index if source is before target and is removed first
                actual_target_index = target_drop_index
                if source_slide_index < target_drop_index:
                    actual_target_index -= 1
                
                if target_drop_index is not None: # Ensure a valid target was calculated
                    if hasattr(self.presentation_manager, 'move_slide'):
                        success = self.presentation_manager.move_slide(
                            source_slide_index,
                            actual_target_index,
                            self._current_drop_target_song_title  # Pass the stored song title
                        )
                        if success:
                            event.acceptProposedAction()
                            # You can add a more informative print statement here if you like:
                            # print(f"SlideDragDropHandler: Moved slide from {source_slide_index} to {actual_target_index} in section '{self._current_drop_target_song_title}'.")
                        else:
                            print(f"SlideDragDropHandler: move_slide from {source_slide_index} to {actual_target_index} failed.")
                            event.ignore()
                    else:
                        print("SlideDragDropHandler: PresentationManager has no 'move_slide' method.")
                        event.ignore()
                else:
                    print(f"SlideDragDropHandler: Could not calculate target_drop_index at drop event.")
                    event.ignore()
            else:
                event.ignore()
        self._current_drop_target_song_title = None
        self._dragged_slide_source_index = -1 # Reset
        self.drop_indicator.hide()

    def _get_song_title_for_flow_widget(self, flow_container_widget: QWidget) -> Optional[str]:
        vbox_layout = self.slide_buttons_layout
        for i in range(vbox_layout.count()):
            item = vbox_layout.itemAt(i)
            if item and item.widget() == flow_container_widget:
                if i > 0:
                    prev_widget_item = vbox_layout.itemAt(i - 1)
                    if prev_widget_item and isinstance(prev_widget_item.widget(), SongHeaderWidget):
                        return prev_widget_item.widget().get_song_title()
        return None

    def _calculate_logical_drop_index(self, pos_in_content_widget: QPoint) -> Optional[int]:
        """
        Calculates the logical overall slide index where a drop at 'pos_in_content_widget'
        (relative to slide_buttons_widget) should occur.
        This is a simplified version of the logic in _update_drop_indicator_position,
        focused only on determining the numerical index.
        """
        target_flow_layout_widget: Optional[QWidget] = None
        for i in range(self.slide_buttons_layout.count()):
            item = self.slide_buttons_layout.itemAt(i)
            if not item or not item.widget(): continue
            widget_in_vbox = item.widget()
            if isinstance(widget_in_vbox.layout(), FlowLayout):
                if widget_in_vbox.geometry().contains(pos_in_content_widget):
                    target_flow_layout_widget = widget_in_vbox
                    # Don't break, find most specific

        if not target_flow_layout_widget:
            # Not over a flow, determine if it's before a song header or at the end
            current_idx_count = 0
            for i in range(self.slide_buttons_layout.count()):
                item = self.slide_buttons_layout.itemAt(i)
                if not item or not item.widget(): continue
                widget_in_vbox = item.widget()
                if pos_in_content_widget.y() < widget_in_vbox.geometry().bottom():
                    return current_idx_count # Drop before this item/song
                if isinstance(widget_in_vbox.layout(), FlowLayout):
                    current_idx_count += widget_in_vbox.layout().count()
            return len(self.presentation_manager.get_slides()) # Append to very end

        # Over a specific flow layout
        flow_layout = target_flow_layout_widget.layout()
        pos_in_flow_widget = target_flow_layout_widget.mapFromParent(pos_in_content_widget)
        
        calculated_insertion_index_in_flow = flow_layout.count() # Default to end
        for i in range(flow_layout.count()):
            item_widget = flow_layout.itemAt(i).widget()
            if item_widget and isinstance(item_widget, ScaledSlideButton):
                if pos_in_flow_widget.y() < item_widget.geometry().bottom(): # On the same visual row or above
                    if pos_in_flow_widget.x() < item_widget.geometry().center().x():
                        calculated_insertion_index_in_flow = i
                        break
                    else:
                        calculated_insertion_index_in_flow = i + 1
        
        return self._get_base_index_for_flow(target_flow_layout_widget) + calculated_insertion_index_in_flow

    def _update_drop_indicator_position(self, main_window_pos: QPoint, is_slide_reorder: bool):
        """
        Updates the position and visibility of the drop indicator.
        'main_window_pos' is the mouse position relative to MainWindow.
        'is_slide_reorder' is True if a slide is being reordered, False for image drop.
        """
        global_mouse_pos = self.main_window.mapToGlobal(main_window_pos)
        indicator_rect = QRect() # Initialize indicator_rect at the beginning
        y_in_viewport = self.scroll_area.viewport().mapFromGlobal(global_mouse_pos).y()
        true_y_in_content = y_in_viewport + self.scroll_area.verticalScrollBar().value()
        x_in_content = self.slide_buttons_widget.mapFromGlobal(global_mouse_pos).x()
        pos_in_content_widget = QPoint(x_in_content, true_y_in_content)

        target_flow_layout: Optional[FlowLayout] = None
        # This is the QWidget that *contains* the FlowLayout (e.g., a song_slides_container)
        target_flow_layout_widget: Optional[QWidget] = None

        # Iterate through items in the main vertical layout (slide_buttons_layout)
        for i in range(self.slide_buttons_layout.count()):
            item = self.slide_buttons_layout.itemAt(i)
            if not item or not item.widget():
                continue
            
            widget_in_vbox = item.widget()
            
            # Check if this widget is a container for a FlowLayout
            if isinstance(widget_in_vbox.layout(), FlowLayout):
                row_container_rect = widget_in_vbox.geometry()
                if row_container_rect.contains(pos_in_content_widget):
                    target_flow_layout = widget_in_vbox.layout()
                    target_flow_layout_widget = widget_in_vbox # This is the QWidget containing the FlowLayout
                    # Don't break; continue to find the most specific (lowest) container
                    # This logic might need refinement if there are nested flow layouts,
                    # but for Plucky's structure (VBox of [SongHeader, FlowContainer]), this should be okay.
            
            # Handle "No slides" label case
            elif isinstance(widget_in_vbox, QLabel) and "No slides" in widget_in_vbox.text():
                # This case is mostly for image drops into an empty presentation
                if i == self.slide_buttons_layout.count() -1: # If it's the last item
                    self.drop_indicator.setFixedHeight(self.scroll_area.viewport().height() // 4)
                    self.drop_indicator.move(5, 5)
                    self.drop_indicator.show()
                    self.drop_indicator.raise_()
                    self._potential_drop_index = 0
                    self._current_drop_target_song_title = None
                    return

        if not target_flow_layout or not target_flow_layout_widget:
            # Mouse is not directly over any QWidget that contains a FlowLayout
            # (e.g., over a SongHeaderWidget, or empty space between songs, or below all songs).
            if not self.presentation_manager.get_slides(): # Check PM instead of slide_buttons_list
                # No slides at all, show indicator at top-left (mostly for image drop)
                self.drop_indicator.setFixedHeight(50)
                self.drop_indicator.move(5, 5)
                self.drop_indicator.show()
                self.drop_indicator.raise_()
                self._potential_drop_index = 0
            else: # Slides exist, but mouse isn't over a slide row. Default to append.
                # For image drop, it means appending a new background slide.
                self._potential_drop_index = len(self.presentation_manager.get_slides())
                if is_slide_reorder:
                    # Try to place indicator at the end of the last flow layout
                    if self.slide_buttons_layout.count() > 0:
                        last_vbox_item = self.slide_buttons_layout.itemAt(self.slide_buttons_layout.count() - 1)
                        # Skip stretch items
                        idx = self.slide_buttons_layout.count() - 1
                        while idx >= 0 and (not last_vbox_item or not last_vbox_item.widget() or last_vbox_item.spacerItem()):
                            idx -=1
                            if idx >=0: last_vbox_item = self.slide_buttons_layout.itemAt(idx)
                            else: last_vbox_item = None

                        if last_vbox_item and last_vbox_item.widget() and isinstance(last_vbox_item.widget().layout(), FlowLayout):
                            last_flow_container = last_vbox_item.widget()
                            self._position_indicator_at_flow_end(last_flow_container, is_slide_reorder)
                            return # Positioned, exit
                self.drop_indicator.hide() # Fallback if no suitable end-of-flow found
            self._current_drop_target_song_title = None
            return
        
        # Mouse is over a specific FlowLayout (song row)
        # Convert mouse position to be relative to this FlowLayout's QWidget
        pos_in_flow_widget = target_flow_layout_widget.mapFromGlobal(self.main_window.mapToGlobal(main_window_pos))
        calculated_insertion_index_in_flow = target_flow_layout.count() # Default to end of this flow


        processed_a_button_on_mouse_row = False

        for i in range(target_flow_layout.count()): # Iterate through logical items in the flow
            item_widget_item = target_flow_layout.itemAt(i)
            if not item_widget_item or not item_widget_item.widget():
                continue
            item_widget = item_widget_item.widget()

            if not isinstance(item_widget, ScaledSlideButton):
                continue

            item_rect_in_flow_container = item_widget.geometry() # Relative to target_flow_layout_widget

            # Check if mouse Y is within the vertical bounds of this item
            if pos_in_flow_widget.y() >= item_rect_in_flow_container.top() and \
               pos_in_flow_widget.y() < item_rect_in_flow_container.bottom():
                # This item is on the same visual row as the mouse.
                processed_a_button_on_mouse_row = True
                item_center_x = item_rect_in_flow_container.left() + item_rect_in_flow_container.width() / 2
                
                if pos_in_flow_widget.x() < item_center_x:
                    # Mouse is to the left of this item's center. Insert before this item.
                    calculated_insertion_index_in_flow = i
                    break # Found the insertion point for this row.
                else:
                    # Mouse is to the right of this item's center. Insert after this item.
                    calculated_insertion_index_in_flow = i + 1
                    # Continue to check next item on this row.
            elif processed_a_button_on_mouse_row:
                # We were processing items on the mouse's row, but this current item is not on that row
                # (e.g., it's on the next visual line of the FlowLayout).
                
                break
        # --- Visual positioning of the indicator (geometry calculation) ---
        # This part calculates where the indicator *would* go if shown.
        default_indicator_height = int(self.main_window.get_setting("BASE_PREVIEW_HEIGHT", BASE_PREVIEW_HEIGHT) * self.main_window.button_scale_factor)

        if target_flow_layout.count() == 0: # Flow is empty
            indicator_x = target_flow_layout_widget.geometry().left() + target_flow_layout.contentsMargins().left() + 2
            indicator_y = target_flow_layout_widget.geometry().top() + target_flow_layout.contentsMargins().top()
            indicator_rect.setRect(indicator_x, indicator_y, self.drop_indicator.width(), default_indicator_height)
        elif calculated_insertion_index_in_flow < target_flow_layout.count():
            # Before an existing item
            target_button_item = target_flow_layout.itemAt(calculated_insertion_index_in_flow)
            if target_button_item and target_button_item.widget(): # Check if item and widget exist
                btn_widget = target_button_item.widget()
                btn_geom_in_flow_container = btn_widget.geometry()
                btn_top_left_in_sbg = target_flow_layout_widget.mapToParent(btn_geom_in_flow_container.topLeft())
                
                indicator_x = btn_top_left_in_sbg.x() - (target_flow_layout.horizontalSpacing() / 2) - (self.drop_indicator.width() / 2)
                indicator_y = btn_top_left_in_sbg.y()
                indicator_height = btn_geom_in_flow_container.height() # Use button height for indicator
                indicator_rect.setRect(int(indicator_x), indicator_y, self.drop_indicator.width(), indicator_height)
            # else: if target_button_item or its widget is None, indicator_rect remains empty/invalid
        else: # At the end of the flow (calculated_insertion_index_in_flow == target_flow_layout.count())
            if target_flow_layout.count() > 0: # Ensure there's at least one item to position after
                last_button_item = target_flow_layout.itemAt(target_flow_layout.count() - 1)
                if last_button_item and last_button_item.widget(): # Check if item and widget exist
                    btn_widget = last_button_item.widget()
                    btn_geom_in_flow_container = btn_widget.geometry()
                    btn_top_right_in_sbg = target_flow_layout_widget.mapToParent(btn_geom_in_flow_container.topRight())

                    indicator_x = btn_top_right_in_sbg.x() + (target_flow_layout.horizontalSpacing() / 2) - (self.drop_indicator.width() / 2)
                    indicator_y = btn_top_right_in_sbg.y()
                    indicator_height = btn_geom_in_flow_container.height() # Use button height for indicator
                    indicator_rect.setRect(int(indicator_x), btn_top_right_in_sbg.y(), self.drop_indicator.width(), indicator_height)
            # else: if last_button_item or its widget is None, indicator_rect remains empty/invalid
            # else: if flow is empty, already handled by the first condition.

        # --- Show or hide the indicator based on is_slide_reorder and validity ---
        if is_slide_reorder:
            if not indicator_rect.isNull() and indicator_rect.isValid():
                self.drop_indicator.setGeometry(indicator_rect)
                self.drop_indicator.show()
                self.drop_indicator.raise_()
            else: # Invalid rect for slide reorder
                self.drop_indicator.hide()
                
        else: # Not a slide reorder (e.g., image drop)
             self.drop_indicator.hide()

        # Calculate and store the potential drop index regardless of whether indicator is shown
        base_index_for_this_flow = self._get_base_index_for_flow(target_flow_layout_widget)
        calculated_insertion_index_in_flow = self._calculate_index_within_flow(target_flow_layout, pos_in_flow_widget)
        self._potential_drop_index = base_index_for_this_flow + calculated_insertion_index_in_flow
        self._current_drop_target_song_title = self._get_song_title_for_flow_widget(target_flow_layout_widget)

    def _calculate_index_within_flow(self, flow_layout: FlowLayout, pos_in_flow_widget: QPoint) -> int:
        """
        Calculates the insertion index within a specific FlowLayout based on mouse position.
        pos_in_flow_widget is the mouse position relative to the FlowLayout's container widget.
        """
        calculated_insertion_index_in_flow = flow_layout.count() # Default to end
        processed_a_button_on_mouse_row = False

        for i in range(flow_layout.count()):
            item_widget_item = flow_layout.itemAt(i)
            if not item_widget_item or not item_widget_item.widget():
                continue
            item_widget = item_widget_item.widget()

            if not isinstance(item_widget, ScaledSlideButton):
                continue

            item_rect_in_flow_container = item_widget.geometry() # Relative to flow_layout's container

            # Check if mouse Y is within the vertical bounds of this item
            if pos_in_flow_widget.y() >= item_rect_in_flow_container.top() and \
               pos_in_flow_widget.y() < item_rect_in_flow_container.bottom():
                # This item is on the same visual row as the mouse.
                processed_a_button_on_mouse_row = True
                item_center_x = item_rect_in_flow_container.left() + item_rect_in_flow_container.width() / 2

                if pos_in_flow_widget.x() < item_center_x:
                    # Mouse is to the left of this item's center. Insert before this item.
                    calculated_insertion_index_in_flow = i
                    break # Found the insertion point for this row.
                else:
                    # Mouse is to the right of this item's center. Insert after this item.
                    calculated_insertion_index_in_flow = i + 1
                    # Continue to check next item on this row.
            elif processed_a_button_on_mouse_row:
                # We were processing items on the mouse's row, but this current item is not on that row.
                break # End of row

        return calculated_insertion_index_in_flow

    def _get_base_index_for_flow(self, target_flow_layout_widget: QWidget) -> int:
        """Calculates the number of slides in flow layouts preceding the target_flow_layout_widget."""
        base_index = 0
        for i in range(self.slide_buttons_layout.count()):
            item_widget_in_vbox_item = self.slide_buttons_layout.itemAt(i)
            if not item_widget_in_vbox_item or not item_widget_in_vbox_item.widget():
                continue
            widget_in_vbox = item_widget_in_vbox_item.widget()
            if widget_in_vbox == target_flow_layout_widget:
                break
            if isinstance(widget_in_vbox.layout(), FlowLayout):
                base_index += widget_in_vbox.layout().count() # Add count of flows *before* the target
        return base_index # Return the sum of counts of preceding flows

    def _position_indicator_at_flow_end(self, flow_container_widget: QWidget, is_slide_reorder: bool):
        """Helper to position indicator at the end of a given flow container."""
        flow_layout = flow_container_widget.layout()
        if not isinstance(flow_layout, FlowLayout):
            self.drop_indicator.hide()
            return

        default_indicator_height = int(self.main_window.get_setting("BASE_PREVIEW_HEIGHT", BASE_PREVIEW_HEIGHT) * self.main_window.button_scale_factor)
        indicator_rect = QRect()

        if flow_layout.count() > 0:
            last_button_item = flow_layout.itemAt(flow_layout.count() - 1)
            if last_button_item and last_button_item.widget():
                btn_widget = last_button_item.widget()
                btn_geom_in_flow_container = btn_widget.geometry()
                btn_top_right_in_sbg = flow_container_widget.mapToParent(btn_geom_in_flow_container.topRight())

                indicator_x = btn_top_right_in_sbg.x() + (flow_layout.horizontalSpacing() / 2) - (self.drop_indicator.width() / 2)
                indicator_y = btn_top_right_in_sbg.y()
                indicator_height = btn_geom_in_flow_container.height() # Use button height for indicator
                indicator_rect.setRect(int(indicator_x), indicator_y, self.drop_indicator.width(), indicator_height)
        else: # Flow is empty
            indicator_x = flow_container_widget.geometry().left() + flow_layout.contentsMargins().left() + 2
            indicator_y = flow_container_widget.geometry().top() + flow_layout.contentsMargins().top()
            indicator_rect.setRect(indicator_x, indicator_y, self.drop_indicator.width(), default_indicator_height)

        if not indicator_rect.isNull() and indicator_rect.isValid():
            self.drop_indicator.setGeometry(indicator_rect)
            self.drop_indicator.show()
            self.drop_indicator.raise_()
        else:
            self.drop_indicator.hide()
