from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.presentation_manager import PresentationManager # Forward declaration

class Command(ABC):
    """Abstract base class for commands."""
    def __init__(self, manager: 'PresentationManager'):
        self.manager = manager # The PresentationManager instance

    @abstractmethod
    def execute(self):
        """Performs the action."""
        pass

    @abstractmethod
    def undo(self):
        """Reverts the action."""
        pass