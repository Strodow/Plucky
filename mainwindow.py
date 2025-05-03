# c:\Users\Logan\Documents\Plucky\mainwindow.py

# --- Standard Library Imports ---
import sys
import json
import os

# --- PySide6 Imports ---
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QLabel, QFrame, QSizePolicy, QSpacerItem,
    QScrollArea, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QFileDialog, QSlider,
    QSplitter # Import QSplitter
)
from PySide6.QtCore import Qt, QMimeData, QRect, QSize # Import QSize
from PySide6.QtGui import QFont, QPixmap, QColor # Removed QDrag, QMouseEvent

# --- Local Imports ---
from button_widgets import ButtonGridWidget
from lyric_display_window import LyricDisplayWindow
from settings_dialog import SettingsDialog # Import the new dialog
# from custom_widgets import DraggableButton # No longer using DraggableButton
from button_remake import LyricCardWidget # Assuming button_remake.py contains the updated LyricCardWidget
from song_list_widget import SongListWidget # Import the new song list widget

# --- Main Window Class ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Application")

        # --- Store current screen index ---
        self.current_screen_index = 0
        self._last_clicked_button = None # Track the highlighted button
        self._button_id_to_widget_map = {} # Map button_id to LyricCardWidget instance

        # --- Data Loading ---
        self._load_template_settings()
        self._load_songs_data()

        # --- Create Button Area first ---
        # ButtonGridWidget now primarily acts as a container for the grid layout
        self.button_area = ButtonGridWidget() # Create this before _setup_main_ui

        # --- Setup UI Components ---
        self._setup_lyric_window()
        self._setup_main_ui()
        self.song_list.populate(self.songs_data) # Populate the song list after UI setup
        self._populate_button_grid()

        self.setGeometry(100, 100, 800, 600)

    # --------------------------------------------------------------------------
    # Initialization Helper Methods
    # --------------------------------------------------------------------------

    def _load_template_settings(self):
        """Loads lyric display template settings from template.json."""
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

    def _load_songs_data(self):
        """Loads song data from JSON files in the 'songs' directory."""
        self.songs_data = {}
        songs_directory = "songs"
        if os.path.exists(songs_directory) and os.path.isdir(songs_directory):
            for filename in os.listdir(songs_directory):
                if filename.endswith(".json"):
                    file_path = os.path.join(songs_directory, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            song_data = json.load(f)
                            song_key = os.path.splitext(filename)[0]
                            self.songs_data[song_key] = song_data
                            print(f"Loaded song: {song_data.get('title', song_key)}")
                    except json.JSONDecodeError:
                        print(f"Error: Could not decode JSON in {filename}. Skipping.")
                    except Exception as e:
                        print(f"An unexpected error occurred while loading {filename}: {e}")
                        print("Skipping song.")
        else:
            print(f"Warning: Songs directory not found or is not a directory at {songs_directory}.")

    def _setup_main_ui(self):
        """Sets up the main window's UI elements (buttons, scroll area, layout)."""
        # --- Top Controls Layout ---
        top_button_layout = QHBoxLayout()
        top_button_layout.setContentsMargins(10, 5, 10, 5)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        top_button_layout.addWidget(self.settings_button)

        self.set_background_button = QPushButton("Set Background Image")
        self.set_background_button.clicked.connect(self.select_background_image)
        top_button_layout.addWidget(self.set_background_button)

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

    def _setup_lyric_window(self):
        """Creates and configures the lyric display window."""
        self.lyric_window = LyricDisplayWindow()
        screens = QApplication.screens()
        if len(screens) > 1:
            target_screen_index = 1 # Try secondary screen first
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
        """Removes all widgets from the button grid layout."""
        if not hasattr(self.button_area, 'grid_layout'):
            print("Error: button_area does not have grid_layout.")
            return

        # Iterate backwards while removing items
        while (item := self.button_area.grid_layout.takeAt(0)) is not None:
            if item.widget():
                item.widget().deleteLater() # Delete the widget
            elif item.layout():
                # If the item is a layout, clear it recursively (important for row_container_widget)
                while (sub_item := item.layout().takeAt(0)) is not None:
                    # print(f"  Clearing sub-item: {sub_item}")
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
                item.layout().deleteLater() # Delete the layout itself

    def _populate_button_grid(self):
        """Populates the button grid with songs and sections, ensuring consistent button size."""
        self._button_id_to_widget_map.clear() # Clear the map before repopulating
        current_grid_row = 0
        for song_key, song_data in self.songs_data.items():
            song_title = song_data.get("title", song_key)

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
                print(f"Adding buttons for song: {song_title}")

                current_button_row_widgets = []
                button_count_in_row = 0

                for i, section in enumerate(song_data["sections"]):
                    if isinstance(section, dict):
                        section_name = section.get("name", f"Section {i+1}")
                        lyric_text = section.get("lyrics", "")
                        button_id = f"{song_key}_{section_name.replace(' ', '_').replace('-', '_').lower()}"
                        background_path = section.get("background_image") # Get the background image path
                        unique_button_object_name = f"btn_{button_id}_{i}" # Add index for uniqueness

                        # --- Create LyricCardWidget ---
                       # Pass all relevant info: id, number, name, lyrics, background
                        new_button = LyricCardWidget(button_id=button_id, slide_number=i + 1, section_name=section_name, lyrics=lyric_text, background_image_path=background_path)
                        new_button.setObjectName(unique_button_object_name) # Set unique object name
                        # The size policy is now set within the LyricCardWidget itself to Fixed
                        # We can optionally set a fixed size here as well, though sizeHint should be used by the layout
                        # new_button.setFixedSize(new_button.sizeHint()) # Optional: Force the size

                        # Use lambda to pass the button object itself to the handler
                        new_button.clicked.connect(
                            lambda btn=new_button: self._handle_button_click(btn)
                        )

                        # Store the widget reference in the map
                        self._button_id_to_widget_map[button_id] = new_button

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

    def _update_column_count(self, value):
        """Slot connected to the column slider's valueChanged signal."""
        self.column_count_label.setText(str(value))
        if hasattr(self.button_area, 'max_cols'):
            self.button_area.max_cols = value
            self._clear_button_grid() # Clear existing buttons
            self._populate_button_grid() # Repopulate with new column count
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
            if button_object._background_image_path:
                self.lyric_window.set_background_image(button_object._background_image_path)
            # Apply highlight to the new card
            button_object.set_highlight(True)
            self._last_clicked_button = button_object # Store reference
        else:
            # --- Handle Clear button click (or other non-LyricCardWidget source) ---
            print("Handling click for Clear button (or non-card source)")
            self.lyric_window.set_background_image(None) # Clear the background on the lyric window
            self.lyric_window.display_lyric("") # Display empty lyric
            # self._last_clicked_button is already cleared or was handled above


    # --- Slot to Open Settings Dialog ---
    def open_settings_dialog(self):
        """Opens the settings dialog and applies changes if accepted."""
        dialog = SettingsDialog(self.current_screen_index, self)
        if dialog.exec(): # Show the dialog modally, returns True if accepted
            new_index = dialog.get_selected_screen_index()
            if new_index != self.current_screen_index:
                print(f"Changing output screen to index: {new_index}")
                self.lyric_window.set_fullscreen_on_screen(new_index)
                self.current_screen_index = new_index # Update stored index
            else:
                print("Screen selection unchanged.")


    # --- Slot to Select Background Image ---
    def select_background_image(self):
        """Opens a file dialog to select a background image and sets it."""
        filter_options = "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Image",
            "", # Start directory (empty means default/last used)
            filter_options
        )

        if file_path:
            print(f"Selected background image: {file_path}")
            self.lyric_window.set_background_image(file_path)
        else:
            print("No background image selected.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
