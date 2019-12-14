import os
from config import QUESTIONFILES_DIR
from MPD.MpdBase import Mpd
from models import ItemFile, session
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
                # KEY_UP:     self.get_item_extract, # <-- inter-queue
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                # KEY_A:      self.load_global_topics,  # <-- inter-queue
                GAME_X:     self.delete_item
        }

    @staticmethod
    def rel_to_abs_item(filepath: str) -> str:
        """ Convert a filepath relative to the mpd base dir to an
        absolute filepath
        """
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(QUESTIONFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_item(filepath: str) -> str:
        """ Convert an absolute filepath to a filepath relative to
        the mpd base dir
        """
        filename = os.path.basename(filepath)
        directory = os.path.basename(QUESTIONFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def get_global_items(self):
        """ Load outstanding items """
        items = (session
                 .query(ItemFile)
                 .filter_by(deleted=False)
                 .all())
        if items:
            playlist = []
            for item in items:
                rel_fp = self.abs_to_rel_item(item.filepath)
                if self.mpd_recognised(rel_fp):
                    playlist.append(rel_fp)
            if playlist:
                self.load_playlist(playlist)
                self.load_global_item_options()
            else:
                print("No items")
        else:
            print("Error loading global item queue - No items")

    def load_global_item_options(self):
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.active_keys = self.item_keys
        self.queue = "global item queue"
        self.clozing = False
        self.recording = False
        print("Item options loaded")
        print("Keys:")
        print(self.active_keys)
        print("Playlist:", self.queue)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)
    
    # TODO
    def delete_item(self):
        pass


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
