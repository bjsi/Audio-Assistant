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
from models import TopicFile, ExtractFile, session
from Sounds.sounds import speak


class TopicQueue(Mpd, object):

    """ Extends core mpd functions for the
    Topic queue.
    """

    def __init__(self):
        """
        :queue: String. Name of the current playlist
        :active_keys: Dict[Keycode constants: method names]
        :recording: Boolean. True if currently recording
        :clozing: Boolean. True if currently clozing
        :topic_keys: Dict[Keycode constants: method names]
        """

        Mpd.__init__(self)

        # State
        self.queue = "global topic queue"
        self.active_keys = {}
        self.recording = False
        self.clozing = False

        # Keys
        self.topic_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.prev_topic,
                KEY_Y:      self.next_topic,
                KEY_RIGHT:  self.seek_forward,
                KEY_LEFT:   self.seek_backward,
                # KEY_DOWN:   self.load_topic_extracts, <-- inter-queue
                KEY_OK:     self.start_recording,
                # KEY_A:      self.load_global_extracts, <-- inter-queue
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

    def load_topic_options(self):
        with self.connection():
            self.client.repeat(1)
            self.client.single(0)
        self.active_keys = {}
        self.active_keys = self.topic_keys
        self.current_playlist = "global topic queue"
        self.recording = False
        print("Topic options loaded")
        print("Keys:")
        print(self.active_keys)
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
            self.load_playlist(topics)
            self.load_topic_options()
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
            self.load_topic_options()
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
        else:
            print("Couldn't find ")

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


if __name__ == "__main__":
    """ When run as a top-level script, the
    ExtractQueue can be tested in isolation
    from TopicQueue and ItemQueue """

    topic_queue = TopicQueue()
    topic_queue.get_global_topics()

    # Create the main loop
    while True:
        r, w, x = select(controller.devices, [], [])
        for fd in r:
            for event in controller.devices[fd].read():
                if event.value == 1:
                    if event.code in audio_assistant.active_keys:
                        audio_assistant.active_keys[event.code]()

    # TODO Catch Exceptions
