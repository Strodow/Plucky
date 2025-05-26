import sqlite3
import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple

try:
    from .plucky_standards import PluckyStandards
    # Assuming PresentationIOHandler is where manifest loading logic resides
    # This is a placeholder for whatever class handles reading presentation manifest data
    # from .presentation_io_handler import PresentationIOHandler
except ImportError:
    # Fallback for potential execution context issues, adjust as needed
    from plucky_standards import PluckyStandards
    # class PresentationIOHandler: # Placeholder
    #     def load_manifest_data_from_file(self, filepath: str) -> Optional[Dict[str, Any]]:
    #         print(f"Warning: Using placeholder PresentationIOHandler to load {filepath}")
    #         # This would need actual implementation to read .plucky_pres files
    #         return None


class ResourceTracker:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or PluckyStandards.get_resource_db_path()
        self._ensure_db_initialized()
        # self.io_handler = PresentationIOHandler() # Or get it passed in

    def _get_connection(self):
        return sqlite3.connect(self.db_path, timeout=10) # Added timeout for potentially busy DB

    def _ensure_db_initialized(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        # --- Sections Table ---
        # Stores info about .plucky_section files in the central store
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sections (
                section_filename TEXT PRIMARY KEY,
                title TEXT,
                internal_file_id TEXT, 
                last_seen_in_presentations TEXT, -- JSON list of presentation filenames
                last_full_scan_timestamp INTEGER,
                discovered_timestamp INTEGER
            )
        ''')
        # --- Cached Backgrounds Table ---
        # Stores info about images in the ImageCacheManager
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_backgrounds (
                cache_key TEXT PRIMARY KEY, -- Typically the original image path
                last_seen_in_presentations TEXT, -- JSON list of presentation filenames
                last_full_scan_timestamp INTEGER,
                discovered_timestamp INTEGER
            )
        ''')
        # --- Presentations Table ---
        # Keeps track of presentations that have been scanned
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presentations (
                filepath TEXT PRIMARY KEY,
                last_scanned_for_resources_timestamp INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    # --- Section Tracking ---
    def add_or_update_section_info(self, section_filename: str, title: str, internal_file_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sections (section_filename, title, internal_file_id, last_seen_in_presentations, discovered_timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(section_filename) DO UPDATE SET
                title=excluded.title,
                internal_file_id=excluded.internal_file_id
        ''', (section_filename, title, internal_file_id, json.dumps([]), int(time.time())))
        conn.commit()
        conn.close()

    def mark_section_used(self, section_filename: str, presentation_filepath: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        # Ensure the section record exists before trying to update its usage.
        # Use placeholder for title/id if discovered via scan and not formal creation.
        cursor.execute('''
            INSERT OR IGNORE INTO sections (section_filename, title, internal_file_id, last_seen_in_presentations, discovered_timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (section_filename, f"Scanned: {os.path.basename(section_filename)}", "N/A_Scan", json.dumps([]), int(time.time())))

        cursor.execute("SELECT last_seen_in_presentations FROM sections WHERE section_filename=?", (section_filename,))
        row = cursor.fetchone()
        if row:
            presentations = json.loads(row[0] or "[]")
            if presentation_filepath not in presentations:
                presentations.append(presentation_filepath)
            cursor.execute("UPDATE sections SET last_seen_in_presentations=? WHERE section_filename=?",
                           (json.dumps(presentations), section_filename))
            conn.commit()
        conn.close()

    def remove_section_usage(self, section_filename: str, presentation_filepath: str):
        """Removes a presentation from a section's usage list (e.g., if presentation is deleted or section removed from it)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT last_seen_in_presentations FROM sections WHERE section_filename=?", (section_filename,))
        row = cursor.fetchone()
        if row:
            presentations = json.loads(row[0] or "[]")
            if presentation_filepath in presentations:
                presentations.remove(presentation_filepath)
                cursor.execute("UPDATE sections SET last_seen_in_presentations=? WHERE section_filename=?",
                               (json.dumps(presentations), section_filename))
                conn.commit()
        conn.close()

    def delete_section_record(self, section_filename: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sections WHERE section_filename=?", (section_filename,))
        conn.commit()
        conn.close()

    def get_orphaned_sections(self) -> List[Dict[str, Any]]:
        """Sections are orphaned if their last_seen_in_presentations list is empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Also consider sections where presentations in the list might no longer exist (advanced)
        cursor.execute("SELECT section_filename, title, internal_file_id, last_seen_in_presentations FROM sections WHERE last_seen_in_presentations = '[]' OR last_seen_in_presentations IS NULL")
        orphaned = [{"filename": row[0], "title": row[1], "internal_id": row[2], "used_by_raw": row[3]} for row in cursor.fetchall()]
        conn.close()
        return orphaned
    
    def get_unreferenced_section_files(self) -> List[Dict[str, Any]]:
        """
        Finds section files on disk (in PluckyStandards.get_sections_dir())
        that are not present in the 'sections' database table.
        """
        sections_dir = PluckyStandards.get_sections_dir()
        if not os.path.exists(sections_dir):
            print(f"ResourceTracker: Sections directory '{sections_dir}' not found for unreferenced scan.")
            return []

        disk_files = set()
        try:
            disk_files = {f for f in os.listdir(sections_dir) if f.endswith(".plucky_section")}
        except OSError as e:
            print(f"ResourceTracker: Error listing sections directory '{sections_dir}': {e}")
            return []

        db_files = set()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT section_filename FROM sections")
            db_files = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"ResourceTracker: Database error fetching section filenames for unreferenced scan: {e}")
            return []
        finally:
            conn.close()

        unreferenced_filenames = list(disk_files - db_files)
        return [{"filename": fname, "title": "N/A (On disk, not in DB)", "internal_id": "N/A"} 
                for fname in unreferenced_filenames]

    # --- Cached Background Tracking ---
    def add_or_update_cached_background(self, cache_key: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cached_backgrounds (cache_key, last_seen_in_presentations, discovered_timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO NOTHING
        ''', (cache_key, json.dumps([]), int(time.time())))
        conn.commit()
        conn.close()

    def mark_background_used(self, cache_key: str, presentation_filepath: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        # Ensure the background record exists.
        cursor.execute('''
            INSERT OR IGNORE INTO cached_backgrounds (cache_key, last_seen_in_presentations, discovered_timestamp)
            VALUES (?, ?, ?)
        ''', (cache_key, json.dumps([]), int(time.time())))
        cursor.execute("SELECT last_seen_in_presentations FROM cached_backgrounds WHERE cache_key=?", (cache_key,))
        row = cursor.fetchone()
        if row:
            presentations = json.loads(row[0] or "[]")
            if presentation_filepath not in presentations:
                presentations.append(presentation_filepath)
            cursor.execute("UPDATE cached_backgrounds SET last_seen_in_presentations=? WHERE cache_key=?",
                           (json.dumps(presentations), cache_key))
            conn.commit()
        conn.close()

    def remove_background_usage(self, cache_key: str, presentation_filepath: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT last_seen_in_presentations FROM cached_backgrounds WHERE cache_key=?", (cache_key,))
        row = cursor.fetchone()
        if row:
            presentations = json.loads(row[0] or "[]")
            if presentation_filepath in presentations:
                presentations.remove(presentation_filepath)
                cursor.execute("UPDATE cached_backgrounds SET last_seen_in_presentations=? WHERE cache_key=?",
                               (json.dumps(presentations), cache_key))
                conn.commit()
        conn.close()

    def delete_cached_background_record(self, cache_key: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cached_backgrounds WHERE cache_key=?", (cache_key,))
        conn.commit()
        conn.close()

    def get_orphaned_cached_backgrounds(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cache_key, last_seen_in_presentations FROM cached_backgrounds WHERE last_seen_in_presentations = '[]' OR last_seen_in_presentations IS NULL")
        orphaned = [{"cache_key": row[0], "used_by_raw": row[1]} for row in cursor.fetchall()]
        conn.close()
        return orphaned

    def get_unreferenced_cached_files_on_disk(self, presentation_io_handler, image_cache_manager) -> List[Dict[str, str]]:

        """
        Finds image files physically in the image cache directory that are not
        derived from an original image path currently used as a 'background_source'
        in any slide of any .plucky_section file.
        Requires ImageCacheManager to provide its hashing logic.
        """
        if image_cache_manager is None or presentation_io_handler is None:
            print("RT: ImageCacheManager or PresentationIOHandler not provided for unreferenced cache scan.")
            return []
        print("RT: Starting scan for unreferenced cached files on disk (vs section usage)...")
        active_original_path_base_hashes = set()
        sections_dir = PluckyStandards.get_sections_dir()

        if not os.path.exists(sections_dir):
            print(f"RT: Sections directory '{sections_dir}' not found for cache scan.")
            return []

        for section_filename in os.listdir(sections_dir):
            if section_filename.endswith(".plucky_section"):
                section_full_path = os.path.join(sections_dir, section_filename)
                try:
                    section_data = presentation_io_handler.load_json_file(section_full_path)
                    if section_data:
                        slide_blocks_value = section_data.get("slide_blocks")
                        if isinstance(slide_blocks_value, list):
                            for block_content in slide_blocks_value:
                                if isinstance(block_content, dict):
                                    bg_source = block_content.get("background_source")
                                    if bg_source and isinstance(bg_source, str) and bg_source.strip():
                                        # Assume image_cache_manager has a method to get the base hash
                                        # This method would encapsulate the same logic used to create cache filenames.
                                        # Example: image_cache_manager._generate_cache_filename_base(bg_source)
                                        # For now, let's assume a hypothetical public method:
                                        base_hash = image_cache_manager.get_base_hash_for_original_path(bg_source)
                                        active_original_path_base_hashes.add(base_hash)

                        elif isinstance(slide_blocks_value, dict):
                            for _block_id, block_content in slide_blocks_value.items():
                                if isinstance(block_content, dict):
                                    bg_source = block_content.get("background_source")
                                    if bg_source and isinstance(bg_source, str) and bg_source.strip():
                                        base_hash = image_cache_manager.get_base_hash_for_original_path(bg_source)
                                        active_original_path_base_hashes.add(base_hash)

                except Exception as e:
                    print(f"RT: Error processing section '{section_full_path}' for active BGs: {e}")
        print(f"RT: Active original path base hashes collected from sections: {active_original_path_base_hashes}")

        image_cache_dir = PluckyStandards.get_image_cache_dir()
        if not os.path.exists(image_cache_dir):
            print(f"RT: Image cache directory '{image_cache_dir}' not found.")
            return []

        files_in_cache_dir_set = set()
        try:
            # Store tuples of (filename, full_path)
            files_in_cache_dir_with_paths = [(f, os.path.join(image_cache_dir, f))
                                             for f in os.listdir(image_cache_dir)
                                             if os.path.isfile(os.path.join(image_cache_dir, f))]

        except OSError as e:
            print(f"RT: Error listing image cache directory '{image_cache_dir}': {e}")
            return []

        unreferenced_files_data = []
        for cached_filename, full_cached_path in files_in_cache_dir_with_paths:
            # Parse the base hash from the cached_filename.
            # This assumes HASH is before the first '_w' or '_h', or before '.ext' if no dimensions.
            # A more robust way would be for ImageCacheManager to provide a parsing utility.
            parts = cached_filename.split('_')
            disk_file_base_hash = parts[0] # Assuming hash is the first part before any '_'

            if disk_file_base_hash not in active_original_path_base_hashes:
                unreferenced_files_data.append({"disk_path": full_cached_path, "display_name": cached_filename})

        print(f"RT: Found {len(active_original_path_base_hashes)} unique active original background base hashes.")
        print(f"RT: Found {len(files_in_cache_dir_with_paths)} files in cache directory.")
        print(f"RT: Found {len(unreferenced_files_data)} unreferenced files in cache directory (vs section usage).")

        return [{"disk_path": os.path.join(image_cache_dir, fname), "display_name": fname}
                for item in unreferenced_files_data for fname in [os.path.basename(item["disk_path"])]] # Reconstruct for existing return type

        
    def perform_full_resource_scan(self, presentation_manager_io_handler):
        """
        Scans all known presentations and updates the resource usage in the database.
        This is a potentially long-running operation.
        """
        print("ResourceTracker: Starting full resource scan...")
        # 0. Reset usage: For all sections and backgrounds, clear `last_seen_in_presentations` (or use a temporary flag)
        # This is a destructive way; a better way is to compare with `presentations.last_scanned_for_resources_timestamp`
        # For simplicity now, we'll just rebuild. A more robust scan would be non-destructive.

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            current_scan_time = int(time.time())
            print(f"ResourceTracker: Resetting usage lists for scan at {current_scan_time}.")
            cursor.execute("UPDATE sections SET last_seen_in_presentations = '[]', last_full_scan_timestamp = ?", (current_scan_time,))
            cursor.execute("UPDATE cached_backgrounds SET last_seen_in_presentations = '[]', last_full_scan_timestamp = ?", (current_scan_time,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ResourceTracker: Database error during usage reset: {e}")
        finally:
            conn.close()

        presentations_dir = PluckyStandards.get_presentations_dir()
        for pres_filename in os.listdir(presentations_dir):
            if pres_filename.endswith(".plucky_pres"):
                pres_filepath = os.path.join(presentations_dir, pres_filename)
                print(f"ResourceTracker: Scanning presentation manifest: {pres_filepath}")
                try:
                    manifest_data = presentation_manager_io_handler.load_manifest_data_from_file(pres_filepath)
                    if manifest_data:
                        print(f"ResourceTracker: Processing presentation '{pres_filepath}' for sections and backgrounds.")
                        # Update sections
                        # IMPORTANT: Assumes manifest_data["sections"] is a list of dicts,
                        # and each dict has a "filename" key for the section file.
                        # If your key is "section_filename", change section_entry.get("filename") below.
                        sections_in_manifest = manifest_data.get("sections", [])
                        if not sections_in_manifest:
                            print(f"ResourceTracker: No 'sections' array found or it's empty in manifest '{pres_filepath}'.")

                        for i, section_entry in enumerate(sections_in_manifest):
                            section_file_in_manifest = section_entry.get("path") # Changed "filename" to "path"

                            if section_file_in_manifest:
                                print(f"ResourceTracker: Found section '{section_file_in_manifest}' in '{pres_filepath}'. Marking as used.")

                                self.mark_section_used(section_file_in_manifest, pres_filepath)
                        
                                # Load this section file to find backgrounds
                                section_full_path = os.path.join(PluckyStandards.get_sections_dir(), section_file_in_manifest)
                                if not os.path.exists(section_full_path):
                                    print(f"ResourceTracker: Warning - Section file '{section_full_path}' listed in '{pres_filepath}' not found. Skipping for background scan.")
                                    continue
                                
                                try:
                                    print(f"ResourceTracker: Loading section file '{section_full_path}' to scan for backgrounds.")
                                    # Assuming PresentationIO has load_json_file
                                    section_data = presentation_manager_io_handler.load_json_file(section_full_path)
                                    if section_data:
                                        print(f"ResourceTracker: Section data for '{section_full_path}' loaded. Top-level keys: {list(section_data.keys())}")

                                        # Scan for backgrounds within this section_data
                                        slide_blocks_value = section_data.get("slide_blocks")

                                        if slide_blocks_value is None:
                                            print(f"ResourceTracker: No 'slide_blocks' key found in section '{section_full_path}'.")
                                        elif not slide_blocks_value: # Empty list or dict
                                             print(f"ResourceTracker: 'slide_blocks' is empty in section '{section_full_path}'.")
                                        elif isinstance(slide_blocks_value, list):

                                            if not slide_blocks_value:
                                                print(f"ResourceTracker: 'slide_blocks' list is empty in section '{section_full_path}'.")
                                            for block_content in slide_blocks_value: # Iterate list
                                                if isinstance(block_content, dict):
                                                    print(f"ResourceTracker: Processing block_content (list item). Keys: {list(block_content.keys())}")

                                                    # Look for 'background_source' directly in block_content
                                                    # This 'background_source' is assumed to be the cache_key or transformable to it.
                                                    bg_source = block_content.get("background_source")
                                                    if bg_source:
                                                        # Assuming bg_source (e.g., a filepath) is used as the cache_key
                                                        # or can be directly used to identify the cached background.
                                                        # If ImageCacheManager uses a different keying scheme (e.g. hash),
                                                        # this would need to replicate that scheme.
                                                        print(f"ResourceTracker: Found background_source '{bg_source}' in section '{section_file_in_manifest}' (from '{pres_filepath}'). Using as cache_key.")
                                                        self.mark_background_used(str(bg_source), pres_filepath) # Ensure it's a string
                                                    else:
                                                        print(f"ResourceTracker: No 'background_source' found in block_content for section '{section_file_in_manifest}'. Block content (list item): {block_content}")

                                                else:
                                                    print(f"ResourceTracker: Encountered non-dictionary item in 'slide_blocks' list for section '{section_full_path}'. Item type: {type(block_content)}")
                                        elif isinstance(slide_blocks_value, dict):
                                            if not slide_blocks_value: # Check if dict is empty
                                                print(f"ResourceTracker: 'slide_blocks' dictionary is empty in section '{section_full_path}'.")
                                            for block_id, block_content in slide_blocks_value.items(): # Iterate dict
                                                print(f"ResourceTracker: Processing block_content (dict item, id: {block_id}). Keys: {list(block_content.keys())}")

                                                # Look for 'background_source' directly in block_content
                                                bg_source = block_content.get("background_source")
                                                if bg_source:
                                                    # Assuming bg_source (e.g., a filepath) is used as the cache_key
                                                    print(f"ResourceTracker: Found background_source '{bg_source}' (block_id: {block_id}) in section '{section_file_in_manifest}' (from '{pres_filepath}'). Using as cache_key.")
                                                    self.mark_background_used(str(bg_source), pres_filepath) # Ensure it's a string
                                                else:
                                                    print(f"ResourceTracker: No 'background_source' found in block_content for section '{section_file_in_manifest}'. Block content (dict item, id: {block_id}): {block_content}")

                                        else: # It's something else (not list, not dict, not None)
                                            print(f"ResourceTracker: 'slide_blocks' in section '{section_full_path}' is neither a list nor a dictionary. Type: {type(slide_blocks_value)}")

                                    else:
                                        print(f"ResourceTracker: Section file '{section_full_path}' loaded empty or failed to load.")
                                except Exception as e_sec_load:
                                    print(f"ResourceTracker: Error loading or parsing section file '{section_full_path}' for background scan: {e_sec_load}")
                            else:
                                print(f"ResourceTracker: Section entry {i} in '{pres_filepath}' does not have a 'path' (or your expected key for section filename). Entry: {section_entry}")

                    else:
                        print(f"ResourceTracker: Manifest data for '{pres_filepath}' is None or empty after loading.")

                        conn = self._get_connection()
                        try:
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO presentations (filepath, last_scanned_for_resources_timestamp) VALUES (?, ?)",
                                           (pres_filepath, int(time.time())))
                            conn.commit()
                            print(f"ResourceTracker: Finished processing '{pres_filepath}', committed changes.")
                        except sqlite3.Error as e_db_pres:
                            print(f"ResourceTracker: Database error updating presentation record for '{pres_filepath}': {e_db_pres}")
                        finally:
                            conn.close()
                except AttributeError as ae:
                    # This specific error means the io_handler is not correctly set up.
                    # It's better to stop the scan and let the caller (ResourceManagerWindow) handle this.
                    print(f"ResourceTracker: Critical error during scan of {pres_filepath}: {ae}. The IO handler is missing a required method.")
                    raise # Re-raise the AttributeError
                except Exception as e:
                    print(f"ResourceTracker: Error processing presentation file {pres_filepath} (will continue with next if possible): {e}")

        print("ResourceTracker: Full resource scan completed.")