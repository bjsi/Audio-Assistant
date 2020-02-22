import os
from typing import Dict, Callable, List
from config import EXTRACTFILES_DIR
from MPD.MpdBase import Mpd
from models import ExtractFile, ItemFile, session
from .extract_funcs import cloze_processor
from Sounds.sounds import (negative_beep,
                           espeak,
                           click_sound1,
                           click_sound2,
                           load_beep)
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_UP,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_DOWN,
                    KEY_OK,
                    KEY_MENU,
                    GAME_X)
from contextlib import ExitStack


class ExtractQueue(Mpd, object):

    """ Extends core mpd functions for the
    Extract Queue
    """

    def __init__(self):
        """
        :queue: String. The current playlist
        :active_keys: Dict[Keycode constant: method names]
        :recording: Boolean. True if recording
        :clozing: Boolean. True if recording
        :extracting_keys: Dict[Keycode constant: method names]
        :clozing_keys: Dict[Keycode constant: method names]
        """

        super().__init__()

        # State
        self.queue: str = "global extract queue"
        self.active_keys: Dict[int, Callable] = {}
        self.recording: bool = False
        self.clozing: bool = False

        # Keys
        self.extracting_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_OK:     self.start_clozing,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.get_extract_items,
                KEY_MENU:   self.archive_extract
        }

        self.clozing_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

    def get_global_extracts(self) -> bool:
        """ Get global extracts and load global extract queue
        :returns: True on success else false.
        """
        # Get extracts from DB
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .order_by(ExtractFile.created_at.desc())
                    .all())

        # Add mpd-recognised extracts to queue
        if extracts:
            extract_queue: List[str] = []
            for extract in extracts:
                rel_fp = self.abs_to_rel(extract.filepath)
                if self.mpd_recognised(rel_fp):
                    extract_queue.append(rel_fp)
            if extract_queue:
                self.load_queue(extract_queue)
                self.load_global_extract_options()
                espeak(self.queue)
            else:
                negative_beep()
                espeak("No extracts")
                print("No MPD recognised extracts")
                return False
        else:
            negative_beep()
            print("No extracts found in DB")
            # TODO Should it switch to global extract queue?

    def load_cloze_options(self):
        """ Set the state options for when clozing """
        # Set playback options
        with self.connection() if not self.connected() else ExitStack():
            self.client.repeat(1)
            self.client.single(1)
        # Set state information and keys
        self.clozing = True
        self.recording = False
        self.active_keys = self.clozing_keys

    def load_global_extract_options(self):
        """ Set the state options for "global extract queue" """
        # Set playback options
        with self.connection() if not self.connected() else ExitStack():
            self.client.repeat(1)
            self.client.single(1)
        # Set state information and keys
        self.clozing = False
        self.recording = False
        self.active_keys = self.extracting_keys
        self.queue = "global extract queue"

    def start_clozing(self):
        """ Start a cloze deletion on an extract """
        # TODO Log severe error if either of these asserts break
        assert self.queue in ["local extract queue", "global extract queue"]
        assert not self.clozing

        click_sound1()

        # Get the currently playing extract
        cur_song = self.current_track()
        cur_timestamp = cur_song['elapsed']
        filepath = cur_song['absolute_fp']

        # Find the extract in DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Add a new child item to the extract
        if extract:
            extract.items.append(ItemFile(cloze_startstamp=cur_timestamp))
            session.commit()
            self.load_cloze_options()
        else:
            # TODO Log severe error
            negative_beep()
            print("ERROR: Couldn't find extract in DB.")

    def stop_clozing(self):
        """ Stop the current cloze deletion
        Finish the cloze on the currently playing extract
        Send the Item to the cloze processor"""

        # TODO Log severe error if either of these asserts break
        assert self.queue in ["local extract queue", "global extract queue"]
        assert self.clozing

        click_sound2()

        # Get filepath and timestamp of current extract
        cur_song = self.current_track()
        cur_timestamp = float(cur_song['elapsed'])
        filepath = cur_song['absolute_fp']

        # Get extract from DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Get the last inserted itemfile
        # TODO add more error else's for the if statements
        if extract:
            items = extract.items
            last_item = max(items, key=lambda item: item.created_at)
            # Set the endstamp of the item
            if last_item and last_item.cloze_startstamp:
                if last_item.cloze_startstamp < cur_timestamp:
                    last_item.cloze_endstamp = cur_timestamp
                    session.commit()
                    if self.queue == "local extract queue":
                        self.load_local_extract_options()
                    else:
                        self.load_global_extract_options()

                    # Send item to the cloze processor
                    question, cloze = cloze_processor(last_item)
                    if question and cloze:
                        last_item.question_filepath = question
                        last_item.cloze_filepath = cloze
                        session.commit()
        else:
            # TODO Log severe errors like this
            print("Couldn't find extract in DB")

    def archive_extract(self):
        """ Archive the current extract.
        Archived extracts will be deleted by a script (not at runtime)
        if they have no outstanding child items.
        Achived extracts with outstanding child items are deleted after export
        """
        # TODO Log severe error
        assert self.queue in ["local extract queue", "global extract queue"]

        # Get the currently playing extract
        cur_song = self.current_track()
        filepath = cur_song['absolute_fp']

        # Find the extract in DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Archive the extract
        if extract:
            load_beep()
            extract.archived = True
            session.commit()
        else:
            # TODO Log severe error
            print("ERROR: Currently playing extract not "
                  "found in the database")


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
