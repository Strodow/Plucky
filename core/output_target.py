from PySide6.QtGui import QPixmap, QPainter, QColor, QImage
from PySide6.QtCore import QObject, Signal, QSize, Qt, QRectF
from typing import Optional, TYPE_CHECKING, Dict, Any, List # Added List
import time # For benchmarking
import copy # For deepcopy if needed, though direct rendering is preferred

if TYPE_CHECKING:
    from rendering.slide_renderer import LayeredSlideRenderer
    from data_models.slide_data import SlideData

class OutputTarget(QObject):
    """
    Represents a destination for rendered slide content.
    Manages its own background and content layers and composites them.
    """
    pixmap_updated = Signal(QPixmap) # Emits the final composited pixmap

    def __init__(self, name: str, target_size: QSize, slide_renderer: 'LayeredSlideRenderer', parent: Optional[QObject] = None):
        super().__init__(parent)
        self.name = name
        self.target_size = target_size
        self.slide_renderer = slide_renderer

        self._active_background_slide_data: Optional['SlideData'] = None
        self._active_content_slide_data: Optional['SlideData'] = None # The slide providing the foreground content

        self._cached_background_pixmap: Optional[QPixmap] = None
        self._cached_content_pixmap: Optional[QPixmap] = None # Rendered with its own transparency

        self.final_composited_pixmap: QPixmap = QPixmap(target_size)
        if self.final_composited_pixmap.isNull():
            print(f"OutputTarget '{self.name}': Failed to create final_composited_pixmap of size {target_size}. Using 1x1.")
            self.final_composited_pixmap = QPixmap(1,1) # Fallback
        
        self._cached_key_matte_pixmap: Optional[QPixmap] = None
        self._key_matte_dirty: bool = True
        self.final_composited_pixmap.fill(Qt.GlobalColor.black) # Default to black
    
    def update_slide(self,
                     slide_data: Optional['SlideData'],
                     section_metadata: Optional[List[Dict[str, str]]] = None,
                     section_title: Optional[str] = None):
        """
        Updates the output based on the provided slide_data.
        Determines if it's a background or content update.
        Passes section_metadata and section_title to the renderer.
        """
        update_start_time = time.perf_counter()
        # Store metadata and title for use in internal render calls
        self._current_section_metadata = section_metadata
        self._current_section_title = section_title
        # print(f"OutputTarget '{self.name}': Updating with slide_data (ID: {slide_data.id if slide_data else 'None'})")

        needs_recomposite = False

        if not slide_data: # Blanking the output
            if self._active_background_slide_data is not None or self._cached_background_pixmap is not None:
                needs_recomposite = True
            if self._active_content_slide_data is not None or self._cached_content_pixmap is not None:
                needs_recomposite = True
            
            self._active_background_slide_data = None
            self._active_content_slide_data = None
            self._cached_background_pixmap = None
            self._cached_content_pixmap = None
            if needs_recomposite:
                recomposite_start_time = time.perf_counter()
                self._recomposite_and_emit()
                # self._key_matte_dirty will be set in _recomposite_and_emit
                print(f"  OutputTarget '{self.name}': _recomposite_and_emit (blanking) took: {(time.perf_counter() - recomposite_start_time):.4f}s")
            print(f"OutputTarget '{self.name}': update_slide total for BLANK took: {(time.perf_counter() - update_start_time):.4f}s")


            return

        if slide_data.is_background_slide:
            # This slide defines the new background. It might also have its own content.
            if self._active_background_slide_data != slide_data or not self._cached_background_pixmap:
                render_bg_start_time = time.perf_counter()
                self._render_background_part(slide_data) # This renders the full slide (BG + its text)
                print(f"  OutputTarget '{self.name}': _render_background_part for '{slide_data.id}' took: {(time.perf_counter() - render_bg_start_time):.4f}s")
                needs_recomposite = True
            else: # Background is the same and cached
                self._active_background_slide_data = slide_data # Ensure active data points to current instance

            # When a background slide is active, it IS the content.
            # There's no separate content overlay from another slide.
            # So, clear any existing cached content pixmap.
            if self._cached_content_pixmap is not None:
                self._cached_content_pixmap = None
                needs_recomposite = True # Need to recomposite to remove the old overlay
            self._active_content_slide_data = None # No separate active content slide

        else: # This is a content-only slide
            # The background (_cached_background_pixmap) remains from the last background-setting slide.
            # We only need to update/render the content part if this content slide is different.
            if self._active_background_slide_data is None: # Check if a background was ever set
                print(f"  OutputTarget '{self.name}': No active background, ensuring default for content slide '{slide_data.id}'.")
                needs_recomposite = True

            # This slide provides the new content.
            # Store what was the active content slide *before* this update for comparison
            previous_content_slide_for_cache_check = self._active_content_slide_data
            # Now, set the current slide as the active content slide
            self._active_content_slide_data = slide_data

            if self._active_content_slide_data != slide_data or not self._cached_content_pixmap:
                render_content_start_time = time.perf_counter()
                self._render_content_part(slide_data)
                print(f"  OutputTarget '{self.name}': _render_content_part for '{slide_data.id}' (content slide) took: {(time.perf_counter() - render_content_start_time):.4f}s")
                needs_recomposite = True
            elif previous_content_slide_for_cache_check != slide_data: # Content is cached, but slide_data changed
                 # This case handles if the content slide object instance changed but content is identical
                 # and was cached from a previous identical instance.
                 # We still need to mark for recomposite if the active_content_slide_data pointer changed.
                 needs_recomposite = True

        if needs_recomposite:
            recomposite_start_time = time.perf_counter()
            self._recomposite_and_emit()
            print(f"  OutputTarget '{self.name}': _recomposite_and_emit took: {(time.perf_counter() - recomposite_start_time):.4f}s")
        else:
            print(f"  OutputTarget '{self.name}': No change in slide data or cache hit for relevant layers. No recomposite needed.")
            print(f"OutputTarget '{self.name}': update_slide total for '{slide_data.id if slide_data else 'None'}' took: {(time.perf_counter() - update_start_time):.4f}s")


    def _render_background_part(self, bg_slide_data: 'SlideData'):
        """Renders the background slide and updates _cached_background_pixmap."""
        # print(f"OutputTarget '{self.name}': Rendering background part for slide ID {bg_slide_data.id}")
        self._active_background_slide_data = bg_slide_data
        # Render this background slide fully (it handles its own BG and text if any)
        # base_pixmap=None ensures it's rendered standalone.
        rendered_pixmap, font_error, detailed_benchmarks = self.slide_renderer.render_slide(
            bg_slide_data, self.target_size.width(), self.target_size.height(),
            base_pixmap=None, is_final_output=True, # Assuming True for actual output targets
            section_metadata=self._current_section_metadata,
            section_title=self._current_section_title
        )
        self._cached_background_pixmap = rendered_pixmap
        print(f"    OutputTarget '{self.name}': _render_background_part - Detailed benchmarks: {detailed_benchmarks}")

    def _render_content_part(self, content_slide_data: 'SlideData'):
        """
        Renders the 'content' aspect of a slide (its own BG + text) onto a transparent base.
        This becomes the self._cached_content_pixmap.
        """
        # print(f"OutputTarget '{self.name}': Rendering content part for slide ID {content_slide_data.id}")

        self._active_content_slide_data = content_slide_data
        
        # Create a fully transparent pixmap of the target size to render the content layer onto.
        # This ensures that the content_pixmap only contains the content slide's elements
        # (including its own background if it has one, like a semi-transparent bar)
        # and the rest is transparent to allow the main background to show through during compositing.
        transparent_base_for_content_layer = QPixmap(self.target_size)
        if transparent_base_for_content_layer.isNull():
             print(f"OutputTarget '{self.name}': Failed to create transparent_base_for_content_layer. Using 1x1.")
             transparent_base_for_content_layer = QPixmap(1,1)
        transparent_base_for_content_layer.fill(Qt.GlobalColor.transparent)

        rendered_pixmap, font_error, detailed_benchmarks = self.slide_renderer.render_slide(
            content_slide_data, self.target_size.width(), self.target_size.height(),
            base_pixmap=transparent_base_for_content_layer, is_final_output=True,
            section_metadata=self._current_section_metadata,
            section_title=self._current_section_title
        )
        self._cached_content_pixmap = rendered_pixmap
        print(f"    OutputTarget '{self.name}': _render_content_part - Detailed benchmarks: {detailed_benchmarks}")

    def _recomposite_and_emit(self):
        """Composites the cached background and content pixmaps."""
        # print(f"OutputTarget '{self.name}': Recompositing...")
        self.final_composited_pixmap.fill(Qt.GlobalColor.black) # Start fresh with black (or a default bg color)
        painter_start_time = time.perf_counter()
        painter = QPainter(self.final_composited_pixmap)

        if self._cached_background_pixmap and not self._cached_background_pixmap.isNull():
            painter.drawPixmap(0, 0, self._cached_background_pixmap)
            # print(f"  Drew background pixmap (Size: {self._cached_background_pixmap.size()})")

        # The _cached_content_pixmap is rendered with its own transparency,
        # so drawing it on top works correctly.
        if self._cached_content_pixmap and not self._cached_content_pixmap.isNull():
            painter.drawPixmap(0, 0, self._cached_content_pixmap)
            # print(f"  Drew content pixmap (Size: {self._cached_content_pixmap.size()})")

        painter.end()
        # print(f"    OutputTarget '{self.name}': QPainter operations took: {(time.perf_counter() - painter_start_time):.4f}s")

        self.pixmap_updated.emit(self.final_composited_pixmap)
        self._key_matte_dirty = True # Mark key as dirty whenever fill is updated
        # print(f"OutputTarget '{self.name}': Emitted pixmap_updated.")


    def get_current_pixmap(self) -> QPixmap:
        return self.final_composited_pixmap

    def get_key_matte(self) -> QPixmap:
        """
        Generates or retrieves the key matte. The key matte is derived from the
        alpha channel of the final_composited_pixmap (the fill signal).
        Opaque areas in fill become white in key, transparent in fill become black in key.
        """
        if not self._key_matte_dirty and self._cached_key_matte_pixmap is not None:
            return self._cached_key_matte_pixmap

        if self.final_composited_pixmap.isNull():
            print(f"OutputTarget '{self.name}': final_composited_pixmap is null in get_key_matte. Returning black matte.")
            error_matte = QPixmap(self.target_size)
            if error_matte.isNull(): error_matte = QPixmap(1,1)
            error_matte.fill(Qt.GlobalColor.black)
            return error_matte

        source_fill_image = self.final_composited_pixmap.toImage()
        if source_fill_image.isNull():
            print(f"OutputTarget '{self.name}': Failed to convert final_composited_pixmap to QImage for key matte.")
            error_matte = QPixmap(self.target_size)
            if error_matte.isNull(): error_matte = QPixmap(1,1)
            error_matte.fill(Qt.GlobalColor.black)
            return error_matte

        # Ensure the image is in a format with an alpha channel we can process
        if source_fill_image.format() != QImage.Format_ARGB32_Premultiplied and \
           source_fill_image.format() != QImage.Format_ARGB32:
            source_fill_image = source_fill_image.convertToFormat(QImage.Format_ARGB32_Premultiplied)

        # Convert the source image's alpha information into an alpha mask (grayscale image)
        alpha_mask_image = source_fill_image.convertToFormat(QImage.Format_Alpha8)
        if alpha_mask_image.isNull():
            print(f"OutputTarget '{self.name}': Failed to convert source_fill_image to Format_Alpha8 for key matte.")
            error_matte = QPixmap(self.target_size); error_matte.fill(Qt.GlobalColor.black); return error_matte

        # Create the key matte: black background, with white elements derived from the alpha mask
        key_matte_pixmap = QPixmap(self.target_size)
        key_matte_pixmap.fill(Qt.GlobalColor.black)

        matte_painter = QPainter(key_matte_pixmap)
        # Create a temporary white image, apply the derived alpha mask to it
        white_source_for_matte = QImage(self.target_size, QImage.Format_ARGB32_Premultiplied)
        white_source_for_matte.fill(Qt.GlobalColor.white)
        white_source_for_matte.setAlphaChannel(alpha_mask_image)

        matte_painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        matte_painter.drawImage(0, 0, white_source_for_matte)
        matte_painter.end()

        self._cached_key_matte_pixmap = key_matte_pixmap
        self._key_matte_dirty = False
        return self._cached_key_matte_pixmap