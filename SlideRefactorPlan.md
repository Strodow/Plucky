# Slide Refactor and Modular Presentation Plan

## Overall Goal:
Refactor the application to:
1.  Treat each "section" (song, generic content block as per `ExampleSectionStructure.json`) as an independent JSON file (e.g., `*.plucky_section`).
2.  Introduce a "presentation manifest" JSON file (e.g., `*.plucky_pres`) that lists these section files in order and stores presentation-level metadata.
3.  Define a user data storage location ("UserStore") with subdirectories for presentations and sections.
4.  Update `PresentationManager` to load, manage, and save this new structure, respecting the UserStore.
5.  Adapt `MainWindow` UI and logic to work seamlessly with this new data model.

---

## Phase 0: Setup User Data Storage

1.  **Define UserStore Location:**
    *   Determine the root directory for user-specific Plucky data ("UserStore").
    *   This will be managed by a new `core.plucky_standards.PluckyStandards` module.
    *   The base will be `QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) + /Plucky/UserStore`.
    *   `PluckyStandards.initialize_user_store()` will ensure all standard directories are created on application startup (likely called by `ApplicationConfigManager`).

2.  **Define Subfolder Structure within UserStore:**
    *   `PluckyStandards.get_presentations_dir()`: Default location for saving presentation manifest files (`*.plucky_pres`).
        *   When a presentation is saved (especially "Save As"), it's recommended to create a dedicated subfolder for it (e.g., `UserStore/Presentations/MyEventName/`) where the manifest (`MyEventName.plucky_pres`) resides.
    *   `PluckyStandards.get_sections_dir()`: Default location for saving individual section files (`*.plucky_section`).
        *   Sections associated with a specific presentation should ideally be stored in a subfolder relative to that presentation's manifest (e.g., `UserStore/Presentations/MyEventName/sections/`). This makes presentations self-contained.
    *   `PluckyStandards.get_templates_dir()`: Directory for user-created templates.

---

## Phase 1: Define Data Structures & Core `PresentationManager` Refactor (Loading)

1.  **Define Presentation Manifest Structure (`*.plucky_pres`):**
    *   Create a clear JSON schema for your main presentation file.
    *   It should include:
        *   `version`: For future compatibility (e.g., "1.0.0").
        *   `presentation_title`: Optional overall title for the presentation.
        *   `sections`: An array of objects, each representing a section instance in the presentation.
            *   `id`: A unique ID for this instance of the section *within this presentation* (e.g., UUID, useful for stable reordering).
            *   `path`: Path to the section's JSON file (`*.plucky_section`). This can be:
                *   Relative to the manifest file (e.g., `sections/intro.plucky_section`).
                *   A simple filename (e.g., `amazing_grace.plucky_section`), implying it's in the central `PluckyStandards.get_sections_dir()`.
                *   An absolute path.
            *   `active_arrangement_name`: (Optional) The name of the arrangement to use for this section in this presentation. Defaults to the first one defined in the section file if not specified.
    *   Example `MyEvent.plucky_pres` (located in `UserStore/Presentations/MyEventName/`):
        ```json
        {
          "version": "1.0.0",
          "presentation_title": "Sunday Service - Oct 27",
          "sections": [
            {
              "id": "pres_sec_uuid_1",
              "path": "sections/welcome_slides.plucky_section", // Points to UserStore/Presentations/MyEventName/sections/welcome_slides.plucky_section
              "active_arrangement_name": "Default"
            },
            {
              "id": "pres_sec_uuid_2",
              "path": "sections/amazing_grace.plucky_section", // Points to UserStore/Presentations/MyEventName/sections/amazing_grace.plucky_section
              "active_arrangement_name": "Sunday Morning"
            }
          ]
        }
        ```

2.  **Confirm Section File Structure (`*.plucky_section`):**
    *   The `ExampleSectionStructure.json` (as provided in context, representing a single song or generic section) is the blueprint. It contains `id`, `title`, `slide_blocks`, and `arrangements`.
    *   These files will typically reside in `UserStore/Sections/` or within a presentation-specific `sections/` subfolder.

