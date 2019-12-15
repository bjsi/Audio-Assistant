from .Topics import TopicQueue
from models import session, TopicFile, ExtractFile, ItemFile
from .Extracts import ExtractQueue
from Sounds.sounds import espeak
from .Items import ItemQueue
from config import (KEY_A,
                    KEY_UP,
                    KEY_DOWN)


class Controller(TopicQueue, ExtractQueue, ItemQueue, object):
    """ Combines TopicQueue, ExtractQueue, ItemQueue,
    MpdBase and Device classes. Connects bluetooth, and
    runs the menu loop and saves the state of the program.
    Adds methods for moving between Queues from parent to child """

    def __init__(self):
        """
        :queue: String. Name of the current queue
        :clozing: Boolean. True if currently clozing
        :recording: Boolean. True if currently recording
        :active_keys: Dict[keycode constant: method name]
        :extracting_keys: Dict[keycode constant: method name]
        :topic_keys: Dict[keycode constant: method name]
        :item_keys: Dict[keycode constant: method name]
        """

        TopicQueue.__init__(self)
        ExtractQueue.__init__(self)
        ItemQueue.__init__(self)

        # State
        self.queue = "global topic queue"
        self.clozing = False
        self.recording = False
        self.active_keys = {}

        # inter-queue methods are for navigating between Topic, Extract
        # and Item queues

        # Return to the global topic queue (self.get_global_topics)
        # from both the Extract Queue and the Item Queue

        self.topic_inter_queue_keys = {
                KEY_DOWN:   self.get_topic_extracts,  # local extract queue
                KEY_A:      self.get_global_extracts,  # global extract queue
        }

        self.extracting_inter_queue_keys = {
                KEY_UP:     self.get_extract_topic,  # global topic queue
                KEY_DOWN:   self.get_extract_items,  # local extract queue
                KEY_A:      self.get_global_topics,  # global topic queue
        }

        self.item_inter_queue_keys = {
                KEY_UP:     self.get_item_extract,   # local extract queue
                KEY_A:      self.get_global_topics,  # global topic queue
        }

        # Extend the base class keys with the inter-queue keys

        self.extracting_keys = {**self.extracting_keys,
                                **self.extracting_inter_queue_keys}

        self.topic_keys = {**self.topic_keys,
                           **self.topic_inter_queue_keys}

        self.item_keys = {**self.item_keys,
                          **self.item_inter_queue_keys}

    #####################################
    # Topic (parent) -> Extract (child) #
    #####################################

    def load_local_extract_options(self):
        """ Set the state options for "local extract queue".
        """
        # Set playback options
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)

        # Set state information and keys
        self.clozing = False
        self.recording = False
        self.active_keys = self.extracting_keys
        self.queue = "local extract queue"

    def get_topic_extracts(self):
        """ Get child extracts of the current topic.
        """
        # TODO Log severe error if this assert breaks
        assert self.queue == "global topic queue"

        # Get filepath of current song
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find currently playing topic
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Create list of mpd-recognised child extracts
        if topic and topic.extracts:
            extracts = []
            for extract in topic.extracts:
                if not extract.archived:
                    rel_fp = self.abs_to_rel_extract(extract.filepath)
                    if self.mpd_recognised(rel_fp):
                        extracts.append(rel_fp)
            if extracts:
                self.load_playlist(extracts)
                self.load_local_extract_options()
                espeak(self.queue)
            else:
                # TODO Add negative sound
                print("No non-archived extracts found for this topic")
        else:
            # TODO Log severe errors like this one
            print("ERROR: Currently playing Topic "
                  "not found in the database")

    #####################################
    # Extract (child) -> Topic (parent) #
    #####################################

    def get_extract_topic(self):
        """ Get the parent topic of the currently playing extract
        Places the parent topic first in the global topic queue
        Loads the global topic queue
        """
        # TODO Log severe error if assert breaks
        assert self.queue in ["local extract queue", "global extract queue"]

        # Get filepath of current extract
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find extract in DB
        # TODO Filter extracts with an endstamp / filepath
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())

        # Get extract's parent topic
        if extract:
            parent = extract.topic
            if parent.deleted is False:
                parent_rel_fp = self.abs_to_rel_topic(parent.filepath)

                # Get outstanding topics
                topics = (session
                          .query(TopicFile)
                          .filter_by(deleted=False)
                          .filter_by(archived=False)
                          .all())
                topics = [
                            self.abs_to_rel_topic(topic.filepath)
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
                self.load_playlist(topics)
                self.load_topic_options()
                espeak(self.queue)
                with self.connection():
                    self.remove_stop_state()
                    self.client.seekcur(parent.cur_timestamp)
            else:
                # TODO Add negative sound
                # TODO Log critical error - topic should not be deleted if it
                # has outstanding extracts
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
        assert self.queue in ["local extract queue", "global extract queue"]

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
            items = []
            for item in extract_items:
                if item.question_filepath and not item.deleted:
                    rel_fp = self.abs_to_rel_item(item.filepath)
                    if self.mpd_recognised(rel_fp):
                        items.append(rel_fp)
            if items:
                self.load_playlist(items)
                self.load_local_item_options()
                espeak(self.queue)
            else:
                # TODO Add negative sound
                print("No child items found for extract {}"
                      .format(extract))
        else:
            # TODO Log severe error
            print("ERROR: Extract not found in DB")

    def load_local_item_options(self):
        """ Set state options for "local item queue".
        """
        # Set playback options
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)

        # Set state information options
        self.active_keys = self.item_keys
        self.queue = "local item queue"
        self.clozing = False
        self.recording = False

    ####################################
    # Item (child) -> Extract (parent) #
    ####################################

    def get_item_extract(self):
        """ Get the extract parent of the currently playing Item
        Get the topic parent of the extract
        Create a local extract queue
        Load global extract queue"""

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
            extract = item.extract
            if not extract.deleted:
                # Get the extract's parent topic
                topic = extract.topic
                local_extracts = topic.extracts
                filepath = self.abs_to_rel_extract(extract.filepath)
                extracts = [
                            self.abs_to_rel_extract(extract.filepath)
                            for extract in local_extracts
                            if not extract.deleted
                           ]

                # Move parent extract to the front and load playlist
                extracts.remove(filepath)
                extracts.insert(0, filepath)
                self.load_playlist(extracts)
                self.load_local_extract_options(extracts)
                espeak(self.queue)
            else:
                # TODO Log critical error
                print("ERROR: {} is an orphan. Extract already deleted"
                      .format(item))
        else:
            # TODO Log severe error
            print("ERROR: Item not found in DB.")
