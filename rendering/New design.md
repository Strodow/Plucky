# Design Document: Dynamic Multi-Layer Rendering Engine

## 1. Overview

The goal of this redesign is to evolve the existing `slide_renderer.py` into a fully dynamic, multi-layered composition engine. The current system has a fixed-order pipeline (Background -> Video -> Text) and a data model (`SlideData`) that conflates a single slide's content with its entire visual structure.

The new design will allow for an arbitrary number of layers, in any order, with support for transparency. This enables complex visual compositions, such as placing text *behind* a semi-transparent video, layering multiple images, or having several independent text elements on screen simultaneously.

## 2. Core Concepts: `Scene` and `Layer`

We will replace the monolithic `SlideData` object with two new core data structures: `Scene` and `Layer`.

#### A. The `Scene` Object

A `Scene` represents the entire visual output at a given moment. It is simply a container for an ordered list of `Layer` objects. It does not contain any styling information itself, other than the overall dimensions.

**Structure:**
```json
{
  "width": 1920,
  "height": 1080,
  "layers": [
    // ... ordered list of Layer objects ...
  ]
}
```

#### B. The `Layer` Object

A `Layer` is the fundamental building block of a `Scene`. It represents a single, atomic piece of content. Each layer has a `type` that determines its content and a `properties` object that defines its specific attributes.

**Base Layer Structure:**
```json
{
  "id": "unique_layer_name_123",
  "type": "image",
  "visible": true,
  "opacity": 1.0,
  "position": {
    "x_pc": 0.0,
    "y_pc": 0.0,
    "width_pc": 100.0,
    "height_pc": 100.0
  },
  "properties": {
    // ... type-specific properties go here ...
  }
}
```
* **`id`**: A unique identifier for the layer.
* **`type`**: Determines the content (`image`, `video`, `text`, `solid_color`, `shape`).
* **`visible`**: A boolean to easily toggle the layer's visibility.
* **`opacity`**: A float from `0.0` (fully transparent) to `1.0` (fully opaque) that affects the entire layer.
* **`position`**: Defines the bounding box for the layer's content using percentages of the total scene dimensions.

---

## 3. Layer Types & Properties

Here are the proposed initial layer types and their specific properties. This model is easily extensible with new types in the future (e.g., gradients, web content).

#### **`image` Layer**
Renders a static image.

```json
{
  "type": "image",
  "properties": {
    "path": "C:/path/to/my/image.png",
    "scaling_mode": "fit"
  }
}
```
* **`scaling_mode`**: How the image fits its bounding box. Can be `"fit"` (maintains aspect ratio, letterboxed), `"fill"` (maintains aspect ratio, crops to fill), or `"stretch"` (ignores aspect ratio).

#### **`video` Layer**
Renders a video file.

```json
{
  "type": "video",
  "properties": {
    "path": "C:/path/to/my/video.mp4",
    "scaling_mode": "fit",
    "loop": true,
    "playback_speed": 1.0
  }
}
```

#### **`text` Layer**
Renders a block of text.

```json
{
  "type": "text",
  "properties": {
    "content": "Hello, World!\nThis is line two.",
    "font_family": "Arial",
    "font_size": 72,
    "font_color": "#FFFF00FF",
    "force_all_caps": false,
    "h_align": "center",
    "v_align": "center",
    "shadow": {
      "enabled": true,
      "color": "#00000080",
      "offset_x": 3,
      "offset_y": 3
    },
    "outline": {
      "enabled": true,
      "color": "#000000FF",
      "width": 2
    }
  }
}
```
* **`font_size`**: A base size in points. The renderer will automatically scale this relative to the scene resolution (e.g., relative to 1080p).
* **`font_color`**: An RGBA Hex string (`#RRGGBBAA`).
* **`h_align` / `v_align`**: Horizontal/vertical alignment of text within its bounding box (`left`/`center`/`right` and `top`/`center`/`bottom`).

#### **`solid_color` Layer**
Renders a solid color rectangle. This is a specialized, simpler version of the `shape` layer.

```json
{
  "type": "solid_color",
  "properties": {
    "color": "#80000000"
  }
}
```
* **`color`**: An RGBA Hex string (`#RRGGBBAA`).

#### **`shape` Layer (New)**
Renders a basic geometric shape.

