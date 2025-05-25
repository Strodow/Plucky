# c:\Users\Logan\Documents\Plucky\Plucky\widgets\section_management_panel.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QHBoxLayout, QLabel, QComboBox, QAbstractItemView
)
from PySide6.QtCore import Signal, Slot
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from PySide6.QtCore import Qt # Add this import

if TYPE_CHECKING:
    from core.presentation_manager import PresentationManager

class SectionManagementPanel(QWidget):
    # Signals to MainWindow to interact with PresentationManager
    request_reorder_section = Signal(str, int)  # section_id_in_manifest, direction (-1 for up, 1 for down)
    request_remove_section = Signal(str)      # section_id_in_manifest
    request_add_existing_section = Signal()   # MainWindow will handle file dialog
    request_create_new_section = Signal()     # MainWindow will handle creation and adding

    request_change_active_arrangement = Signal(str, str) # section_id_in_manifest, new_arrangement_name

    def __init__(self, presentation_manager: 'PresentationManager', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.presentation_manager = presentation_manager
        self._id_to_reselect_after_refresh: Optional[str] = None # To store ID for re-selection
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) # Keep it tight

        # --- Toolbar for general actions ---
        toolbar_layout = QHBoxLayout()
        self.create_new_button = QPushButton("Create New Section")
        self.create_new_button.clicked.connect(self.request_create_new_section)
        toolbar_layout.addWidget(self.create_new_button)
 
        self.add_existing_button = QPushButton("Add Existing Section...")
        self.add_existing_button.clicked.connect(self.request_add_existing_section)
        toolbar_layout.addWidget(self.add_existing_button)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # --- List of sections ---
        self.sections_list_widget = QListWidget()
        self.sections_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove) # For reordering
        self.sections_list_widget.itemDoubleClicked.connect(self._on_item_double_clicked) # Placeholder for future (e.g., focus section)
        # Connect to the model's rowsMoved signal to detect drag-and-drop reordering
        self.sections_list_widget.model().rowsMoved.connect(self._handle_sections_drag_reordered)
        main_layout.addWidget(self.sections_list_widget)

        # --- Controls for selected section ---
        selected_section_controls_layout = QHBoxLayout()
        self.move_up_button = QPushButton("Move Up")
        self.move_down_button = QPushButton("Move Down")
        self.remove_button = QPushButton("Remove from Presentation")
        
        self.move_up_button.clicked.connect(self._on_move_up)
        self.move_down_button.clicked.connect(self._on_move_down)
        self.remove_button.clicked.connect(self._on_remove_section)

        selected_section_controls_layout.addWidget(self.move_up_button)
        selected_section_controls_layout.addWidget(self.move_down_button)
        selected_section_controls_layout.addStretch()
        selected_section_controls_layout.addWidget(self.remove_button)
        main_layout.addLayout(selected_section_controls_layout)
        
        self.setLayout(main_layout)
        self.refresh_sections_list() # Initial population

    def _get_selected_section_id(self) -> Optional[str]:
        current_item = self.sections_list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole) # Store section_id_in_manifest here
        return None

    def _on_move_up(self):
        section_id = self._get_selected_section_id()
        if section_id:
            self._id_to_reselect_after_refresh = section_id # Store ID before reordering
            self.request_reorder_section.emit(section_id, -1)

    def _on_move_down(self):
        section_id = self._get_selected_section_id()
        if section_id:
            self._id_to_reselect_after_refresh = section_id # Store ID before reordering
            self.request_reorder_section.emit(section_id, 1)

    def _on_remove_section(self):
        section_id = self._get_selected_section_id()
        if section_id:
            # When removing, we don't need to reselect the same item,
            # so _id_to_reselect_after_refresh is not set here.
            # TODO: Add a confirmation dialog in MainWindow
            self.request_remove_section.emit(section_id)
            
    def _on_item_double_clicked(self, item: QListWidgetItem):
        section_id = item.data(Qt.ItemDataRole.UserRole)
        print(f"SectionManagementPanel: Item double-clicked: {section_id} - {item.text()}")
        # Future: Could emit a signal to focus this section in the main slide view
        
    @Slot()
    def refresh_sections_list(self):
        # Block signals to prevent selectionChanged from firing multiple times during clear/repopulate
        self.sections_list_widget.blockSignals(True)

        self.sections_list_widget.clear()
        if not self.presentation_manager.presentation_manifest_data:
            self.sections_list_widget.blockSignals(False)
            return

        manifest_sections = self.presentation_manager.presentation_manifest_data.get("sections", [])
        item_to_reselect: Optional[QListWidgetItem] = None

        for index, section_manifest_entry in enumerate(manifest_sections):
            section_id_in_manifest = section_manifest_entry.get("id")
            
            # Try to get the title from the loaded section data
            title = f"Section {index + 1} (ID: {section_id_in_manifest})" # Fallback title
            if section_id_in_manifest in self.presentation_manager.loaded_sections:
                section_data = self.presentation_manager.loaded_sections[section_id_in_manifest].get("section_content_data")
                if section_data and section_data.get("title"):
                    title = section_data.get("title")
            
            item = QListWidgetItem(f"{index + 1}. {title}")
            item.setData(Qt.ItemDataRole.UserRole, section_id_in_manifest) # Store ID
            
            # TODO: Add a QComboBox for arrangement selection within a custom widget for the item, or a separate panel
            # For now, just list them.
            self.sections_list_widget.addItem(item)

            if self._id_to_reselect_after_refresh and section_id_in_manifest == self._id_to_reselect_after_refresh:
                item_to_reselect = item
        
        if item_to_reselect:
            self.sections_list_widget.setCurrentItem(item_to_reselect)
        
        self._id_to_reselect_after_refresh = None # Clear the stored ID
        self.sections_list_widget.blockSignals(False) # Re-enable signals

    @Slot("QModelIndex", int, int, "QModelIndex", int)
    def _handle_sections_drag_reordered(self, source_parent, source_start, source_end, dest_parent, dest_row_before_insertion):
        """
        Called when rows (sections) are moved within the QListWidget via drag-and-drop.
        The QListWidget items are already visually reordered at this point.
        """
        # source_parent and dest_parent are usually invalid for QListWidget's flat model.
        # dest_row_before_insertion is the row index *before which* the items are inserted.
        # If items are moved to the end, dest_row_before_insertion == listWidget.count().

        # Determine the ID of the first item in the moved block to re-select it after refresh.
        # The items are already in their new positions in the list widget.
        # The 'dest_row_before_insertion' is the new starting index of the moved block.
        if 0 <= dest_row_before_insertion < self.sections_list_widget.count():
            # The item at dest_row_before_insertion is the first of the moved items in its new place
            first_moved_item_in_new_pos = self.sections_list_widget.item(dest_row_before_insertion)
            if first_moved_item_in_new_pos:
                self._id_to_reselect_after_refresh = first_moved_item_in_new_pos.data(Qt.ItemDataRole.UserRole)
            else:
                self._id_to_reselect_after_refresh = None
        else: # Items moved to the very end, or list might be empty after move (unlikely for reorder)
             self._id_to_reselect_after_refresh = None # Cannot determine specific item if moved to end beyond current count

        new_ordered_ids = []
        for i in range(self.sections_list_widget.count()):
            item = self.sections_list_widget.item(i)
            if item:
                section_id = item.data(Qt.ItemDataRole.UserRole)
                if section_id:
                    new_ordered_ids.append(section_id)
        
        if new_ordered_ids:
            # This will trigger presentation_manager.presentation_changed,
            # which will then call refresh_sections_list, which uses _id_to_reselect_after_refresh.
            self.presentation_manager.update_manifest_section_order(new_ordered_ids)
        else:
            self._id_to_reselect_after_refresh = None # Clear if no IDs found
