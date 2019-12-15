import os
import time
import subprocess
from config import (TOPICFILES_DIR,
                    EXTRACTFILES_DIR,
                    EXTRACTFILES_EXT,
                    RECORDING_SINK)
from MPD.MpdBase import Mpd
from models import TopicFile, ExtractFile, session
from Sounds.sounds import espeak
from config import (KEY_X,
                    KEY_B,
                    KEY_Y,
                    KEY_RIGHT,
                    KEY_LEFT,
                    KEY_OK,
                    GAME_X,
                    GAME_B)


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
                KEY_OK:     self.start_recording,
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
        }

        self.recording_keys = {
                KEY_OK:     self.stop_recording
        }

    @staticmethod
    def rel_to_abs_topic(filepath: str) -> str:
        """ Convert a filepath relative to the mpd base dir to an
        absolute filepath
        Relative: topicfiles/<topic_fp>.wav
        Absolute: /home/pi ... /topicfiles/<topic_fp>.wav """
        filename = os.path.basename(filepath)
        abs_fp = os.path.join(TOPICFILES_DIR, filename)
        return abs_fp

    @staticmethod
    def abs_to_rel_topic(filepath: str) -> str:
        """ Convert an absolute filepath to a filepath relative to
        the mpd base dir
        Relative: topicfiles/<topic_fp>.wav
        Absolute: /home/pi ... /topicfiles/<topic_fp>.wav """
        filename = os.path.basename(filepath)
        directory = os.path.basename(TOPICFILES_DIR)
        rel_fp = os.path.join(directory, filename)
        return rel_fp

    def load_topic_options(self):
        """ Set the state options for "global topic queue".
        """
        # Set playback options
        with self.connection():
            self.client.repeat(1)
            self.client.single(0)
        # Set state information and keys
        self.active_keys = self.topic_keys
        self.queue = "global topic queue"
        self.recording = False
        self.clozing = False

    def load_recording_options(self):
        """ Set the state options for when recording
        """
        # Set playback options
        with self.connection():
            self.client.repeat(1)
            self.client.single(1)
        # Set state information and keys
        self.active_keys = self.recording_keys
        self.queue = "global topic queue"
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
            topics = [
                        self.abs_to_rel_topic(topic.filepath)
                        for topic in topics
                     ]
            self.load_playlist(topics)
            self.load_topic_options()
            espeak(self.queue)
        else:
            # TODO add negative sound
            print("No outstanding topics")

    def start_recording(self):
        """ Start recording a new extract from a topic.
        """
        # Get filename of current topic
        cur_song = self.current_song()
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
        cur_song = self.current_song()

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
                extract.endstamp = cur_song['elapsed']
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
        assert self.queue == "global topic queue"
        self.next()

        # Get information on the next file
        # TODO Do I need to remove stop state here?
        cur_song = self.current_song()
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
        assert self.queue == "global topic queue"
        self.previous()

        # Get information on the previous file
        cur_song = self.current_song()
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
        TODO What are the effects of archiving?
        TODO When is a topic deleted
        """
        # TODO Log severe error on break
        assert self.queue == "global topic queue"

        # Get information on the current topic
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        # Find topic in DB
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        # Archive the Topic
        if topic:
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
