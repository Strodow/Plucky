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
        self.delete_section_button = QPushButton("Delete Selected Section File")
        self.delete_section_button.setEnabled(False)
        self.delete_all_sections_button = QPushButton("Delete All Listed Problematic Sections")
        self.delete_all_sections_button.setEnabled(False)

        sections_layout.addWidget(QLabel("Orphaned or Unreferenced Sections (not used, or on disk but not tracked in database):"))
        sections_layout.addWidget(self.full_scan_button)
        sections_layout.addWidget(self.sections_list)
        sections_button_layout = QHBoxLayout()
        sections_button_layout.addWidget(self.delete_section_button)
        sections_button_layout.addWidget(self.delete_all_sections_button)
        sections_layout.addLayout(sections_button_layout)

        self.full_scan_button.clicked.connect(self._perform_full_scan)
        self.delete_section_button.clicked.connect(self._delete_selected_section)
        self.delete_all_sections_button.clicked.connect(self._delete_all_problematic_sections)
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
        self.problematic_sections_list_data = [] # Store for delete all

        try:
            # 1. Get sections that are in the DB but not used by any presentation
            orphaned_sections = self.resource_tracker.get_orphaned_sections()
            for section_data in orphaned_sections:
                self.problematic_sections_list_data.append({
                    "filename": section_data['filename'],
                    "title": section_data.get('title', 'N/A (From DB)'),
                    "status_description": "In DB, not used in any presentation",
                    "is_deletable": True
                })

            # 2. Get section files that are on disk but not in the DB at all
            unreferenced_on_disk = self.resource_tracker.get_unreferenced_section_files()
            for section_data in unreferenced_on_disk:
                self.problematic_sections_list_data.append({

                    "filename": section_data['filename'],
                    "title": section_data.get('title', 'N/A (Not in DB)'), # Should be "N/A (On disk, not in DB)" from tracker
                    "status_description": "On disk, not tracked in database",
                    "is_deletable": True
                })

            if not self.problematic_sections_list_data:
                self.sections_list.addItem("No orphaned or unreferenced sections found. (Run a full scan if this is unexpected)")
                self.delete_section_button.setEnabled(False)
                self.delete_all_sections_button.setEnabled(False)
                return

            for section_data in self.problematic_sections_list_data:
                item_text = f"{section_data['filename']} (Title: {section_data['title']}) - Status: {section_data['status_description']}"

                item = QListWidgetItem(item_text)
                # Store filename and a flag indicating it's deletable
                item.setData(Qt.UserRole, {"filename": section_data['filename'], 
                                           "is_deletable": section_data.get('is_deletable', False)})

                self.sections_list.addItem(item)
        except Exception as e:
            self.sections_list.addItem(f"Error loading section usage: {e}")
            print(f"ResourceManager Error (Sections): {e}")
        self.delete_section_button.setEnabled(False) # Disable initially, enable on selection
        self.delete_all_sections_button.setEnabled(bool(self.problematic_sections_list_data))



    def _on_section_selection_changed(self):
        selected_items = self.sections_list.selectedItems()
        self.delete_section_button.setEnabled(bool(selected_items and selected_items[0].data(Qt.UserRole).get("is_deletable")))


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
                # Remove from DB (this will do nothing if the section wasn't in the DB, which is fine)
                self.resource_tracker.delete_section_record(section_filename) 

                QMessageBox.information(self, "Success", f"Section '{section_filename}' deleted.")
                self._load_section_usage()
            except Exception as e:
                QMessageBox.critical(self, "Error Deleting", f"Could not delete section: {e}")
                
    def _delete_all_problematic_sections(self):
        if not hasattr(self, 'problematic_sections_list_data') or not self.problematic_sections_list_data:
            QMessageBox.information(self, "No Sections", "There are no problematic sections listed to delete.")
            return

        reply = QMessageBox.question(self, "Confirm Delete All",
                                     f"Are you sure you want to permanently delete all {len(self.problematic_sections_list_data)} listed section files from your computer?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted_count = 0
            errors_encountered = []
            for section_data in self.problematic_sections_list_data:
                section_filename = section_data["filename"]
                try:
                    section_path = os.path.join(PluckyStandards.get_sections_dir(), section_filename)
                    if os.path.exists(section_path): # Check if file exists before trying to remove
                        os.remove(section_path)
                    self.resource_tracker.delete_section_record(section_filename)
                    deleted_count += 1
                except Exception as e:
                    errors_encountered.append(f"Error deleting '{section_filename}': {e}")
            
            QMessageBox.information(self, "Operation Complete", f"Attempted to delete {len(self.problematic_sections_list_data)} sections. Successfully deleted {deleted_count} files.")
            if errors_encountered:
                QMessageBox.warning(self, "Deletion Issues", "Some sections could not be deleted:\n\n" + "\n".join(errors_encountered))
            
            self._load_section_usage() # Refresh the list

    def _setup_cached_backgrounds_tab(self):
        self.cached_bg_tab = QWidget()
        self.tab_widget.addTab(self.cached_bg_tab, "Cached Backgrounds (Current Presentation)")
        cached_bg_layout = QVBoxLayout(self.cached_bg_tab)

        self.cached_bg_list = QListWidget()
        # The full_scan_button is global for both tabs.
        self.clear_selected_cached_bg_button = QPushButton("Remove Selected Unused Background from Cache")
        self.clear_all_unused_cached_bg_button = QPushButton("Remove All Orphaned Backgrounds from Cache")
        
        self.clear_selected_cached_bg_button.setEnabled(False)

        cached_bg_layout.addWidget(QLabel("Problematic Cached Backgrounds (in DB but unused, or on disk but not in any slide):"))

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
        self.problematic_backgrounds_list_data = [] # Unified list for UI and bulk delete

        if not self.presentation_manager or not self.image_cache_manager:
            self.cached_bg_list.addItem("Presentation Manager or Image Cache Manager not available.")
            return

        try:
            # 1. Get backgrounds that are in the DB but not used by any presentation (DB Orphaned)
            db_orphaned_bgs = self.resource_tracker.get_orphaned_cached_backgrounds() # type: ignore
            for bg_data in db_orphaned_bgs: # type: ignore
                cache_key = bg_data["cache_key"] # This is the original_path
                self.problematic_backgrounds_list_data.append({
                    "display_name": os.path.basename(cache_key),
                    "type": "db_orphaned",
                    "key_or_path": cache_key, # Store original_path as key
                    "status_description": "In DB, not used in any presentation"
                })

            # 2. Get background files that are on disk but not referenced in any section file
            # This requires the presentation_io_handler to scan section files.
            if hasattr(self.presentation_manager, 'io_handler') and self.presentation_manager.io_handler:
                disk_unreferenced_bgs = self.resource_tracker.get_unreferenced_cached_files_on_disk( # type: ignore
                    presentation_io_handler=self.presentation_manager.io_handler,
                    image_cache_manager=self.image_cache_manager # Pass the image cache manager
                )

                for bg_data in disk_unreferenced_bgs: # type: ignore
                    self.problematic_backgrounds_list_data.append({
                        "display_name": bg_data["display_name"], # This is basename from cache dir
                        "type": "disk_unreferenced_by_slide",
                        "key_or_path": bg_data["disk_path"], # Store full path to file in cache dir
                        "status_description": "In cache folder, not found in any slide"
                    })
            else:
                print("ResourceManagerWindow: PresentationManager has no io_handler or it's None, skipping disk_unreferenced_by_slide scan.")


            if not self.problematic_backgrounds_list_data:
                self.cached_bg_list.addItem("No problematic cached backgrounds found. (Run 'Analyze UserStore' if this is unexpected)")
            else:
                for bg_item_data in self.problematic_backgrounds_list_data:
                    item_text = f"{bg_item_data['display_name']} - Status: {bg_item_data['status_description']}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, bg_item_data) # Store the whole dict
                    self.cached_bg_list.addItem(item)

        except Exception as e:
            self.cached_bg_list.addItem(f"Error loading background usage: {e}")

            print(f"ResourceManager Error (Backgrounds): {e}")
        self.clear_selected_cached_bg_button.setEnabled(False)
        self.clear_all_unused_cached_bg_button.setEnabled(bool(self.problematic_backgrounds_list_data))


    def _on_cached_bg_selection_changed(self):
        selected = self.cached_bg_list.selectedItems()
        self.clear_selected_cached_bg_button.setEnabled(bool(selected))



    def _clear_selected_cached_bg(self):
        if not self.cached_bg_list.selectedItems(): return
        item_data = self.cached_bg_list.selectedItems()[0].data(Qt.UserRole)
        display_name = item_data["display_name"]
        item_type = item_data["type"]
        key_or_path = item_data["key_or_path"]

        if QMessageBox.question(self, "Confirm Clear", f"Remove '{display_name}'?",

                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            try:
                if item_type == "db_orphaned":
                    # key_or_path is the original_path (cache_key)
                    self.image_cache_manager.remove_image_from_cache(key_or_path) # type: ignore
                    self.resource_tracker.delete_cached_background_record(key_or_path) # type: ignore
                elif item_type == "disk_unreferenced_by_slide":
                    # key_or_path is a full path to the file in the cache directory
                    if os.path.exists(key_or_path):
                        os.remove(key_or_path)
                    # No DB record to delete for these.
                
                QMessageBox.information(self, "Success", f"Background '{display_name}' removed.")

                self._load_cached_background_usage()
            except AttributeError as ae: QMessageBox.critical(self, "Error", f"A required method might be missing: {ae}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Could not remove background: {e}")


    def _clear_all_unused_cached_bg(self):
        if not hasattr(self, 'problematic_backgrounds_list_data') or not self.problematic_backgrounds_list_data:
            QMessageBox.information(self, "No Backgrounds", "There are no problematic backgrounds listed to delete.")
            return

        if QMessageBox.question(self, "Confirm Clear All",
                                f"Remove all {len(self.problematic_backgrounds_list_data)} listed backgrounds?",

                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            cleared_count = 0
            errors_encountered = []
            for item_data in self.problematic_backgrounds_list_data:
                display_name = item_data["display_name"]
                item_type = item_data["type"]
                key_or_path = item_data["key_or_path"]
                try:
                    if item_type == "db_orphaned":
                        self.image_cache_manager.remove_image_from_cache(key_or_path) # type: ignore
                        self.resource_tracker.delete_cached_background_record(key_or_path) # type: ignore
                    elif item_type == "disk_unreferenced_by_slide":
                        if os.path.exists(key_or_path):
                            os.remove(key_or_path)
                    cleared_count +=1
                except Exception as e:
                    error_message = f"Error removing '{display_name}': {e}"

                    print(f"ResourceManager Error (Clear All BG): {error_message}") # Log to console as well
                    errors_encountered.append(error_message)
            QMessageBox.information(self, "Operation Complete", f"Attempted to remove {len(self.problematic_backgrounds_list_data)} items. Successfully removed {cleared_count} items.")
            if errors_encountered:
                QMessageBox.warning(self, "Clearing Issues", "Some items could not be removed:\n\n" + "\n".join(errors_encountered))

            self._load_cached_background_usage()

    def showEvent(self, event):
        """Load data when the dialog is shown."""
        super().showEvent(event)
        self._load_section_usage()
        self._load_cached_background_usage()

from PySide6.QtWidgets import QApplication # For processEvents