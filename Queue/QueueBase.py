from abc import ABC
from typing import Dict, Callable


class QueueBase(ABC):
    """Base class all queues inherit from
    """

    def __init__(self):
        """All queues must implement at least these variables.

        :current_queue: The name of the current queue.

        :active_keys: Currently available methods.

        :recording: True if currently recording.

        :clozing: True if currently clozing.
        """

        super().__init__()

        self.current_queue: str = ""
        # Mapping of keycodes to queue methods.
        self.active_keys: Dict[int, Callable] = {}
        self.recording: bool = False
        self.clozing: bool = False

    def load_initial_queue(self) -> bool:
        """Load the starting queue for this queue.
        :returns: True on success else fail.
        """
        pass
