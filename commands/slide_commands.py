from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any, Optional
import copy # For deep copying dictionaries

if TYPE_CHECKING:
    from core.presentation_manager import PresentationManager
    from data_models.slide_data import SlideData


class Command(ABC):
    """Abstract base class for commands."""
    def __init__(self, presentation_manager: 'PresentationManager'):
        self._presentation_manager = presentation_manager

    @abstractmethod
    def execute(self):
        pass


    @abstractmethod
    def undo(self):
        pass


class AddSlideCommand(Command):
    def __init__(self, manager: 'PresentationManager', slide_data: 'SlideData', at_index: Optional[int] = None):
        self.manager = manager
        self.slide_data = slide_data
        self.at_index = at_index if at_index is not None else len(manager.get_slides())

    def execute(self):
        # This command inherently changes the structure, so it should use the general signal.
        # PresentationManager.add_slide handles this.
        self.manager.add_slide(self.slide_data, self.at_index, _execute_command=False) # _execute_command=False to prevent double signal from PM.do_command

    def undo(self):
        # This command inherently changes the structure, so it should use the general signal.
        # PresentationManager.remove_slide handles this.
        self.manager.remove_slide(self.at_index, _execute_command=False)


class DeleteSlideCommand(Command):
    """Command to delete a slide from the presentation."""
    def __init__(self, presentation_manager: 'PresentationManager', instance_slide_id: str):
        super().__init__(presentation_manager)
        self.instance_slide_id = instance_slide_id # Unique ID of the slide instance from SlideData.id

        # Store the data needed to undo the deletion
        self._deleted_arrangement_item: Optional[Dict[str, Any]] = None
        self._original_index_in_arrangement: Optional[int] = None
        self._section_id_in_manifest: Optional[str] = None # To store for undo
        self._arrangement_name: Optional[str] = None       # To store for undo

    def execute(self):
        print(f"Executing DeleteSlideCommand: Removing slide instance_id '{self.instance_slide_id}'")

        # Call the new PresentationManager method to delete the slide reference
        deleted_info = self._presentation_manager.delete_slide_reference_from_arrangement(
            self.instance_slide_id
        )
        if deleted_info:
            # delete_slide_reference_from_arrangement now returns:
            # (deleted_item, original_index, section_id_in_manifest, arrangement_name)
            self._deleted_arrangement_item, self._original_index_in_arrangement, \
            self._section_id_in_manifest, self._arrangement_name = deleted_info
            print(f"  Successfully removed item at index {self._original_index_in_arrangement} from arrangement.")
        else:
            print(f"  Failed to remove slide reference. Command execution failed.")
            # Consider raising an error or having a more robust failure handling

    def undo(self):
        if (self._deleted_arrangement_item is None or
            self._original_index_in_arrangement is None or
            self._section_id_in_manifest is None or
            self._arrangement_name is None):
            print("Undo DeleteSlideCommand: No deleted item info available to restore.")
            return

        slide_block_id_ref = self._deleted_arrangement_item.get("slide_id_ref", "Unknown")
        print(f"Undoing DeleteSlideCommand: Re-inserting slide_block_id '{slide_block_id_ref}' into arrangement '{self._arrangement_name}' in section '{self._section_id_in_manifest}' at index {self._original_index_in_arrangement}")
        success = self._presentation_manager.insert_slide_reference_into_arrangement(
            self._section_id_in_manifest,
            self._arrangement_name,
            self._deleted_arrangement_item,
            self._original_index_in_arrangement
        )
        if not success:
             print(f"  Failed to re-insert slide reference during undo.")

