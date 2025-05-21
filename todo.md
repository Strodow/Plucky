# Plucky Project TODO

## 🎯 Immediate Priorities
- [ ] Enable "Add Song" functionality and begin work on the Song Creation Window.
- [ ] Change Undo/Redo buttons to use arrow icons.
- [ ] Implement a media pool toggle/feature.
- [ ] Investigate modern dictionary search/highlighting for spellcheck.

## ✨ Features & Enhancements
### Main Window
- [X] Change "Go Live" button to a circle (red when ON, no fill when OFF).
- [X] Change preview size to display as 1x, 2x, 3x, etc.
- [X] Move Load, Save, Recents into a "File" (or "Project") dropdown menu.
- [X] Move Settings and "Edit Templates" into menus.
- [X] Set the application icon for different OSs.
- [X] Re-reference `app_settings.json` for settings.
- [X] Add a timer rotation button on the section bar.
- [X] Update main window background context menu (Add new slide w/ layouts, Add new Section).
- [ ] Get the slides working with the new templates.
- [ ] Add "Recent Projects" button (if different from recent files menu).
- [ ] Medium term caching for thumbnails.
- [ ] Better error handling when hovering over a slide with an error (use the warning icon/info from output).


### Song Creation Window (New)
- [ ] Design and implement the Song Creation Window.
- [ ] Button for adding simple lyrics (empty line with `\n` = new slide).
- [ ] Button / tab for adding quick Title / Attribution.
- [ ] Allow color-coding of templates (to quickly ID if wrong template is on a slide).
- [ ] Drag and drop images.
- [ ] Add back lightweight spellcheck / custom dictionary.
- [ ] Define layout: Songs vertical list on left, large text preview center, controls right (add types/template).
- [ ] Add functionality for showing attribution (default attribution / title templates for quick adding).
- [ ] Add a custom delimiter for slide separation (e.g., "#.", "\\").

### Template Editor
- [X] Renaming existing layouts (add logic still).
- [ ] Implement logic for renaming layouts.
- [ ] Changing layout background color.
- [ ] Setup a color so templates can be color-coded for quick identification.
- [ ] Add a list of text boxes (so if one gets sent to the "ether", they can delete it).
- [ ] Locking/Unlocking text boxes (prevent move/resize).
- [ ] Fix error related to moving textbox buttons above the editing area (likely in UI file).
- [ ] Adding Rulers to the layout preview.
- [ ] Check on Windows if the cursor changes on hover for drag points.

### Settings Window
- [X] Create a Settings Window.
- [X] Implement OpenSource/Pro/Dev toggle (add logic still).
- [ ] Add logic for OpenSource/Pro/Dev toggle.
- [X] Change "Edit Template" to "Templates" (likely referring to button/menu text).
- [X] Check if the monitor selectors are working on Windows.
- [X] Add collapsible section for benchmarks.
- [X] Add program load time stats back.
- [X] Move screen selection into the Settings Window.
- [ ] Place to set default templates and styles.
- [ ] Default Card background color (allow for transparent and checkerboard).

### Output Window
- [ ] Update the template information displayed/used by the output window.

### DeckLink Integration
- [ ] Blackmagic DeckLink card integration.
- [ ] C#/C++ DLL for Blackmagic DeckLink control.

### Media Management
- [ ] Add a media pool.
- [ ] Add a way to clean up the media pool or at least show space usage.



## 🛠️ Technical Debt & Refactoring
- [ ] Refactor Large Methods:
    - [ ] Break down `update_slide_display_and_selection()` for readability.
    - [ ] Break down `handle_apply_template_to_slide()` for readability.
- [ ] Enhance Undo/Redo for All Operations:
    - [ ] Wrap `handle_add_song()` in Command objects.
    - [ ] Wrap `handle_edit_song_title_requested()` in Command objects.
- [ ] Minor Code Organization:
    - [ ] Move `BASE_PREVIEW_WIDTH` to `core/constants.py`.
    - [ ] Address circular dependency between `MainWindow` and `SlideDragDropHandler`.
- [ ] Deployment-Focused Refinements:
    - [ ] Change Benchmark File Location to a standard user application data path.
- [ ] Performance Optimizations:
    - [ ] Revisit DeckLink SDK Lifecycle (initialize once vs. per toggle) if performance issues arise.
- [ ] Refactor: Pull Template Editor Layout tab functionality into a separate Python file/module.

## 🚀 Future Ideas / Long-Term Goals
- [ ] PP, proP importing
- [ ] Transitions
- [ ] maybe output preview? (if it's still feeling light weight)
- [ ] Add a backup feature and on top of that if it's in a network share, you'd be able to commit changes like github and have another person pull to their computer and review
- [ ] Collaborative Project/Song Management (Git-based Backend):
  - [ ] Define file format for individual songs (e.g., `.plucky_song` - text-based, JSON/YAML).
  - [ ] Define file format for presentations (e.g., `.plucky_pres` - text-based, referencing songs).
  - [ ] Implement UI for creating/editing/saving individual songs to a local `songs/` directory.
  - [ ] Implement UI for creating/editing/saving presentations (referencing songs) to a local `presentations/` directory.
  - [ ] Integrate Git operations (via a library like `pygit2` or `LibGit2Sharp`):
    - [ ] Allow user to configure a remote Git repository path (network share).
    - [ ] Implement "Clone/Open from Network Share" functionality.
    - [ ] Implement "Save & Share to Network" (commit & push) functionality.
    - [ ] Implement "Get Latest from Network" (pull) functionality.
  - [ ] Develop a strategy for notifying users about/handling Git merge conflicts.
  - [ ] Font Management Strategy for Collaboration (for now throw an error icon on the slide if missing font):
    - [ ] Implement robust font fallback logic in Plucky (if specified font is not found, use alternatives, then a default).
    - [ ] Display clear warnings to the user if a presentation/template requires a font that is not available on their system (and a fallback is used).
    - [ ] Investigate allowing users to include font files (`.ttf`, `.otf`) in a project-specific `fonts/` directory.
      - [ ] Plucky needs to be able to load/register fonts from this local project `fonts/` directory at runtime.
      - [ ] Implement a strong warning/disclaimer about font licensing when users add fonts to the project directory.
  - [ ] (Future) Explore splitting `songs/` into a dedicated "Song Library" repository if monorepo becomes too large.