3.  **Refactor `PresentationManager` - Internal State:**
    *   `self.loaded_sections`: A list or dictionary to store fully parsed section data. Each entry would contain:
        *   The manifest metadata for this section instance (`id` from manifest, `path`, `active_arrangement_name`).
        *   The complete parsed content of its section JSON file.
        *   An `is_dirty` flag specific to this section file.
    *   `self.presentation_manifest_data`: Stores the parsed content of the `*.plucky_pres` file.
    *   `self.presentation_manifest_is_dirty`: Flag for the manifest file.
    *   `self.current_manifest_filepath`: Path to the currently loaded `*.plucky_pres` file.

4.  **Refactor `PresentationManager` - Loading (`load_presentation`):**
    *   `load_presentation(manifest_filepath)`:
        *   Clear existing presentation data.
        *   Read and parse the presentation manifest JSON.
        *   Store `manifest_filepath` as `self.current_manifest_filepath` and parsed data in `self.presentation_manifest_data`.
        *   For each entry in the manifest's `sections` array:
            *   Resolve the absolute path to the section file (using `os.path.join(os.path.dirname(manifest_filepath), section_entry['path'])`).
            *   Load and parse the section JSON file.
            *   Store this parsed section data in `self.loaded_sections`.
            *   Handle errors (missing section file, corrupt JSON).
        *   `get_slides()`: This method will now iterate through `self.presentation_manifest_data['sections']`, look up the corresponding full section data from `self.loaded_sections`, select the `active_arrangement_name`, resolve `slide_id_ref`s against the section's `slide_blocks`, and construct the flat list of `SlideData` objects for the UI.

---

## Phase 2: `PresentationManager` Refactor (Saving & Modification Stubs)

1.  **Refactor `PresentationManager` - Saving (`save_presentation`, `save_presentation_as`):**
    *   `save_presentation()`:
        *   If `self.current_manifest_filepath` is set and `self.presentation_manifest_is_dirty` is true, save the presentation manifest JSON.
        *   Iterate through `self.loaded_sections`. If a section's `is_dirty` flag is true, save that section's JSON data back to its original file path.
        *   Clear `is_dirty` flags upon successful save.
    *   `save_presentation_as(new_manifest_filepath)`:
        *   Update `self.current_manifest_filepath` and `self.presentation_manifest_data.presentation_title` (if changed).
        *   Create the directory for the new manifest if it doesn't exist (e.g., `UserStore/Presentations/NewEventName/`).
        *   Create a `sections/` subfolder within this new presentation directory.
        *   For each section in the presentation:
            *   Copy its corresponding section file to the new `sections/` subfolder.
            *   Update the `path` in `self.presentation_manifest_data['sections']` to be relative to the new manifest location (e.g., `sections/copied_section_name.plucky_section`).
        *   Save the (now modified) presentation manifest to `new_manifest_filepath`.
        *   Save all section files (even if not dirty, as their canonical path within this presentation context might have changed if they were copied).
        *   Mark all `is_dirty` flags as false.

2.  **Refactor `PresentationManager` - Dirty Tracking:**
    *   Modify methods that change data (e.g., `update_slide_data_in_section`, `add_slide_to_section`, `change_section_arrangement`, `reorder_sections_in_manifest`) to set the appropriate `is_dirty` flag (on the specific section object and/or `self.presentation_manifest_is_dirty`).

3.  **Stub out Modification Methods in `PresentationManager`:**
    *   `add_section_to_presentation(section_filepath, insert_at_index, desired_arrangement_name=None)`:
        *   Loads the section file if not already loaded.
        *   Adds a new entry to `self.presentation_manifest_data['sections']`.
        *   Sets `self.presentation_manifest_is_dirty = True`.
    *   `remove_section_from_presentation(section_presentation_id)`: Removes from manifest.
    *   `reorder_sections_in_manifest(section_presentation_id, new_index)`: Reorders in manifest.
    *   `set_active_arrangement_for_section_in_presentation(section_presentation_id, arrangement_name)`
    *   `add_slide_to_section(section_file_path_or_id, slide_data, arrangement_name, at_index_in_arrangement)`: Modifies a specific section's `slide_blocks` and its `arrangements`. Marks the section as dirty.
    *   `update_slide_in_section(...)`: Similar.
    *   `delete_slide_from_section(...)`: Similar.