```json
{
  "type": "shape",
  "properties": {
    "shape_type": "ellipse",
    "fill_color": "#FF000080",
    "stroke": {
      "enabled": true,
      "color": "#FFFFFFFF",
      "width": 5
    }
  }
}
```
* **`shape_type`**: The kind of shape to draw. Can be `"rectangle"` or `"ellipse"`.
* **`fill_color`**: The color used to fill the shape. An RGBA Hex string (`#RRGGBBAA`).
* **`stroke`**: An object defining the shape's outline.
    * **`enabled`**: boolean.
    * **`color`**: RGBA Hex string for the stroke color.
    * **`width`**: The width of the stroke in pixels (will be scaled with resolution).

---

## 4. Renderer Architecture

The rendering architecture will be updated to process the new `Scene` and `Layer` models.

#### A. Main Renderer: `CompositionRenderer`

The `LayeredSlideRenderer` will be renamed to `CompositionRenderer`. Its primary method, `render_scene`, will take a `Scene` object as input. The rendering logic remains the same, but it will now be able to handle the new `shape` layer type.

#### B. Layer Handlers: `RenderLayerHandler`

A new `ShapeLayerHandler` will need to be created. It will be responsible for parsing the `shape` layer properties and using `QPainter` to draw the appropriate shape with the specified fill and stroke.

**New `render` signature:**
```python
from abc import ABC, abstractmethod
from PySide6.QtGui import QPixmap

class RenderLayerHandler(ABC):
    @abstractmethod
    def render(self,
               current_pixmap: QPixmap,
               layer_data: dict, # A dictionary representing the Layer object
               target_width: int,
               target_height: int) -> QPixmap:
        pass
```

---

## 5. Example `Scene` Composition

This example demonstrates the power and flexibility of the new design. It creates a scene with a full-screen background image, a title, a semi-transparent black bar across the bottom, main text on top of that bar, and now a semi-transparent red circle with a white outline.

```json
{
  "width": 1920,
  "height": 1080,
  "layers": [
    {
      "id": "background_image",
      "type": "image",
      "visible": true,
      "opacity": 1.0,
      "position": { "x_pc": 0, "y_pc": 0, "width_pc": 100, "height_pc": 100 },
      "properties": {
        "path": "resources/default_background.png",
        "scaling_mode": "fill"
      }
    },
    {
      "id": "decorative_circle",
      "type": "shape",
      "visible": true,
      "opacity": 1.0,
      "position": { "x_pc": 75, "y_pc": 5, "width_pc": 20, "height_pc": 20 },
      "properties": {
        "shape_type": "ellipse",
        "fill_color": "#FF000080",
        "stroke": { "enabled": true, "color": "#FFFFFFFF", "width": 5 }
      }
    },
    {
      "id": "title_text",
      "type": "text",
      "visible": true,
      "opacity": 1.0,
      "position": { "x_pc": 5, "y_pc": 5, "width_pc": 90, "height_pc": 20 },
      "properties": {
        "content": "Amazing Grace",
        "font_family": "Impact", "font_size": 90, "font_color": "#FFFFFFFF",
        "h_align": "center", "v_align": "center",
        "outline": { "enabled": true, "color": "#000000FF", "width": 4 }
      }
    },
    {
      "id": "transparent_bar",
      "type": "solid_color",
      "visible": true,
      "opacity": 1.0,
      "position": { "x_pc": 0, "y_pc": 70, "width_pc": 100, "height_pc": 30 },
      "properties": {
        "color": "#C0000000"
      }
    },
    {
      "id": "main_lyrics",
      "type": "text",
      "visible": true,
      "opacity": 1.0,
      "position": { "x_pc": 5, "y_pc": 72, "width_pc": 90, "height_pc": 26 },
      "properties": {
        "content": "Amazing grace, how sweet the sound\nThat saved a wretch like me",
        "font_family": "Arial", "font_size": 72, "font_color": "#FFFFFFFF",
        "h_align": "center", "v_align": "center"
      }
    }
  ]
}
```

## 6. Benefits of this Design

* **Ultimate Flexibility**: Users can create any composition by simply ordering layers in a list.
* **Scalability**: Adding new layer types (e.g., `GradientLayerHandler`, `WebLayerHandler`) is straightforward and does not require changing the core renderer.
* **Separation of Concerns**: The renderer orchestrates the process, while handlers are experts at rendering one specific thing. Data is cleanly separated from logic.
* **Clarity**: The `Scene` model is a declarative, human-readable representation of the final output, making it easier to debug, save, and load complex visual states.
* **Dynamic Control**: Individual layers can be easily toggled (`visible`), faded (`opacity`), moved, or have their properties changed at runtime without rebuilding the entire structure.
