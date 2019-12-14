from .Topics import TopicQueue
from Models.models import session, TopicFile, ExtractFile, ItemFile
from .Extracts import ExtractQueue
from .Items import ItemQueue
from config import (KEY_X,
                    KEY_A,
                    KEY_B,
                    KEY_Y,
                    KEY_UP,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_DOWN,
                    KEY_OK,
                    GAME_X,
                    GAME_B)


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

        # Keys
        self.extracting_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_OK:     self.start_clozing,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_UP:     self.get_extract_topic,  # <-- inter-queue method
                KEY_DOWN:   self.get_extract_items,  # <-- inter-queue method
                KEY_A:      self.get_global_topics,  # <-- inter-queue method
                GAME_X:     self.archive_extract
        }

        self.topic_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.play_previous,
                KEY_Y:      self.play_next,
                KEY_RIGHT:  self.seek_forward,
                KEY_LEFT:   self.seek_backward,
                KEY_DOWN:   self.get_topic_extracts,  # <-- inter-queue method
                KEY_OK:     self.start_recording,
                KEY_A:      self.get_global_extracts,  # <- inter-queue method
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down
        }

        self.item_keys = {
                KEY_X:      self.toggle,
                KEY_UP:     self.get_item_extract,  # <-- inter-queue method
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_A:      self.get_global_topics,  # <-- inter-queue method
                GAME_X:     self.delete_item
        }

    # Define methods for moving between queues

    # Return to the global topic queue - accessible
    # from both the Extract Queue and the Item Queue

    #####################################
    # Topic (parent) -> Extract (child) #
    #####################################

    def load_local_extract_options(self):
        """ Sets the state options for local extract queue """
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.clozing = False
        self.active_keys = self.extracting_keys
        self.queue = "local extract queue"
        print("Load Extract Options:")
        print("Keys:")
        print(self.active_keys)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)
        print("Playlist:", self.queue)

    def get_topic_extracts(self):
        """ Gets the extract children of the current topic """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())
        if topic and topic.extracts:
            extracts = []
            for extract in topic.extracts:
                if not extract.deleted:
                    # Check if mpd recognises each extract
                    rel_fp = self.abs_to_rel_extract(extract.filepath)
                    if self.mpd_recognised(rel_fp):
                        extracts.append(rel_fp)
            if extracts:
                self.load_playlist(extracts)
                self.load_local_extract_options()
            else:
                print("No extracts")
        else:
            print("Error querying topic's extracts")

    #####################################
    # Extract (child) -> Topic (parent) #
    #####################################

    def get_extract_topic(self):
        """Query and load the parent topic of the current extract
        Seeks to the current timestamp of the parent topic after loading
        """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())
        if extract:
            parent = extract.topic
            if parent.deleted is False:
                parent_rel_fp = self.abs_to_rel_topic(parent.filepath)
                topics = (session
                          .query(TopicFile)
                          .filter_by(deleted=False)
                          .all())
                topics = [
                            self.abs_to_rel_topic(topic.filepath)
                            for topic in topics
                         ]
                if parent_rel_fp in topics:
                    topics.remove(parent_rel_fp)
                else:
                    topics.insert(0, parent_rel_fp)
                self.load_playlist(topics)
                self.load_topic_options()
                with self.connection():
                    self.client.seekcur(parent.cur_timestamp)
            else:
                print("Parent is deleted!")
        else:
            print("Couldn't find extract in DB")

    #####################################
    # Extract (parent) -> Item (child) #
    #####################################

    def get_extract_items(self):
        """ Load the child items of the current extract """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())
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
            else:
                print("No items")
        else:
            print("No extracts")

    def load_local_item_options(self):
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.active_keys = self.item_keys
        self.queue = "local item queue"
        self.clozing = False
        self.recording = False
        print("Item options loaded")
        print("Keys:")
        print(self.active_keys)
        print("Playlist:", self.queue)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)

    ####################################
    # Item (child) -> Extract (parent) #
    ####################################

    def get_item_extract(self):
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        item = (session
                .query(ItemFile)
                .filter_by(question_filepath=filepath)
                .one_or_none())
        if item:
            extract = item.extract
            if not extract.deleted:
                topic = extract.topic
                if not topic.deleted:
                    local_extracts = topic.extracts
                    filepath = self.abs_to_rel_extract(extract.filepath)
                    extracts = [
                                self.abs_to_rel_extract(extract.filepath)
                                for extract in local_extracts
                                if not extract.deleted
                               ]
                    extracts.remove(filepath)
                    extracts.insert(0, filepath)
                    self.load_playlist(extracts)
                    self.load_local_extract_options(extracts)
                else:
                    print("Error loading local extract queue")
            else:
                print("Orphan Item: Parent extract deleted.")
        else:
            print("Item not found.")
