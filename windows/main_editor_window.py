import sys
import os
import uuid # For generating unique IDs for the test manifest
import json # For writing the test section file
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QComboBox, QSplitter, QListWidgetItem,
    QListWidget, QApplication, QLabel, QFrame, QPushButton, QLineEdit, QMenu
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir, QEvent, QObject, Slot, QSize, QTimer, QPoint, Signal
from typing import Optional # Added Optional for type hinting

from PySide6.QtWidgets import QGroupBox # Added QGroupBox for the collapsible section
# Attempt to import PluckyStandards for directory paths
try:
    from core.plucky_standards import PluckyStandards # Try importing first
except ImportError:
    # If running directly from 'windows' and 'core' is a sibling, adjust path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # After path adjustment, the imports below will be attempted.
    # No need to re-import PluckyStandards here if it's imported unconditionally below.

# Now that sys.path is potentially adjusted, import all necessary core components.
from core.plucky_standards import PluckyStandards
from core.template_manager import TemplateManager
from data_models.slide_data import SlideData
from core.presentation_manager import PresentationManager # Moved here
from rendering.slide_renderer import LayeredSlideRenderer
from core.image_cache_manager import ImageCacheManager
from core.app_config_manager import ApplicationConfigManager

# QtGui imports can be grouped
from PySide6.QtGui import QColor, QCursor, QPixmap, QIcon, QBrush, QAction

# Import the custom slide item widget
from windows.slide_editor_item_widget import SlideEditorItemWidget

THUMBNAIL_WIDTH = 128 # Define a fixed width for thumbnails
THUMBNAIL_HEIGHT = 72  # Define a fixed height for thumbnails (16:9 aspect)

