import os
from config import QUESTIONFILES_DIR
from Sounds.sounds import espeak
from MPD.MpdBase import Mpd
from models import ItemFile, session
from Sounds.sounds import (negative_beep,
                           load_beep)
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    GAME_X)


class ItemQueue(Mpd, object):
    """ Extends core mpd functions for the Item queue """

    def __init__(self):
        """
        :queue: String. The name of the current queue
        :active_keys: Dict[keycode constants: method names]
        :clozing: Boolean. True if currently clozing
        :recording: Boolean. True if currently recording
        :item_keys: Dict[keycode constants: method names]
        """

        Mpd.__init__(self)

        # State
        self.queue = "global item queue"
        self.active_keys = {}
        self.clozing = False
        self.recording = False

        # Keys
        self.item_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                GAME_X:     self.archive_item
        }

    @staticmethod
    def rel_to_abs_item(filepath: str) -> str:
        """ Convert a filepath relative to the mpd base dir to an
        absolute filepath
        Relative: questionfiles/<item_filename>.wav
        Absolute: /home/pi ... /questionfiles/<item_filename>.wav
        """
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(QUESTIONFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_item(filepath: str) -> str:
        """ Convert an absolute filepath to a filepath relative to
        the mpd base dir
        Relative: questionfiles/<item_filename>.wav
        Absolute: /home/pi ... /questionfiles/<item_filename>.wav
        """
        filename = os.path.basename(filepath)
        directory = os.path.basename(QUESTIONFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def get_global_items(self):
        """ Get outstanding items
        Load global item queue"""

        # Query DB for outstanding items
        items = (session
                 .query(ItemFile)
                 .filter_by(deleted=False)
                 .filter(ItemFile.question_filepath != None)
                 .all())

        # Add mpd-recognised items to the queue
        if items:
            playlist = []
            for item in items:
                rel_fp = self.abs_to_rel_item(item.question_filepath)
                if self.mpd_recognised(rel_fp):
                    playlist.append(rel_fp)
            if playlist:
                self.load_playlist(playlist)
                self.load_global_item_options()
                espeak(self.queue)
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
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)
        # Set state information options
        self.active_keys = self.item_keys
        self.queue = "global item queue"
        self.clozing = False
        self.recording = False

    def archive_item(self):
        """ Archive the current item.
        Archived items will be deleted by a script
        Non-archived items are archived and deleted after export
        """
        # TODO Log severe error
        assert self.queue in ["local item queue", "global item queue"]

        # Get the currently playing item
        cur_song = self.current_song()
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
            session.commmit()
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
