# Plucky Template System Evolution Plan (templatePlan)

This document outlines the proposed evolution of the Plucky templating system to support multiple, individually styled text boxes per slide.

## Core Concepts:

The system will be based on three main entities:

1.  **Layout Definitions (Layouts):**
    *   **Purpose:** Define the *structural* arrangement of text boxes on a slide.
    *   **Contents:**
        *   Number of text boxes.
        *   Unique identifier (ID/name) for each text box (e.g., "title", "body", "footer_left").
        *   Position (X, Y) and dimensions (width, height) for each text box.
        *   Overall slide background (color/image).
    *   **Creation:** When a new Layout is created, the user will be prompted for the number of text boxes it should contain. This number will be fixed for that specific Layout Definition.

2.  **Style Definitions (Styles):**
    *   **Purpose:** Define the *visual appearance* of text.
    *   **Contents:**
        *   Font properties (family, size, weight, italic).
        *   Text color.
        *   Text alignment (horizontal/vertical) within its box.
        *   (Future: effects like shadows, outlines).
    *   **Reusability:** Styles are designed to be highly reusable across different text boxes and Master Templates.

3.  **Master Templates (Display Templates):**
    *   **Purpose:** The final, usable template that a user applies to a slide. It combines a Layout with Styles.
    *   **Contents:**
        *   A reference to one **Layout Definition**.
        *   A mapping: For each text box ID defined in the chosen Layout, a reference to one **Style Definition** is assigned.

## `TemplateEditorWindow` Overhaul:

The `c:\Users\Logan\Documents\Plucky\Plucky\windows\template_editor_window.py` will be significantly redesigned to manage these three entities, likely with separate sections/tabs:

*   **Layout Management:**
    *   Create new Layouts (prompting for number of text boxes).
    *   Edit existing Layouts (adjusting text box positions, sizes, IDs).
    *   Delete Layouts.
*   **Style Management:**
    *   Create new Styles (defining font, color, alignment).
    *   Edit/Delete Styles.
*   **Master Template Assembly:**
    *   Create new Master Templates:
        1.  Select a Layout Definition.
        2.  For each text box in the selected Layout, assign a Style Definition.
    *   Edit/Delete Master Templates.
*   **"Modify Associated" Feature:** When editing a Master Template, provide buttons to quickly jump to editing the underlying Layout Definition or the assigned Style Definitions for a particular text box.

## Data Flow and Rendering:

*   **`SlideData`:**
    *   Will store a reference to the **Master Template** being used.
    *   Will store a dictionary of `text_contents`, mapping text box IDs (from the Layout) to the actual text strings for that slide.
*   **`SlideRenderer`:**
    1.  Retrieves the Master Template used by the `SlideData`.
    2.  From the Master Template, gets the Layout Definition (for positions/sizes) and the Style Definition assigned to each text box ID (for font/color/alignment).
    3.  Renders the text from `SlideData.text_contents` for each text box using its combined layout and style properties.

## Impact on `MainWindow`:

*   The currently disabled buttons (`add_song_button`, `add_test_slide_button`, `edit_template_button` in `c:\Users\Logan\Documents\Plucky\Plucky\windows\main_window.py`) will remain disabled until this new template system is functional.
*   Adding/editing slide content will require a new UI that dynamically presents input fields based on the text boxes defined in the chosen Master Template.