class MouseHoverDebugger(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("MouseHoverDebugger: Initialized") # Confirm instance creation
        sys.stdout.flush()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            widget_under_mouse = QApplication.widgetAt(QCursor.pos())
            if widget_under_mouse:
                print(f"DEBUG_HOVER: Widget: {widget_under_mouse.__class__.__name__}, Name: '{widget_under_mouse.objectName()}', Pos: {widget_under_mouse.mapFromGlobal(QCursor.pos())}, Size: {widget_under_mouse.size()}")
            else:
                print(f"DEBUG_HOVER: No Qt widget under mouse at {QCursor.pos()}")
            sys.stdout.flush() # Ensure it prints immediately
        return False # Crucial: Let other event filters and the widget process the event

# Store references to open editor windows to prevent garbage collection
_open_editor_windows = []

class MainEditorWindow(QMainWindow):
    section_content_saved = Signal(str) # Emits section_id_in_manifest upon successful save

    def __init__(self, presentation_manager_ref: PresentationManager, section_id_to_edit: Optional[str] = None, parent: QWidget = None):
        super().__init__(parent)

        # --- Initialize Hover Debugger (can be toggled later) ---
        self._hover_debugger_instance: Optional[MouseHoverDebugger] = None
        self._test_section_id: Optional[str] = section_id_to_edit # Store the ID of the section to edit

        # Use the passed-in PresentationManager
        self.presentation_manager = presentation_manager_ref
        self.template_manager = TemplateManager()

        # Instantiate Renderer and its dependencies
        # --- Core Components ---
        # self.presentation_manager = PresentationManager(template_manager=self.template_manager) # REMOVED: Use passed-in PM

        if not self.presentation_manager:
            # This should ideally not happen if MainWindow passes it correctly.
            # Fallback for standalone testing (though it will be limited).
            print("MainEditorWindow: WARNING - No PresentationManager provided. Creating a new one for limited testing.")
            self.presentation_manager = PresentationManager(template_manager=self.template_manager)

        self.image_cache_manager = ImageCacheManager()
        # Connect presentation_changed to multiple slots if needed, or one central update slot
        self.presentation_manager.slide_visual_property_changed.connect(self._handle_slide_visual_property_update) # Connect here
        self.slide_renderer = LayeredSlideRenderer(app_settings=self, image_cache_manager=self.image_cache_manager)


        # Load the UI file
        loader = QUiLoader()
        script_dir = QFileInfo(__file__).absolutePath()
        ui_file_path = QDir(script_dir).filePath("main_editor_window.ui")

        # Load the .ui file. This will return the QMainWindow instance defined in the .ui file.
        # We load it without a specific Qt parent first, or pass self if self should be its Qt parent.
        # Let's call the loaded instance 'loaded_ui_window'.
        loaded_ui_window = loader.load(ui_file_path, self) # self will be the Qt parent

        if not loaded_ui_window:
            print(f"Failed to load UI file: {ui_file_path}")
            # Fallback: Set a central widget with an error message
            error_label = QLabel("Error: Could not load main_editor_window.ui")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setCentralWidget(error_label) # 'self' is the QMainWindow we are configuring
            self.setWindowTitle("Error Loading UI")
            return

        # 'self' (this instance of MainEditorWindow) is the QMainWindow we want to use.
        # We will take the central widget and properties from 'loaded_ui_window'.

        try:
            # Transfer window title and other QMainWindow properties from loaded_ui_window to self FIRST.
            # This is done before altering loaded_ui_window's structure (like taking its central widget),
            # which might lead to its premature cleanup if self is its parent.
            self.setWindowTitle(loaded_ui_window.windowTitle())
            self.setGeometry(loaded_ui_window.geometry())

            # Transfer the central widget from loaded_ui_window to self.
            # This also handles reparenting of the central widget.
            central_widget_from_ui = loaded_ui_window.centralWidget()
            if central_widget_from_ui:
                self.setCentralWidget(central_widget_from_ui)
            else:
                print("Warning: loaded_ui_window has no central widget.")
                # Set a default central widget for 'self' if needed
                self.setCentralWidget(QWidget(self)) 

            # TODO: Transfer MenuBar, ToolBars, StatusBar if they exist in loaded_ui_window
            # and you want them on 'self'. Example:
            # if loaded_ui_window.menuBar(): self.setMenuBar(loaded_ui_window.menuBar())

        except RuntimeError as e:
            print(f"RuntimeError during UI setup from loaded_ui_window: {e}")
            # Fallback or re-raise if critical
            error_label = QLabel(f"Error during UI setup: {e}\nLoaded UI might be incomplete.")
            self.setCentralWidget(error_label)
            return # Stop further initialization if basic setup failed

        # Child widgets (like templates_combo_box) are now part of self.centralWidget(),
        # or directly part of 'self' if they are dock widgets, toolbars, etc.
        # Therefore, self.findChild() should work correctly on 'self' to find them.
        #self.templates_combo_box: QComboBox = self.findChild(QComboBox, "templates_combo_box")
        self.main_slides_scroll_area: QScrollArea = self.findChild(QScrollArea, "main_slides_scroll_area")
        self.section_title_banner_label: QLabel = self.findChild(QLabel, "section_title_banner_label") # Find the new banner
        self.scroll_area_content_widget: QWidget = self.findChild(QWidget, "scrollAreaContentWidget")
        self.slides_container_layout: QVBoxLayout = None

        if self.scroll_area_content_widget:
            self.slides_container_layout = self.scroll_area_content_widget.layout()
            if not self.slides_container_layout: # If layout wasn't set in Qt Designer
                 self.slides_container_layout = QVBoxLayout(self.scroll_area_content_widget)
                 print("Warning: slides_container_layout was not set in UI, created dynamically.")
        else:
            print("Error: scrollAreaContentWidget not found!")
        
        self.save_sidebar_button: QPushButton = self.findChild(QPushButton, "save_sidebar_button")
        if self.save_sidebar_button:
            self.save_sidebar_button.clicked.connect(self.handle_save)
            self.save_sidebar_button.hide() # Initially hidden

        self.slide_thumbnails_list_widget: QListWidget = self.findChild(QListWidget, "slide_thumbnails_list_widget")

        # Connect presentation_changed to update save button visibility
        self.presentation_manager.presentation_changed.connect(self._update_save_button_visibility)
        self.presentation_manager.presentation_changed.connect(self._handle_presentation_changed_for_ui_refresh) # New connection for full UI refresh

        # Connect the itemClicked signal for the thumbnail list
        if self.slide_thumbnails_list_widget:
            self.slide_thumbnails_list_widget.itemClicked.connect(self._handle_thumbnail_clicked)
            

        # The 'loaded_ui_window' instance has served its purpose of providing the initial structure.
        # Since its central widget (and potentially menubar etc.) has been reparented to 'self',
        # 'loaded_ui_window' is now an empty shell. It's also a child of 'self' due to the parent argument in load().
        # --- Setup for Collapsible Section Properties ---
        self.section_properties_group_box: QGroupBox = self.findChild(QGroupBox, "section_properties_group_box")
        self.section_properties_content_container: QWidget = self.findChild(QWidget, "section_properties_content_container")

        if self.section_properties_group_box and self.section_properties_content_container:
            self.section_properties_group_box.toggled.connect(self._toggle_section_properties_content)
            # Set initial visibility based on the group box's checked state (should be false from UI)
            self._toggle_section_properties_content(self.section_properties_group_box.isChecked())
        else:
            if not self.section_properties_group_box:
                print("Error: section_properties_group_box not found in UI!")
            if not self.section_properties_content_container:
                print("Error: section_properties_content_container not found in UI!")
        # Qt's parent-child system should manage its lifecycle. Or, you could explicitly:
        # --- Metadata UI Elements ---
        self.metadata_entries_layout: QVBoxLayout = self.findChild(QVBoxLayout, "metadata_entries_layout")
        self.add_metadata_button: QPushButton = self.findChild(QPushButton, "add_metadata_button")
        if self.add_metadata_button:
            self.add_metadata_button.clicked.connect(self._show_add_metadata_menu)
        self._metadata_row_widgets_store = [] # To store refs to UI elements of metadata rows
        # loaded_ui_window.deleteLater() # If you want to be sure it's cleaned up and not lingering.
        
        
        # --- Setup and add items from the test section ---
        self._load_section_for_editing() # Renamed and adapted method
        
        # --- Adjust initial splitter sizes ---
        self.main_splitter: QSplitter = self.findChild(QSplitter, "main_splitter")
        if self.main_splitter:
            # Attempt to set initial sizes.
            # The QSplitter will try to respect these sizes while also respecting minimumSizeHint of children.
            # We want the right panel (thumbnails) to be smaller. Let's aim for around 200-250px.
            # However, self.main_splitter.width() might be 0 or small at this point if the window isn't fully shown.
            # It's better to set a fixed initial width for the right panel if possible,
            # or use stretch factors more reliably.
            # For now, let's try to set a fixed width for the right panel (index 1).
            # This might not work perfectly if the window is too small.
            # A QTimer.singleShot might be needed to set sizes after the window is shown.
            initial_right_panel_width = 200 # Desired initial width for the thumbnail panel
            total_width = self.width() # Use the window's width as a proxy
            
            # Ensure total_width is somewhat reasonable before calculating
            if total_width > initial_right_panel_width + 100: # Ensure left panel has at least 100px
                initial_left_panel_width = total_width - initial_right_panel_width
                self.main_splitter.setSizes([initial_left_panel_width, initial_right_panel_width])
            else: # Fallback to stretch factors if initial width is too small or unexpected
                self.main_splitter.setStretchFactor(0, 18) # Left panel (main editor)
                self.main_splitter.setStretchFactor(1, 1) # Right panel (thumbnails)
        
        # --- Example: Add a simple menu to toggle the hover debugger ---
        self._create_debug_menu()

        # Schedule a one-time call to ensure all initial thumbnails are set
        QTimer.singleShot(100, self._ensure_initial_thumbnails) # Increased delay slightly for safety
        
        # Initial check for save button visibility
        self._update_save_button_visibility()
        # Populate metadata after section is loaded
        self._populate_metadata_fields_from_section()


    def _load_section_for_editing(self):
        """
        Loads the specified section (via self._test_section_id which is set from section_id_to_edit)
        from the provided PresentationManager and populates the UI.
        """
        if not self._test_section_id:
            # This case is for standalone testing if no section_id_to_edit was passed.
            # We'll create the "Test Song Example" section as before.
            # This part can be removed if standalone testing of MainEditorWindow is no longer needed
            # or handled differently.
            print("MainEditorWindow: No specific section_id_to_edit provided. Setting up default 'Test Song Example'.")
            test_section_filename = "Test Song Example.plucky_section"
            test_section_content = {
                "version": "1.0.0", "id": "test_song_example_section_id", "title": "Test Song Example", "metadata": [],
                "slide_blocks": [
                    {"slide_id": "slide_98a32b0b648f", "label": "Verse 1", "content": {"main_text": "Lyrics of the first verse"}, "template_id": "TestLyrics", "background_source": None, "notes": None},
                    {"slide_id": "slide_0cdf2f98e93a", "label": "Title Slide", "content": {"main_text": "Test Song Title", "Player": "Player Name", "Writer": "Writer Name"}, "template_id": "TestTitle", "background_source": None, "notes": None},
                ],
                "arrangements": {"Default": [{"slide_id_ref": "slide_0cdf2f98e93a", "enabled": True}, {"slide_id_ref": "slide_98a32b0b648f", "enabled": True}]}
            }
            test_section_content["id"] = "test_song_example_section_id"
            try:
                sections_dir = PluckyStandards.get_sections_dir()
                if not os.path.exists(sections_dir): os.makedirs(sections_dir)
                test_section_filepath = os.path.join(sections_dir, test_section_filename)
                if not os.path.exists(test_section_filepath):
                    with open(test_section_filepath, 'w') as f: json.dump(test_section_content, f, indent=4)
                else:
                    with open(test_section_filepath, 'r') as f: test_section_content = json.load(f)
            except Exception as e:
                print(f"Error setting up default test section file: {e}")
                return

            # Create a dummy manifest entry for this test section
            # The self.presentation_manager is now the one passed from MainWindow
            # We should be careful not to overwrite MainWindow's actual presentation.
            # For standalone testing, this is okay. When launched from MainWindow, this path shouldn't be hit.
            manifest_section_id_for_test = f"editor_standalone_sec_{uuid.uuid4().hex}"
            self._test_section_id = manifest_section_id_for_test # This is the key for loaded_sections

            # Load this test section into the (potentially shared) PresentationManager
            # This is a bit risky if PM is shared. Ideally, MainEditorWindow for a specific section
            # doesn't modify the PM's manifest_data. It just works with loaded_sections.
            if self._test_section_id not in self.presentation_manager.loaded_sections:
                 self.presentation_manager.loaded_sections[self._test_section_id] = {
                    "manifest_entry_data": {"id": self._test_section_id, "path": test_section_filename, "active_arrangement_name": "Default"}, # Dummy manifest entry
                    "section_content_data": test_section_content,
                    "is_dirty": False,
                    "resolved_filepath": test_section_filepath
                }
            section_to_load_data = test_section_content # Use the content directly

        elif self._test_section_id not in self.presentation_manager.loaded_sections:
            print(f"MainEditorWindow: Error - Section ID '{self._test_section_id}' not found in PresentationManager's loaded sections.")
            if self.section_title_banner_label:
                self.section_title_banner_label.setText("Error Loading Section")
            return
        else:
            # Section ID is valid and found in PM
            section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
            section_to_load_data = section_wrapper.get("section_content_data")
            if not section_to_load_data:
                print(f"MainEditorWindow: Error - No content_data for section '{self._test_section_id}'.")
                if self.section_title_banner_label:
                    self.section_title_banner_label.setText("Error: Section Content Missing")
                return

        # --- Now, populate UI using slides from PresentationManager ---
        # We need to get slides *for this specific section only*.
        # PresentationManager.get_slides() returns all slides from the *active arrangement* of *all sections* in the manifest.
        # We need a way to get SlideData objects for a specific section, perhaps using its default arrangement.

        # For now, let's adapt by creating SlideData objects directly from section_to_load_data
        # This bypasses PM.get_slides() for populating this editor, which is fine as it's section-focused.
        
        slide_blocks = section_to_load_data.get("slide_blocks", [])
        section_title_for_banner = section_to_load_data.get("title", "Untitled Section")

        if self.section_title_banner_label:
            self.section_title_banner_label.setText(section_title_for_banner)
        
        if not slide_blocks:
            print(f"MainEditorWindow: Section '{section_title_for_banner}' has no slide_blocks.")
            # Still populate metadata if section is loaded
            self._populate_metadata_fields_from_section()
            return

        # Create SlideData objects for each block in this section
        # This is a simplified version of what PM.get_slides() does, focused on one section.
        # It assumes the "Default" arrangement or the first one if "Default" isn't present.
        arrangements_map = section_to_load_data.get("arrangements", {})
        active_arrangement_name = "Default" # Or logic to pick first if Default not present
        if active_arrangement_name not in arrangements_map and arrangements_map:
            active_arrangement_name = next(iter(arrangements_map))
        
        arrangement_slide_refs = arrangements_map.get(active_arrangement_name, [])
        slide_blocks_dict = {sb["slide_id"]: sb for sb in slide_blocks}

        slides_for_this_section_ui = []
        for arr_item_idx, arr_item in enumerate(arrangement_slide_refs):
            slide_id_ref = arr_item.get("slide_id_ref")
            if slide_id_ref in slide_blocks_dict:
                block_data = slide_blocks_dict[slide_id_ref]
                # Create SlideData (simplified for editor context)
                # The template_settings will be resolved by SlideEditorItemWidget
                instance_id = f"editor_{self._test_section_id}_{slide_id_ref}_{arr_item_idx}" # Make it unique for editor session
                
                # Resolve template settings for this block
                resolved_template_settings = self.template_manager.resolve_slide_template_for_block(
                    block_data, section_to_load_data
                )
                # Populate text_content into resolved_template_settings
                block_content_source = block_data.get('content', {})
                final_text_content = {}
                if resolved_template_settings and "text_boxes" in resolved_template_settings:
                    for tb_def in resolved_template_settings["text_boxes"]:
                        tb_id = tb_def.get("id")
                        if tb_id:
                            final_text_content[tb_id] = block_content_source.get(tb_id, "")
                resolved_template_settings["text_content"] = final_text_content

                # Safely determine background_image_path and background_color
                bg_source_value = block_data.get('background_source')
                bg_image_path_val = None
                bg_color_val = None
                if isinstance(bg_source_value, str):
                    if bg_source_value.startswith('/') or bg_source_value.startswith('C:'): # Basic check for path
                        bg_image_path_val = bg_source_value
                    elif bg_source_value.startswith('#'): # Check for color
                        bg_color_val = bg_source_value

                slide_data_obj = SlideData(
                    id=instance_id,
                    lyrics=final_text_content.get('main_text', ''), # Or more robustly get from first text_box
                    song_title=section_title_for_banner, # Section title
                    overlay_label=block_data.get('label', ''),
                    template_settings=resolved_template_settings,
                    background_image_path=bg_image_path_val,
                    background_color=bg_color_val,
                    notes=block_data.get('notes'),
                    is_enabled_in_arrangement=arr_item.get('enabled', True),
                    banner_color=QColor(block_data.get('ui_banner_color')) if block_data.get('ui_banner_color') else None,
                    section_id_in_manifest=self._test_section_id, # The ID of the section in PM's loaded_sections
                    slide_block_id=slide_id_ref, # The ID of the block within the section file
                    active_arrangement_name_for_section=active_arrangement_name
                )
                slides_for_this_section_ui.append(slide_data_obj)

        all_slides_from_pm = self.presentation_manager.get_slides()
        if not all_slides_from_pm:
            print("MainEditorWindow: WARNING - PresentationManager.get_slides() returned empty after loading test section.")
            # Set banner text even if no slides
            section_title_for_banner = test_section_content.get("title", "Untitled Section") # Get title from loaded content
            if self.section_title_banner_label:
                self.section_title_banner_label.setText(section_title_for_banner)
            else:
                print("Error: section_title_banner_label not found in UI.")
            return
        for slide_data_from_pm in slides_for_this_section_ui: # Use the locally constructed list
            self.add_slide_item(slide_data_from_pm)

        # After loading section data, populate metadata UI
        self._populate_metadata_fields_from_section()

    def _clear_all_slide_items(self):
        """Removes all SlideEditorItemWidgets and thumbnail items."""
        if self.slides_container_layout:
            while self.slides_container_layout.count() > 0:
                item = self.slides_container_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        if self.slide_thumbnails_list_widget:
            self.slide_thumbnails_list_widget.clear()
        print("MainEditorWindow: Cleared all slide items from UI.")
        self._clear_metadata_rows()

    def _populate_all_slide_items(self):
        """Populates the UI with slides from PresentationManager."""
        if not self.presentation_manager: return
        all_slides_from_pm = self.presentation_manager.get_slides()
        print(f"MainEditorWindow: Populating UI with {len(all_slides_from_pm)} slides from PM.")
        for slide_data_from_pm in all_slides_from_pm:
            self.add_slide_item(slide_data_from_pm)
        # Ensure initial thumbnails are generated after repopulating
        self._populate_metadata_fields_from_section()
        QTimer.singleShot(0, self._ensure_initial_thumbnails)



    def add_slide_item(self, slide_data: SlideData): # Changed signature
        if not self.slides_container_layout:
            print("Error: Cannot add slide item, slides_container_layout is not available.")
            return
        new_slide_widget = SlideEditorItemWidget(
            slide_data=slide_data, # Pass SlideData object
            template_manager=self.template_manager,
            slide_renderer=self.slide_renderer, # Pass the slide_renderer
            main_editor_ref=self, # Pass reference to self (MainEditorWindow)
            parent=self.scroll_area_content_widget
        )
        # Connect the new signal from SlideEditorItemWidget to a slot in MainWindow
        new_slide_widget.preview_updated.connect(self._update_thumbnail_for_slide)
        new_slide_widget.banner_color_change_requested.connect(self._handle_slide_item_banner_color_changed)
        new_slide_widget.add_slide_after_requested.connect(self._handle_add_slide_after_requested)
        new_slide_widget.remove_slide_requested.connect(self._handle_remove_slide_requested)
        new_slide_widget.content_changed.connect(self._mark_section_dirty) # Connect the new signal

        self.slides_container_layout.addWidget(new_slide_widget)
        
        # Add a separator line
        separator = QFrame(self.scroll_area_content_widget)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        # separator.setStyleSheet("background-color: #c0c0c0;") # Optional: for a specific color
        self.slides_container_layout.addWidget(separator)

        # Add to thumbnails (placeholder)
        if self.slide_thumbnails_list_widget:
            # Store slide_data.id with the item for later lookup
            display_text = slide_data.overlay_label if slide_data.overlay_label else f"Slide: {slide_data.id[:8]}..." # Use label, fallback to shortened ID
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, slide_data.id) # Store ID
            # Set a placeholder icon size
            self.slide_thumbnails_list_widget.setIconSize(QSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
            if slide_data.banner_color and slide_data.banner_color.isValid():
                list_item.setBackground(QBrush(slide_data.banner_color))
            self.slide_thumbnails_list_widget.addItem(list_item)

        print(f"Added slide item: {slide_data.id}")

    # This method is no longer needed as template selection is per-slide.
    # def on_template_changed(self, template_name: str):
    #     print(f"Global template changed to: {template_name}")

    def get_setting(self, key: str, default_value=None):
        """Provides settings for components like SlideRenderer."""
        if key == "display_checkerboard_for_transparency":
            # For editor previews, usually good to show checkerboard for transparency
            return True
        # Add other settings as needed
        return default_value

    def _create_debug_menu(self):
        # Simple way to add a menu if one doesn't exist, or add to existing
        menu_bar = self.menuBar()
        if not menu_bar:
            menu_bar = QMenuBar(self)
            self.setMenuBar(menu_bar)
        
        debug_menu = menu_bar.addMenu("Debug")
        toggle_hover_action = debug_menu.addAction("Toggle Mouse Hover Debug")
        toggle_hover_action.setCheckable(True)
        toggle_hover_action.toggled.connect(self._toggle_mouse_hover_debug)

    def _toggle_mouse_hover_debug(self, checked: bool):
        if checked and not self._hover_debugger_instance:
            app_instance = QApplication.instance()
            if app_instance:
                self._hover_debugger_instance = MouseHoverDebugger(app_instance) # Parent to app
                app_instance.installEventFilter(self._hover_debugger_instance)
                print("MouseHoverDebugger: ENABLED and installed on application.")
            else:
                print("MouseHoverDebugger: ERROR - QApplication instance not found for installing filter.")
        elif not checked and self._hover_debugger_instance:
            app_instance = QApplication.instance()
            if app_instance:
                app_instance.removeEventFilter(self._hover_debugger_instance)
                self._hover_debugger_instance.deleteLater() # Clean up
                self._hover_debugger_instance = None
                print("MouseHoverDebugger: DISABLED and removed.")
        sys.stdout.flush()
        
    @Slot()
    def _handle_presentation_changed_for_ui_refresh(self):
        print("MainEditorWindow: presentation_changed signal received, refreshing all slide editor items.")
        self._clear_all_slide_items()
        self._populate_all_slide_items()
        self._populate_metadata_fields_from_section()
        # Save button visibility will be updated by its own connection to presentation_changed.

        
    @Slot(QListWidgetItem)
    def _handle_thumbnail_clicked(self, clicked_item: QListWidgetItem):
        if not clicked_item or not self.slides_container_layout:
            return

        slide_id_to_find = clicked_item.data(Qt.ItemDataRole.UserRole)
        if not slide_id_to_find:
            return
        
        print(f"Thumbnail clicked for slide_id: {slide_id_to_find}") # Debug

        for i in range(self.slides_container_layout.count()):
            widget_item = self.slides_container_layout.itemAt(i)
            if widget_item:
                widget = widget_item.widget()
                if isinstance(widget, SlideEditorItemWidget):
                    print(f"Checking SlideEditorItemWidget with id: {widget.slide_data.id if widget.slide_data else 'N/A'}") # Debug
                    if widget.slide_data and widget.slide_data.id == slide_id_to_find:
                        # We found the SlideEditorItemWidget
                        if self.main_slides_scroll_area:
                            print(f"Found target widget: {widget.objectName()} for slide_id: {slide_id_to_find}. Attempting to scroll.") # Debug
                            # Using QTimer.singleShot to ensure layout has settled
                            QTimer.singleShot(0, lambda w=widget: self.main_slides_scroll_area.ensureWidgetVisible(w, 50, 50))
                            # The 50, 50 are x and y margins. Adjust if needed.
                            # This ensures the widget is not just barely visible but has some space around it.
                            
                            # Optional: You might want to give focus or some visual indication
                            # widget.setFocus() # Example
                        break

    def _ensure_initial_thumbnails(self):
        print("MainEditorWindow: Running _ensure_initial_thumbnails...")
        if not self.slides_container_layout or not self.slide_thumbnails_list_widget:
            return

        for i in range(self.slides_container_layout.count()):
            widget = self.slides_container_layout.itemAt(i).widget()
            if isinstance(widget, SlideEditorItemWidget):
                # Check if the corresponding list item already has an icon
                list_item = self.slide_thumbnails_list_widget.item(i // 2) # Assuming 1 separator per item
                if list_item and list_item.icon().isNull(): # Only update if no icon yet
                    current_preview = widget.get_current_preview_pixmap()
                    if current_preview and not current_preview.isNull():
                        self._update_thumbnail_for_slide(widget.slide_data.id, current_preview.copy())

    @Slot(str, QPixmap)
    def _handle_slide_item_banner_color_changed(self, slide_id: str, new_color: Optional[QColor]): # Allow new_color to be None
        if not self.presentation_manager:
            return
        
        # Find the global index of this slide_id
        all_slides = self.presentation_manager.get_slides()
        slide_index = -1
        print(f"DEBUG_MAIN_WINDOW: _handle_slide_item_banner_color_changed for emitted slide_id (block_id): {slide_id}") # DEBUG
        for i, s_data in enumerate(all_slides):
            # 'slide_id' emitted from SlideEditorItemWidget is its self.slide_data.id, which was set from slide_block_id
            if s_data.slide_block_id == slide_id: # Match against slide_block_id from PresentationManager's SlideData
                slide_index = i
                print(f"DEBUG_MAIN_WINDOW: Found match in PM.get_slides() at global index {i} (instance_id: {s_data.id})") # DEBUG
                break
        if slide_index != -1:
            self.presentation_manager.set_slide_banner_color(slide_index, new_color) # PM.set_slide_banner_color should handle None
            # The PresentationManager will emit slide_visual_property_changed,
            # which should trigger SlideEditorItemWidget to update its banner style via a slot (if connected)
            # or MainEditorWindow to refresh relevant parts.
            # For now, let's assume SlideEditorItemWidget needs to be told to refresh its banner.
            # This might require a direct call or another signal.
            # A simpler approach is that set_slide_banner_color in PM emits a signal that
            # SlideUIManager listens to, which then tells the specific SlideEditorItemWidget to refresh.
            # For now, the change is in PM; UI update will follow from its signals.
            print(f"MainEditorWindow: Banner color change requested for slide_id {slide_id} (index {slide_index}) to {new_color.name() if new_color else 'None'}")
        elif slide_index == -1 : # Added elif to only print error if truly not found
            print(f"DEBUG_MAIN_WINDOW: ERROR - Could not find global index for slide_block_id: {slide_id}") # DEBUG

    @Slot(list)
    def _handle_slide_visual_property_update(self, updated_global_indices: list[int]):
        """
        Called when PresentationManager signals that visual properties of some slides have changed.
        Refreshes the UI for those specific slides.
        """
        print(f"DEBUG_MAIN_WINDOW: _handle_slide_visual_property_update for global_indices: {updated_global_indices}") # DEBUG
        all_pm_slides = self.presentation_manager.get_slides() # Get the latest slide data

        for global_idx in updated_global_indices:
            if not (0 <= global_idx < len(all_pm_slides)):
                print(f"DEBUG_MAIN_WINDOW: Skipping invalid global_idx: {global_idx}") # DEBUG
                continue
            
            updated_slide_data = all_pm_slides[global_idx]
            target_instance_id = updated_slide_data.id # Corrected: Use instance_id for matching UI elements
            target_slide_block_id = updated_slide_data.slide_block_id # Corrected
            new_banner_color_from_pm = updated_slide_data.banner_color 
            print(f"DEBUG_MAIN_WINDOW: Processing update for global_idx {global_idx}, slide_block_id: {target_slide_block_id}, new_banner_color: {new_banner_color_from_pm.name() if new_banner_color_from_pm else 'None'}") # DEBUG

            # 1. Refresh the SlideEditorItemWidget's banner
            for i in range(self.slides_container_layout.count()):
                widget_item = self.slides_container_layout.itemAt(i)
                if widget_item and isinstance(widget_item.widget(), SlideEditorItemWidget):
                    editor_widget: SlideEditorItemWidget = widget_item.widget()
                    # editor_widget.slide_data.id was initialized with the instance_id
                    if editor_widget.slide_data and editor_widget.slide_data.id == target_instance_id:
                        print(f"DEBUG_MAIN_WINDOW: Found matching SlideEditorItemWidget for instance_id: {target_instance_id}") # DEBUG
                        # Update only the necessary property in the existing slide_data object
                        # Ensure that if new_banner_color_from_pm is an invalid QColor, we store None
                        if new_banner_color_from_pm and not new_banner_color_from_pm.isValid():
                            editor_widget.slide_data.banner_color = None
                        else:
                            editor_widget.slide_data.banner_color = new_banner_color_from_pm
                        editor_widget.refresh_ui_appearance()
                        # editor_widget.update_slide_preview() # refresh_ui_appearance doesn't change render, so not strictly needed here for banner color
                        break 
            # 2. Refresh the thumbnail background in the QListWidget
            for i in range(self.slide_thumbnails_list_widget.count()):
                list_item = self.slide_thumbnails_list_widget.item(i)
                # list_item stores the instance_id in UserRole
                if list_item and list_item.data(Qt.ItemDataRole.UserRole) == target_instance_id:
                    print(f"DEBUG_MAIN_WINDOW: Found matching QListWidgetItem for instance_id: {target_instance_id}") # DEBUG
                    if new_banner_color_from_pm and new_banner_color_from_pm.isValid():
                        list_item.setBackground(QBrush(new_banner_color_from_pm))
                    else:
                        list_item.setBackground(QBrush(self.palette().base())) # Reset to default background
                    # The icon (pixmap) of the thumbnail doesn't need to change for just a banner color update.
                    break

    @Slot(str, QPixmap)
    def _update_thumbnail_for_slide(self, slide_id: str, preview_pixmap: QPixmap):
        if not self.slide_thumbnails_list_widget or preview_pixmap.isNull():
            print(f"ThumbUpdate: Skipping for {slide_id}. ListWidget: {self.slide_thumbnails_list_widget is not None}, PixmapNull: {preview_pixmap.isNull()}")
            return

        for i in range(self.slide_thumbnails_list_widget.count()):
            item = self.slide_thumbnails_list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == slide_id:
                # Scale the received preview_pixmap (which is 320x180) down to thumbnail size
                thumbnail_pixmap = preview_pixmap.scaled(
                    THUMBNAIL_WIDTH,
                    THUMBNAIL_HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item.setIcon(QIcon(thumbnail_pixmap))
                print(f"ThumbUpdate: Updated icon for slide_id: {slide_id}")
                break

    # --- File Operation Handlers ---
    def handle_new(self):
        print("MainEditorWindow: 'New' action triggered (Not yet fully implemented for this editor).")
        # This editor is focused on the test section. "New" might not be applicable
        # or would need to clear the current test setup and PresentationManager.
        pass

    def handle_load(self):
        print("MainEditorWindow: 'Load' action triggered (Not yet fully implemented for this editor).")
        # This editor is focused on the test section.
        pass

    def handle_save(self) -> bool:
        print("MainEditorWindow: 'Save Changes' (for test section) action triggered.")
        if not self._test_section_id or not self.presentation_manager:
            print("MainEditorWindow: Test section ID or PresentationManager not available. Cannot save.")
            return False

        if self._test_section_id in self.presentation_manager.loaded_sections:
            section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
            if section_wrapper.get("is_dirty"):
                section_content_data = section_wrapper.get("section_content_data")
                section_filepath = section_wrapper.get("resolved_filepath")

                if section_content_data and section_filepath:
                    try:
                        # --- Update slide_blocks in section_content_data from UI widgets ---
                        # This is crucial to save text changes and template changes made in SlideEditorItemWidgets.
                        if "slide_blocks" in section_content_data and self.slides_container_layout:
                            # Create a map of slide_block_id to its data in section_content_data for efficient update
                            slide_blocks_map_from_file = {
                                block.get("slide_id"): block
                                for block in section_content_data["slide_blocks"]
                                if block.get("slide_id") # Ensure block has a slide_id
                            }

                            for i in range(self.slides_container_layout.count()):
                                widget_item = self.slides_container_layout.itemAt(i)
                                if widget_item and isinstance(widget_item.widget(), SlideEditorItemWidget):
                                    editor_widget: SlideEditorItemWidget = widget_item.widget()
                                    widget_slide_data = editor_widget.slide_data # This is the SlideData object held by the widget

                                    if widget_slide_data and widget_slide_data.slide_block_id in slide_blocks_map_from_file:
                                        target_block_in_section_file = slide_blocks_map_from_file[widget_slide_data.slide_block_id]

                                        # Update the 'content' field (text)
                                        target_block_in_section_file["content"] = widget_slide_data.template_settings.get("text_content", {})

                                        # Update template_id
                                        target_block_in_section_file["template_id"] = widget_slide_data.template_settings.get("layout_name")

                                        # Update banner color
                                        if widget_slide_data.banner_color and widget_slide_data.banner_color.isValid():
                                            target_block_in_section_file["ui_banner_color"] = widget_slide_data.banner_color.name(QColor.HexArgb)
                                        elif "ui_banner_color" in target_block_in_section_file: # If it was set and now is None
                                            target_block_in_section_file["ui_banner_color"] = None

                                        # Update other direct fields if necessary (label, background_source, notes)
                                        target_block_in_section_file["label"] = widget_slide_data.overlay_label
                                        target_block_in_section_file["background_source"] = widget_slide_data.background_image_path
                                        target_block_in_section_file["notes"] = widget_slide_data.notes
                                    elif widget_slide_data:
                                        print(f"MainEditorWindow: Warning - Slide block ID '{widget_slide_data.slide_block_id}' from UI widget not found in section_content_data for saving.")
                        # --- End of update slide_blocks ---

                        # Gather metadata from UI and update section_content_data
                        updated_metadata_list_to_save = []
                        for row_data in self._metadata_row_widgets_store:
                            if not row_data.get("is_savable", True): # Skip non-savable entries
                                continue

                            key_widget = row_data["key_ui"]
                            value_widget = row_data["value_ui"]
                            
                            key_text = ""
                            if isinstance(key_widget, QLineEdit):
                                key_text = key_widget.text()
                            elif isinstance(key_widget, QLabel): # Predefined keys are QLabels in the UI
                                key_text = key_widget.text()
                            
                            # Value can be QLineEdit or QLabel (for non-editable like SectionTitle, though non-savable ones are skipped)
                            value_text = value_widget.text() if hasattr(value_widget, 'text') else ""

                            if key_text: # Only save if key is not empty
                                updated_metadata_list_to_save.append({"key": key_text, "value": value_text})
                        
                        section_content_data["metadata"] = updated_metadata_list_to_save
                        self.presentation_manager.io_handler.save_json_file(section_content_data, section_filepath)
                        print(f"MainEditorWindow: Saved test section '{os.path.basename(section_filepath)}' to {section_filepath}")
                        section_wrapper["is_dirty"] = False # Mark the specific section as not dirty
                        # The overall dirty status of the manifest is managed by PresentationManager itself.
                        self.section_content_saved.emit(self._test_section_id) # Emit signal
                        self._update_save_button_visibility()
                        return True
                    except Exception as e:
                        print(f"MainEditorWindow: Error saving test section '{os.path.basename(section_filepath)}': {e}")
                        return False
                else:
                    print(f"MainEditorWindow: Warning - Cannot save test section '{self._test_section_id}', missing content or resolved path.")
            else:
                print("MainEditorWindow: Test section is not dirty. Nothing to save.")
                self._update_save_button_visibility() # Ensure button hides if somehow shown for non-dirty
                return True # No error, just nothing to do
        else:
            print(f"MainEditorWindow: Test section ID '{self._test_section_id}' not found in loaded sections.")
        return False

    def handle_save_as(self) -> bool:
        print("MainEditorWindow: 'Save As' action triggered (Not yet fully implemented for this editor).")
        # This editor is focused on the test section. "Save As" for the whole test presentation
        # would involve saving a new manifest and potentially copying the section.
        return False # Placeholder

    @Slot()
    def _update_save_button_visibility(self):
        if not hasattr(self, 'save_sidebar_button') or not self.save_sidebar_button:
            print("DEBUG_MAIN_WINDOW: _update_save_button_visibility - save_sidebar_button attribute not found or is None.") # DEBUG
            return
        
        # Check the dirty state of the *current test section* being edited in this window.
        current_section_is_dirty = False
        if self.presentation_manager and self._test_section_id:
            if self._test_section_id in self.presentation_manager.loaded_sections:
                section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
                current_section_is_dirty = section_wrapper.get("is_dirty", False)
            else:
                # Section ID known but not in loaded_sections, treat as not dirty for this button's purpose
                print(f"DEBUG_MAIN_WINDOW: _update_save_button_visibility - _test_section_id '{self._test_section_id}' not in loaded_sections.") # DEBUG
        
        print(f"DEBUG_MAIN_WINDOW: _update_save_button_visibility called. Current section ('{self._test_section_id}') is_dirty = {current_section_is_dirty}") # DEBUG
        
        if current_section_is_dirty:
            self.save_sidebar_button.show()
            print("DEBUG_MAIN_WINDOW: Save button SHOWN.") # DEBUG
        else:
            self.save_sidebar_button.hide()
            print("DEBUG_MAIN_WINDOW: Save button HIDDEN.") # DEBUG

    @Slot(str)
    def _handle_add_slide_after_requested(self, current_slide_instance_id: str):
        if not self.presentation_manager: return
        print(f"MainEditorWindow: Add slide after requested for instance_id: {current_slide_instance_id}")

        arrangement_info = self.presentation_manager._get_arrangement_info_from_instance_id(current_slide_instance_id)
        if not arrangement_info:
            print(f"MainEditorWindow: Could not find arrangement info for instance_id {current_slide_instance_id}")
            return

        section_id_in_manifest = arrangement_info["section_id_in_manifest"]
        arrangement_name = arrangement_info["arrangement_name"]
        index_in_arrangement = arrangement_info["index_in_arrangement"]

        # Create new slide block data
        new_slide_block_id = f"slide_{uuid.uuid4().hex[:12]}"
        # Use SectionFactory to get default slide block structure
        # SectionFactory.create_new_section_data creates a whole section. We need just a slide block.
        # Let's define a simple default slide block here or add a method to SectionFactory.
        # For now, a simple default:
        config = ApplicationConfigManager() 
        user_default_template_id_setting = config.get_app_setting("new_slide_default_template_id", None)
        actual_template_id_for_new_slide = None if user_default_template_id_setting == "None" or user_default_template_id_setting is None else user_default_template_id_setting

        new_slide_block_data = {
            "slide_id": new_slide_block_id,
            "label": "New Slide",
            "content": {"main_text": ""},
            "template_id": actual_template_id_for_new_slide, # Use user's default or None
            "background_source": None,
            "notes": None
        }

        success = self.presentation_manager.add_slide_block_to_section(
            section_id_in_manifest,
            new_slide_block_data,
            arrangement_name,
            at_index_in_arrangement=index_in_arrangement + 1 # Insert after current
        )
        if success:
            print(f"MainEditorWindow: Successfully requested to add new slide block '{new_slide_block_id}' after index {index_in_arrangement} in '{arrangement_name}'.")
        else:
            print(f"MainEditorWindow: Failed to add new slide block.")

    @Slot(str)
    def _handle_remove_slide_requested(self, slide_instance_id_to_remove: str):
        if not self.presentation_manager: return
        print(f"MainEditorWindow: Remove slide requested for instance_id: {slide_instance_id_to_remove}")
        # TODO: Add confirmation dialog here?
        # reply = QMessageBox.question(self, "Remove Slide", "Are you sure you want to remove this slide?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        # if reply == QMessageBox.Yes:
        deleted_info = self.presentation_manager.delete_slide_reference_from_arrangement(slide_instance_id_to_remove)
        if deleted_info:
            print(f"MainEditorWindow: Successfully requested to remove slide instance '{slide_instance_id_to_remove}'.")
        else:
            print(f"MainEditorWindow: Failed to remove slide instance '{slide_instance_id_to_remove}'.")
            
    @Slot(bool)
    def _toggle_section_properties_content(self, checked: bool):
        """Shows or hides the content container of the section properties group box."""
        if self.section_properties_content_container:
            self.section_properties_content_container.setVisible(checked)
            # print(f"Section properties content visibility set to: {checked}") # Optional debug
        else:
            print("Error: _toggle_section_properties_content - section_properties_content_container is None.")
            
    # --- Metadata Field Methods ---
    def _clear_metadata_rows(self):
        if not self.metadata_entries_layout:
            return
        while self.metadata_entries_layout.count() > 0:
            item = self.metadata_entries_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._metadata_row_widgets_store.clear()

    def _populate_metadata_fields_from_section(self):
        self._clear_metadata_rows()
        if not self._test_section_id or not self.presentation_manager or \
           self._test_section_id not in self.presentation_manager.loaded_sections:
            print("MainEditorWindow: Cannot populate metadata, test section not loaded.")
            return
        
        section_data = self.presentation_manager.loaded_sections[self._test_section_id]["section_content_data"]
        section_title = section_data.get("title", "N/A")

        # Add the non-editable, non-savable SectionTitle first
        self._add_metadata_row_widget(
            key_text="SectionTitle",
            value_text=section_title,
            is_predefined_key=True, # Key is a QLabel
            value_is_editable=False, # Value is a QLabel
            is_removable=False,
            is_savable=False, # Do not save this derived entry
            connect_signals=False # No user interaction to mark dirty
        )

        # Then add user-defined metadata from the file
        metadata_list = section_data.get("metadata", [])
        predefined_keys = ["Artist", "CCLI", "Performer"]
        for item in metadata_list:
            key = item.get("key")
            value = item.get("value", "")
            if key:
                is_predefined = key in predefined_keys
                self._add_metadata_row_widget(key, value, is_predefined_key=is_predefined, connect_signals=True)
    
    def _show_add_metadata_menu(self):
        menu = QMenu(self)
        
        artist_action = menu.addAction("Add Artist")
        artist_action.triggered.connect(lambda: self._handle_add_predefined_metadata_field("Artist"))
        
        ccli_action = menu.addAction("Add CCLI")
        ccli_action.triggered.connect(lambda: self._handle_add_predefined_metadata_field("CCLI"))

        performer_action = menu.addAction("Add Performer")
        performer_action.triggered.connect(lambda: self._handle_add_predefined_metadata_field("Performer"))

        menu.addSeparator()
        custom_action = menu.addAction("Add Custom Field...")
        custom_action.triggered.connect(self._handle_add_custom_metadata_field)

        menu.exec(self.add_metadata_button.mapToGlobal(QPoint(0, self.add_metadata_button.height())))

    def _handle_add_predefined_metadata_field(self, key_name: str):
        # Check if this predefined key already exists
        for row_data in self._metadata_row_widgets_store:
            key_widget = row_data["key_ui"]
            if isinstance(key_widget, QLabel) and key_widget.text() == key_name:
                print(f"MainEditorWindow: Metadata field '{key_name}' already exists.")
                # Optionally, focus the existing field or show a message
                return 
        
        self._add_metadata_row_widget(key_name, "", is_predefined_key=True, connect_signals=True)
        self._mark_section_dirty()

    def _handle_add_custom_metadata_field(self):
        self._add_metadata_row_widget("NewCustomKey", "", is_predefined_key=False, connect_signals=True)
        self._mark_section_dirty()

    def _add_metadata_row_widget(self,
                                 key_text: str,
                                 value_text: str,
                                 is_predefined_key: bool, # Renamed for clarity
                                 value_is_editable: bool = True,
                                 is_removable: bool = True,
                                 is_savable: bool = True,
                                 connect_signals: bool = True):
        if not self.metadata_entries_layout:
            return

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0,0,0,0) # Compact layout
        row_layout.setSpacing(5) # Add a little spacing between elements in the row

        # --- Key UI Element ---
        key_ui_element: QWidget
        if is_predefined_key:
            key_label = QLabel(key_text)
            key_label.setFixedWidth(80) # Give some fixed width to labels
            key_ui_element = key_label
        else:
            key_edit = QLineEdit(key_text)
            key_edit.setPlaceholderText("Custom Key")
            if connect_signals and is_savable: # Only connect if it can affect dirty state
                key_edit.textChanged.connect(self._mark_section_dirty)
            key_ui_element = key_edit
        
        # --- Value UI Element ---
        value_ui_element: QWidget
        if value_is_editable:
            value_edit = QLineEdit(value_text)
            value_edit.setPlaceholderText("Value")
            if connect_signals and is_savable: # Only connect if it can affect dirty state
                value_edit.textChanged.connect(self._mark_section_dirty)
            value_ui_element = value_edit
        else: # Not editable, use a QLabel
            value_label = QLabel(value_text)
            value_label.setWordWrap(True) # Allow wrapping for potentially long titles
            value_ui_element = value_label

        row_layout.addWidget(key_ui_element)
        row_layout.addWidget(value_ui_element, 1) # Give value field more stretch factor

        if is_removable:
            remove_button = QPushButton("-")
            remove_button.setFixedSize(25, 25)
            remove_button.clicked.connect(lambda checked=False, rw=row_widget: self._remove_metadata_row(rw))
            row_layout.addWidget(remove_button)
        
        # Insert before the spacer if it exists
        spacer_item = self.metadata_entries_layout.itemAt(self.metadata_entries_layout.count() -1)
        if spacer_item and spacer_item.spacerItem(): # Check if it's a QSpacerItem
            self.metadata_entries_layout.insertWidget(self.metadata_entries_layout.count() -1, row_widget)
        else: # No spacer, or it's not the last item (should not happen with current UI)
            self.metadata_entries_layout.addWidget(row_widget)

        self._metadata_row_widgets_store.append({
            "widget": row_widget,
            "key_ui": key_ui_element,
            "value_ui": value_ui_element,
            "is_predefined_key": is_predefined_key,
            "is_savable": is_savable
        })

    def _remove_metadata_row(self, row_widget_to_remove: QWidget):
        if not self.metadata_entries_layout: return

        for i, row_data in enumerate(self._metadata_row_widgets_store):
            if row_data["widget"] == row_widget_to_remove:
                # Remove from layout
                self.metadata_entries_layout.removeWidget(row_widget_to_remove)
                row_widget_to_remove.deleteLater()
                # Remove from our store
                del self._metadata_row_widgets_store[i]
                self._mark_section_dirty()
                print(f"MainEditorWindow: Removed metadata row.")
                break

    def _mark_section_dirty(self):
        if self._test_section_id and self.presentation_manager and \
           self._test_section_id in self.presentation_manager.loaded_sections:
            
            # Call PresentationManager's method to set dirty status, which will also emit presentation_changed
            self.presentation_manager.set_section_dirty_status(self._test_section_id, True)

            self._update_save_button_visibility()
        else:
            print("MainEditorWindow: Could not mark section dirty (no test_section_id or PM).")

    def get_current_section_metadata(self) -> Optional[list[dict]]:
        """Returns the metadata list for the currently loaded test section."""
        if self._test_section_id and self.presentation_manager and \
           self._test_section_id in self.presentation_manager.loaded_sections:
            section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
            section_content_data = section_wrapper.get("section_content_data", {})
            return section_content_data.get("metadata", [])
        print("MainEditorWindow: get_current_section_metadata - Could not retrieve metadata (section not loaded or PM issue).")
        return None

    def get_current_section_title(self) -> Optional[str]:
        """Returns the title for the currently loaded test section."""
        if self._test_section_id and self.presentation_manager and \
           self._test_section_id in self.presentation_manager.loaded_sections:
            section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
            section_content_data = section_wrapper.get("section_content_data", {})
            return section_content_data.get("title") # Get the 'title' field
        print("MainEditorWindow: get_current_section_title - Could not retrieve title (section not loaded or PM issue).")
        return None

    def closeEvent(self, event: QEvent): # QEvent is correct for closeEvent
        is_dirty = False
        if self.presentation_manager and self._test_section_id and \
           self._test_section_id in self.presentation_manager.loaded_sections:
            section_wrapper = self.presentation_manager.loaded_sections[self._test_section_id]
            is_dirty = section_wrapper.get("is_dirty", False)

        if is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Save before closing?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save)
            if reply == QMessageBox.StandardButton.Save:
                if self.handle_save(): # If save is successful
                    pass # Proceed to close
                else: # Save failed or was cancelled by user
                    event.ignore() 
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            # If Discard, fall through to accept
        
        if self in _open_editor_windows:
            _open_editor_windows.remove(self)
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # For standalone testing, we need a mock PresentationManager and a section ID.
    # This is more complex now. For simplicity, we'll assume it loads the default test section.
    mock_pm = PresentationManager(template_manager=TemplateManager())
    # The MainEditorWindow will create the "Test Song Example" section if section_id_to_edit is None.
    main_editor = MainEditorWindow(presentation_manager_ref=mock_pm, section_id_to_edit=None)
    
    # Keep a reference to the window
    _open_editor_windows.append(main_editor)

    main_editor.show()
    sys.exit(app.exec())
