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

        self.current_playlist = "global extract queue"
        self.active_keys = {}
        self.recording = False
        self.clozing = False

        self.extracting_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_OK:     self.start_clozing,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.load_extract_items,
                KEY_A:      self.load_global_topics,
                GAME_X:     self.delete_extract
        }

        self.cloze_keys = {
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

        def load_local_extract_options(self):
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
                        # Put parent extract first in queue,
                        # followed by other local extracts
                        filepath = self.abs_to_rel_extract(extract.filepath)
                        extracts = [
                                    abs_to_rel_extract(extract.filepath)
                                    for extract in local_extracts
                                    if not extract.deleted
                                   ]
                        extracts.remove(filepath)
                        extracts.insert(0, filepath)
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

        def load_global_extracts(self, extracts: Optional[List[str]]):
            if extracts:
                with self.connection():
                    self.client.clear()
                    for file in self.outstanding_extracts:
                        self.client.add(file)
                self.load_global_extract_options()
                print(extracts)
            else:
                print("Error loading global extract queue - No extracts")

        def load_local_extracts(self, extracts: Optional[List[str]]):
            if extracts:
                with self.connection():
                    self.client.clear()
                    for file in self.outstanding_extracts:
                        self.client.add(file)
                self.load_local_extract_options()
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