class EditLyricsCommand(Command):
    """Command to edit the text content of a slide, supporting multiple text boxes."""
    def __init__(self, manager: 'PresentationManager', instance_slide_id: str,
                 old_content_dict: Dict[str, str], # Was old_text_content
                 new_content_dict: Dict[str, str]): # Was new_text_content
        super().__init__(manager) # Use super() for PresentationManager
        self.instance_slide_id = instance_slide_id
        self.old_content_dict = copy.deepcopy(old_content_dict)
        self.new_content_dict = copy.deepcopy(new_content_dict)
        # Store section_id and block_id once resolved
        self._section_id_in_manifest: Optional[str] = None
        self._slide_block_id: Optional[str] = None

    def _resolve_ids(self) -> bool:
        if self._section_id_in_manifest and self._slide_block_id:
            return True
        # Use the PresentationManager's helper method
        arrangement_info = self._presentation_manager._get_arrangement_info_from_instance_id(self.instance_slide_id)
        if not arrangement_info:
            print(f"EditLyricsCommand Error: Could not resolve instance_id '{self.instance_slide_id}'")
            return False
        self._section_id_in_manifest = arrangement_info["section_id_in_manifest"]
        self._slide_block_id = arrangement_info["slide_block_id"] # This is the ID of the slide_block
        return True

    def execute(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("EditLyricsCommand: Could not resolve IDs for execution.")
            return
        print(f"Executing EditLyricsCommand for instance '{self.instance_slide_id}' (block '{self._slide_block_id}' in section '{self._section_id_in_manifest}')")
        success = self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"content": self.new_content_dict}, # Pass the new content dict
            _execute_command=False # PM method called by command, PM.do_command will emit signal
        )
        if not success: print("EditLyricsCommand: Execute failed in PresentationManager.")

    def undo(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("EditLyricsCommand: Could not resolve IDs for undo.")
            return
        print(f"Undoing EditLyricsCommand for instance '{self.instance_slide_id}'")
        success = self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"content": self.old_content_dict}, # Restore old content
            _execute_command=False
        )
        if not success: print("EditLyricsCommand: Undo failed in PresentationManager.")


class ApplyTemplateCommand(Command):
    def __init__(self, manager: 'PresentationManager',
                 instance_slide_id: str,
                 old_template_id: Optional[str],
                 new_template_id: str,
                 old_content_dict: Dict[str, str],
                 new_content_dict: Dict[str, str]):
        super().__init__(manager)
        self.instance_slide_id = instance_slide_id
        self.old_template_id = old_template_id
        self.new_template_id = new_template_id
        self.old_content_dict = copy.deepcopy(old_content_dict)
        self.new_content_dict = copy.deepcopy(new_content_dict)

        self._section_id_in_manifest: Optional[str] = None
        self._slide_block_id: Optional[str] = None

    def _resolve_ids(self) -> bool:
        if self._section_id_in_manifest and self._slide_block_id:
            return True
        arrangement_info = self._presentation_manager._get_arrangement_info_from_instance_id(self.instance_slide_id)
        if not arrangement_info:
            print(f"ApplyTemplateCommand Error: Could not resolve instance_id '{self.instance_slide_id}'")
            return False
        self._section_id_in_manifest = arrangement_info["section_id_in_manifest"]
        self._slide_block_id = arrangement_info["slide_block_id"]
        return True

    def execute(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("ApplyTemplateCommand: Could not resolve IDs for execution.")
            return
        print(f"Executing ApplyTemplateCommand for instance '{self.instance_slide_id}' to template '{self.new_template_id}'")
        self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"template_id": self.new_template_id, "content": self.new_content_dict},
            _execute_command=False
        )

    def undo(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("ApplyTemplateCommand: Could not resolve IDs for undo.")
            return
        print(f"Undoing ApplyTemplateCommand for instance '{self.instance_slide_id}' to template '{self.old_template_id}'")
        self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"template_id": self.old_template_id, "content": self.old_content_dict},
            _execute_command=False
        )