---

## Phase 3: `MainWindow` - File Operations & Basic UI Adaptation

1.  **Update `MainWindow` - "New" Presentation (`handle_new`):**
    *   Call `presentation_manager.clear_presentation()`. This should initialize an empty manifest structure internally.
    *   The UI will show "No slides."
    *   The presentation is considered "untitled" until the first "Save" or "Save As."

2.  **Update `MainWindow` - "Load" (`handle_load`):**
    *   File dialog filters for `*.plucky_pres`, defaulting to `UserStore/Presentations/`.
    *   The default path for the file dialog should come from `config_manager.get_default_presentations_path()` (which uses `PluckyStandards`).
    *   `update_slide_display_and_selection` (triggered by `presentation_changed` signal) will display slides from all loaded sections.

3.  **Update `MainWindow` - "Save" (`handle_save`):**
    *   If `presentation_manager.current_manifest_filepath` is set, call `presentation_manager.save_presentation()`.
    *   Otherwise, call `handle_save_as()`.

4.  **Update `MainWindow` - "Save As" (`handle_save_as`):**
    *   Prompt for a new manifest filepath, defaulting to `UserStore/Presentations/`.
    *   The default path for the file dialog should come from `config_manager.get_default_presentations_path()`.
    *   `PresentationManager` handles copying section files to a relative subfolder.

5.  **Update `MainWindow` - "Add New Section" (replaces "Add Song"):**
    *   This action will now create a *new section file* and add it to the *current presentation*.
    *   Prompt for section title (e.g., song title, sermon part).
    *   Generate a filename (e.g., `cleaned_title.plucky_section`).
    *   Determine save path:
        *   If presentation is saved: `current_manifest_dir/sections/new_section_filename.plucky_section`.
        *   If presentation is unsaved: `PluckyStandards.get_sections_dir()/new_section_filename.plucky_section` (and the manifest path will be relative to this when saved). Or, prompt user.
    *   Create a basic section JSON structure (like "empty song" example, with the given title, a default slide, and a "Default" arrangement).
    *   Save this new section file.
    *   Call `presentation_manager.add_section_to_presentation(new_section_filepath, insertion_index)`.
    *   The user can then add/edit slides within this new section.

6.  **Adapt `update_slide_display_and_selection`:**
    *   `SongHeaderWidget` logic needs to get the title from the *section's metadata* (e.g., `section_object.title`) rather than `slide_data.song_title` if `slide_data.song_title` is deprecated for this purpose. The `PresentationManager.get_slides()` method should now return `SlideData` objects that also include a reference to their parent section's title or ID.
    *   The key is that `PresentationManager.get_slides()` assembles the flat list from the structured section data, including section titles for headers.

---

## Phase 4: `MainWindow` - Editing Operations & Commands

1.  **Identify Target Section for Edits:**
    *   When a slide is edited, `MainWindow` (or `SlideEditHandler`) needs to determine which loaded section file that slide belongs to. `PresentationManager.get_slides()` should augment `SlideData` with enough info (e.g., `section_file_path` or `section_id_from_manifest`).
    *   The corresponding section object in `PresentationManager.loaded_sections` must be marked as dirty.

