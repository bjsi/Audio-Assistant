import os
import time
from typing import List, Optional
import subprocess
from config import (TOPICFILES_DIR,
                    EXTRACTFILES_DIR,
                    EXTRACTFILES_EXT,
                    RECORDING_SINK)
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_DOWN,
                    KEY_OK,
                    KEY_A,
                    GAME_X,
                    GAME_B)
from MPD.MpdBase import Mpd
from Models.models import TopicFile, ExtractFile, session
from Sounds.sounds import speak


class TopicQueue(Mpd, object):

    """ Extends core mpd functions for the
    Topic queue.
    """

    def __init__(self):
        """
        :outstanding_topics: List. Topics less than 90% complete
        :archived_topics: List. Archived topics
        :current_playlist: String. Name of the current playlist
        :active_keys: Dict[Keycode constants: method names]
        :topic_keys: Dict[Keycode constants: method names]
        :repeat: Int 0/1. 1 repeat track / playlist
        :single: Int 0/1. 1 play a single track
        """
        Mpd.__init__(self)
        self.current_playlist = "global topic queue"
        self.active_keys = {}
        self.recording = False
        self.clozing = False

        self.topic_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.play_previous,
                KEY_Y:      self.play_next,
                KEY_RIGHT:  self.seek_forward,
                KEY_LEFT:   self.seek_backward,
                KEY_DOWN:   self.load_topic_extracts,
                KEY_OK:     self.start_recording,
                KEY_A:      self.load_global_extracts,
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
                # GAME_Y:     self.requires_video
        }

        self.recording_keys = {
                KEY_OK:     self.stop_recording
        }

    @staticmethod
    def rel_to_abs_topic(filepath: str) -> str:
        """ Convert a filepath relative to the mpd base dir to an
        absolute filepath
        """
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(TOPICFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_topic(filepath: str) -> str:
        """ Convert an absolute filepath to a filepath relative to
        the mpd base dir
        """
        filename = os.path.basename(filepath)
        directory = os.path.basename(TOPICFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def load_global_topics(self, topics: Optional[List[str]]):
        if topics:
            with self.connection():
                self.client.clear()
                for file in topics:
                    self.client.add(file)
            self.load_topic_options()
            print(topics)
        else:
            print("Error loading global topic queue")

    def load_topic_options(self):
        with self.connection():
            self.client.repeat(1)
            self.client.single(0)
        self.active_keys = self.topic_keys
        self.current_playlist = "global topic queue"
        self.recording = False
        print("Topic options loaded")
        print("Keys:")
        print(self.active_keys)
        print("Repeat:", self.repeat)
        print("Single:", self.single)
        print("Playlist:", self.current_playlist)

    def load_recording_options(self):
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)
        self.active_keys = self.recording_keys
        self.current_playlist = "global topic queue"
        self.recording = True
        print("Recording options loaded")
        print("Keys:")
        print(self.active_keys)
        print("Repeat:", self.repeat)
        print("Single:", self.single)
        print("Playlist:", self.current_playlist)

    def get_global_topics(self):
        """ Query DB for outstanding topics
        """
        topics = (session
                  .query(TopicFile)
                  .filter_by(deleted=False)
                  .filter_by(archived=False)
                  .filter((TopicFile.cur_timestamp / TopicFile.duration) < 0.9)
                  .order_by(TopicFile.created_at.asc())
                  .all())
        if topics:
            topics = [
                        self.abs_to_rel_topic(topic.filepath)
                        for topic in topics
                     ]
            print("Global topics:")
            self.load_global_topics(topics)
        else:
            print("No outstanding topics")

    def start_recording(self):
        cur_song = self.current_song()
        basename = os.path.basename(cur_song['absolute_fp'])
        extract_fp = os.path.join(EXTRACTFILES_DIR,
                                  os.path.splitext(basename)[0] +
                                  "-" +
                                  str(int(time.time())) +
                                  EXTRACTFILES_EXT)
        subprocess.Popen(['parecord',
                          '--channels=1',
                          '-d',
                          RECORDING_SINK,
                          extract_fp], shell=False)
        self.load_recording_options()
        source_topic_fp = cur_song['absolute_fp']
        timestamp = cur_song['elapsed']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=source_topic_fp)
                 .one_or_none())
        if topic:
            extract = ExtractFile(filepath=extract_fp,
                                  startstamp=timestamp)
            topic.extracts.append(extract)
            session.commit()
        else:
            self.perror("Topic {} for extract {} not found in DB"
                        .format(source_topic_fp, extract_fp))

    def stop_recording(self):
        cur_song = self.current_song()
        child = subprocess.Popen(['pkill', 'parecord'],
                                 stdout=subprocess.PIPE,
                                 shell=False)
        response = child.communicate()[0]
        if child.returncode == 0:
            speak("rec stop")
            self.active_keys = {}
            self.active_keys.update(self.topic_keys)
            self.recording = False
            with self.connection():
                self.client.single(0)
            # Get the last inserted extract
            extract = (session
                       .query(ExtractFile)
                       .order_by(ExtractFile.created_at.desc())
                       .first())
            if extract:
                extract.endstamp = cur_song['elapsed']
                session.commit()
            else:
                print("No record in the DB for this extract")
        else:
            print("There was no active parecord process")

    def next_topic(self):
        self.previous()
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())
        if topic:
            with self.connection():
                self.client.seekcur(float(topic.cur_timestamp))

    def prev_topic(self):
        self.next()
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())
        if topic:
            with self.connection():
                self.client.seekcur(float(topic.cur_timestamp))
        else:
            print("Couldn't find ")

    def archive_topic(self):
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())
        if topic:
            topic.archived = 1
            session.commit()
            print("Deleted:", topic)
        else:
            print("Couldn't find topic in DB")