class ChangeOverlayLabelCommand(Command):
    def __init__(self, manager: 'PresentationManager', instance_slide_id: str, old_label: str, new_label: str):
        super().__init__(manager) # Use super() for PresentationManager
        self.instance_slide_id = instance_slide_id
        self.old_label = old_label
        self.new_label = new_label
        self._section_id_in_manifest: Optional[str] = None
        self._slide_block_id: Optional[str] = None

    def _resolve_ids(self) -> bool:
        if self._section_id_in_manifest and self._slide_block_id:
            return True
        arrangement_info = self._presentation_manager._get_arrangement_info_from_instance_id(self.instance_slide_id)
        if not arrangement_info:
            print(f"ChangeOverlayLabelCommand Error: Could not resolve instance_id '{self.instance_slide_id}'")
            return False
        self._section_id_in_manifest = arrangement_info["section_id_in_manifest"]
        self._slide_block_id = arrangement_info["slide_block_id"]
        return True

    def execute(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("ChangeOverlayLabelCommand: Could not resolve IDs for execution.")
            return
        print(f"Executing ChangeOverlayLabelCommand for instance '{self.instance_slide_id}' to label '{self.new_label}'")
        self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"label": self.new_label}, # Update the 'label' field in slide_block_data
            _execute_command=False # PM method called by command, PM.do_command will handle signal
        )

    def undo(self):
        if not self._resolve_ids() or not self._section_id_in_manifest or not self._slide_block_id:
            print("ChangeOverlayLabelCommand: Could not resolve IDs for undo.")
            return
        print(f"Undoing ChangeOverlayLabelCommand for instance '{self.instance_slide_id}' to label '{self.old_label}'")
        self._presentation_manager.update_slide_block_in_section(
            self._section_id_in_manifest,
            self._slide_block_id,
            {"label": self.old_label},
            _execute_command=False
        )

class AddSlideBlockToSectionCommand(Command):
    """
    Command to add a new slide_block to a section and a reference to it
    in one of its arrangements.
    """
    def __init__(self, presentation_manager: 'PresentationManager',
                 section_id_in_manifest: str,
                 new_slide_block_data: Dict[str, Any], # Includes new unique slide_block_id
                 arrangement_name: str,
                 at_index_in_arrangement: Optional[int] = None):
        super().__init__(presentation_manager)
        self.section_id_in_manifest = section_id_in_manifest
        self.new_slide_block_data = copy.deepcopy(new_slide_block_data)
        self.slide_block_id_to_add = new_slide_block_data["slide_id"] # Must exist
        self.arrangement_name = arrangement_name
        self.at_index_in_arrangement = at_index_in_arrangement
        # For undo, we just need to remove the slide_block and its reference.
        # The PM method will handle the details.

    def execute(self):
        print(f"Executing AddSlideBlockToSectionCommand: Adding slide_block '{self.slide_block_id_to_add}' to section '{self.section_id_in_manifest}', arr '{self.arrangement_name}'")
        self._presentation_manager.add_slide_block_to_section(
            self.section_id_in_manifest,
            self.new_slide_block_data,
            self.arrangement_name,
            self.at_index_in_arrangement,
            _execute_command=False # PM method called directly by command
        )

    def undo(self):
        print(f"Undoing AddSlideBlockToSectionCommand: Removing slide_block '{self.slide_block_id_to_add}' from section '{self.section_id_in_manifest}', arr '{self.arrangement_name}'")
        # This will use the instance_id map to find the correct item to remove.
        # We need a way to get the instance_id of the newly added slide.
        # For now, let's assume PM's delete_slide_reference_from_arrangement can handle it by slide_block_id if it's the last one added.
        # A more robust undo would store the instance_id created during execute.
        # This is a simplification for now.
        # The PM's delete_slide_reference_from_arrangement needs to be robust enough or we need to store more info.
        
        # Find the instance ID of the slide we just added to delete it.
        # This is tricky without storing the instance ID.
        # For now, the undo might be incomplete or rely on PM's internal state.
        # A proper undo would require PresentationManager.add_slide_block_to_section to return the instance_id.
        
        # Let's assume for now that the PM's delete method can find the last added reference
        # to this slide_block_id in the arrangement. This is a simplification.
        # A more robust undo would involve storing the exact instance_id created.
        self._presentation_manager.delete_slide_reference_from_arrangement_by_block_id( # New PM method needed for undo
            self.section_id_in_manifest,
            self.arrangement_name,
            self.slide_block_id_to_add,
            _execute_command=False
        )

