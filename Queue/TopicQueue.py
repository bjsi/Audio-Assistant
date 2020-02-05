import os
import time
import subprocess
from typing import Dict, List, Callable
from config import (TOPICFILES_DIR,
                    EXTRACTFILES_DIR,
                    EXTRACTFILES_EXT,
                    RECORDING_SINK)
from MPD.MpdBase import Mpd
from models import TopicFile, ExtractFile, session
from Sounds.sounds import (negative_beep,
                           espeak,
                           click_sound1,
                           load_beep)
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_OK,
                    GAME_X,
                    GAME_B,
                    KEY_MENU)


class TopicQueue(Mpd, object):

    """Extends core mpd functions for the Topic queue.
    """

    def __init__(self):
        """
        :queue: String. Name of the current playlist.
        :active_keys: Functions available in current queue.
        :recording: True if recording.
        :clozing: True if clozing.
        :topic_keys: Functions available in current queue.
        """

        super().__init__()

        # State
        self.current_queue: str = "global topic queue"
        self.active_keys: Dict[int, Callable] = {}
        self.recording: bool = False
        self.clozing: bool = False

        # Keys
        self.topic_keys: Dict[int, Callable] = {
                KEY_X:      self.toggle,
                KEY_B:      self.prev_topic,
                KEY_Y:      self.next_topic,
                KEY_RIGHT:  self.seek_forward,
                KEY_LEFT:   self.seek_backward,
                KEY_OK:     self.start_recording,
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
                KEY_MENU:   self.archive_topic
        }

        self.recording_keys: Dict[int, Callable] = {
                KEY_OK:     self.stop_recording
        }

    def load_topic_options(self):
        """Set state options for "global topic queue".
        """
        # Set playback options
        self.repeat(1)
        self.single(0)
        # Set state information and keys
        self.active_keys = self.topic_keys
        self.current_queue = "global topic queue"
        self.recording = False
        self.clozing = False

    def load_recording_options(self):
        """Set state options for when recording
        """
        # Set playback options
        self.repeat(1)
        self.single(1)
        # Set state information and keys
        self.active_keys = self.recording_keys
        self.current_queue = "global topic queue"
        self.recording = True
        self.clozing = False

    def get_global_topics(self):
        """ Query DB for outstanding topics
        """
        # Get outstanding topics from DB
        topics = (session
                  .query(TopicFile)
                  .filter_by(deleted=False)
                  .filter_by(archived=False)
                  .filter((TopicFile.cur_timestamp / TopicFile.duration) < 0.9)
                  .order_by(TopicFile.created_at.asc())
                  .all())
        if topics:
            topic_queue = [
                            self.abs_to_rel(topic.filepath)
                            for topic in topics
                          ]
            if self.load_queue(topic_queue):
                self.load_topic_options()
                espeak(self.current_queue)
            else:
                negative_beep()
                print("Failed to load topic queue")
        else:
            negative_beep()
            print("No outstanding topics")

    def start_recording(self):
        """Start recording a new extract from a topic.
        """
        click_sound1()

        # Get filename of current topic
        cur_song = self.current_track()
        basename = os.path.basename(cur_song['absolute_fp'])

        # create extract filepath
        # /home/pi ... /extractfiles/<name-epoch time->.wav
        extract_fp = os.path.join(EXTRACTFILES_DIR,
                                  os.path.splitext(basename)[0] +
                                  "-" +
                                  str(int(time.time())) +
                                  EXTRACTFILES_EXT)

        # TODO consider changing to ffmpeg
        # Start parecord process and load recording options
        subprocess.Popen(['parecord',
                          '--channels=1',
                          '-d',
                          RECORDING_SINK,
                          extract_fp], shell=False)
        self.load_recording_options()

        # Add the extract as a child of the topic
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
            # TODO Log severe error
            print("ERROR: Couldn't find topic in DB")

    def stop_recording(self):
        """ Stop the current recording.
        """
        # TODO Log severe error if this breaks
        assert self.recording
        # Get current song info
        cur_track = self.current_track()

        # Kill the active parecord process
        child = subprocess.Popen(['pkill', 'parecord'],
                                 stdout=subprocess.PIPE,
                                 shell=False)

        # TODO Check if this is correct
        # If return code is 0, a parecord process was killed
        response = child.communicate()[0]
        if child.returncode == 0:
            espeak("rec stop")
            self.load_topic_options()

            # Get the last inserted extract
            extract = (session
                       .query(ExtractFile)
                       .order_by(ExtractFile.created_at.desc())
                       .first())
            if extract:
                extract.endstamp = cur_track['elapsed']
                session.commit()
            else:
                # TODO Log severe error
                print("ERROR: No extract found in DB")
        else:
            # TODO Log strange error
            print("ERROR: There was no active parecord process")

    def next_topic(self):
        """ Go to the next topic in the queue.
        Skip to the topic's current timestamp
        """
        # TODO Log severe error if this breaks
        assert self.current_queue == "global topic queue"
        self.next()

        click_sound1()

        # Get information on the next file
        # TODO Do I need to remove stop state here?
        cur_song = self.current_track()
        filepath = cur_song['absolute_fp']

        # Find the topic in the DB
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Seek to the current timestamp
        if topic:
            with self.connection():
                self.client.seekcur(float(topic.cur_timestamp))
        else:
            # TODO Log severe error
            print("ERROR: Currently playing Topic not in DB")

    def prev_topic(self):
        """ Go to the previous topic in the queue.
        Skip to the topic's current timestamp
        """
        # TODO Log severe error if this breaks
        assert self.current_queue == "global topic queue"
        self.previous()

        click_sound1()

        # Get information on the previous file
        cur_song = self.current_track()
        filepath = cur_song['absolute_fp']

        # Find the topic in the DB
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Seek to the current timestamp
        if topic:
            with self.connection():
                self.client.seekcur(float(topic.cur_timestamp))
        else:
            # TODO Log severe error
            print("ERROR: Currently playing Topic not in DB")

    def archive_topic(self):
        """ Archive the current topic.
        Topics should be archived automatically when progress > 90%.
        Archived can also be set to True at runtime.
        Archived topics with no outstanding child extracts will be deleted.
        """
        # TODO Log severe error on break
        assert self.current_queue == "global topic queue"

        # Get information on the current topic
        cur_song = self.current_track()
        filepath = cur_song['absolute_fp']

        # Find topic in DB
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Archive the Topic
        if topic:
            load_beep()
            topic.archived = 1
            session.commit()
            print("Archived {}".format(topic))
        else:
            # TODO Log severe error
            print("ERROR: Couldn't find topic in DB")


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
