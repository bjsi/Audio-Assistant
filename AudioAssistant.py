from config import *
import mpd
from extract_funcs import cloze_processor
import time
import subprocess
from config import *
from models import TopicFile, ExtractFile, ItemFile, session
from typing import Optional, Tuple
import os
from MpdBase import Mpd
from BluetoothDevices import BTDevice
from sounds import speak, negative, click_one, click_two


class AudioAssistant(Mpd, object):

    """Extending core mpd functions adding recording,
       audio cloze deletions, scheduling, queueing etc."""

    def __init__(self):
        """TODO: to be defined.
        :recording: Boolean. Am I currently recording?
        :clozing: Boolean. Am I currently making a cloze?
        :current_playlist: String.
        # TODO These aren't strings
        :*_keys: Dict[int, str]. subsets of CONTROLLER['keys'].
        string values are names of methods to call when the
        buttons are pressed
        """
        Mpd.__init__(self)
        self.recording = False
        self.clozing = False
        # One of the following: 
        # global topic queue [default],
        # global extract queue, 
        # local extract queue,
        # local item queue
        self.current_playlist = "global topic queue"

        # Updated during runtime according to state
        self.active_keys = {}

        self.topic_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.play_previous,
                KEY_Y:      self.play_next,
                KEY_RIGHT:  self.seek_forward,
                KEY_LEFT:   self.seek_backward,
                KEY_DOWN:   self.load_topic_extracts,
                KEY_OK:     self.start_recording,
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
                KEY_A:      self.load_global_extracts
        }

        self.recording_keys = {
                KEY_OK:     self.stop_recording
        }

        self.extracting_keys = {
                KEY_X:      self.toggle,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_OK:     self.start_clozing,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_UP:     self.get_extract_topic,
                KEY_DOWN:   self.load_extract_items,
                GAME_X:     self.volume_up,
                GAME_B:     self.volume_down,
                KEY_A:      self.load_global_topics,
        }

        self.cloze_keys = {
                KEY_X:      self.toggle,
                KEY_RIGHT:  self.stutter_forward,
                KEY_LEFT:   self.stutter_backward,
                KEY_OK:     self.stop_clozing,
        }

        self.item_keys = {
                KEY_X:      self.toggle,
                KEY_UP:     self.get_item_extract,
                KEY_B:      self.previous,
                KEY_Y:      self.next,
                KEY_A:      self.load_global_topics
        }

    @negative
    def perror(self, stdoutmsg="", function=""):
        """
        Print a message to stdout with error message and
        function name
        """
        print("Message:", stdoutmsg)
        print("Function:", function)

    def load_global_topics(self):
        topics = self.get_global_topics()
        self.load_playlist(topics)

    def load_global_extracts(self):
        extracts = self.get_global_extracts()
        self.load_playlist(extracts)

    def load_topic_extracts(self):
        extracts = self.get_topic_extracts()
        self.load_playlist(extracts)

    def load_extract_items(self):
        items = self.get_extract_items()
        self.load_playlist(items)

    # TODO more specific typing
    def get_global_topics(self) -> Optional[Tuple]:
        """Query DB for outstanding topics
            outstanding = not deleted and cur timestamp /
            duration < 0.9
        :returns: generator of audio filepaths relative to mpd base dir

        """
        topics = (session
                  .query(TopicFile)
                  .filter_by(deleted=False)
                  .filter(TopicFile.cur_timestamp /
                          TopicFile.duration < 0.9)
                  # TODO Implement a queueing algorithm
                  .order_by(TopicFile.created_at.asc())
                  .all())

        if topics:
            topics = (
                        os.path.join(
                            os.path.basename(TOPICFILES_DIR),
                            os.path.basename(topic.filepath))
                        for topic in topics
                     )
            return topics, "global topic queue"
        return None

    # TODO more specific typing
    def get_global_extracts(self) -> Optional[Tuple]:
        """Query DB for outstanding extracts
           outstanding = not deleted
        :returns: generator of audio filepaths relative to mpd base dir

        """
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .order_by(ExtractFile.created_at.desc())
                    .all())

        if extracts:
            extracts = (
                         os.path.join(
                             os.path.basename(EXTRACTFILES_DIR),
                             os.path.basename(extract.extract_filepath))
                         for extract in extracts
                       )
            return extracts, "global extract queue"
        return None

    # TODO more specific typing
    def get_topic_extracts(self) -> Optional[Tuple]:
        """Get the children extracts from the current topic
        :returns: TODO

        """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        if topic and topic.extractfiles:
            extracts = [] 
            with self.connection():
                for extract in topic.extractfiles:
                # What if it's deleted
                    try:
                        recognised = self.client.find('file',
                                        os.path.join(
                                            os.path.basename(EXTRACTFILES_DIR),
                                            os.path.basename(extract.extract_filepath)))
                        if recognised:
                            extracts.append(recognised[0]['file'])
                    except mpd.base.CommandError:
                        print("Mpd doesn't recognise {}"
                              .format(extract.extract_filepath))
                        continue

            if extracts:
                return extracts, "local extract queue"
        return None

    # TODO More specific typing
    def get_item_extract(self):
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']

        item = (session
                .query(ItemFile)
                .filter_by(question_filepath=filepath)
                .one_or_none())
        
        if item:
            extract = item.extractfile
            if extract.deleted is False:
                filepath = os.path.join(os.path.basename(EXTRACTFILES_DIR),
                                        os.path.basename(extract.extract_filepath))
                extracts = self.get_global_extracts()
                self.load_playlist(extracts)
                with self.connection():
                    playlist = self.client.playlistinfo()
                    for track in playlist:
                        if track['file'] == filepath:
                            extract_id = track['id']
                            break
                        self.client.moveid(extract_id, 0)
                        self.remove_stop_state()
            else:
                self.perror("Orphan Item: No parent extract found.",
                            "get_item_extract")

    def get_extract_items(self):
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        extract = (session
                   .query(ExtractFile)
                   .filter_by(extract_filepath=filepath)
                   .one_or_none())
        
        if extract and extract.itemfiles:
            # using list to check for existence
            items = []
            with self.connection():
                for item in extract.itemfiles:
                    # What if it's deleted
                    if item.question_filepath:
                        try:
                            recognised = self.client.find('file',
                                                os.path.join(
                                                    os.path.basename(QUESTIONFILES_DIR),
                                                    os.path.basename(item.question_filepath)))
                            if recognised:
                                items.append(recognised[0]['file'])
                        except mpd.base.CommandError:
                            print("Mpd doesn't recognise {}"
                                  .format(item.filepath))
                            continue
            if items:
                return items, "local item queue"
        return None

    # TODO More specific type
    def load_playlist(self, data: Tuple):
        """load the playlist and set the global state

        :data: TODO
        :returns: TODO

        """
        options = {
                   "global extract queue": {
                       "repeat": 1,
                       "single": 1,
                       "controller": self.extracting_keys,
                       "dir": 'extractfiles'},
                   "local extract queue": {
                       "repeat": 1,
                       "single": 1,
                       "controller": self.extracting_keys,
                       "dir": 'extractfiles'},
                   "global topic queue": {
                       "repeat": 1,
                       "single": 0,
                       "controller": self.topic_keys,
                       "dir": 'topicfiles'},
                   "local item queue": {
                       "repeat": 1,
                       "single": 1,
                       "controller": self.item_keys,
                       "dir": "questionfiles"
                       }
        }
        if data:
            playlist, name = data
            if playlist and name in options.keys():
                with self.connection():
                    self.client.clear()
                    # files mpd has scanned and recognised in mpd base dir
                    # hacky
                    mpd_recognised = [
                                        d.get('file')
                                        for d in self.client.listall(options[name]['dir'])
                                        if d.get('file') is not None
                                     ]
                    for track in playlist:
                        if track in mpd_recognised:
                            self.client.add(track)

                    self.client.repeat(options[name]['repeat'])
                    self.client.single(options[name]['single'])

                speak(name)
                self.current_playlist = name
                self.active_keys = {}
                self.active_keys.update(options[name]['controller'])
                return
        else:
            self.perror("Error loading playlist.",
                        "load_playlist")

    def get_extract_topic(self):
        """get the parent topic of the current extract
        :returns: TODO

        """
        cur_song = self.current_song()
        filepath = cur_song['absolute_fp']
        extract = (session
                   .query(ExtractFile)
                   .filter_by(extract_filepath=filepath)
                   .one_or_none())

        if extract:
            parent = extract.topicfile
            if parent.deleted is False:
                filepath = os.path.join(os.path.basename(TOPICFILES_DIR),
                                        os.path.basename(parent.filepath))
                topics = self.get_global_topics()
                self.load_playlist(topics)
                with self.connection():
                    playlist = self.client.playlistinfo()
                    for track in playlist:
                        if track['file'] == filepath:
                            parent_id = track['id']
                            break
                        self.client.moveid(parent_id, 0)
                        self.remove_stop_state()
                        self.client.seekcur(parent.cur_timestamp)
            else:
                self.perror("Ophan extract: No parent",
                            "get_extract_topic")

    @click_one
    def start_clozing(self):
        """Start a cloze deletion on an extract
        :returns: TODO

        """
        if self.current_playlist in ['local extract queue',
                                     'global extract queue']:
            if not self.clozing:
                cur_song = self.current_song()
                cur_timestamp = cur_song['elapsed']
                filepath = cur_song['absolute_fp']

                extract = (session
                           .query(ExtractFile)
                           .filter_by(extract_filepath=filepath)
                           .one_or_none())

                if extract:
                    extract.itemfiles.append(ItemFile(cloze_startstamp=cur_timestamp))
                    session.commit()
                    self.clozing = True
                    self.active_keys = {}
                    self.active_keys.update(self.cloze_keys)
                else:
                    self.perror("Couldn't find extract {} in DB."
                                .format(extract),
                                "start_clozing")
            else:
                self.perror("Already clozing (self.clozing is True)")
        else:
            self.perror("Not in an extract queue. Current queue is {}"
                        .format(self.current_playlist))

    @click_two
    def stop_clozing(self):
        """Stop the current cloze deletion on an extract
        :returns: TODO

        """
        if self.current_playlist in ['local extract queue',
                                     'global extract queue']:
            if self.clozing:
                cur_song = self.current_song()
                cur_timestamp = float(cur_song['elapsed'])
                filepath = cur_song['absolute_fp']
                extract = (session
                           .query(ExtractFile)
                           .filter_by(extract_filepath=filepath)
                           .one_or_none())

                if extract:
                    items = extract.itemfiles
                    last_item = max(items, key=lambda item: item.created_at)
                if last_item and last_item.cloze_startstamp:
                    # Get the last inserted itemfile
                    if last_item.cloze_startstamp  < cur_timestamp:
                        last_item.cloze_endstamp = cur_timestamp
                        session.commit()
                        self.clozing = False
                        self.active_keys = {}
                        self.active_keys.update(self.extracting_keys)

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

    @click_two
    def stop_recording(self):
        """Stop the current recording
        :returns: TODO

        """
        if self.recording:
            if self.current_playlist == "global topic queue":
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
                        extract.topicfile_endstamp = cur_song['elapsed']
                        session.commit()

    @click_one
    def start_recording(self):
        """Start recording an extract while in topic queue
        :returns: TODO

        """
        if not self.recording:
            if self.current_playlist == "global topic queue":
                cur_song = self.current_song()
                basename = os.path.basename(cur_song['absolute_fp'])
                extract_fp = os.path.join(EXTRACTFILES_DIR,
                                          os.path.splitext(basename)[0] +
                                          "-" +
                                          str(int(time.time())) +
                                          EXTRACTFILES_EXT)
                print(extract_fp)
                subprocess.Popen(['parecord',
                                  '--channels=1',
                                  '-d',
                                  RECORDING_SINK,
                                  extract_fp], shell=False)
                self.recording = True
                self.active_keys = {}
                self.active_keys.update(self.recording_keys)
                with self.connection():
                    self.client.single(1)

                source_topic_fp = cur_song['absolute_fp']
                timestamp = cur_song['elapsed']

                topic = (session
                         .query(TopicFile)
                         .filter_by(filepath=source_topic_fp)
                         .one_or_none())
                if topic:
                    extract = ExtractFile(extract_filepath=extract_fp,
                                          topicfile_startstamp=timestamp)
                    topic.extractfiles.append(extract)
                    session.commit()
                else:
                    self.perror("Topic {} for extract {} not found in DB"
                                .format(source_topic_fp, extract_fp))

    def seek_to_cur_timestamp(self):
        """Query the DB to find how much of the current track
        you have already listened to. Skip to that point.
        :returns: TODO

        """
        if self.current_playlist in ['global topic queue',
                                     'local topic queue']:
            cur_song = self.current_song()
            filepath = cur_song['absolute_fp']
            topic = (session
                     .query(TopicFile)
                     .filter_by(filepath=filepath)
                     .one_or_none())
            if topic:
                with self.connection():
                    self.client.seekcur(topic.cur_timestamp)

    @click_one
    def play_next(self):
        self.next()
        if self.current_playlist == "global topic queue":
            # seek cur timestamp
            cur_song = self.current_song()
            filepath = cur_song['absolute_fp']
            topic = (session
                     .query(TopicFile)
                     .filter_by(filepath=filepath)
                     .one_or_none())
            if topic:
                with self.connection():
                    self.client.seekcur(float(topic.cur_timestamp))

    @click_one
    def play_previous(self):
        self.previous()
        if self.current_playlist == "global topic queue":
            # seek cur timestamp
            cur_song = self.current_song()
            filepath = cur_song['absolute_fp']
            topic = (session
                     .query(TopicFile)
                     .filter_by(filepath=filepath)
                     .one_or_none())
            if topic:
                with self.connection():
                    self.client.seekcur(float(topic.cur_timestamp))
