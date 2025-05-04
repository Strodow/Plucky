# c:\Users\Logan\Documents\Plucky\mainwindow.py

# --- Standard Library Imports ---
import sys
import json
import os
import time # Import the time module

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QFrame, QSizePolicy, QSpacerItem,
    QScrollArea, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QFileDialog, QSlider,
    QSplitter, QMessageBox # Import QSplitter and QMessageBox
)
from PySide6.QtCore import Qt, QMimeData, QRect, QSize, QEvent # Import QSize, QEvent
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter # Removed QDrag, QMouseEvent, Added QPainter for splash

# --- Local Imports ---
from button_widgets import ButtonGridWidget
from lyric_display_window import LyricDisplayWindow
from settings_dialog import SettingsDialog # Import the new dialog
# from custom_widgets import DraggableButton # No longer using DraggableButton
from button_remake import LyricCardWidget # Assuming button_remake.py contains the updated LyricCardWidget
from song_list_widget import SongListWidget # Import the new song list widget
from song_section_editor_window import SongSectionEditorWindow # Import the new section editor window
from song_metadata_editor_window import SongMetadataEditorWindow # Import the new metadata editor window
from PySide6.QtWidgets import QSplashScreen # Import QSplashScreen

# --- Main Window Class ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Application")

        # --- Store current screen index ---
        self.current_screen_index = 0
        self._last_clicked_button = None # Track the highlighted button
        self.app_settings = {} # Dictionary for persistent app settings (screen, colors, etc.)
        self.load_stats = {} # Dictionary to store loading times
        self._button_id_to_widget_map = {} # Map button_id to LyricCardWidget instance
        self._editor_windows = {} # To keep references to open editor windows (key: ('song', song_key) or ('section', button_id))
        self._ordered_buttons = [] # List to store LyricCardWidgets in grid order

        # --- Basic UI Structure Setup (moved data loading out) ---
        # ButtonGridWidget now primarily acts as a container for the grid layout
        self.button_area = ButtonGridWidget() # Create this before _setup_main_ui

        # Setup main UI structure (without populating data yet)
        self._setup_main_ui_structure()

        # Allow the main window to receive focus via click or tabbing
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setGeometry(100, 100, 800, 600)

    def perform_initial_load(self, splash=None):
        """Performs data loading and UI population, updating the splash screen."""
        overall_start_time = time.time()
        self._update_splash(splash, "Loading application settings...")
        self.load_stats['app_settings_load_time'] = self._load_app_settings() # Load app settings first
        self._update_splash(splash, "Loading template settings...")
        self.load_stats['template_load_time'] = self._load_template_settings()

        self._update_splash(splash, "Loading song data...")
        # Setup lyric window AFTER template settings are loaded
        self._setup_lyric_window()
        self.load_stats['song_data_load_time'] = self._load_songs_data()
        self._update_splash(splash, "Populating UI...")
        # UI population timing is handled within _populate_ui_elements
        self._populate_ui_elements(splash) # New method to handle population

    # --------------------------------------------------------------------------
    # Initialization Helper Methods
    # --------------------------------------------------------------------------
    def _load_app_settings(self):
        """Loads persistent application settings (screen index, colors, etc.)."""
        start_time = time.time()
        default_settings = {
            "output_screen_index": 0,
            "card_background_color": "#000000" # Default to black
        }
        settings_file_path = "app_settings.json"
        if os.path.exists(settings_file_path):
            try:
                with open(settings_file_path, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    # Merge loaded settings with defaults to ensure all keys exist
                    self.app_settings = {**default_settings, **loaded_settings}
                print(f"Successfully loaded app settings from {settings_file_path}")
            except json.JSONDecodeError:
                print(f"Error: Could not decode {settings_file_path}. Using default settings.")
                self.app_settings = default_settings
            except Exception as e:
                print(f"An unexpected error occurred while loading app settings: {e}")
                print("Using default settings.")
                self.app_settings = default_settings
        else:
            print(f"Warning: App settings file not found at {settings_file_path}.")
            print("Using default settings.")
            self.app_settings = default_settings

        self.current_screen_index = self.app_settings.get("output_screen_index", 0) # Update current index from loaded/default settings
        return time.time() - start_time
    
    
    def _load_template_settings(self):
        """Loads lyric display template settings from template.json."""
        start_time = time.time()
        self.lyric_template_settings = {}
        template_file_path = "template.json"
        if os.path.exists(template_file_path):
            try:
                with open(template_file_path, "r", encoding="utf-8") as f:
                    self.lyric_template_settings = json.load(f)
                print(f"Successfully loaded template from {template_file_path}")
            except json.JSONDecodeError:
                print(f"Error: Could not decode {template_file_path}. Check file format.")
                print("Using default lyric display settings.")
            except Exception as e:
                print(f"An unexpected error occurred while loading template: {e}")
                print("Using default lyric display settings.")
        else:
            print(f"Warning: Template file not found at {template_file_path}.")
            print("Using default lyric display settings.")
        return time.time() - start_time

    def _load_songs_data(self):
        """Loads song data from JSON files in the 'songs' directory."""
        start_time = time.time()
        loaded_songs = {}
        songs_directory = "songs"
        order_file_path = "song_order.json"
        ordered_keys = []
        order_applied = False

        # 1. Load all songs from the directory into a temporary dictionary
        if os.path.exists(songs_directory) and os.path.isdir(songs_directory):
            for filename in os.listdir(songs_directory):
                if filename.endswith(".json"):
                    file_path = os.path.join(songs_directory, filename)
                    song_key = os.path.splitext(filename)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            song_data = json.load(f)
                            loaded_songs[song_key] = song_data
                            print(f"Loaded song: {song_data.get('title', song_key)}")
                    except json.JSONDecodeError:
                        print(f"Error: Could not decode JSON in {filename}. Skipping.")
                    except Exception as e:
                        print(f"An unexpected error occurred while loading {filename}: {e}")
                        print("Skipping song.")

        # 2. Try to load the order from song_order.json
        if os.path.exists(order_file_path):
            try:
                with open(order_file_path, "r", encoding="utf-8") as f:
                    ordered_keys = json.load(f)
                    if isinstance(ordered_keys, list):
                        print(f"Successfully loaded song order from {order_file_path}")
                        order_applied = True
                    else:
                        print(f"Warning: Content of {order_file_path} is not a JSON list. Ignoring order file.")
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON in {order_file_path}. Ignoring order file.")
            except Exception as e:
                print(f"An unexpected error occurred while loading {order_file_path}: {e}. Ignoring order file.")
        else:
            print(f"Info: Order file {order_file_path} not found. Songs will be sorted alphabetically by key.")

        # 3. Create the final ordered self.songs_data dictionary
        self.songs_data = {}
        keys_to_process = ordered_keys if order_applied else sorted(loaded_songs.keys())
        processed_keys = set()

        for key in keys_to_process:
            if key in loaded_songs:
                self.songs_data[key] = loaded_songs[key]
                processed_keys.add(key)
            elif order_applied: # Only warn if using the order file
                print(f"Warning: Song key '{key}' found in {order_file_path} but no matching file found in '{songs_directory}'.")

        # # 4. Add any songs found in the directory but not listed in the order file (append alphabetically)
        # # --- If you want to ONLY load songs listed in song_order.json, keep this section commented out ---
        # remaining_keys = sorted(list(set(loaded_songs.keys()) - processed_keys))
        # if remaining_keys:
        #     print(f"Info: Appending songs found in directory but not in {order_file_path}: {', '.join(remaining_keys)}")
        #     for key in remaining_keys:
        #         self.songs_data[key] = loaded_songs[key]

        if not self.songs_data:
             print(f"Warning: No songs loaded. Check the '{songs_directory}' directory and '{order_file_path}' if used.")
        return time.time() - start_time

    def _setup_main_ui_structure(self):
        """Sets up the main window's UI elements (buttons, scroll area, layout)."""
        # --- Top Controls Layout ---
        top_button_layout = QHBoxLayout()
        top_button_layout.setContentsMargins(10, 5, 10, 5)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        top_button_layout.addWidget(self.settings_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_data_and_ui)
        top_button_layout.addWidget(self.refresh_button)

        # self.stats_button = QPushButton("Show Load Stats") # Removed from here
        # self.stats_button.clicked.connect(self._show_load_stats)
        # top_button_layout.addWidget(self.stats_button) # Removed from here

        # --- Column Slider ---
        top_button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)) # Spacer
        top_button_layout.addWidget(QLabel("Columns:"))
        self.column_slider = QSlider(Qt.Orientation.Horizontal)
        self.column_slider.setMinimum(1)
        self.column_slider.setMaximum(10) # Adjust max columns as needed
        # Set initial value from the button_area's default
        initial_cols = getattr(self.button_area, 'max_cols', 4) # Default to 4 if not found
        self.column_slider.setValue(initial_cols)
        self.column_slider.setTickInterval(1)
        self.column_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.column_slider.valueChanged.connect(self._update_column_count)
        top_button_layout.addWidget(self.column_slider)
        self.column_count_label = QLabel(str(initial_cols)) # Display initial value
        top_button_layout.addWidget(self.column_count_label)

        top_button_layout.addStretch(1)

        # --- Song List Widget ---
        self.song_list = SongListWidget()
        self.song_list.section_selected.connect(self._handle_song_list_selection)
        self.song_list.song_title_selected.connect(self._handle_song_title_selection) # Connect new signal
        self.song_list.edit_song_requested.connect(self._open_song_editor) # Connect edit signal

        # --- Scroll Area (containing button grid) ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.button_area)

        # --- Splitter for Song List and Button Grid ---
        self.central_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.central_splitter.addWidget(self.song_list)
        self.central_splitter.addWidget(self.scroll_area)
        # Set initial sizes (adjust these values as needed for a good starting look)
        # Give song list a smaller initial size compared to the scroll area
        self.central_splitter.setSizes([150, 600]) # Example: 150px for list, 600px for grid area
        self.central_splitter.setStretchFactor(1, 1) # Allow the scroll area (index 1) to expand more readily

        # --- Main Layout ---
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addLayout(top_button_layout)
        # main_layout.addWidget(self.scroll_area) # Removed: scroll_area is now inside central_layout
        main_layout.addWidget(self.central_splitter, 1) # Add the QSplitter with stretch factor 1
        central_widget = QWidget()
        central_widget.setLayout(main_layout)

        

        self.setCentralWidget(central_widget)

    def _populate_ui_elements(self, splash=None):
        """Populates the UI elements that depend on loaded data."""
        start_time = time.time()
        self._update_splash(splash, "Populating song list...")
        self.song_list.populate(self.songs_data)
        # _populate_button_grid now returns its own time and image time
        grid_time, image_time = self._populate_button_grid(splash)
        # Card background color is applied during _populate_button_grid
        self.load_stats['grid_population_time'] = grid_time
        self.load_stats['image_load_time'] = image_time

    def _setup_lyric_window(self):
        """Creates and configures the lyric display window."""
        self.lyric_window = LyricDisplayWindow()
        screens = QApplication.screens()
        if len(screens) > 1:
            target_screen_index = self.current_screen_index # Use loaded/default index
            try:
                self.lyric_window.set_fullscreen_on_screen(target_screen_index)
                self.current_screen_index = target_screen_index # Store the used index
                print(f"Lyric window set to screen {target_screen_index}.")
            except Exception as e:
                 print(f"Error setting fullscreen on screen 1: {e}")
                 print("Falling back to primary screen.")
                 self.lyric_window.set_fullscreen_on_screen(self.current_screen_index) # Use default index 0
        else:
            print("Warning: Only one screen detected. Lyric window will be fullscreen on the primary screen.")
            self.lyric_window.set_fullscreen_on_screen(self.current_screen_index) # Use default index 0
        # Apply loaded template settings
        self.lyric_window.set_template_settings(self.lyric_template_settings)

    def _clear_button_grid(self):
        """Removes all widgets from the button grid layout and disconnects signals."""
        if not hasattr(self.button_area, 'grid_layout'):
            print("Error: button_area does not have grid_layout.")
            return

        print("Clearing button grid...")
        # Explicitly clear the last clicked button reference first
        self._last_clicked_button = None
        self._ordered_buttons.clear() # Clear the ordered list

        # Iterate backwards while removing items
        items_to_remove = []
        for i in range(self.button_area.grid_layout.count()):
            items_to_remove.append(self.button_area.grid_layout.itemAt(i))

        for item in reversed(items_to_remove): # Remove in reverse order
            widget = item.widget()
            layout_item = item.layout()

            if widget:
                # Check if it's a row container widget holding LyricCardWidgets
                if isinstance(widget, QWidget) and widget.layout() is not None and isinstance(widget.layout(), QHBoxLayout):
                    row_layout = widget.layout()
                    # Clear widgets within the row container
                    sub_items_to_remove = []
                    for j in range(row_layout.count()):
                        sub_items_to_remove.append(row_layout.itemAt(j))

                    for sub_item in reversed(sub_items_to_remove):
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            # Disconnect if it's a LyricCardWidget
                            if isinstance(sub_widget, LyricCardWidget):
                                try:
                                    # Disconnect all slots connected to the clicked signal
                                    sub_widget.clicked.disconnect()
                                except RuntimeError as e:
                                    # This might happen if it was already disconnected or somehow invalid
                                    print(f"  Warning: Could not disconnect signal for {sub_widget.objectName()}: {e}")
                                except TypeError:
                                    # PySide6 might raise TypeError if no connections exist
                                    pass # Ignore if no connections
                            # This should be at the same level as the 'if sub_widget:' check
                            sub_widget.deleteLater()
                        elif sub_item.spacerItem():
                            row_layout.removeItem(sub_item) # Remove spacer item

                # Also handle the clear button container
                elif widget.objectName() == "clear_lyrics_button_container":
                    clear_layout = widget.layout()
                    if clear_layout and clear_layout.count() > 1: # Check layout exists and has items
                        # Assuming button is at index 1 between stretches
                        clear_button_item = clear_layout.itemAt(1)
                        if clear_button_item and clear_button_item.widget():
                            try:
                                clear_button_item.widget().clicked.disconnect()
                            except (RuntimeError, TypeError): pass # Ignore errors
                            clear_button_item.widget().deleteLater()

                # Delete the widget itself (row container, title label, separator, clear container)
                widget.deleteLater()

            elif layout_item:
                 # This case shouldn't happen with the current structure, but good to have
                 print(f"Warning: Found layout item directly in grid - clearing recursively.")
                 while (sub_item := layout_item.takeAt(0)) is not None:
                    if sub_item.widget():
                        # Disconnect if LyricCardWidget
                        if isinstance(sub_item.widget(), LyricCardWidget):
                            try: sub_item.widget().clicked.disconnect()
                            except (RuntimeError, TypeError): pass
                        sub_item.widget().deleteLater()
                 layout_item.deleteLater()
            elif item.spacerItem():
                 # Remove the main vertical spacer
                 self.button_area.grid_layout.removeItem(item)

            # Remove the item from the main grid layout (important!) - This should be outside the if/elif/else for widget/layout/spacer
            self.button_area.grid_layout.removeItem(item)

        print("Button grid cleared.")

    def _populate_button_grid(self, splash=None):
        """Populates the button grid with songs and sections, ensuring consistent button size."""
        start_time = time.time()
        total_image_load_time = 0.0 # Accumulator for image loading

        self._update_splash(splash, "Clearing existing buttons...")
        self._button_id_to_widget_map.clear() # Clear the map before repopulating
        self._ordered_buttons.clear() # Clear the ordered list before repopulating
        current_grid_row = 0
        for song_index, (song_key, song_data) in enumerate(self.songs_data.items()):
            song_title = song_data.get("title", song_key)
            self._update_splash(splash, f"Loading sections for: {song_title}")

            # --- Add Separator and Song Title ---
            if current_grid_row > 0: # Add separator before every song title
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                separator.setStyleSheet("color: #555;")
                self.button_area.grid_layout.addWidget(separator, current_grid_row, 0, 1, self.button_area.max_cols)
                current_grid_row += 1

            title_label = QLabel(song_title)
            title_font = QFont("Arial", 12)
            title_font.setBold(True)
            title_label.setFont(title_font) # Corrected typo
            title_label.setStyleSheet("color: white; margin-top: 5px;")
            self.button_area.grid_layout.addWidget(title_label, current_grid_row, 0, 1, self.button_area.max_cols, alignment=Qt.AlignmentFlag.AlignLeft) # Assuming max_cols
            current_grid_row += 1
            # --- End Add Separator and Song Title ---

            if "sections" in song_data and isinstance(song_data["sections"], list):
                # print(f"Adding buttons for song: {song_title}") # Less verbose now

                current_button_row_widgets = []
                button_count_in_row = 0

                for i, section in enumerate(song_data["sections"]):
                    if isinstance(section, dict):
                        section_name = section.get("name", f"Section {i+1}")
                        lyric_text = section.get("lyrics", "")
                        section_name_key = section_name.replace(' ', '_').replace('-', '_').lower()
                        button_id = f"{song_key}__{section_name_key}" # Use double underscore as delimiter
                        background_path = section.get("background_image") # Get the background image path
                        unique_button_object_name = f"btn_{button_id}_{i}" # Add index for uniqueness
                        card_bg_color = self.app_settings.get("card_background_color", "#000000") # Get color from settings
                        # self._update_splash(splash, f"  Loading: {section_name}") # Option for more detail

                        # --- Create LyricCardWidget ---
                       # Pass all relevant info: id, number, name, lyrics, background
                        new_button = LyricCardWidget(
                            button_id=button_id,
                            slide_number=i + 1,
                            section_name=section_name,
                            song_title=song_title, # Pass the song title
                            lyrics=lyric_text,
                            background_image_path=background_path,
                            template_settings=self.lyric_template_settings, # Pass the loaded template settings
                            card_background_color=card_bg_color # Pass the card background color
                        )
                        total_image_load_time += new_button.get_last_image_load_time() # Get time from the widget
                        new_button.setObjectName(unique_button_object_name) # Set unique object name
                        # The size policy is now set within the LyricCardWidget itself to Fixed
                        # We can optionally set a fixed size here as well, though sizeHint should be used by the layout
                        # new_button.setFixedSize(new_button.sizeHint()) # Optional: Force the size

                        # Use lambda to pass the button object itself to the handler
                        new_button.clicked.connect(
                            lambda btn=new_button: self._handle_button_click(btn)
                        )
                        # Connect the edit song signal from the card
                        new_button.edit_song_requested.connect(self._open_song_editor)
                        # Connect the edit section signal from the card
                        new_button.edit_section_requested.connect(self._open_section_editor)

                        # Store the widget reference in the map
                        self._button_id_to_widget_map[button_id] = new_button
                        self._ordered_buttons.append(new_button) # Add to the ordered list

                        current_button_row_widgets.append(new_button)
                        button_count_in_row += 1

                        if button_count_in_row == self.button_area.max_cols or i == len(song_data["sections"]) - 1:
                            row_layout = QHBoxLayout()
                            row_layout.setSpacing(self.button_area.grid_layout.spacing())
                            row_layout.setContentsMargins(0, 0, 0, 0)

                            for button in current_button_row_widgets:
                                # Add the button to the layout. The layout will respect the widget's size policy.
                                row_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)

                            # Add a stretch to push the fixed-size buttons to the left
                            row_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

                            # --- Create Container Widget for the Row ---
                            row_container_widget = QWidget()
                            row_container_widget.setLayout(row_layout)
                            # Set size policy for the container to prefer its content size but not expand
                            row_container_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

                            # Add the row container to the main grid layout
                            self.button_area.grid_layout.addWidget(row_container_widget, current_grid_row, 0, 1, self.button_area.max_cols, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                            # Keep column stretch if needed, but the row container's policy is more important here
                            self.button_area.grid_layout.setColumnStretch(0, 0)

                            current_grid_row += 1
                            current_button_row_widgets = []
                            button_count_in_row = 0
            else:
                print(f"Warning: No valid 'sections' list found for song '{song_title}'. Skipping buttons for this song.")

        # --- Add Clear Button ---
        clear_button = QPushButton("Clear") # Standard button, not draggable
        clear_button.setObjectName("clear_lyrics_button")
        clear_button.clicked.connect(lambda: self._handle_button_click(None)) # Pass None for button object

        clear_layout = QHBoxLayout()
        clear_layout.addStretch(1)
        clear_layout.addWidget(clear_button, alignment=Qt.AlignmentFlag.AlignCenter)
        clear_layout.addStretch(1)
        clear_layout.setContentsMargins(0, 0, 0, 0)

        clear_container_widget = QWidget()
        clear_container_widget.setObjectName("clear_lyrics_button_container") # Set object name here
        clear_container_widget.setLayout(clear_layout)
        clear_container_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.button_area.grid_layout.addWidget(clear_container_widget, current_grid_row, 0, 1, self.button_area.max_cols, alignment=Qt.AlignmentFlag.AlignCenter)
        self.button_area.grid_layout.setColumnStretch(0, 0)
        current_grid_row += 1

        # --- Add Vertical Spacer ---
        vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.button_area.grid_layout.addItem(vertical_spacer, current_grid_row, 0, 1, self.button_area.max_cols)

        # Ensure the last row doesn't stretch vertically if content is short
        self.button_area.grid_layout.setRowStretch(current_grid_row, 1)

        self._update_splash(splash, "Button population complete.")
        total_time = time.time() - start_time
        return total_time, total_image_load_time # Return total time and image time

    def _update_splash(self, splash, message):
        """Safely updates the splash screen message and processes events."""
        if splash:
            splash.showMessage(message, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, Qt.GlobalColor.white)
            QApplication.processEvents() # IMPORTANT: Allow GUI to update

    def _update_column_count(self, value):
        """Slot connected to the column slider's valueChanged signal."""
        self.column_count_label.setText(str(value))
        if hasattr(self.button_area, 'max_cols'):
            self.button_area.max_cols = value
            # Repopulate (don't need splash, and ignore returned times here)
            self._clear_button_grid()
            self._button_id_to_widget_map.clear()
            self._populate_button_grid()
    # --------------------------------------------------------------------------
    # Refresh Functionality
    # --------------------------------------------------------------------------
    def _refresh_data_and_ui(self):
        """Reloads song data and template, then updates the UI."""
        print("--- Refreshing Data and UI ---")

        # Optional: Show a simple "Refreshing..." message if desired
        # You could potentially reuse the splash mechanism here, but it might be overkill

        # Reset stats for refresh timing if desired (optional)
        # self.load_stats = {}

        # 1. Reload data
        # We could time these again, but maybe not necessary for refresh
        self._load_template_settings() # Returns time, but we ignore it here
        self._load_songs_data()      # Returns time, but we ignore it here

        # 2. Clear existing UI elements dependent on data
        self._clear_button_grid()
        self._button_id_to_widget_map.clear() # Also clear the map
        # self._ordered_buttons is cleared within _clear_button_grid
        self.song_list.clear()

        # 3. Repopulate UI elements (without splash, ignore returned times)
        # Note: This will overwrite the initial load stats if not reset above
        self._populate_ui_elements()
        self.lyric_window.set_template_settings(self.lyric_template_settings) # Re-apply template
        #self._handle_button_click(None) # Clear lyric display and highlight
        print("--- Refresh Complete ---")
    def _save_app_settings(self):
        """Saves the current app settings to the JSON file."""
        settings_file_path = "app_settings.json"
        print(f"Saving app settings to: {settings_file_path}")
        try:
            # Update the settings dict with current values before saving
            self.app_settings["output_screen_index"] = self.current_screen_index
            # self.app_settings["card_background_color"] is updated when dialog closes
            with open(settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.app_settings, f, indent=2) # Use indent for readability
            print("App settings saved successfully.")
        except Exception as e:
            print(f"Error saving app settings file: {e}")
    # --------------------------------------------------------------------------
    # Event Handlers / Slots
    # --------------------------------------------------------------------------

    def _handle_song_list_selection(self, button_id, lyric_text):
        """Handles selection changes in the SongListWidget."""
        print(f"Received selection from song list: ID={button_id}, Lyric='{lyric_text[:20]}...'")

        # Find the corresponding button widget
        target_widget = self._button_id_to_widget_map.get(button_id)

        if target_widget:
            # Scroll the scroll area to make the widget visible
            self.scroll_area.ensureWidgetVisible(target_widget)
            # Programmatically handle the click to update lyrics and highlight
            self._handle_button_click(target_widget)
            # Set focus back to the main window to capture arrow keys
            self.setFocus()
    # --------------------------------------------------------------------------
    def _handle_song_title_selection(self, first_section_button_id):
        """Handles clicks on song titles in the SongListWidget."""
        print(f"Received song title selection, scrolling to first section: ID={first_section_button_id}")

        # Find the corresponding button widget for the first section
        target_widget = self._button_id_to_widget_map.get(first_section_button_id)

        if target_widget:
            # Scroll the scroll area to make the widget visible
            self.scroll_area.ensureWidgetVisible(target_widget)
            # Clear highlight from any previously clicked button card, but don't select a new one
            if self._last_clicked_button:
                self._last_clicked_button.set_highlight(False)
                self._last_clicked_button = None
            # Set focus back to the main window to capture arrow keys
            self.setFocus()
    # --------------------------------------------------------------------------

    # Renamed from handle_button_with_lyric_clicked for clarity
    def _handle_button_click(self, button_object):
        """Handles clicks from LyricCardWidgets and the Clear button."""

        # --- Remove highlight from the previous button ---
        if self._last_clicked_button and self._last_clicked_button != button_object:
            self._last_clicked_button.set_highlight(False)
            self._last_clicked_button = None # Clear reference only after de-highlighting

        if isinstance(button_object, LyricCardWidget):
            # --- Handle LyricCardWidget click ---
            print(f"Handling click for {button_object.button_id} with lyric: '{button_object.lyric_text}'")
            # Always display the lyric text
            self.lyric_window.display_lyric(button_object.lyric_text)
            # ONLY set the background if the clicked card has one specified
            # Access the path via the content_area child widget
            if button_object.content_area._background_image_path:
                self.lyric_window.set_background_image(button_object.content_area._background_image_path)
            # Apply highlight to the new card
            button_object.set_highlight(True)
            self._last_clicked_button = button_object # Store reference
        else:
            # --- Handle Clear button click (or other non-LyricCardWidget source) ---
            print("Handling click for Clear button (or non-card source)")
            self.lyric_window.set_background_image(None) # Clear the background on the lyric window
            self.lyric_window.display_lyric("") # Display empty lyric
            # self._last_clicked_button is already cleared or was handled above

        # Set focus back to the main window after any click handling
        # to ensure arrow key navigation keeps working.
        self.setFocus()

    # --- Slot to Open Settings Dialog ---
    def open_settings_dialog(self):
        """Opens the settings dialog and applies changes if accepted."""
        # Pass current settings values to the dialog constructor
        dialog = SettingsDialog(
            current_screen_index=self.app_settings.get("output_screen_index", 0),
            current_card_bg_color=self.app_settings.get("card_background_color", "#000000"),
            load_stats=self.load_stats,
            parent=self
        )
        if dialog.exec(): # Show the dialog modally, returns True if accepted
            new_index = dialog.get_selected_screen_index()
            new_card_bg_color = dialog.get_selected_card_background_color() # Get selected color
            if new_index != self.current_screen_index:
                print(f"Changing output screen to index: {new_index}")
                self.lyric_window.set_fullscreen_on_screen(new_index)
                self.current_screen_index = new_index # Update stored index
                self.app_settings["output_screen_index"] = new_index # Update settings dict

            # Update settings dict and apply the new color
            self.app_settings["card_background_color"] = new_card_bg_color # Update settings dict
            self._update_all_card_backgrounds(new_card_bg_color) # Apply new color to existing cards
            self._save_app_settings() # Save updated settings to file

    def _open_song_editor(self, song_key):
        """Opens the SongMetadataEditorWindow for the specified song."""
        print(f"Opening song metadata editor for song key: {song_key}")
        editor_key = ('song', song_key) # Use tuple as key

        # Avoid opening multiple editors for the same song
        if editor_key in self._editor_windows and self._editor_windows[editor_key].isVisible():
            self._editor_windows[editor_key].activateWindow() # Bring existing window to front
            return
        
        # --- Find the song data ---
        song_data = self.songs_data.get(song_key)
        if not song_data:
            print(f"Error: Song data not found for key '{song_key}' when trying to open editor.")
            QMessageBox.warning(self, "Error", f"Could not find song data for '{song_key}'.")
            return

        # --- Create and show the editor window ---
        try:
            # Pass the song_key and the full song_data dictionary
            editor_window = SongMetadataEditorWindow(song_key, song_data, parent=self)
            editor_window.metadata_saved.connect(self._handle_song_metadata_saved) # Connect the save signal
            # Add a close connection to remove from tracking dict
            editor_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            editor_window.destroyed.connect(lambda: self._editor_windows.pop(editor_key, None))
            editor_window.show()
            self._editor_windows[editor_key] = editor_window # Store reference using tuple key
        except ImportError as e:
             print(f"Error importing song metadata editor components: {e}")
             QMessageBox.critical(self, "Import Error", "Could not load the song metadata editor component. Please ensure 'song_metadata_editor_widget.py' exists.")
        except Exception as e:
            print(f"Error creating song metadata editor window: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while opening the song editor: {e}")

        # Add a close connection to remove from tracking dict
        editor_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        editor_window.destroyed.connect(lambda: self._editor_windows.pop(editor_key, None))
        editor_window.show()
        self._editor_windows[editor_key] = editor_window # Store reference using tuple key

    def _open_section_editor(self, button_id):
        """Opens the SongSectionEditorWindow for the specified section."""
        print(f"DEBUG: _open_section_editor called with button_id: '{button_id}'") # Enhanced print
        editor_key = ('section', button_id) # Use tuple as key

        # Avoid opening multiple editors for the same section
        if editor_key in self._editor_windows and self._editor_windows[editor_key].isVisible():
            self._editor_windows[editor_key].activateWindow()
            return

        # --- Find the section data ---
        try:
            song_key, section_name_key = button_id.split('__', 1) # Split using double underscore
            print(f"  DEBUG: Parsed song_key: '{song_key}', section_name_key: '{section_name_key}'") # Added print
        except ValueError:
            print(f"Error: Could not parse song_key and section_name from button_id '{button_id}'")
            QMessageBox.warning(self, "Error", f"Could not identify section from ID '{button_id}'.")
            return

        # Check if the key exists *before* getting the data
        if song_key not in self.songs_data:
             print(f"  DEBUG: Error - Song key '{song_key}' NOT FOUND in self.songs_data keys: {list(self.songs_data.keys())}") # Added print
             QMessageBox.warning(self, "Error", f"Could not find song data for key '{song_key}'.") # Keep this message specific
             return

        song_data = self.songs_data.get(song_key)
        # Check if song_data is valid (has 'sections')
        if not song_data or "sections" not in song_data:
            print(f"  DEBUG: Error - Song data found for key '{song_key}' but it's invalid or missing 'sections'. Data: {song_data}") # Modified print
            QMessageBox.warning(self, "Error", f"Could not find valid section data within song '{song_key}'.") # Modified message
            return

        target_section_data = None
        for idx, section in enumerate(song_data["sections"]):
            # Reconstruct the key part used in button_id for comparison
            current_section_name_key = section.get("name", f"Section {idx+1}").replace(' ', '_').replace('-', '_').lower()
            if current_section_name_key == section_name_key:
                target_section_data = section
                section_index = idx
                break

        if target_section_data is None:
            print(f"  DEBUG: Error - Section '{section_name_key}' not found within song '{song_key}' after checking {len(song_data.get('sections',[]))} sections.") # Enhanced print
            QMessageBox.warning(self, "Error", f"Could not find section data for '{button_id}'.")
            return

        # --- Create and show the editor window ---
        try:
            # Pass the original button_id and the found section data
            editor_window = SongSectionEditorWindow(button_id, target_section_data, parent=self)
            editor_window.section_data_saved.connect(self._handle_section_data_saved)
            # Add a close connection to remove from tracking dict
            editor_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            editor_window.destroyed.connect(lambda: self._editor_windows.pop(editor_key, None))
            editor_window.show()
            self._editor_windows[editor_key] = editor_window # Store reference
        except ImportError as e:
             print(f"Error importing section editor components: {e}")
             QMessageBox.critical(self, "Import Error", "Could not load the section editor component. Please ensure 'section_editor_widget.py' exists.")
        except Exception as e:
            print(f"Error creating section editor window: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while opening the section editor: {e}")

    def _handle_section_data_saved(self, button_id, updated_data):
        """Handles the data saved from the SongSectionEditorWindow."""
        print(f"Received saved data for section: {button_id}")

        try:
            song_key, section_name_key = button_id.split('__', 1) # Split using double underscore
        except ValueError:
            print(f"Error: Could not parse song_key/section_name from button_id '{button_id}' during save.")
            return

        # --- Update self.songs_data ---
        if song_key in self.songs_data and "sections" in self.songs_data[song_key]:
            found = False
            for idx, section in enumerate(self.songs_data[song_key]["sections"]):
                current_section_name_key = section.get("name", f"Section {idx+1}").replace(' ', '_').replace('-', '_').lower()
                if current_section_name_key == section_name_key:
                    # Update the section in the list
                    self.songs_data[song_key]["sections"][idx] = updated_data
                    found = True
                    break
            if not found:
                print(f"Error: Could not find section '{section_name_key}' in song '{song_key}' data to update.")
                return # Stop if section wasn't found in data
        else:
            print(f"Error: Song data for '{song_key}' not found or invalid during save.")
            return # Stop if song data is missing

        # --- Save updated song data to JSON file ---
        song_file_path = os.path.join("songs", f"{song_key}.json")
        try:
            with open(song_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.songs_data[song_key], f, indent=2, ensure_ascii=False)
            print(f"Successfully saved updated data to {song_file_path}")
        except Exception as e:
            print(f"Error saving updated song file {song_file_path}: {e}")
            QMessageBox.warning(self, "Save Error", f"Could not save changes to {song_file_path}:\n{e}")
            # Decide if you want to revert self.songs_data here or leave it modified in memory

        # --- Update the corresponding LyricCardWidget ---
        target_widget = self._button_id_to_widget_map.get(button_id)
        if target_widget:
            new_section_name = updated_data.get("name", "Section ?")
            new_lyrics = updated_data.get("lyrics", "")
            new_background = updated_data.get("background_image")

            target_widget.set_lyrics(new_lyrics)
            target_widget.info_bar.set_data(target_widget._slide_number, new_section_name) # Update info bar name
            target_widget.content_area.set_background(new_background) # Update background image

            # If this card was the last clicked, update the main display too
            if self._last_clicked_button == target_widget:
                self.lyric_window.display_lyric(new_lyrics)
                self.lyric_window.set_background_image(new_background)

            print(f"Updated UI for card {button_id}")
        else:
            print(f"Warning: Could not find widget for button_id '{button_id}' to update UI.")

        # --- Refresh Song List (in case section name changed) ---
        # This is a simple refresh, could be optimized to only update the specific song/section item
        self.song_list.populate(self.songs_data)
        print("Refreshed song list.")

    def _handle_song_metadata_saved(self, song_key, updated_metadata):
        """Handles the metadata saved from the SongMetadataEditorWindow."""
        print(f"Received saved metadata for song: {song_key}")

        # --- Update self.songs_data ---
        if song_key in self.songs_data:
            # Preserve the existing 'sections' data
            existing_sections = self.songs_data[song_key].get("sections", [])
            # Update the song data dictionary with the new metadata
            self.songs_data[song_key].update(updated_metadata)
            # Ensure 'sections' is put back if it was overwritten by update()
            self.songs_data[song_key]["sections"] = existing_sections
        else:
            print(f"Error: Song data for '{song_key}' not found during metadata save.")
            return # Stop if song data is missing

        # --- Save updated song data to JSON file ---
        song_file_path = os.path.join("songs", f"{song_key}.json")
        try:
            with open(song_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.songs_data[song_key], f, indent=2, ensure_ascii=False)
            print(f"Successfully saved updated metadata to {song_file_path}")
        except Exception as e:
            print(f"Error saving updated song file {song_file_path}: {e}")
            QMessageBox.warning(self, "Save Error", f"Could not save metadata changes to {song_file_path}:\n{e}")
            # Consider reverting self.songs_data here if save fails

        # --- Update UI Elements ---
        new_song_title = updated_metadata.get("title", song_key)

        # Update relevant LyricCardWidget titles
        for button_id, widget in self._button_id_to_widget_map.items():
            try:
                widget_song_key, _ = button_id.split('__', 1) # Split using double underscore
            except ValueError:
                continue # Skip if button_id format is unexpected
            if widget_song_key == song_key:
                widget.song_title = new_song_title
                # If the card's context menu relies on song_title, it will now be updated
                # No visual update needed on the card itself unless you display the song title there

        # Refresh Song List to reflect the potential title change
        self.song_list.populate(self.songs_data)
        print("Refreshed song list after metadata save.")


    def _update_all_card_backgrounds(self, hex_color):
        """Iterates through all created LyricCardWidgets and updates their background color."""
        print(f"Updating card backgrounds to: {hex_color}")
        for button_widget in self._button_id_to_widget_map.values():
            button_widget.set_card_background_color(hex_color) # Call method on widget
            
    def keyPressEvent(self, event: QEvent):
        """Handles key presses for navigation."""
        key = event.key()

        if key == Qt.Key.Key_Right or key == Qt.Key.Key_Left:
            if not self._ordered_buttons:
                print("No buttons available for navigation.")
                event.accept() # Consume the event even if nothing happens
                return

            current_index = -1
            if self._last_clicked_button:
                try:
                    current_index = self._ordered_buttons.index(self._last_clicked_button)
                except ValueError:
                    print("Warning: Last clicked button not found in ordered list.")
                    # Fallback: treat as if no button was selected
                    current_index = -1

            num_buttons = len(self._ordered_buttons)
            next_index = -1

            if key == Qt.Key.Key_Right:
                if current_index == -1: # No button selected, go to the first one
                    next_index = 0
                else:
                    next_index = (current_index + 1) % num_buttons # Wrap around
            elif key == Qt.Key.Key_Left:
                if current_index == -1: # No button selected, go to the last one
                    next_index = num_buttons - 1
                else:
                    next_index = (current_index - 1 + num_buttons) % num_buttons # Wrap around

            if 0 <= next_index < num_buttons:
                target_widget = self._ordered_buttons[next_index]
                print(f"Navigating {'Right' if key == Qt.Key.Key_Right else 'Left'} to button index {next_index}: {target_widget.button_id}")
                self.scroll_area.ensureWidgetVisible(target_widget) # Scroll to the button
                self._handle_button_click(target_widget) # Simulate click
            else:
                print(f"Could not determine valid next/previous index from current: {current_index}")

            event.accept() # Indicate we've handled the arrow key
        else:
            super().keyPressEvent(event) # Pass other key presses to the base class


    # --- Method to Show Load Stats ---
    def _show_load_stats(self):
        """Displays the collected loading statistics in a message box."""
        if not self.load_stats:
            QMessageBox.information(self, "Load Stats", "No loading statistics collected yet.")
            return

        stats_message = "Initial Load Times:\n\n"
        stats_message += f"- App Settings Load: {self.load_stats.get('app_settings_load_time', 0):.4f} seconds\n"
        stats_message += f"- Template Load: {self.load_stats.get('template_load_time', 0):.4f} seconds\n"
        stats_message += f"- Song Data Load: {self.load_stats.get('song_data_load_time', 0):.4f} seconds\n"
        stats_message += f"- Grid Population: {self.load_stats.get('grid_population_time', 0):.4f} seconds\n"
        stats_message += f"  - Image Loading (within grid): {self.load_stats.get('image_load_time', 0):.4f} seconds\n"

        QMessageBox.information(self, "Load Stats", stats_message)

# --- Helper Function to Create a Simple Splash Pixmap ---
def create_splash_pixmap(width=400, height=200):
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(50, 50, 70)) # Dark background

    painter = QPainter(pixmap)
    font = QFont("Arial", 20, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(200, 200, 220)) # Light text color
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Plucky\nLoading...")
    painter.end()
    return pixmap

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # --- Splash Screen Setup ---
    splash_pix = create_splash_pixmap() # Or load from file: QPixmap("path/to/splash.png")
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents() # Ensure splash is shown before loading starts

    main_window = MainWindow()
    main_window.perform_initial_load(splash) # Perform the loading steps

    main_window.show()
    splash.finish(main_window) # Close splash when main window is ready
    sys.exit(app.exec())
