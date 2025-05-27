import sys
import os
import json # For writing the test section file
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QScrollArea, QComboBox, 
    QListWidget, QApplication, QLabel, QFrame
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QFileInfo, QDir, QEvent, QObject # Added QEvent, QObject

# Attempt to import PluckyStandards for directory paths
try:
    from core.plucky_standards import PluckyStandards
except ImportError:
    # If running directly from 'windows' and 'core' is a sibling, adjust path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.plucky_standards import PluckyStandards
    from core.template_manager import TemplateManager # Import TemplateManager
    from data_models.slide_data import SlideData      # For SlideData objects
    from rendering.slide_renderer import LayeredSlideRenderer # For rendering
    from core.image_cache_manager import ImageCacheManager # Dependency for renderer    
    from PySide6.QtGui import QColor, QCursor # Added for banner_qcolor and QCursor
    
# Import the custom slide item widget
from slide_editor_item_widget import SlideEditorItemWidget

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

class MainEditorWindow(QMainWindow):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        # --- Initialize Hover Debugger (can be toggled later) ---
        self._hover_debugger_instance: Optional[MouseHoverDebugger] = None

        # Instantiate TemplateManager
        self.template_manager = TemplateManager()
        # Instantiate Renderer and its dependencies
        self.image_cache_manager = ImageCacheManager()
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
        self.scroll_area_content_widget: QWidget = self.findChild(QWidget, "scrollAreaContentWidget")
        self.slides_container_layout: QVBoxLayout = None

        if self.scroll_area_content_widget:
            self.slides_container_layout = self.scroll_area_content_widget.layout()
            if not self.slides_container_layout: # If layout wasn't set in Qt Designer
                 self.slides_container_layout = QVBoxLayout(self.scroll_area_content_widget)
                 print("Warning: slides_container_layout was not set in UI, created dynamically.")
        else:
            print("Error: scrollAreaContentWidget not found!")

        self.slide_thumbnails_list_widget: QListWidget = self.findChild(QListWidget, "slide_thumbnails_list_widget")

        # Connect signals or add initial items
        # The global templates_combo_box is removed, so this connection is also removed.
        # if self.templates_combo_box:
        #     self.templates_combo_box.currentTextChanged.connect(self.on_template_changed)

        # The 'loaded_ui_window' instance has served its purpose of providing the initial structure.
        # Since its central widget (and potentially menubar etc.) has been reparented to 'self',
        # 'loaded_ui_window' is now an empty shell. It's also a child of 'self' due to the parent argument in load().
        # Qt's parent-child system should manage its lifecycle. Or, you could explicitly:
        # loaded_ui_window.deleteLater() # If you want to be sure it's cleaned up and not lingering.
        
        # --- Setup and add items from the test section ---
        self._setup_and_load_test_section_items()
        
        # --- Example: Add a simple menu to toggle the hover debugger ---
        self._create_debug_menu()


    def _setup_and_load_test_section_items(self):
        """
        Creates the test section file if it doesn't exist and then
        adds slide items to the UI based on its content.
        """
        test_section_filename = "Test Song Example.plucky_section"
        test_section_content = {
            "version": "1.0.0", "id": "song_f93d922b4b4e4bb09bbbb300c6c0173e", "title": "Test Song Example",
            "artist": None, "ccli_number": None, "tags": [],
            "slide_blocks": [
                {"slide_id": "slide_98a32b0b648f", "label": "Verse 1", "content": {"main_text": "Lyrics of the first verse"}, "template_id": "TestLyrics", "background_source": None, "notes": None},
                {"slide_id": "slide_0cdf2f98e93a", "label": "Title Slide", "content": {"main_text": "Test Song Title", "Player": "Player Name", "Writer": "Writer Name"}, "template_id": "TestTitle", "background_source": None, "notes": None},
                {"slide_id": "slide_65215e57c9f9", "label": "Verse 2", "content": {"main_text": "Lyrics of the second verse"}, "template_id": "TestLyrics", "background_source": None, "notes": None, "ui_banner_color": "#ff63f7ff"},
                {"slide_id": "slide_eabe0a658a80", "label": "Verse 3", "content": {"main_text": "Lyrics of the third verse"}, "template_id": "TestLyrics", "background_source": None, "notes": None},
                {"slide_id": "slide_c8a39151cfcd", "label": "Chorus 1", "content": {"main_text": "Chorus Chorus Chorus A"}, "template_id": "TestLyrics", "background_source": None, "notes": None},
                {"slide_id": "slide_2055ac0c9187", "label": "Chorus 2", "content": {"main_text": "Chorus Chorus Chorus B"}, "template_id": "TestLyrics", "background_source": None, "notes": None},
                {"slide_id": "slide_1b1144bd508d", "label": "Ending Slide", "content": {"main_text": "Final words for the song"}, "template_id": "TestLyrics", "background_source": None, "notes": None}
            ],
            "arrangements": {
                "Default": [
                    {"slide_id_ref": "slide_0cdf2f98e93a", "enabled": True},
                    {"slide_id_ref": "slide_98a32b0b648f", "enabled": True},
                    {"slide_id_ref": "slide_c8a39151cfcd", "enabled": True},
                    {"slide_id_ref": "slide_65215e57c9f9", "enabled": True},
                    {"slide_id_ref": "slide_2055ac0c9187", "enabled": True},
                    {"slide_id_ref": "slide_eabe0a658a80", "enabled": True},
                    {"slide_id_ref": "slide_1b1144bd508d", "enabled": True}
                ]
            }
        }

        # Ensure UserStore/Sections directory exists and write the file
        try:
            sections_dir = PluckyStandards.get_sections_dir()
            if not os.path.exists(sections_dir):
                os.makedirs(sections_dir)
                print(f"Created directory: {sections_dir}")

            test_section_filepath = os.path.join(sections_dir, test_section_filename)
            
            # Write the file (or overwrite if it exists, for testing consistency)
            with open(test_section_filepath, 'w') as f:
                json.dump(test_section_content, f, indent=4)
            print(f"Test section file '{test_section_filename}' ensured at: {test_section_filepath}")

        except Exception as e:
            print(f"Error setting up test section file: {e}")
            # Fallback to adding a couple of default items if file setup fails
            self.add_slide_item("error_slide_1")
            self.add_slide_item("error_slide_2")
            return

        # Add slide items based on the test_section_content
        if "slide_blocks" in test_section_content:
            for i, slide_block in enumerate(test_section_content["slide_blocks"]):
                slide_id_from_block = slide_block.get("slide_id", f"missing_id_{i}")
                template_id_from_block = slide_block.get("template_id", "Default Layout") 
                content_data_from_block = slide_block.get("content", {})
                background_source_from_block = slide_block.get("background_source")
                label_from_block = slide_block.get("label", "")
                banner_color_hex = slide_block.get("ui_banner_color")
                banner_qcolor = QColor(banner_color_hex) if banner_color_hex else None


                # Resolve template settings using TemplateManager
                # This should return the full structure including text_boxes, styles, etc.
                template_settings = self.template_manager.resolve_layout_template(template_id_from_block)
                if not template_settings: # Fallback if resolution fails
                    print(f"Warning: Could not resolve template '{template_id_from_block}' for slide '{slide_id_from_block}'. Using minimal fallback.")
                    template_settings = {"layout_name": template_id_from_block, "text_boxes": [], "text_content": {}}

                # Ensure 'text_content' is part of template_settings and populate it
                current_text_content = {}
                if "text_boxes" in template_settings:
                    for tb_def in template_settings["text_boxes"]:
                        tb_id = tb_def.get("id")
                        if tb_id: # Only process if text box has an ID
                            current_text_content[tb_id] = content_data_from_block.get(tb_id, "") # Get content or default to empty
                template_settings["text_content"] = current_text_content

                bg_image_path, bg_color = None, None
                if background_source_from_block:
                    if background_source_from_block.startswith('#'): bg_color = background_source_from_block
                    else: bg_image_path = background_source_from_block

                slide_data_for_item = SlideData(
                    id=slide_id_from_block, lyrics="", song_title=test_section_content.get("title", "Test Section"), # lyrics is legacy
                    overlay_label=label_from_block, template_settings=template_settings,
                    background_image_path=bg_image_path, background_color=bg_color, banner_color=banner_qcolor
                )
                self.add_slide_item(slide_data_for_item)
        else:
            print("Warning: Test section content does not contain 'slide_blocks'. No items added.")

    def add_slide_item(self, slide_data: SlideData): # Changed signature
        if not self.slides_container_layout:
            print("Error: Cannot add slide item, slides_container_layout is not available.")
            return
        new_slide_widget = SlideEditorItemWidget(
            slide_data=slide_data, # Pass SlideData object
            template_manager=self.template_manager,
            slide_renderer=self.slide_renderer, # Pass the slide_renderer
            parent=self.scroll_area_content_widget
        )
        self.slides_container_layout.addWidget(new_slide_widget)
        
        # Add a separator line
        separator = QFrame(self.scroll_area_content_widget)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        # separator.setStyleSheet("background-color: #c0c0c0;") # Optional: for a specific color
        self.slides_container_layout.addWidget(separator)

        # Add to thumbnails (placeholder)
        if self.slide_thumbnails_list_widget:
            self.slide_thumbnails_list_widget.addItem(f"Thumbnail for {slide_data.id}")

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    main_editor = MainEditorWindow()
    main_editor.show()
    sys.exit(app.exec())
