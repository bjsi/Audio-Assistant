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
from contextlib import ExitStack
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(funcName)s():%(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("topic_queue.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class TopicQueue(Mpd, object):

    """Extends core mpd functions for the Topic queue.
    """

    def __init__(self):
        """
        :queue: Name of the current queue.

        :active_keys: Methods available in current queue.

        :recording: True if recording.

        :clozing: True if clozing.

        :topic_keys: Methods available in current queue.
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

    def load_topic_options(self) -> None:
        """Set state options for global topic queue.
        """
        # Set playback options
        self.repeat(1)
        self.single(0)
        # Set state information and keys
        self.active_keys = self.topic_keys
        self.current_queue = "global topic queue"
        self.recording = False
        self.clozing = False
        espeak(self.current_queue)
        logger.info("Loaded global topic options.")

    def load_recording_options(self) -> None:
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
        logger.info("Loaded recording options.")

    def get_global_topics(self) -> bool:
        """Get global topics and load global topic queue.
        :returns: True on success else false.
        """
        # Get outstanding topics from DB
        topics: List[TopicFile] = (session
                                   .query(TopicFile)
                                   .filter_by(deleted=False)
                                   .filter_by(archived=False)
                                   .filter((TopicFile.cur_timestamp
                                            / TopicFile.duration) < 0.9)
                                   .order_by(TopicFile.created_at.asc())
                                   .all())

        if topics:
            # List of rel_fps.
            topic_queue: List[str] = [
                                      self.abs_to_rel(topic.filepath)
                                      for topic in topics
                                     ]
            if self.load_queue(topic_queue):
                self.load_topic_options()
                logger.info("Loaded global topic queue.")
                return True
            else:
                negative_beep()
                logger.info("Call to load_queue failed.")
                return False
        else:
            negative_beep()
            logger.info("No outstanding topics found in DB.")
            return False

    def start_recording(self) -> bool:
        """Start recording a new extract from a topic.
        """
        assert self.current_queue == "global topic queue"

        logger.info("Started recording")

        click_sound1()

        # Get filename of current topic
        cur_song = self.current_track()
        basename = os.path.basename(cur_song['abs_fp'])

        # create extract filepath
        # /home/pi ... /extractfiles/<name-epoch time->.wav
        extract_fp = os.path.join(EXTRACTFILES_DIR,
                                  os.path.splitext(basename)[0] +
                                  "-" +
                                  str(int(time.time())) +
                                  EXTRACTFILES_EXT)

        # TODO consider changing to ffmpeg
        # TODO check the exit code of the subprocess
        # Start parecord process and load recording options
        subprocess.Popen(['parecord',
                          '--channels=1',
                          '-d',
                          RECORDING_SINK,
                          extract_fp], shell=False)

        self.load_recording_options()

        # Add the extract as a child of the topic
        source_topic_fp = cur_song['abs_fp']
        timestamp = cur_song['elapsed']
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=source_topic_fp)
                            .one_or_none())
        if topic:
            extract: ExtractFile = ExtractFile(filepath=extract_fp,
                                               startstamp=timestamp)
            topic.extracts.append(extract)
            session.commit()
            logger.info("Created a new extract.")
            return True

        logger.error("Currently playing topic not found in DB.")
        return False

    def stop_recording(self) -> bool:
        """Stop the current recording.
        """
        assert self.recording is True

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
            extract: ExtractFile = (session
                                    .query(ExtractFile)
                                    .order_by(ExtractFile.created_at.desc())
                                    .first())
            if extract:
                extract.endstamp = cur_track['elapsed']
                session.commit()
                logger.info("Stopped recording.")
                return True
            else:
                logger.error("Currently recording extract not found in DB.")
                return False
        else:
            logger.error("There was no active parecord process to stop.")
            return False

    def next_topic(self) -> bool:
        """ Go to the next topic in the queue at the lastest timestamp.
        """
        assert self.current_queue == "global topic queue"

        self.next()
        click_sound1()

        # Get information on the next file
        # TODO Do I need to remove stop state here?
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find the topic in the DB
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=filepath)
                            .one_or_none())

        # Seek to the current timestamp
        if topic:
            with self.connection() if not self.connected() else ExitStack():
                self.client.seekcur(float(topic.cur_timestamp))
            logger.info("Playing the next topic.")
            return True
        logger.error("Currently playing Topic not in DB.")
        return False

    def prev_topic(self) -> bool:
        """Go to the previous topic in the queue at the latest timestamp.
        """
        assert self.current_queue == "global topic queue"

        self.previous()
        click_sound1()

        # Get information on the previous file
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find the topic in the DB
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=filepath)
                            .one_or_none())

        # Seek to the current timestamp
        if topic:
            with self.connection() if not self.connected() else ExitStack():
                self.client.seekcur(float(topic.cur_timestamp))
            logger.info("Playing the next topic.")
            return True
        logger.error("Currently playing Topic not in DB")
        return False

    def archive_topic(self) -> bool:
        """ Archive the current topic.
        Topics should be archived automatically when progress > 90%.
        Archived can also be set to True at runtime.
        Archived topics with no outstanding child extracts will be deleted.
        """
        assert self.current_queue == "global topic queue"

        # Get information on the current topic
        cur_song = self.current_track()
        filepath = cur_song['abs_fp']

        # Find topic in DB
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=filepath)
                            .one_or_none())

        # Archive the Topic
        if topic:
            load_beep()
            topic.archived = 1
            session.commit()
            logger.info("Archived a topic.")
            return True
        logger.error("Currently playing topic could not in DB.")
        return False


if __name__ == "__main__":
    """Run this script to test the topic queue in isolation.
    """

    topic_queue = TopicQueue()
    topic_queue.get_global_topics()

    # TODO: Add loop
