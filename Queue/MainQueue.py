from .TopicQueue import TopicQueue
from typing import Dict, Callable, List
from models import session, TopicFile, ExtractFile, ItemFile
from .ExtractQueue import ExtractQueue
from .ItemQueue import ItemQueue
from Sounds.sounds import (click_sound1,
                           negative_beep,
                           espeak)
from config import (KEY_A,
                    KEY_UP,
                    KEY_DOWN,
                    controller_config)


class MainQueue(TopicQueue, ExtractQueue, ItemQueue, object):

    """Main AudioAssistant queue
    """

    def __init__(self):

        """
        :current_queue: The name of the current queue.
        :clozing: True if currently clozing
        :recording: True if currently recording
        :active_keys: Functions available in current queue.
        :extracting_keys: Functions available in extract queue.
        :topic_keys: Functions available in topic queue.
        :item_keys: Functions available in item queue.
        """

        super.__init__()

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

    def get_topic_extracts(self):
        """ Get child extracts of the current topic.
        """
        # TODO Log severe error if this assert breaks
        assert self.current_queue == "global topic queue"

        click_sound1()

        # Get filepath of current song
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find currently playing topic
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Create list of mpd-recognised child extracts
        if topic:
            extract_queue = []
            for extract in topic.extracts:
                if not extract.archived:
                    rel_fp = self.abs_to_rel(extract.filepath)
                    if self.mpd_recognised(rel_fp):
                        extract_queue.append(rel_fp)
            if extract_queue:
                self.load_queue(extract_queue)
                self.load_local_extract_options()
                espeak(self.current_queue)
            else:
                negative_beep()
                print("No non-archived extracts found for this topic")
        else:
            # TODO Log severe errors like this one
            print("ERROR: Currently playing Topic "
                  "not found in the database")

    #####################################
    # Extract (child) -> Topic (parent) #
    #####################################

    def get_extract_topic(self):
        """Get the parent topic of the currently playing extract.
        Places the parent topic first in the global topic queue.
        Loads the global topic queue
        """
        # TODO Log severe error if assert breaks
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]

        click_sound1()

        # Get filepath of current extract
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find extract in DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Get extract's parent topic
        if extract:
            parent = extract.topic
            if not parent.deleted:
                parent_rel_fp = self.abs_to_rel(parent.filepath)

                # Get outstanding topics
                topics = (session
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
                    espeak(self.current_queue)
                # Seek to the startstamp of the child extract
                    with self.connection():
                        self.remove_stop_state()
                        self.client.seekcur(extract.startstamp)
                else:
                    negative_beep()
                    print("Error: Topics failed to load")
            else:
                # TODO Log critical error - topic should not be deleted if it
                # has outstanding extracts
                negative_beep()
                print("ERROR: Parent of extract {} already deleted!"
                      .format(extract))
        else:
            # TODO Log severe error
            print("Extract {} could not be found in the DB"
                  .format(extract.filepath))

    ####################################
    # Extract (parent) -> Item (child) #
    ####################################

    def get_extract_items(self):
        """ Get child items of the current parent extract
        Load local extract queue """
        # TODO Log severe error if assert breaks
        assert self.current_queue in ["local extract queue",
                                      "global extract queue"]

        click_sound1()

        # Get filepath of currently playing extract
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find extract in DB
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Find extract's outstanding child items
        if extract:
            extract_items = extract.items
            item_queue: List[str] = []
            for item in extract_items:
                if item.question_filepath and not item.archived:
                    rel_fp = self.abs_to_rel(item.question_filepath)
                    if self.mpd_recognised(rel_fp):
                        item_queue.append(rel_fp)
            if item_queue:
                if self.load_queue(item_queue):
                    self.load_local_item_options()
                    espeak(self.current_queue)
                else:
                    negative_beep()
                    print("Error: Failed to load items")
            else:
                negative_beep()
                print("No child items found for extract {}"
                      .format(extract))
        else:
            # TODO Log severe error
            print("ERROR: Extract not found in DB")

    def load_local_item_options(self):
        """Set state options for "local item queue".
        """
        # Set playback options
        self.client.repeat(1)
        self.client.single(1)
        # Set state information options
        self.active_keys = self.item_keys
        self.current_queue = "local item queue"
        self.clozing = False
        self.recording = False

    ####################################
    # Item (child) -> Extract (parent) #
    ####################################

    def get_item_extract(self):
        """Get the extract parent of the currently playing Item.
        Get the topic parent of the extract.
        Create a local extract queue.
        Load global extract queue.
        """
        # TODO Log severe error if broken
        assert self.current_queue in ["local item queue", "global item queue"]

        click_sound1()

        # get the filepath of the currently playing item
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find item in the DB
        item = (session
                .query(ItemFile)
                .filter_by(question_filepath=filepath)
                .one_or_none())

        # Get the item's parent extract
        if item:
            parent = item.extract
            if not parent.deleted:
                # Get the extract's parent topic
                topic = parent.topic
                local_extracts = topic.extracts
                parent_extract_fp = self.abs_to_rel(parent.filepath)
                extract_queue: List[str] = [
                                        self.abs_to_rel(extract.filepath)
                                        for extract in local_extracts
                                        if not extract.deleted
                                      ]

                # Move parent extract to the front and load playlist
                extract_queue.remove(parent_extract_fp)
                extract_queue.insert(0, parent_extract_fp)
                self.load_queue(extract_queue)
                self.load_local_extract_options()
                espeak(self.current_queue)
            else:
                # TODO Log critical error
                negative_beep()
                print("ERROR: {} is an orphan. Extract already deleted"
                      .format(item))
        else:
            # TODO Log severe error
            print("ERROR: Item not found in DB.")
