from typing import Dict, Callable, List
from MPD.MpdBase import Mpd
from models import ExtractFile, ItemFile, session
from Sounds.sounds import (espeak,
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
                    GAME_X,
                    GAME_B,
                    GAME_A,
                    GAME_OK)
import logging
from Queue.QueueBase import QueueBase


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(funcName)s():"
                              "%(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("extract_queue.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class ExtractQueue(Mpd, QueueBase, object):

    """Extends core mpd functions for the Extract Queue
    """

    def __init__(self):
        """
        :current_queue: Name of the current queue.

        :active_keys: Currently available methods.

        :recording: True if recording.

        :clozing: True if clozing.

        :extracting_keys: Methods available while extracting.

        :clozing_keys: Methods available while clozing.

        :load_initial_queue: The initial queue method for this queue.
        """

        super().__init__()

        # State
        self.current_queue: str = "global extract queue"
        self.active_keys: Dict[int, Callable] = {}
        self.recording: bool = False
        self.clozing: bool = False

        # Set the initial queue method.
        self.load_initial_queue = self.get_global_extracts

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
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
                GAME_A:     self.archive_extract,
                GAME_OK:    self.toggle_to_export,
                # KEY_MENU clashes with GAME_X
                # KEY_MENU:   self.archive_extract
        }

        # Keycodes mapped to methods for clozing.
        self.clozing_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

    def toggle_to_export(self) -> bool:
        """Toggles the to_export field of the current extract.

        :returns: True on success else false.
        """
        # Get the currently playing extract
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        if extract:
            if extract.to_export:
                extract.to_export = False
                session.commit()
                espeak("Export true")
            else:
                extract.to_export = True
                session.commit()
                espeak("Export false")

            logger.info(f"{extract} to_export field was "
                        f"set to {extract.to_export}")
            return True

        else:
            logger.error("Currently playing extract not found in DB.")
            return False

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
                    logger.info("Loaded global extract queue.")
                    self.load_global_extract_options()
                    return True
                else:
                    logger.info("Call to load_queue failed.")
            else:
                logger.info("No MPD-recognised outstanding extracts found.")
        else:
            logger.info("No extracts found in DB.")
        return False

    def load_cloze_options(self):
        """Set the state options for when clozing.
        """
        assert self.current_queue in ["global extract queue",
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
        self.repeat(1)
        self.single(1)
        # Set state information and keys
        self.clozing = False
        self.recording = False
        self.active_keys = self.extracting_keys
        self.current_queue = "global extract queue"
        logger.info("Loaded global extract queue options.")
        espeak(self.current_queue)

    def start_clozing(self) -> bool:
        """Start a cloze deletion on an extract
        """
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]
        assert not self.clozing

        click_sound1()
        
        # Get the currently playing extract
        cur_song = self.current_track()
        cur_timestamp = cur_song['elapsed']
        filepath = cur_song['abs_fp']

        if filepath:

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
            else:
                logger.error("Couldn't find currently playing extract in DB.")
        else:
            logger.error("No currently playing track.")
        return False

    def stop_clozing(self) -> bool:
        """Stop the current cloze deletion and send to cloze processor.

        :returns: True on success else false.
        """
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]
        assert self.clozing

        click_sound2()

        # Get filepath and timestamp of current extract
        cur_song = self.current_track()
        cur_timestamp = cur_song['elapsed']
        filepath = cur_song['abs_fp']

        if filepath:

            # Get extract from DB
            extract: ExtractFile = (session
                                    .query(ExtractFile)
                                    .filter_by(filepath=filepath)
                                    .one_or_none())

            # Get the last inserted itemfile
            if extract:
                items: List[ItemFile] = extract.items
                # TODO: Is there a better way to get the last inserted
                last_item: ItemFile = max(items,
                                          key=lambda item: item.created_at)
                # Set the endstamp of the item
                if last_item:
                    if last_item.cloze_startstamp:
                        if last_item.cloze_startstamp < cur_timestamp:
                            last_item.cloze_endstamp = cur_timestamp
                            session.commit()
                            logger.info("Stopped the current cloze.")
                            if self.current_queue == "local extract queue":
                                self.load_local_extract_options()
                            else:
                                self.load_global_extract_options()
                            if last_item.process_cloze():
                                logger.info("New cloze created.")
                                return True
                            else:
                                logger.error("Call to process_cloze failed.")
                    else:
                        logger.error("Attempted to stop a cloze without "
                                     "a startstamp.")
                else:
                    logger.error("Couldn't find last created item for "
                                 "this extract.")
            else:
                logger.error("Couldn't find currently playing extract in DB.")
        else:
            logger.error("No currently playing track.")
        return False

    def archive_extract(self) -> bool:
        """Archive the current extract.

        Archived extracts will be deleted by a script (not at runtime)
        if they have no outstanding child items.
        Achived extracts with outstanding child items are deleted after export
        """
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]
        
        # Get the currently playing extract
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        if filepath:
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
            else:
                logger.error("Currently playing extract not found in DB.")
        else:
            logger.error("No currently playing track.")
        return False
