import sys
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget,
    QListWidget, QPushButton, QHBoxLayout, QMessageBox, QListWidgetItem
)
from PySide6.QtCore import Qt

# Assuming PluckyStandards and ResourceTracker are in the core directory
try:
    from core.plucky_standards import PluckyStandards
    from core.resource_tracker import ResourceTracker 
except ImportError:
    # Fallback for development if Plucky's root is not in PYTHONPATH
    # This allows running the window file directly for testing, if needed,
    # though ideally, the project is run from its root.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir) # Assumes /windows is one level down from project root
    if project_root_dir not in sys.path:
        sys.path.append(project_root_dir)
    from core.plucky_standards import PluckyStandards
    from core.resource_tracker import ResourceTracker


class ResourceManagerWindow(QDialog):
    def __init__(self, presentation_manager, image_cache_manager, parent=None):
        super().__init__(parent)
        self.presentation_manager = presentation_manager
        self.image_cache_manager = image_cache_manager
        self.resource_tracker = ResourceTracker() # Initialize the tracker

        self.setWindowTitle("Resource Manager")
        self.setMinimumSize(700, 500)

        self.layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        self._setup_sections_tab()
        self._setup_cached_backgrounds_tab()

        self.setLayout(self.layout)

    def _setup_sections_tab(self):
        self.sections_tab = QWidget()
        self.tab_widget.addTab(self.sections_tab, "Section Usage")
        sections_layout = QVBoxLayout(self.sections_tab)

        self.sections_list = QListWidget()
        self.full_scan_button = QPushButton("Analyze UserStore (can be slow)")
        self.delete_section_button = QPushButton("Delete Selected Orphaned Section File")
        self.delete_section_button.setEnabled(False)

        sections_layout.addWidget(QLabel("Orphaned sections (not used in any known presentation according to last scan):"))
        sections_layout.addWidget(self.full_scan_button)
        sections_layout.addWidget(self.sections_list)
        sections_layout.addWidget(self.delete_section_button)

        self.full_scan_button.clicked.connect(self._perform_full_scan)
        self.delete_section_button.clicked.connect(self._delete_selected_section)
        self.sections_list.itemSelectionChanged.connect(self._on_section_selection_changed)

    def _perform_full_scan(self):
        self.setCursor(Qt.WaitCursor)
        QApplication.processEvents() # type: ignore
        try:
            # Pass the IO handler from PresentationManager for manifest reading during scan
            self.resource_tracker.perform_full_resource_scan(self.presentation_manager.io_handler)
            QMessageBox.information(self, "Scan Complete", "Full resource scan finished. Lists will now reflect the latest data.")
        except AttributeError as ae:
            QMessageBox.critical(self, "Scan Error", f"A required method might be missing from PresentationManager.io_handler: {ae}")
            print(f"ResourceManager Scan Error: {ae}")
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"An error occurred during the scan: {e}")
            print(f"ResourceManager Scan Error: {e}")
        finally:
            self.unsetCursor()
            self._load_section_usage() # Refresh lists after scan
            self._load_cached_background_usage()

    def _load_section_usage(self):
        self.sections_list.clear()
        try:
            orphaned_sections = self.resource_tracker.get_orphaned_sections()
            if not orphaned_sections:
                self.sections_list.addItem("No orphaned sections found in the database. (Run a full scan if this is unexpected)")
                self.delete_section_button.setEnabled(False)
                return

            for section_data in orphaned_sections:
                title = section_data.get('title', 'N/A') # Get title if available
                item_text = f"{section_data['filename']} (Title: {title})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {"filename": section_data['filename'], "orphaned": True})
                self.sections_list.addItem(item)
        except Exception as e:
            self.sections_list.addItem(f"Error loading section usage: {e}")
            print(f"ResourceManager Error (Sections): {e}")

    def _on_section_selection_changed(self):
        selected_items = self.sections_list.selectedItems()
        self.delete_section_button.setEnabled(bool(selected_items and selected_items[0].data(Qt.UserRole).get("orphaned")))

    def _delete_selected_section(self):
        item_data = self.sections_list.selectedItems()[0].data(Qt.UserRole)
        section_filename = item_data["filename"]
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to permanently delete the section file '{section_filename}' from your computer?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                section_path = os.path.join(PluckyStandards.get_sections_dir(), section_filename)
                os.remove(section_path) # Delete from disk
                self.resource_tracker.delete_section_record(section_filename) # Remove from DB
                QMessageBox.information(self, "Success", f"Section '{section_filename}' deleted.")
                self._load_section_usage()
            except Exception as e:
                QMessageBox.critical(self, "Error Deleting", f"Could not delete section: {e}")

    def _setup_cached_backgrounds_tab(self):
        self.cached_bg_tab = QWidget()
        self.tab_widget.addTab(self.cached_bg_tab, "Cached Backgrounds (Current Presentation)")
        cached_bg_layout = QVBoxLayout(self.cached_bg_tab)

        self.cached_bg_list = QListWidget()
        # The full_scan_button is global for both tabs.
        self.clear_selected_cached_bg_button = QPushButton("Remove Selected Unused Background from Cache")
        self.clear_all_unused_cached_bg_button = QPushButton("Remove All Orphaned Backgrounds from Cache")
        
        self.clear_selected_cached_bg_button.setEnabled(False)

        cached_bg_layout.addWidget(QLabel("Orphaned cached backgrounds (not used in any known presentation according to last scan):"))
        # cached_bg_layout.addWidget(self.refresh_cached_bg_button) # Removed, use full_scan_button
        cached_bg_layout.addWidget(self.cached_bg_list)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.clear_selected_cached_bg_button)
        button_layout.addWidget(self.clear_all_unused_cached_bg_button)
        cached_bg_layout.addLayout(button_layout)
        
        # self.refresh_cached_bg_button.clicked.connect(self._load_cached_background_usage) # Removed
        self.clear_selected_cached_bg_button.clicked.connect(self._clear_selected_cached_bg)
        self.clear_all_unused_cached_bg_button.clicked.connect(self._clear_all_unused_cached_bg)
        self.cached_bg_list.itemSelectionChanged.connect(self._on_cached_bg_selection_changed)

    def _load_cached_background_usage(self):
        self.cached_bg_list.clear()
        if not self.presentation_manager or not self.image_cache_manager: return
        
        self.orphaned_bgs_from_db = [] # Store keys for bulk delete action
        try:
            orphaned_bgs = self.resource_tracker.get_orphaned_cached_backgrounds()
            if not orphaned_bgs:
                self.cached_bg_list.addItem("No orphaned cached backgrounds found in the database. (Run a full scan if this is unexpected)")
                self.clear_all_unused_cached_bg_button.setEnabled(False)
                self.clear_selected_cached_bg_button.setEnabled(False)
                return

            for bg_data in orphaned_bgs:
                cache_key = bg_data["cache_key"]
                item_text = f"{os.path.basename(cache_key)}" # Display only filename
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {"cache_key": cache_key, "orphaned": True})
                self.cached_bg_list.addItem(item)
                self.orphaned_bgs_from_db.append(cache_key)
            
            self.clear_all_unused_cached_bg_button.setEnabled(bool(self.orphaned_bgs_from_db))

        except Exception as e:
            self.cached_bg_list.addItem(f"Error loading orphaned backgrounds: {e}")
            print(f"ResourceManager Error (Backgrounds): {e}")

    def _on_cached_bg_selection_changed(self):
        selected = self.cached_bg_list.selectedItems()
        self.clear_selected_cached_bg_button.setEnabled(bool(selected and not selected[0].data(Qt.UserRole)["used"]))

    def _clear_selected_cached_bg(self):
        item_data = self.cached_bg_list.selectedItems()[0].data(Qt.UserRole)
        cache_key = item_data["cache_key"]
        if QMessageBox.question(self, "Confirm Clear", f"Remove '{os.path.basename(cache_key)}' from image cache and tracking database?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            try:
                self.image_cache_manager.remove_image_from_cache(cache_key) # Remove from cache
                self.resource_tracker.delete_cached_background_record(cache_key) # Remove from DB
                self._load_cached_background_usage()
            except AttributeError as ae: QMessageBox.critical(self, "Error", f"A required method might be missing: {ae}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not remove from cache: {e}")

    def _clear_all_unused_cached_bg(self):
        if not self.orphaned_bgs_from_db: return
        if QMessageBox.question(self, "Confirm Clear All",
                                f"Remove {len(self.orphaned_bgs_from_db)} orphaned backgrounds from cache and tracking database?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            cleared_count = 0
            errors_encountered = []
            for key in self.orphaned_bgs_from_db:
                try:
                    self.image_cache_manager.remove_image_from_cache(key) # From cache
                    self.resource_tracker.delete_cached_background_record(key) # From DB
                    cleared_count +=1
                except Exception as e:
                    errors_encountered.append(f"Error removing '{os.path.basename(key)}': {e}")
            QMessageBox.information(self, "Cleared", f"Removed {cleared_count} items from cache.")
            self._load_cached_background_usage()

    def showEvent(self, event):
        """Load data when the dialog is shown."""
        super().showEvent(event)
        self._load_section_usage()
        self._load_cached_background_usage()

from PySide6.QtWidgets import QApplication # For processEvents