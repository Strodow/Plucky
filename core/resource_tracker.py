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
        return sqlite3.connect(self.db_path)

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

    # --- Full Scan Operation (Conceptual - requires PresentationIOHandler) ---
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
        cursor = conn.cursor()
        cursor.execute("UPDATE sections SET last_seen_in_presentations = '[]', last_full_scan_timestamp = ?", (int(time.time()),))
        cursor.execute("UPDATE cached_backgrounds SET last_seen_in_presentations = '[]', last_full_scan_timestamp = ?", (int(time.time()),))
        conn.commit()
        conn.close()

        presentations_dir = PluckyStandards.get_presentations_dir()
        for pres_filename in os.listdir(presentations_dir):
            if pres_filename.endswith(".plucky_pres"):
                pres_filepath = os.path.join(presentations_dir, pres_filename)
                print(f"Scanning: {pres_filepath}")
                try:
                    # You'll need a way to get manifest data without loading the whole presentation
                    # This is where presentation_manager.io_handler.load_manifest_data_from_file comes in
                    manifest_data = presentation_manager_io_handler.load_manifest_data_from_file(pres_filepath)
                    if manifest_data:
                        # Update sections
                        for section_entry in manifest_data.get("sections", []):
                            section_file_in_manifest = section_entry.get("section_filename")
                            if section_file_in_manifest:
                                self.mark_section_used(section_file_in_manifest, pres_filepath)
                        
                        # Update backgrounds (This requires loading slide data, which is more intensive)
                        # For now, this part is more complex as it requires full slide data.
                        # A simpler start is to only update based on manifest, or have a separate
                        # mechanism for background scanning when a presentation is fully loaded.
                        # For a *full* scan, you would indeed load each presentation.
                        # slides_data = presentation_manager_io_handler.load_slides_from_presentation_file(pres_filepath)
                        # for slide in slides_data:
                        #    if slide.background_image_path:
                        #        self.mark_background_used(slide.background_image_path, pres_filepath)

                        conn = self._get_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO presentations (filepath, last_scanned_for_resources_timestamp) VALUES (?, ?)",
                                       (pres_filepath, int(time.time())))
                        conn.commit()
                        conn.close()
                except Exception as e:
                    print(f"Error scanning presentation {pres_filepath}: {e}")
        print("ResourceTracker: Full resource scan completed.")