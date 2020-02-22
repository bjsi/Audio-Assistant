import os
from typing import Dict, Callable, List, Literal
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
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(funcName)s():%(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("extract_queue.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class ExtractQueue(Mpd, object):

    """Extends core mpd functions for the Extract Queue
    """

    def __init__(self):
        """
        :queue: Name of the current queue.

        :active_keys: Currently available methods.

        :recording: True if recording.

        :clozing: True if clozing.

        :extracting_keys: Methods available while extracting.

        :clozing_keys: Methods available while clozing.
        """

        super().__init__()

        # State
        self.queue: str = "global extract queue"
        self.active_keys: Dict[int, Callable] = {}
        self.recording: bool = False
        self.clozing: bool = False

        # Keycodes mapped to methods for extracting.
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

        # Keycodes mapped to methods for clozing.
        self.clozing_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

    def get_global_extracts(self) -> bool:
        """Get global extracts and load global extract queue.

        :returns: True on success else false.
        """
        # Get extracts from DB
        extracts: List[ExtractFile] = (session
                                       .query(ExtractFile)
                                       .filter_by(deleted=False)
                                       .order_by(ExtractFile.created_at.desc())
                                       .all())

        # Add mpd-recognised extracts to queue
        if extracts:
            # List of rel_fps
            extract_queue: List[str] = []
            for extract in extracts:
                rel_fp = self.abs_to_rel(extract.filepath)
                # Check that mpd recognises the files
                # Necessary after recording an extract with parecord
                if self.mpd_recognised(rel_fp):
                    extract_queue.append(rel_fp)
            if extract_queue:
                if self.load_queue(extract_queue):
                    self.load_global_extract_options()
                    logger.info("Loaded global extract queue.")
                    return True
                else:
                    logger.info("Call to load_queue failed.")
                    return False
            else:
                logger.info("No MPD-recognised outstanding extracts found.")
                espeak("No extracts found.")
                return False
        else:
            logger.info("No extracts found in DB.")
            espeak("No extracts found.")
            return False

    def load_cloze_options(self):
        """Set the state options for when clozing.
        """
        assert self.queue in ["global extract queue",
                              "local extract queue"]
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information and keys
        self.clozing = True
        self.recording = False
        self.active_keys = self.clozing_keys
        logger.info("Loaded cloze options.")

    def load_global_extract_options(self):
        """Set the state options for global extract queue.
        """
        # Set playback options
        with self.connection() if not self.connected() else ExitStack():
            self.repeat(1)
            self.single(1)
        # Set state information and keys
        self.clozing = False
        self.recording = False
        self.active_keys = self.extracting_keys
        self.queue = "global extract queue"
        logger.info("Loaded global extract queue options.")
        espeak(self.queue)

    def start_clozing(self) -> bool:
        """Start a cloze deletion on an extract
        """
        assert self.queue in ["local extract queue",
                              "global extract queue"]
        assert not self.clozing

        click_sound1()

        # Get the currently playing extract
        cur_song = self.current_track()
        cur_timestamp = cur_song['elapsed']
        filepath = cur_song['abs_fp']

        # Find the extract in DB
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        # Add a new child item to the extract
        if extract:
            extract.items.append(ItemFile(cloze_startstamp=cur_timestamp))
            session.commit()
            self.load_cloze_options()
            logger.info("Started clozing.")
            return True
        logger.error("Couldn't find currently playing extract in DB.")
        negative_beep()
        return False

    def stop_clozing(self) -> bool:
        """Stop the current cloze deletion and send to cloze processor.

        :returns: True on success else false.
        """

        assert self.queue in ["local extract queue",
                              "global extract queue"]
        assert self.clozing
        logger.info("Stopping the current cloze.")

        click_sound2()

        # Get filepath and timestamp of current extract
        cur_song = self.current_track()
        cur_timestamp = cur_song['elapsed']
        filepath = cur_song['abs_fp']

        # Get extract from DB
        # TODO: Do you need to filter by outstanding?
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        # Get the last inserted itemfile
        if extract:
            items: List[ItemFile] = extract.items
            # TODO: Is there a better way to get the last inserted
            last_item = max(items, key=lambda item: item.created_at)
            # Set the endstamp of the item
            if last_item:
                if last_item.cloze_startstamp:
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
                            logger.info("New cloze created.")
                            return True
                        else:
                            logger.error("Cloze question or answer not returned from processor.")
                else:
                    logger.error("Attempted to stop a cloze without a startstamp.")
                    return False
            else:
                logger.error("Couldn't find last item for this extract.")
                return False
        else:
            logger.error("Couldn't find currently playing extract in DB.")
            return False

    def archive_extract(self) -> bool:
        """ Archive the current extract.

        Archived extracts will be deleted by a script (not at runtime)
        if they have no outstanding child items.
        Achived extracts with outstanding child items are deleted after export
        """
        assert self.queue in ["local extract queue",
                              "global extract queue"]

        # Get the currently playing extract
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find the extract in DB
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        # Archive the extract
        if extract:
            extract.archived = True
            session.commit()
            load_beep()
            logger.info("Archived extract.")
            return True
        logger.error("Currently playing extract not found in DB.")
        return False


if __name__ == "__main__":
    """Run the file to test the extract queue in isolation.
    """

    extract_queue = ExtractQueue()
    extract_queue.get_global_extracts()

    # Create the main loop
    # TODO: Main Loop