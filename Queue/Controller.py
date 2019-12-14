from .Topics import TopicQueue
from typing import List, Optional
from Models.models import session, TopicFile, ExtractFile, ItemFile
from .Extracts import ExtractQueue
from .Items import ItemQueue
from select import select
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


class Controller(TopicQueue, ExtractQueue, ItemQueue, object):
    """ Combines TopicQueue, ExtractQueue, ItemQueue,
    MpdBase and Device classes. Connects bluetooth, and
    runs the menu loop and saves the state of the program.
    Adds methods for moving between Queues from parent to child"""

    def __init__(self):
        TopicQueue.__init__(self)
        ExtractQueue.__init__(self)
        ItemQueue.__init__(self)

        # State
        self.current_playlist = ""
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
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.load_extract_items,
                KEY_A:      self.load_global_topics,  # <-- inter-queue method
                GAME_X:     self.archive_extracts
        }

    # Define methods for moving between queues

    #####################################
    # Topic (parent) -> Extract (child) #
    #####################################

    def load_local_extracts(self, extracts: Optional[List[str]]):
        """ Loads the extract descendants of a topic """
        if extracts:
            with self.connection():
                self.client.clear()
                for file in extracts:
                    self.client.add(file)
            self.load_local_extract_options()
            print(extracts)
        else:
            print("Error loading global extract queue - No extracts")

    def load_local_extract_options(self):
        """ Sets the state options for local extract queue """
        with self.connection():
            self.client.repeat = 1
            self.client.single = 1
        self.clozing = False
        self.active_keys = self.extracting_keys
        self.current_playlist = "local extract queue"
        print("Load Extract Options:")
        print("Keys:")
        print(self.active_keys)
        print("Clozing:", self.clozing)
        print("Recording:", self.recording)
        print("Playlist:", self.current_playlist)

    def get_topic_extracts(self):
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())
        if topic and topic.extracts:
            extracts = []
            with self.connection():
                for extract in topic.extracts:
                    if not extract.deleted:
                        # Check if mpd recognises the extract files.
                        # Necessary just after finishing a recording -
                        # Takes a few seconds for mpd to recognise new extract
                        try:
                            recognised = self.client.find('file',
                                            self.abs_to_rel_extract(extract.filepath))
                            if recognised:
                                extracts.append(recognised[0]['file'])
                        except mpd.base.CommandError:
                            print("Mpd doesn't recognise {}"
                                  .format(extract.filepath))
                            continue
            self.load_local_extracts(extracts)
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
                self.load_global_topics(topics)
                with self.connection():
                    self.client.seekcur(parent.cur_timestamp)
            else:
                print("Parent is deleted!")
        else:
            print("Couldn't find extract in DB")

    #####################################
    # Extract (parent) -> Item (child) #
    #####################################

    def load_extract_items(self):
        """ Load the child items of the current extract """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        extract = (session
                   .query(ExtractFile)
                   .filter_by(filepath=filepath)
                   .one_or_none())
        if extract:
            items = extract.items
            items = [
                        self.abs_to_rel_item(item.question_filepath)
                        for item in items
                        if not item.deleted
                    ]
            print(items)
            self.load_local_items(items)
        else:
            print("No extracts")

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
                    self.load_local_extracts(extracts)
                else:
                    self.perror("Error loading local extract queue"
                                "get_item_extract")
            else:
                self.perror("Orphan Item: Parent extract deleted.",
                            "get_item_extract")
        else:
            self.perror("Item not found.",
                        "get_item_extract")
