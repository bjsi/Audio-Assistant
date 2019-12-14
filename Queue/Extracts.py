import os
from typing import List, Optional
import mpd
from config import EXTRACTFILES_DIR
from MPD.MpdBase import Mpd
from Models.models import ExtractFile, TopicFile, ItemFile, session
from .extract_funcs import cloze_processor
from config import (KEY_X,
                    KEY_A,
                    KEY_B,
                    KEY_Y,
                    KEY_PWR,
                    KEY_MENU,
                    KEY_UP,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_DOWN,
                    KEY_OK,
                    GAME_X,
                    GAME_A,
                    GAME_B,
                    GAME_Y,
                    GAME_PWR,
                    GAME_MENU,
                    GAME_OK)


class ExtractQueue(Mpd, object):

    """ Extends core mpd functions for the
    Extract Queue
    """

    def __init__(self):
        """
        :current_playlist: String. The current playlist
        :active_keys: Dict[Keycode constant: method names]
        :recording: Boolean. True if recording
        :clozing: Boolean. True if recording
        """

        Mpd.__init__(self)

        # State
        self.current_playlist = "global extract queue"
        self.active_keys = {}
        self.recording = False
        self.clozing = False

        # Keys
        self.extracting_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_OK:     self.start_clozing,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.load_extract_items,
                GAME_X:     self.archive_extracts
        }

        self.clozing_keys = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

    @staticmethod
    def rel_to_abs_extract(filepath: str) -> str:
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(EXTRACTFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_extract(filepath: str) -> str:
        filename = os.path.basename(filepath)
        directory = os.path.basename(EXTRACTFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def get_global_extracts(self):
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .order_by(ExtractFile.created_at.desc())
                    .all())
        if extracts:
            print(extracts)
            extracts = [
                         self.abs_to_rel_extract(extract.filepath)
                         for extract in extracts
                       ]
            print("Extracts:")
            print(extracts)
            self.load_global_extracts(extracts)
        else:
            print("No extracts in DB")

    def load_cloze_options(self):
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.clozing = True
        self.recording = False
        self.active_keys = self.cloze_keys
        print("Load Cloze Options:")
        print("Keys:")
        print(self.active_keys)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)

    def load_global_extract_options(self):
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.clozing = False
        self.active_keys = self.extracting_keys
        self.current_playlist = "global extract queue"
        print("Load Global Extract Options:")
        print("Keys:")
        print(self.active_keys)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)
        print("Playlist:", self.current_playlist)

    def load_global_extracts(self, extracts: Optional[List[str]]):
        if extracts:
            with self.connection():
                self.client.clear()
                for file in extracts:
                    self.client.add(file)
            self.load_global_extract_options()
            print(extracts)
        else:
            print("Error loading global extract queue - No extracts")

    def start_clozing(self):
        """ Start a cloze deletion on an extract """
        if self.current_playlist in ["local extract queue",
                                     "global extract queue"]:
            if not self.clozing:
                cur_song = self.current_song()
                cur_timestamp = cur_song['elapsed']
                filepath = cur_song['absolute_fp']
                extract = (session
                           .query(ExtractFile)
                           .filter_by(filepath=filepath)
                           .one_or_none())
                if extract:
                    extract.items.append(ItemFile(cloze_startstamp=cur_timestamp))
                    session.commit()
                    self.load_cloze_options()
                else:
                    self.perror("Couldn't find extract {} in DB."
                                .format(extract),
                                "start_clozing")
            else:
                self.perror("Already clozing (self.clozing is True)")

    def stop_clozing(self):
        """ Stop the current cloze deletion on an extract """
        if self.current_playlist in ["local extract queue",
                                     "global extract queue"]:
            if self.clozing:
                cur_song = self.current_song()
                cur_timestamp = float(cur_song['elapsed'])
                filepath = cur_song['absolute_fp']
                extract = (session
                           .query(ExtractFile)
                           .filter_by(filepath=filepath)
                           .one_or_none())
                if extract:
                    items = extract.items
                    last_item = max(items, key=lambda item: item.created_at)
                if last_item and last_item.cloze_startstamp:
                    # Get the last inserted itemfile
                    if last_item.cloze_startstamp < cur_timestamp:
                        last_item.cloze_endstamp = cur_timestamp
                        session.commit()
                        self.load_extract_keys()

                        # Send to the extractor
                        question, cloze = cloze_processor(last_item)
                        if question and cloze:
                            last_item.question_filepath = question
                            last_item.cloze_filepath = cloze
                            session.commit()
                else:
                    self.perror("Couldn't find extract {} in DB"
                                .format(extract),
                                "stop_clozing")
            else:
                self.perror("Not currently clozing",
                            "stop_clozing")
        else:
            self.perror("Current queue is not an extract queue",
                        "stop_clozing")


if __name__ == "__main__":
    """ When run as a top-level script, the
    ExtractQueue can be tested in isolation
    from TopicQueue and ItemQueue """

    extract_queue = ExtractQueue()
    extract_queue.get_global_extracts()

    # Create the main loop
    while True:
        r, w, x = select(controller.devices, [], [])
        for fd in r:
            for event in controller.devices[fd].read():
                if event.value == 1:
                    if event.code in audio_assistant.active_keys:
                        audio_assistant.active_keys[event.code]()

    # TODO Catch Exceptions
