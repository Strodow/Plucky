import os
import hashlib
from PySide6.QtGui import QImage, QPixmap, QColor
from PySide6.QtCore import QSize, QStandardPaths, Qt, QDir
from typing import Optional

class ImageCacheManager:
    """
    Manages a cache of pre-scaled images to speed up rendering of large background images.
    """
    def __init__(self, cache_base_dir_name: str = "image_cache"):
        # Get the user's local app data directory
        app_data_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if not app_data_path: # Fallback if AppLocalDataLocation is not available
            app_data_path = QDir.homePath() 
            print(f"ImageCacheManager: Warning - AppLocalDataLocation not found, using home directory: {app_data_path}")

        # Define the cache directory within the application's data folder
        # Example: C:/Users/Logan/AppData/Local/YourOrganizationName/Plucky/image_cache
        # Or if AppLocalDataLocation is not found: C:/Users/Logan/image_cache (less ideal)
        # We'll use a subdirectory within the Plucky user store for better organization.
        try:
            from core.plucky_standards import PluckyStandards
            self.cache_directory = os.path.join(PluckyStandards.get_user_store_root(), cache_base_dir_name)
        except ImportError:
            # Fallback if PluckyStandards is not available during early init or testing
            # This path might need to be made more robust or passed in.
            # For now, let's assume PluckyStandards is available when this is used by the main app.
            # A simpler fallback for standalone testing:
            self.cache_directory = os.path.join(os.path.expanduser("~"), ".plucky_cache", cache_base_dir_name)
            print(f"ImageCacheManager: PluckyStandards not found, using fallback cache dir: {self.cache_directory}")

        self._ensure_cache_dir_exists()
        print(f"ImageCacheManager: Initialized. Cache directory: {self.cache_directory}")

    def _ensure_cache_dir_exists(self):
        """Creates the cache directory if it doesn't already exist."""
        if not os.path.exists(self.cache_directory):
            try:
                os.makedirs(self.cache_directory, exist_ok=True)
                print(f"ImageCacheManager: Created cache directory: {self.cache_directory}")
            except OSError as e:
                print(f"ImageCacheManager: Error creating cache directory {self.cache_directory}: {e}")
                # Fallback to a temporary directory or disable caching if creation fails
                # For now, we'll proceed, and operations might fail if dir isn't writable.

    def _generate_cache_filename(self, original_image_path: str, target_size: QSize) -> str:
        """
        Generates a unique filename for the cached image based on the original path and target size.
        Uses a hash to keep filenames manageable and avoid issues with special characters in paths.
        """
        # Normalize path to handle different slashes and case sensitivity (on some systems)
        normalized_path = os.path.normcase(os.path.abspath(original_image_path))
        
        # Create a string representation for hashing
        # Include file modification time to handle cases where the original image is updated
        try:
            mtime = os.path.getmtime(normalized_path)
        except OSError:
            mtime = 0 # Fallback if file doesn't exist or mtime can't be read

        identifier_string = f"{normalized_path}|{target_size.width()}x{target_size.height()}|{mtime}"
        
        # Use SHA256 for a robust hash
        hasher = hashlib.sha256()
        hasher.update(identifier_string.encode('utf-8'))
        hash_hex = hasher.hexdigest()
        
        # Keep original extension for easier identification, though not strictly necessary
        _, ext = os.path.splitext(original_image_path)
        if not ext: # Ensure there's an extension, default to .png
            ext = ".png"
            
        return f"{hash_hex}_w{target_size.width()}_h{target_size.height()}{ext.lower()}"

    def get_cached_image_path(self, original_image_path: str, target_size: QSize) -> Optional[str]:
        """
        Checks if a cached version of the image exists for the given target size.
        Returns the absolute path to the cached image if found, otherwise None.
        """
        if not original_image_path or not os.path.exists(original_image_path):
            return None # Original image doesn't exist

        cache_filename = self._generate_cache_filename(original_image_path, target_size)
        cached_file_path = os.path.join(self.cache_directory, cache_filename)

        if os.path.exists(cached_file_path):
            # print(f"ImageCacheManager: Cache HIT for '{original_image_path}' at size {target_size}. Path: {cached_file_path}")
            return cached_file_path
        else:
            # print(f"ImageCacheManager: Cache MISS for '{original_image_path}' at size {target_size}. Expected: {cached_file_path}")
            return None

    def cache_image(self, original_image_path: str, target_size: QSize, scaled_image_qimage: QImage) -> Optional[str]:
        """
        Saves the provided QImage (assumed to be already scaled) to the cache.
        Returns the path to the cached file, or None if saving fails.
        """
        if scaled_image_qimage.isNull():
            print(f"ImageCacheManager: Cannot cache null QImage for '{original_image_path}'.")
            return None

        cache_filename = self._generate_cache_filename(original_image_path, target_size)
        cached_file_path = os.path.join(self.cache_directory, cache_filename)

        try:
            # Determine format based on original extension, default to PNG
            _, original_ext = os.path.splitext(original_image_path)
            save_format = original_ext[1:].upper() if original_ext else "PNG"
            if save_format not in ["PNG", "JPG", "JPEG", "BMP"]: # Supported QImage save formats
                save_format = "PNG" # Default to PNG for broad support and alpha

            if scaled_image_qimage.save(cached_file_path, format=save_format, quality=90): # quality for JPG
                print(f"ImageCacheManager: Successfully cached '{original_image_path}' to '{cached_file_path}' as {save_format}.")
                return cached_file_path
            else:
                print(f"ImageCacheManager: Failed to save cached image to '{cached_file_path}'. QImage.save() returned false.")
                return None
        except Exception as e:
            print(f"ImageCacheManager: Exception while saving cached image '{cached_file_path}': {e}")
            # Attempt to remove partially written file if save failed
            if os.path.exists(cached_file_path):
                try: os.remove(cached_file_path)
                except OSError: pass
            return None

    def clear_cache_for_original(self, original_image_path: str, target_sizes: Optional[list[QSize]] = None):
        """
        Deletes cached versions of a specific original image.
        If target_sizes is provided, only those specific cached sizes are deleted.
        Otherwise, attempts to find and delete all cached versions (less precise without knowing all sizes used).
        """
        print(f"ImageCacheManager: Clearing cache for original image '{original_image_path}'.")
        if target_sizes:
            for size in target_sizes:
                cache_filename = self._generate_cache_filename(original_image_path, size)
                cached_file_path = os.path.join(self.cache_directory, cache_filename)
                if os.path.exists(cached_file_path):
                    try:
                        os.remove(cached_file_path)
                        print(f"  Removed cached file: {cached_file_path}")
                    except OSError as e:
                        print(f"  Error removing cached file {cached_file_path}: {e}")
        else:
            # This is less precise: tries to find files that *might* be related if target_sizes aren't known
            normalized_path_for_hash_part = os.path.normcase(os.path.abspath(original_image_path))
            # This is a simplified search; a more robust way would be to store metadata or use a database.
            # For now, we'll rely on the hash prefix if we don't have specific sizes.
            # This part is tricky without knowing all sizes it might have been cached at.
            # A full clear_entire_cache might be safer if precise invalidation is hard.
            print(f"  Precise cache clearing for '{original_image_path}' without target_sizes is complex. Consider full cache clear or providing sizes.")


    def clear_entire_cache(self):
        """Deletes all files in the cache directory."""
        print(f"ImageCacheManager: Clearing ENTIRE image cache at {self.cache_directory}...")
        if not os.path.isdir(self.cache_directory):
            print(f"  Cache directory not found: {self.cache_directory}")
            return
        
        for filename in os.listdir(self.cache_directory):
            file_path = os.path.join(self.cache_directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                # Optionally, handle subdirectories if your cache structure becomes more complex
            except Exception as e:
                print(f'  Failed to delete {file_path}. Reason: {e}')
        print("ImageCacheManager: Entire image cache cleared.")