2.  **Refactor Undo/Redo Commands:**
    *   Commands (`ChangeOverlayLabelCommand`, `EditLyricsCommand`, etc.) currently take a global `slide_index`.
    *   They will need to operate on:
        *   The `section_file_path` (or a unique ID for the loaded section).
        *   The `slide_id` (from the section's `slide_blocks`).
        *   The `arrangement_name` within that section if the change affects arrangement order or enabled status.
    *   `PresentationManager.do_command(command)` will route the command to modify data within a specific loaded section object.

3.  **Context Menus ("Insert Slide", "Add New Section"):**
    *   `_determine_insertion_context`: Will need to determine not just the global index but also the target section file and potentially the arrangement within that section.
    *   `_handle_insert_slide_from_layout`: Will call a `PresentationManager` method to add the slide to the correct section's `slide_blocks` and update its active arrangement in the manifest (or a default arrangement if adding to a section not yet in manifest).
    *   `_prompt_and_insert_new_section`: As described in Phase 3.5.

---

## Phase 5: Advanced Features & UI Enhancements

1.  **Section Management UI Panel:**
    *   Create a new widget class `SectionManagementPanel` (e.g., in `widgets/section_management_panel.py`).
    *   This panel will contain UI elements (list view, buttons) to manage sections.
    *   `MainWindow` will instantiate this panel and host it, likely within a `QDockWidget` to allow toggling its visibility.
    *   Add a "View" menu action in `MainWindow` to show/hide the Section Management Panel.
    *   The panel will display sections from `presentation_manager.presentation_manifest_data`.
    *   It will emit signals for actions (reorder, remove, add existing, change arrangement). `MainWindow` will connect these signals to new or existing `PresentationManager` methods (potentially via new `Command` objects).
    *   Allows:
        *   Creating a new section (prompts for type - e.g., Song/Generic - then title, creates typed file in central store, adds to current presentation).
        *   Reordering sections (modifies manifest, calls `presentation_manager.reorder_sections_in_manifest`).
        *   Deleting sections from presentation (removes from manifest, calls `presentation_manager.remove_section_from_presentation`). Optionally offer to delete the underlying section file if not used elsewhere.
        *   Adding existing section files (from `PluckyStandards.get_sections_dir()` or elsewhere) to the presentation.
        *   Changing the `active_arrangement_name` for a section within the presentation.
        *   Quick navigation.
    *   `PresentationManager.presentation_changed` signal should trigger a refresh of this panel.

2.  **Drag and Drop:**
    *   **Slides within a section's arrangement:** Modifies the arrangement array within that specific section file's data.
    *   **Slides between sections:** Complex. Involves:
        *   Removing the `slide_block` from source section's `slide_blocks` (if it's the last reference in any arrangement of that section).
        *   Removing from source section's active arrangement.
        *   Adding the `slide_block` to target section's `slide_blocks` (if not already present with same content).
        *   Adding to target section's active arrangement.
        *   Marking both section files and the manifest dirty.
    *   **Reordering sections in the UI Panel:** Modifies the presentation manifest order.

3.  **Error Handling and User Feedback:**
    *   Handle missing/moved section files gracefully when loading a presentation. Offer to locate or remove.
    *   Clearer status messages.

---

## Key Considerations During Implementation:

*   **File Paths:**
    *   Consistently use relative paths for section files within the manifest, anchored to the manifest file's location.
    *   Use `os.path.join`, `os.path.dirname`, `os.path.relpath`.
    *   `ApplicationConfigManager` should use `PluckyStandards` to get base paths like the UserStore root.
*   **IDs:**
    *   `slide_id` in `slide_blocks` must be unique *within that section file*.
    *   The `id` for a section *in the presentation manifest* must be unique *within that manifest*.
    *   The `id` for a section file itself (e.g., `song_a1b2...`) should be globally unique.
*   **`PresentationManager.get_slides()` Performance:** Optimize if it becomes a bottleneck. Caching the flattened list and invalidating it smartly is an option.
*   **Atomicity of Saves:** Consider strategies for saving multiple files (manifest + dirty sections).
*   **Backup/Autosave:** Plan for robust backup/autosave, especially with multiple files.
*   **Importing Sections:** When adding an existing section file from an arbitrary location to a presentation, offer to copy it into the presentation's local `sections/` subfolder to maintain portability and encapsulation. Update the manifest path accordingly.






other Todo
update presentation manager
`For now, many of the existing methods (add_slide, remove_slide, etc.) are left as stubs or with TODO comments because their logic will depend heavily on how load_presentation and get_slides are implemented. We're focusing on setting up the new internal data containers first.`