import os
from config import QUESTIONFILES_DIR
from typing import List, Dict, Callable
from Sounds.sounds import espeak
from MPD.MpdBase import Mpd
from models import ItemFile, session
from Sounds.sounds import (negative_beep,
                           load_beep)
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_MENU,
                    GAME_X)


class ItemQueue(Mpd, object):

    """Extends core mpd functions for the Item queue."""

    def __init__(self):
        """
        :queue: The name of the current queue.
        :active_keys: Functions available in current queue.
        :clozing: Boolean. True if clozing.
        :recording: True if recording.
        :item_keys: Mapping between key codes and methods.
        """

        super().__init__()

        # State
        self.current_queue: str = "global item queue"
        self.active_keys: Dict[int, Callable] = {}
        self.clozing: bool = False
        self.recording: bool = False

        # Keys
        self.item_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_MENU:   self.archive_item
        }

    def get_global_items(self):
        """Get outstanding items.
        Load global item queue"""

        # Query DB for outstanding items
        items = (session
                 .query(ItemFile)
                 .filter_by(deleted=False)
                 .filter(ItemFile.question_filepath != None)
                 .all())

        # Add mpd-recognised items to the queue
        if items:
            item_queue = []
            for item in items:
                rel_fp = self.abs_to_rel(item.question_filepath)
                if self.mpd_recognised(rel_fp):
                    item_queue.append(rel_fp)
            if item_queue:
                if self.load_queue(item_queue):
                    self.load_global_item_options()
                    espeak(self.current_queue)
                else:
                    negative_beep()
                    print("Failed to load global item queue.")
            else:
                negative_beep()
                print("No outstanding items in DB")
        else:
            negative_beep()
            print("No items in DB")

    def load_global_item_options(self):
        """ Set state options for "global item queue".
        """
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information options
        self.active_keys = self.item_keys
        self.current_queue = "global item queue"
        self.clozing = False
        self.recording = False

    def archive_item(self):
        """Archive the current item.
        Archived items will be deleted by a script
        Non-archived items are archived and deleted after export
        """
        # TODO Log severe error
        assert self.current_queue in ["local item queue", "global item queue"]

        # Get the currently playing item
        cur_song = self.current_track()
        filepath = cur_song['absolute_fp']

        # Find the item in DB
        item = (session
                .query(ItemFile)
                .filter_by(question_filepath=filepath)
                .one_or_none())
        # Archive the item
        if item:
            load_beep()
            item.archived = True
            session.commit()
        else:
            # TODO Log severe error
            print("ERROR: Currently playing item "
                  "not found in the DB")


if __name__ == "__main__":
    """ When run as a top-level script, the
    ExtractQueue can be tested in isolation
    from TopicQueue and ItemQueue """

    item_queue = ItemQueue()
    item_queue.get_global_items()

    # Create the main loop
    while True:
        r, w, x = select(controller.devices, [], [])
        for fd in r:
            for event in controller.devices[fd].read():
                if event.value == 1:
                    if event.code in audio_assistant.active_keys:
                        audio_assistant.active_keys[event.code]()

    # TODO Catch Exceptions