class MoveSlideInstanceCommand(Command):
    """
    Command to move a slide instance from one location (section/arrangement/index)
    to another.
    """
    def __init__(self, presentation_manager: 'PresentationManager',
                 source_instance_id: str,
                 target_section_id_in_manifest: str,
                 target_arrangement_name: str,
                 target_index_in_arrangement: int):
        super().__init__(presentation_manager)
        self.source_instance_id = source_instance_id
        self.target_section_id = target_section_id_in_manifest
        self.target_arrangement_name = target_arrangement_name
        self.target_index = target_index_in_arrangement # Index in the target arrangement

        # For undo
        self._original_section_id: Optional[str] = None
        self._original_arrangement_name: Optional[str] = None
        self._original_index_in_arrangement: Optional[int] = None
        self._moved_slide_block_id: Optional[str] = None # The ID of the slide_block being moved
        self._original_arrangement_item: Optional[Dict[str, Any]] = None # Stores {"slide_id_ref": ..., "enabled": ...}
        self._copied_slide_block_data_to_target: bool = False # Flag if block was copied to target

        # For redoing the removal from the new location during undo, this is the index in the target arrangement
        self._actual_inserted_index_in_target: Optional[int] = None

    def execute(self):
        print(f"Executing MoveSlideInstanceCommand: Moving instance '{self.source_instance_id}' to section '{self.target_section_id}', arr '{self.target_arrangement_name}', index {self.target_index}")
        
        source_details = self._presentation_manager._get_arrangement_info_from_instance_id(self.source_instance_id)
        if not source_details:
            print(f"MoveSlideInstanceCommand: ERROR - Could not find source details for instance '{self.source_instance_id}'. Aborting.")
            return False

        self._original_section_id = source_details["section_id_in_manifest"]
        self._original_arrangement_name = source_details["arrangement_name"]
        self._original_index_in_arrangement = source_details["index_in_arrangement"]
        self._moved_slide_block_id = source_details["slide_block_id"] # This is the slide_id_ref

        # Get the actual slide_block_data from the source section
        source_slide_block_data = self._presentation_manager._get_slide_block_data(
            self._original_section_id, self._moved_slide_block_id
        )
        if not source_slide_block_data:
            print(f"MoveSlideInstanceCommand: ERROR - Could not find source slide_block_data for ID '{self._moved_slide_block_id}' in section '{self._original_section_id}'. Aborting.")
            return False

        # 1. Remove from original location
        removal_result = self._presentation_manager.delete_slide_reference_from_arrangement(self.source_instance_id, _execute_command=False)
        if removal_result is None:
            print(f"MoveSlideInstanceCommand: ERROR - Failed to remove source instance '{self.source_instance_id}'. Aborting.")
            return False
        
        # delete_slide_reference_from_arrangement returns: (deleted_item, original_index, section_id, arrangement_name)
        # We only need the deleted_item here for its structure (like "enabled" state)
        self._original_arrangement_item, _, _, _ = removal_result

        # Adjust target_index if moving within the same section and arrangement
        # and the original position was before the target position.
        actual_target_index_for_insertion = self.target_index
        if self._original_section_id == self.target_section_id and \
           self._original_arrangement_name == self.target_arrangement_name and \
           self._original_index_in_arrangement is not None and \
           self._original_index_in_arrangement < self.target_index:
            actual_target_index_for_insertion -= 1
            print(f"MoveSlideInstanceCommand: Adjusted target_index for insertion to {actual_target_index_for_insertion} due to same section/arrangement move.")

        # If moving to a different section, copy the slide_block_data to the target section
        self._copied_slide_block_data_to_target = False
        if self._original_section_id != self.target_section_id:
            copied_block_data = copy.deepcopy(source_slide_block_data)
            # Ensure the ID is the same, or decide if a new ID is needed for the copy.
            # For a move, keeping the same block ID but in a new section context is okay.
            # If it was a "copy" operation, a new block ID would be essential.
            add_block_success = self._presentation_manager._add_slide_block_to_section_data_only(
                self.target_section_id, copied_block_data
            )
            if not add_block_success:
                print(f"MoveSlideInstanceCommand: ERROR - Failed to copy slide_block_data to target section '{self.target_section_id}'. Aborting.")
                # Attempt to revert removal from original might be needed here if critical
                return False
            self._copied_slide_block_data_to_target = True

        # 2. Add to new location
        # The item to insert is based on the original item, but references the same slide_block_id
        item_to_insert = {"slide_id_ref": self._moved_slide_block_id, "enabled": self._original_arrangement_item.get("enabled", True)}
        
        success_add = self._presentation_manager.insert_slide_reference_into_arrangement(
            self.target_section_id,
            self.target_arrangement_name,
            item_to_insert,
            actual_target_index_for_insertion,
            _execute_command=False # Command will emit presentation_changed
        )
        if not success_add:
            print(f"MoveSlideInstanceCommand: ERROR - Failed to add to target. Attempting to revert removal.")
            # Attempt to revert the removal if adding to new location fails
            if self._original_arrangement_item and self._original_section_id and self._original_arrangement_name and self._original_index_in_arrangement is not None:
                 self._presentation_manager.insert_slide_reference_into_arrangement(
                    self._original_section_id, self._original_arrangement_name,
                    self._original_arrangement_item, self._original_index_in_arrangement, _execute_command=False
                )
            return False

        self._actual_inserted_index_in_target = actual_target_index_for_insertion # Store the index used for insertion
        
        # self._presentation_manager.presentation_changed.emit() # PM.do_command will handle this
        return True

    def undo(self):
        if self._original_section_id is None or \
           self._original_arrangement_name is None or \
           self._original_index_in_arrangement is None or \
           self._moved_slide_block_id is None or \
           self._original_arrangement_item is None or \
           self._actual_inserted_index_in_target is None: # Check the index used for insertion
            print("MoveSlideInstanceCommand: ERROR - Undo information incomplete. Cannot undo.")
            return False

        print(f"Undoing MoveSlideInstanceCommand: Removing '{self._moved_slide_block_id}' from target and restoring to original.")

        # 1. Remove reference from the new (target) location
        removed_from_target = self._presentation_manager._remove_slide_reference_by_details_for_undo(
            self.target_section_id, self.target_arrangement_name, self._actual_inserted_index_in_target, self._moved_slide_block_id
        )
        if not removed_from_target:
            print(f"MoveSlideInstanceCommand: UNDO WARNING - Failed to remove from target location. Data might be inconsistent.")
            # Continue to try re-inserting in original, but this is a problematic state.

        # 2. If slide_block_data was copied to the target section, remove it
        if self._copied_slide_block_data_to_target:
            removed_block_from_target = self._presentation_manager._remove_slide_block_from_section_data_only(
                self.target_section_id, self._moved_slide_block_id
            )
            if not removed_block_from_target:
                print(f"MoveSlideInstanceCommand: UNDO WARNING - Failed to remove copied slide_block_data '{self._moved_slide_block_id}' from target section '{self.target_section_id}'.")


        # 2. Add back to the original location
        success_reinsert = self._presentation_manager.insert_slide_reference_into_arrangement(
            self._original_section_id,
            self._original_arrangement_name,
            self._original_arrangement_item, # Use the stored original item
            self._original_index_in_arrangement,
            _execute_command=False # PM.do_command will handle this
        )
        if not success_reinsert:
            print(f"MoveSlideInstanceCommand: ERROR - Failed to re-insert into original location during undo.")
            return False # Undo failed
            
        # self._presentation_manager.presentation_changed.emit() # PM.do_command will handle this
        return True