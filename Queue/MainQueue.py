from .TopicQueue import TopicQueue
from typing import Dict, Callable, List, Any
from models import session, TopicFile, ExtractFile, ItemFile
from .ExtractQueue import ExtractQueue
from .ItemQueue import ItemQueue
from Sounds.sounds import (click_sound1,
                           negative_beep,
                           espeak)
from config import (KEY_A,
                    KEY_UP,
                    KEY_DOWN)
from contextlib import ExitStack
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(funcName)s():%(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("main_queue.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class MainQueue(TopicQueue, ExtractQueue, ItemQueue, object):

    """Main AudioAssistant queue with Topics, Extracts and Items.
    """

    def __init__(self):

        """
        :current_queue: The name of the current queue.

        :clozing: True if currently clozing.

        :recording: True if currently recording.

        :active_keys: Methods available in current queue.

        :extracting_keys: Methods available in extract queue.

        :topic_keys: Methods available in topic queue.

        :item_keys: Methods available in item queue.
        """

        super().__init__()

        # State
        self.current_queue: str = "global topic queue"
        self.clozing: bool = False
        self.recording: bool = False
        self.active_keys: Dict[int, Callable] = self.topic_keys

        # Inter-queue methods are for navigating between queues
        self.topic_inter_queue_keys: Dict[int, Callable] = {
                KEY_DOWN:   self.get_topic_extracts,
                KEY_A:      self.get_global_extracts,
        }

        self.extracting_inter_queue_keys: Dict[int, Callable] = {
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.get_extract_items,
                KEY_A:      self.get_global_topics,
        }

        self.item_inter_queue_keys: Dict[int, Callable] = {
                KEY_UP:     self.get_item_extract,
                KEY_A:      self.get_global_topics,
        }

        # Add inter-queue keys to base queue keys
        # TODO: Switch to Chain Maps for keys?
        self.extracting_keys: Dict[int, Callable] = {
                **self.extracting_keys,
                **self.extracting_inter_queue_keys
        }

        self.topic_keys: Dict[int, Callable] = {
                **self.topic_keys,
                **self.topic_inter_queue_keys
        }

        self.item_keys: Dict[int, Callable] = {
                **self.item_keys,
                **self.item_inter_queue_keys
        }

    #####################################
    # Topic (parent) -> Extract (child) #
    #####################################

    def load_local_extract_options(self):
        """Set the state options for "local extract queue".
        """
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information and keys
        self.clozing = False
        self.recording = False
        self.active_keys = self.extracting_keys
        self.current_queue = "local extract queue"
        espeak(self.current_queue)
        logger.info("Loaded local extract options.")

    def get_topic_extracts(self) -> bool:
        """Get child extracts of the current topic.
        """
        assert self.current_queue == "global topic queue"

        logger.info("Getting topic's child extracts.")

        click_sound1()

        # Get filepath of current song
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find currently playing topic
        topic: List[TopicFile] = (session
                                  .query(TopicFile)
                                  .filter_by(filepath=filepath)
                                  .one_or_none())

        # Create list of mpd-recognised child extracts
        if topic:
            # List of rel_fps
            extract_queue: List[str] = []
            for extract in topic.extracts:
                if not extract.archived:
                    rel_fp = self.abs_to_rel(extract.filepath)
                    if self.mpd_recognised(rel_fp):
                        extract_queue.append(rel_fp)
            if extract_queue:
                self.load_queue(extract_queue)
                self.load_local_extract_options()
                logger.info("Loaded local extract queue.")
                return True
            else:
                negative_beep()
                # TODO: add Topic information to the log message.
                logger.info("No outstanding extracts found for topic.")
                return False
        else:
            logger.error("Currently playing topic not found in DB.")
            return False

    #####################################
    # Extract (child) -> Topic (parent) #
    #####################################

    def get_extract_topic(self) -> bool:
        """Get the parent topic of the currently playing extract.

        Places the parent topic first in the global topic queue.
        Loads the global topic queue.

        :returns: True on success else false.
        """
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]

        logger.info("Getting extract's topic.")

        click_sound1()

        # Get filepath of current extract
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find extract in DB
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        # Get extract's parent topic
        if extract:
            parent: TopicFile = extract.topic
            if not parent.deleted:
                parent_rel_fp = self.abs_to_rel(parent.filepath)

                # Get outstanding topics
                topics: List[TopicFile] = (session
                                           .query(TopicFile)
                                           .filter_by(deleted=False)
                                           .filter_by(archived=False)
                                           .all())
                topics = [
                            self.abs_to_rel(topic.filepath)
                            for topic in topics
                         ]

                # If extract's parent topic is outstanding
                # move it to the beginning of the topic queue
                if parent_rel_fp in topics:
                    topics.remove(parent_rel_fp)
                    topics.insert(0, parent_rel_fp)

                # If extract's parent is archived and not in outstanding queue
                # Add it to the beginning of the queue
                else:
                    topics.insert(0, parent_rel_fp)

                # Load global topic queue
                if self.load_queue(topics):
                    self.load_topic_options()
                # Seek to the startstamp of the child extract
                    with self.connection() if not self.connected() else ExitStack():
                        self.remove_stop_state()
                        self.client.seekcur(extract.startstamp)
                    logger.info("Loaded global topic queue.")
                    return True
                else:
                    negative_beep()
                    logger.error("Call to load_queue failed.")
                    return False
            else:
                negative_beep()
                logger.error("Parent topic has outstanding extracts, but has been deleted.")
                return False
        else:
            negative_beep()
            logger.error("Extract could not be found in the DB")
            return False

    ####################################
    # Extract (parent) -> Item (child) #
    ####################################

    def get_extract_items(self) -> bool:
        """Get child items of the current parent extract and load queue.
        """
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]

        logger.info("Getting child items.")

        click_sound1()

        # Get filepath of currently playing extract
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find extract in DB
        extract: ExtractFile = (session
                                .query(ExtractFile)
                                .filter_by(filepath=filepath)
                                .one_or_none())

        # Find extract's outstanding child items
        if extract:
            extract_items: List[ItemFile] = extract.items
            # List of rel_fps
            item_queue: List[str] = []
            for item in extract_items:
                if item.question_filepath and not item.archived:
                    rel_fp = self.abs_to_rel(item.question_filepath)
                    if self.mpd_recognised(rel_fp):
                        item_queue.append(rel_fp)
            if item_queue:
                if self.load_queue(item_queue):
                    self.load_local_item_options()
                    logger.info("Loaded local item queue.")
                    return True
                else:
                    negative_beep()
                    logger.error("Call to load_queue failed.")
                    return False
            else:
                negative_beep()
                logger.error("No child items found for extract.")
                return False
        else:
            logger.error("Extract was not found in DB.")
            return False

    def load_local_item_options(self):
        """Set state options for "local item queue".
        """
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information options
        self.active_keys = self.item_keys
        self.current_queue = "local item queue"
        self.clozing = False
        self.recording = False
        logger.info("Loaded local item options.")
        espeak(self.current_queue)

    ####################################
    # Item (child) -> Extract (parent) #
    ####################################

    def get_item_extract(self) -> bool:
        """Get the extract parent of the currently playing Item.
        Get the topic parent of the extract.
        Create a local extract queue.
        Load global extract queue.

        :returns: True on success else false.
        """
        assert self.current_queue in ["local item queue",
                                      "global item queue"]

        logger.info("Getting extract of current item.")

        click_sound1()

        # get the filepath of the currently playing item
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find item in the DB
        item: ItemFile = (session
                          .query(ItemFile)
                          .filter_by(question_filepath=filepath)
                          .one_or_none())

        # Get the item's parent extract
        if item:
            parent: ExtractFile = item.extract
            if not parent.deleted:
                # Get the extract's parent topic
                topic: TopicFile = parent.topic
                local_extracts: List[ExtractFile] = topic.extracts
                parent_extract_fp = self.abs_to_rel(parent.filepath)
                # List of rel_fps.
                extract_queue: List[str] = [
                                        self.abs_to_rel(extract.filepath)
                                        for extract in local_extracts
                                        if not extract.deleted
                                      ]

                # Move parent extract to the front and load playlist
                extract_queue.remove(parent_extract_fp)
                extract_queue.insert(0, parent_extract_fp)
                if self.load_queue(extract_queue):
                    self.load_local_extract_options()
                    logger.info("Loaded local extract queue.")
                    return True
                else:
                    negative_beep()
                    logger.error("Call to load_queue failed.")
                    return False
            else:
                negative_beep()
                logger.error("Item has no undeleted parent extract.")
                return False
        else:
            negative_beep()
            logger.error("Currently playing item not found in DB.")
            return False
