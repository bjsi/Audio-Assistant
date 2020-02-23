from typing import List, Dict, Callable
from Sounds.sounds import espeak
from MPD.MpdBase import Mpd
from models import ItemFile, session
from Sounds.sounds import load_beep
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_MENU)
import logging
from Queue.QueueBase import QueueBase


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(funcName)s():%(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("item_queue.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class ItemQueue(Mpd, QueueBase, object):

    """Extends core mpd functions for the Item queue.
    """

    def __init__(self):
        """
        :queue: The name of the current queue.

        :active_keys: Methods available in current queue.

        :clozing: Boolean. True if clozing.

        :recording: True if recording.

        :item_keys: Methods available in the item queue.
        """

        super().__init__()

        # State
        self.current_queue: str = "global item queue"
        self.active_keys: Dict[int, Callable] = {}
        self.clozing: bool = False
        self.recording: bool = False

        # Set initial queue method.
        self.load_initial_queue = self.get_global_items

        # Keys
        self.item_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_MENU:   self.archive_item
        }

    def get_global_items(self) -> bool:
        """Get global items and load the global item queue.
        
        :returns: True on success else false.
        """
        # Query DB for outstanding items
        items: List[ItemFile] = (session
                                 .query(ItemFile)
                                 .filter_by(deleted=False)
                                 .filter(ItemFile.question_filepath != None)
                                 .all())

        # Add mpd-recognised items to the queue
        if items:
            # List of rel_fps
            item_queue: List[str] = []
            for item in items:
                rel_fp = self.abs_to_rel(item.question_filepath)
                if self.mpd_recognised(rel_fp):
                    item_queue.append(rel_fp)
            if item_queue:
                if self.load_queue(item_queue):
                    logger.info("Loaded a global item queue.")
                    self.load_global_item_options()
                    return True
                else:
                    logger.error("Call to load_queue failed.")
                    return False
            else:
                logger.info("No MPD-recognised items found in DB.")
                return False
        else:
            logger.info("No items found in DB.")
            return False

    def load_global_item_options(self) -> None:
        """Set state options for global item queue.
        """
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information options
        self.active_keys = self.item_keys
        self.current_queue = "global item queue"
        self.clozing = False
        self.recording = False
        espeak(self.current_queue)
        logger.info("Loaded global item options.")

    def archive_item(self) -> bool:
        """Archive the current item.

        Archived items will be deleted by a script.
        Non-archived items are archived and deleted after export
        """
        assert self.current_queue in ["local item queue",
                                      "global item queue"]

        # TODO: What if abs_fp returns None
        # Get the currently playing item
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find the item in DB
        item: ItemFile = (session
                          .query(ItemFile)
                          .filter_by(question_filepath=filepath)
                          .one_or_none())

        # Archive the item
        if item:
            item.archived = True
            session.commit()
            load_beep()
            logger.info("Archived an item.")
            return True
        logger.error("Currently playing item not found in DB.")   
        return False
