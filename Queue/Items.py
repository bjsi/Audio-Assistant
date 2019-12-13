import os
from typing import List, Optional
import time
from config import QUESTIONFILES_DIR
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
from MPD.MpdBase import Mpd
from Models.models import ExtractFile, ItemFile, session


class ItemQueue(Mpd, object):
    """ Extends core mpd functions for the Item queue """

    def __init__(self):

        Mpd.__init__(self)
        self.current_playlist = "local item queue"
        self.active_keys = {}
        self.item_keys = {
                KEY_X:      self.toggle,
                KEY_UP:     self.get_item_extract,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_A:      self.load_global_topics,
                GAME_X:     self.delete_item
        }
        self.clozing = False
        self.recording = False

        @staticmethod
        def rel_to_abs_item(filepath: str) -> str:
            """ Convert a filepath relative to the mpd base dir to an
            absolute filepath
            """
            filename = os.path.basename(filepath)
            abs_fp = os.path.join(QUESTIONFILES_DIR, filename)
            return abs_fp

        @staticmethod
        def abs_to_rel_item(filepath: str) -> str:
            """ Convert an absolute filepath to a filepath relative to
            the mpd base dir
            """
            filename = os.path.basename(filepath)
            directory = os.path.basename(QUESTIONFILES_DIR)
            rel_fp = os.path.join(directory, filename)
            return rel_fp

        def load_local_items(self, items: Optional[List[str]]):
            """ Load the item question files from the current extract """
            if items:
                with self.connection():
                    self.client.clear()
                    for file in items:
                        self.client.add(file)
                self.load_item_options()
                print(items)
            else:
                print("Error loading local item queue - No items")

        def load_item_options(self):
            with self.connection():
                self.client.repeat = 1
                self.client.single = 1
            self.active_keys = self.item_keys
            self.current_playlist = "local item queue"
            self.clozing = False
            self.recording = False
            print("Item options loaded")
            print("Keys:")
            print(self.active_keys)
            print("Playlist:", self.current_playlist)
            print("Clozing:", self.clozing)
            print("Recording:", self.recording)

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
                load_local_items(items)
            else:
                print("No extracts")
