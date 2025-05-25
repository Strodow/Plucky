# Slide Output Refactor Plan

This document outlines the plan to refactor the slide output system in Plucky to be more robust, flexible, and prepare for features like shared caching and diverse output targets.

## Core Goal

To introduce distinct "OutputTarget" objects, one for the main on-screen display and one for DeckLink (and potentially others in the future), managed consistently by `MainWindow`.

## Phases of Implementation

### Phase 1: Create the `OutputTarget` Class

This class will be the cornerstone of the new system, encapsulating the logic for managing a single output destination.

1.  **Define `OutputTarget` Class:**
    *   Create a new file: `core/output_target.py`.
    *   **Class Definition**:
        *   Inherit from `QObject`.
        *   Emit a signal: `pixmap_updated = Signal(QPixmap)`.
    *   **Attributes**:
        *   `name: str` (e.g., "MainScreen", "DeckLink")
        *   `target_size: QSize`
        *   `slide_renderer: LayeredSlideRenderer` (reference)
        *   Internal state for active slide data:
            *   `_active_background_slide_data: Optional[SlideData]`
            *   `_active_content_slide_data: Optional[SlideData]`
        *   Internal cached pixmaps:
            *   `_cached_background_pixmap: Optional[QPixmap]`
            *   `_cached_content_pixmap: Optional[QPixmap]` (rendered with its own transparency)
        *   `final_composited_pixmap: QPixmap`
    *   **Methods**:
        *   `update_slide(self, slide_data: Optional[SlideData])`:
            *   Main entry point.
            *   Determines if `slide_data` is a background setter or content.
            *   Updates `_active_background_slide_data` or `_active_content_slide_data`.
            *   Calls internal methods to re-render cached pixmaps *only if necessary*.
            *   Calls `_recomposite_and_emit()`.
        *   `_render_background_part(self, bg_slide_data: SlideData)`: Renders the background slide and updates `_cached_background_pixmap`.
        *   `_render_content_part(self, content_slide_data: SlideData)`: Renders the content slide (with its own transparency) and updates `_cached_content_pixmap`.
        *   `_recomposite_and_emit()`: Composites `_cached_background_pixmap` and `_cached_content_pixmap` into `final_composited_pixmap` and emits `pixmap_updated`.
        *   `get_current_pixmap() -> QPixmap`: Returns `final_composited_pixmap`.
        *   `get_key_matte() -> Optional[QPixmap]`: Generates the key matte, primarily based on `_active_content_slide_data`.

### Phase 2: Integrate `OutputTarget` into `MainWindow`

Refactor `MainWindow` to utilize `OutputTarget` instances.

1.  **Instantiate `OutputTarget`s in `MainWindow`**:
    *   Add `self.main_output_target: Optional[OutputTarget]` and `self.decklink_output_target: Optional[OutputTarget]`.
    *   Create `_init_main_output_target()` and `_init_decklink_output_target()` helper methods to initialize these when configurations (screen resolution, DeckLink mode) are known/change.
2.  **Connect `OutputTarget` Signals**:
    *   Connect `main_output_target.pixmap_updated` to `self.output_window.set_pixmap`.
    *   Connect `decklink_output_target.pixmap_updated` to a new method, e.g., `self._handle_decklink_target_update(fill_pixmap: QPixmap)`.
3.  **Refactor `MainWindow._display_slide(self, index: int)`**:
    *   Simplify to get `slide_data_to_display`.
    *   Call `self.main_output_target.update_slide(slide_data_to_display)` if active.
    *   Call `self.decklink_output_target.update_slide(slide_data_to_display)` if active.
    *   Retain `self.current_live_background_pixmap` and `self.current_background_slide_id` in `MainWindow` for UI-specific logic (e.g., `SlideUIManager` needs).
4.  **Implement `MainWindow._handle_decklink_target_update(self, fill_pixmap: QPixmap)`**:
    *   Get `key_matte_pixmap` from `self.decklink_output_target.get_key_matte()`.
    *   Convert pixmaps to `QImage` and then to bytes.
    *   Send to `decklink_handler.send_external_keying_frames()`.
5.  **Refactor `MainWindow._show_blank_on_output()`**:
    *   Call `update_slide(None)` on active `OutputTarget` instances.
6.  **Update Output Initialization Logic**:
    *   `toggle_live()` calls `_init_main_output_target()`.
    *   `toggle_decklink_output_stream()` calls `_init_decklink_output_target()`.
    *   Handle re-creation of `OutputTarget`s if output resolutions or DeckLink modes change.

### Phase 3: Shared Caching Strategy (Optional but Recommended for Future)

Focus on sharing rendered layers if multiple `OutputTarget`s display the same component at the same resolution.

1.  **Introduce `RenderCacheManager` (Conceptual)**:
    *   Stores rendered pixmaps (e.g., for backgrounds) keyed by `slide_data.id` (or hash) and `QSize`.
2.  **Modify `OutputTarget` to Use `RenderCacheManager`**:
    *   Query cache before rendering internal `_cached_background_pixmap` or `_cached_content_pixmap`.
    *   If cache miss, render and offer to cache.
3.  **Cache Invalidation Strategy**:
    *   Invalidate on `slide_data` change, renderer settings change, or presentation close.

### Phase 4: Video Integration (Future)

Integrate video backgrounds using the new `OutputTarget` structure.

1.  **Option A: "Video Layer in `OutputWindow`"**:
    *   `MainWindow` tells `OutputTarget` to use a transparent/passthrough background.
    *   `MainWindow` manages `QVideoWidget` visibility in `OutputWindow`.
    *   `OutputTarget`'s content pixmap is overlaid. DeckLink requires frame grabbing and manual compositing.
2.  **Option B: "Decode Frames and Draw to Pixmap" (Preferred for DeckLink consistency)**:
    *   Create `VideoBackgroundRenderLayer` in `LayeredSlideRenderer`.
    *   `OutputTarget._render_background_part` invokes this layer for video slides.
    *   `MainWindow` uses a timer to call `output_target.update_slide()` at video frame rate.

## Implementation Order

1.  **Phase 1**: Implement and test `OutputTarget` class.
2.  **Phase 2**: Refactor `MainWindow` to use `OutputTarget` instances. This is the largest part.
3.  **Phase 3 (Shared Caching)**: Defer until core system is stable. This is an optimization.
4.  **Phase 4 (Video Integration)**: Tackle after static image rendering via `OutputTarget`s is robust.