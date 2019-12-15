import os
import mpd
from config import EXTRACTFILES_DIR
from MPD.MpdBase import Mpd
from models import ExtractFile, ItemFile, session
from .extract_funcs import cloze_processor
from Sounds.sounds import negative, espeak
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_UP,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_DOWN,
                    KEY_OK,
                    GAME_X)


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

        Mpd.__init__(self)

        # State
        self.queue = "global extract queue"
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
                KEY_DOWN:   self.get_extract_items,
                GAME_X:     self.archive_extract,
        }

        self.clozing_keys = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

    @staticmethod
    def rel_to_abs_extract(filepath: str) -> str:
        """ Convert filepath relative to absolute
        Relative means relative to mpd base directory
        Relative: extractfiles/<extract_fp>.wav
        Absolute: /home/pi ... /extractfiles/<extract_fp>.wav """
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(EXTRACTFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_extract(filepath: str) -> str:
        """ Convert filepath absolute to relative
        Relative means relative to mpd base directory
        Relative: extractfiles/<extract_fp>.wav
        Absolute: /home/pi ... /extractfiles/<extract_fp>.wav """
        filename = os.path.basename(filepath)
        directory = os.path.basename(EXTRACTFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def get_global_extracts(self):
        """ Get global extracts
        Load the global extract queue"""
        # TODO Log severe error if this assert breaks
        assert self.queue == "global topic queue"

        # Get extracts from DB
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .order_by(ExtractFile.created_at.desc())
                    .all())

        # Add mpd-recognised extracts to queue
        if extracts:
            playlist = []
            for extract in extracts:
                rel_fp = self.abs_to_rel_extract(extract.filepath)
                if self.mpd_recognised(rel_fp):
                    playlist.append(rel_fp)
            if playlist:
                self.load_playlist(playlist)
                self.load_global_extract_options()
                espeak(self.queue)
            else:
                # TODO Add negative sound
                print("No MPD recognised extracts")
        else:
            # TODO Add negative sound
            print("No extracts found in DB")

    def load_cloze_options(self):
        """ Set the state options for when clozing """
        # Set playback options
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)
        # Set state information and keys
        self.clozing = True
        self.recording = False
        self.active_keys = self.clozing_keys

    def load_global_extract_options(self):
        """ Set the state options for "global extract queue" """
        # Set playback options
        with self.connection():
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

        # Get the currently playing extract
        cur_song = self.current_song()
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
            # TODO add negative sound
            print("ERROR: Couldn't find extract in DB.")

    def stop_clozing(self):
        """ Stop the current cloze deletion
        Finish the cloze on the currently playing extract
        Send the Item to the cloze processor"""

        # TODO Log severe error if either of these asserts break
        assert self.queue in ["local extract queue", "global extract queue"]
        assert self.clozing

        # Get filepath and timestamp of current extract
        cur_song = self.current_song()
        cur_timestamp = float(cur_song['elapsed'])
        filepath = cur_song['absolute_fp']

        # Get extract from DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Get the last inserted itemfile
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
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find the extract in DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Archive the extract
        if extract:
            # TODO Add sound as feedback
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
