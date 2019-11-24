from config import *
import sys
from models import *
import os
from evdev import InputDevice, ecodes
from contextlib import contextmanager
import mpd
import subprocess
import datetime
import time
from select import select
from menu_sounds import *

# from controller import Controller
# before loop: Controller.connect_device

class Controller():
    
    def __init__(self):
        self.client = mpd.MPDClient() # connect via context manager
        self.host = HOST # from config
        self.port = PORT # from config
        self.recording = False
        self.clozing = False
        self.current_playlist = "global topic queue" # loads global topics at start

        # TODO Can the event numbers change or are they static?
        self.inputdevs = map(InputDevice, 
                            ('/dev/input/event0',
                             '/dev/input/event1',
                             '/dev/input/event2',
                             '/dev/input/event3'))

        self.devices = { dev.fd: dev
                         for dev in self.inputdevs }

        self.choices = {
            
            # active menu options added here
            # may contain the the contents of 
            # topic_mode, record_mode, extract_mode,
            # cloze_mode or item_mode
            # default on startup is topic_mode

        }

        ###  Topic mode ###
        self.topic_mode = {

            KEY_X       :   self.toggle,    
            KEY_B       :   self.previous,      
            KEY_Y       :   self.next,
           #KEY_UP      :   self.vol_up,
            KEY_RIGHT   :   self.seek_forward,
            KEY_LEFT    :   self.seek_backward,
            KEY_DOWN    :   self.load_topic_extracts,
            KEY_OK      :   self.start_recording,

            GAME_X      :   self.vol_up,
            GAME_B      :   self.vol_down,

            KEY_A       :   self.load_global_extracts,

        }

        # sub-mode of topic_mode
        # active only when in the middle of recording
        self.record_mode = {

            KEY_OK      :   self.stop_recording,

        }

        ### Extract Mode ###
        self.extract_mode = {

            KEY_X       :   self.toggle,
            KEY_B       :   self.previous,
            KEY_Y       :   self.next,
            KEY_OK      :   self.start_clozing,
            KEY_RIGHT   :   self.stutter_forward,
            KEY_LEFT    :   self.stutter_backward,
            KEY_UP      :   self.get_extract_topic,
           #KEY_DOWN    :   self.get local items
            KEY_MENU    :   self.delete_extract,

            GAME_X      :   self.vol_up,
            GAME_B      :   self.vol_down,

            KEY_A       :   self.load_global_topics,

        }

        # a sub-mode of extract mode
        # active when in the middle of a cloze
        self.cloze_mode = {

            KEY_X       :   self.toggle,
            KEY_RIGHT   :   self.stutter_forward,
            KEY_LEFT    :   self.stutter_backward,
            KEY_OK      :   self.stop_clozing,

        }

        ### Item Mode ###
        self.item_mode = {

            KEY_X       :   self.toggle,
            KEY_B       :   self.previous,
            KEY_Y       :   self.next,
           #KEY_UP      :   get parent,

            GAME_X      :   self.vol_up,
            GAME_B      :   self.vol_down,

            KEY_A       :   self.load_global_topics,

        }

    def load_global_topics(self):
        topics = self.get_global_topics()
        self.load_playlist(topics)


    def load_global_extracts(self):
        extracts = self.get_global_extracts()
        self.load_playlist(extracts)


    def load_topic_extracts(self):
        extracts = self.get_topic_extracts()
        self.load_playlist(extracts)


    def get_global_topics(self):
        # query DB for oustanding topics
        topics = (session
                  .query(TopicFile)
                  .filter_by(deleted=False)
                  .order_by(TopicFile.created_at.asc())
                  .all())
        if topics:
            topics = ( 
                       os.path.join('topicfiles', os.path.basename(topic.filepath))
                       for topic in topics 
                     )
            return topics, "global topic queue"
        else:
            return None, "global topic queue"


    def get_global_extracts(self):

        # query DB for outstanding extracts
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .order_by(ExtractFile.created_at.asc())
                    .all())

        if extracts:
            # generator of paths relative to mpd base dir
            extracts = (
                        os.path.join('extractfiles',
                                     os.path.basename(
                                         extract.extract_filepath))
                        for extract in extracts
                       )
            return extracts, "global extract queue"
        else:
            return None, "global extract queue"


    def get_topic_extracts(self):
        """ create a playlist of a topic's extract children """         
        assert (self.current_playlist == "global topic queue",
                "Current playlist is not global topic queue.")
                                        
        with self.mpd_connection():
            self.remove_stop_state()
            cur_song = self.client.currentsong()

        relative_fp = cur_song['file']
        filepath = os.path.join(TOPICFILES_DIR,
                                os.path.basename(relative_fp))
            
        topic = (session
                 .query(TopicFile)
                 .filter_by(filepath=filepath)
                 .one_or_none())

        if topic and topic.extractfiles:
            # each child in children gnerator
            # 'extractfiles/<filename>.wav'
            children = (
                            os.path.join('extractfiles', os.path.basename(
                                                         child.extract_filepath))
                            for child in topic.extractfiles
                            if child.deleted == 0
                       )
            
            if children:
                return children, "local extract queue"
        return None, "local extract queue"


    def load_playlist(self, playlist: tuple):
        """ 
        Playlist tuple contains a generator expression of audio tracks
        and the playlist name
        """

        # Make this global?

        options = {
                   "global extract queue": {
                       "repeat": 1,
                       "single": 1,
                       "controller": self.extract_mode},
                   "local extract queue": {
                       "repeat": 1,
                       "single": 1,
                       "controller": self.extract_mode},
                   "global topic queue": {
                       "repeat": 1,
                       "single": 0,
                       "controller": self.topic_mode}
                   }

        playlist, name = playlist
        if playlist is not None and name in options.keys():
            with self.mpd_connection():
                self.client.clear()
                for track in playlist:
                    self.client.add(track)
                self.client.repeat(options[name]['repeat'])
                self.client.single(options[name]['single'])
            
            self.espeak(name)
            self.current_playlist = name
            self.choices = {}
            self.choices.update(options[name]['controller'])
            return

        else: 
            self.perror("Error loading playlist \"{}\"."
                   .format(name),
                   "load_playlist")


    def remove_stop_state(self):
        """ 
        mpd status can be stop, play or pause.
        if the status is stop, you can't use toggle to switch between play / pause.
        you also can't get information like current track
        this function checks if state is stop, if it is it switches state to pause
        """
        # always called from within self.mpd_connection context,
        # so no mpd_connection context manager here
        state = self.client.status()['state']
        if state == "stop":
            self.client.play()
            self.client.pause(1)
        return

    
    def get_extract_topic(self):
        """ get the parent topic of the currently playing extract """
        
        assert ( self.current_playlist in ["local extract queue",
                                           "global extract queue"],
                 "Current playlist is neither local nor global extract queue." )
        
        with self.mpd_connection():
            self.remove_stop_state()
            cur_song = self.client.currentsong()
            
        relative_fp = cur_song['file']
        filepath = os.path.join(EXTRACTFILES_DIR,
                                os.path.basename(relative_fp))
        extract = (session
                  .query(ExtractFile)
                  .filter_by(extract_filepath=filepath)
                  .one_or_none())

        if extract:
            parent = extract.topicfiles
            if parent and parent.deleted is False:
                filepath = os.path.join('topicfiles', 
                                      os.path.basename(parent.filepath))
            
                topics = self.get_global_topics()
                self.load_playlist(topics)
                with self.mpd_connection():
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


    def seek_to_cur_timestamp(self):
        assert self.current_playlist in ["global topic queue",
                                         "local topic queue"]
        with self.mpd_connection():
            self.remove_stop_state()
            relative_fp = self.client.currentsong()['file']
            filepath = os.path.join(TOPICFILES_DIR,
                                    os.path.basename(relative_fp))
            file = (session
                    .query(TopicFile)
                    .filter_by(filepath=filepath)
                    .one_or_none())

            if file:
                self.client.seekcur(file.cur_timestamp)

            
    @contextmanager
    def mpd_connection(self):
        """ Connect, execute mpd command, disconnect """
        try:
            self.client.connect(HOST, PORT)
            yield
        finally:
            self.client.close()
            self.client.disconnect()


    @staticmethod
    def device_connected(device: dict, attempts=5):

        dev_name = device['name']
        dev_address = device['address']
        
        count = 0
        while count  < attempts:
            count = count + 1
            
            bt_data = subprocess.getoutput("hcitool con")
            if dev_address in bt_data.split():
                break
            
            print("{} not connected.".format(dev_name))
            print("Connecting now. Attempt #{}.".format(count))

            # try to connect to the headphones
            connected = subprocess.call(['bluetoothctl',
                                         'connect',
                                         dev_address])
            # 0 is the bash success exit code
            if connected == 0:
                break

            # Add error message / exit status code
            print("Connection attempt {} failed.".format(count))     
            time.sleep(5)

        print("Successfully connected to {}.".format(dev_name))
        return True


    @negative
    def perror(self, stdoutmsg, function, ttsmsg=''):
        # error reporting to stdout / espeak    
        # maybe this should be logging instead

        print("Message:", stdoutmsg)
        print("Function:", function)
        if ttsmsg:
            self.espeak(ttsmsg)            


    def espeak(self, msg):
        subprocess.Popen(['espeak', msg], shell=False)


    def menu_loop(self):
        self.load_global_topics()
        self.choices = {}
        self.choices.update(self.topic_mode)
        self.seek_to_cur_timestamp()
        while True:
            r, w, x = select(self.devices, [], [])
            for fd in r:
                for event in self.devices[fd].read():
                    # if event.type == ecodes.EV_KEY:
                    # binary values - 1 for pressed, 0 for unpressed
                    if event.value == 1:
                        if event.code in self.choices:
                            self.choices[event.code]()


    @click_one
    def toggle(self):
        with self.mpd_connection():
            status = self.client.status()
            self.remove_stop_state()
            self.client.pause()


    @click_one
    def previous(self):
        """ works with both extracts and topics"""
        with self.mpd_connection():
            self.remove_stop_state()
            self.client.previous()
            relative_fp = self.client.currentsong()['file']
            
            filepath = os.path.join(AUDIOFILES_BASEDIR,
                                    relative_fp)

            file = (session
                    .query(TopicFile)
                    .filter_by(filepath=filepath)
                    .one_or_none())

            if file:
                cur_timestamp = file.cur_timestamp
                self.client.seekcur(float(cur_timestamp))
                print("prev")


    @click_one
    def next(self):
        with self.mpd_connection():
            self.remove_stop_state()
            self.client.next()
            relative_fp = self.client.currentsong()['file']
            filepath = os.path.join(AUDIOFILES_BASEDIR,
                                    relative_fp)

            file = (session
                    .query(TopicFile)
                    .filter_by(filepath=filepath)
                    .one_or_none())

            if file:
                cur_timestamp = file.cur_timestamp
                self.client.seekcur(float(cur_timestamp))
                print("next")
    

    @click_one
    def seek_forward(self):
        with self.mpd_connection():
            self.remove_stop_state()
            status = self.client.status()
            timestamp = float(status.get('elapsed', 0.0))
            seek_to = timestamp + 7
            self.client.seekcur(seek_to)
            print("seek ->")


    @click_one
    def seek_backward(self):
        with self.mpd_connection():
            self.remove_stop_state()
            status = self.client.status()
            timestamp = float(status['elapsed'])
            seek_to = timestamp - 7
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
            print("seek <-")


    @click_one
    def vol_up(self):
        with self.mpd_connection():
            cur_vol = self.client.status()['volume']
            new_vol = int(cur_vol) + 5
            if new_vol > 100:
                return
            self.client.setvol(new_vol)
            print("vol up")


    @click_one
    def vol_down(self):
        with self.mpd_connection():
            cur_vol = self.client.status()['volume']
            new_vol = int(cur_vol) - 5
            if new_vol < 0:
                return
            self.client.setvol(new_vol)
            print("vol down")

    
    @click_one
    def start_clozing(self):
        if ( not self.clozing ) and \
           ( self.current_playlist in ['local extract queue',
                                       'global extract queue'] ):

            with self.mpd_connection():
                cur_song = self.client.currentsong()
                status = self.client.status()
            
            cur_timestamp = float(status['elapsed'])
            print("cloze start")
            relative_fp = cur_song['file']
            filepath = os.path.join(
                    EXTRACTFILES_DIR,
                    os.path.basename(relative_fp))

            extract = (session
                       .query(ExtractFile)
                       .filter_by(extract_filepath=filepath)
                       .one_or_none())
            if extract:
                extract.cloze_startstamp = cur_timestamp
                session.commit()
                self.clozing = True
                self.choices = {}
                self.choices.update(self.cloze_mode)
            else:
                self.perror("Couldn't find extract {} in DB."
                        .format(extract),
                        "start_clozing")


    @click_two
    def stop_clozing(self):
        if ( self.clozing ) and \
           ( self.current_playlist in ["local extract queue",
                                       "global extract queue"] ):

            with self.mpd_connection():
                cur_song = self.client.currentsong()
                status = self.client.status()

            cur_timestamp = float(status['elapsed'])
            print("cloze stop")
            relative_fp = cur_song['file']
            filepath = os.path.join(
                    EXTRACTFILES_DIR,
                    os.path.basename(relative_fp))

            extract = (session
                       .query(ExtractFile)
                       .filter_by(extract_filepath=filepath)
                       .one_or_none())

            if extract:
                if extract.cloze_startstamp < cur_timestamp:
                    extract.cloze_endstamp = cur_timestamp
                    session.commit()
                    self.clozing = False
                    self.choices = {}
                    self.choices.update(self.extract_mode)
            else:
                self.perror("Couldn't find extract {} in DB"
                        .format(extract),
                        "stop_clozing")


    def stutter_forward(self):
        with self.mpd_connection():
            #self.client.pause(1)
            self.remove_stop_state()
            # seek back a small amount.
            status = self.client.status()
            timestamp = float(status.get('elapsed', 0.0))
            seek_to = timestamp - 0.18 # 20 17 18
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)


    def stutter_backward(self):
        # pretty much perfect
        with self.mpd_connection():
            self.remove_stop_state()
            #self.client.pause(1)
            status = self.client.status()
            timestamp = float(status['elapsed'])
            seek_to = timestamp - 0.4
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)


    @click_two
    def stop_recording(self):
        if self.recording and self.current_playlist == "global topic queue":
            with self.mpd_connection():
                status = self.client.status()
                cur_song = self.client.currentsong()
                self.client.single(0)
                relative_fp = os.path.basename(self.client.currentsong()['file'])

            # Attempt to kill running parecord instances
            child = subprocess.Popen(['pkill', 'parecord'],
                                     stdout=subprocess.PIPE,
                                     shell=False)

            response = child.communicate()[0]
            
            # returncode 0 = bash success exit code
            if child.returncode == 0:
                subprocess.Popen(['espeak', 'rec stop'], shell=False)
                self.choices = {}
                self.choices.update(self.topic_mode)
                self.recording = False

            # get the last extract by timestamp

                extract = (session
                           .query(ExtractFile)
                           .order_by(ExtractFile.created_at.desc())
                           .first())
                
                if extract:
                    timestamp = status['elapsed']
                    extract.topicfile_endstamp = timestamp
                    session.commit()
                print("kill rec")

            
    @click_one
    def start_recording(self):
        if not self.recording and self.current_playlist == "global topic queue":
            with self.mpd_connection():
                status = self.client.status()
                filename = os.path.basename(self.client.currentsong()['file'])
                self.client.single(1)
            
            self.choices = {}
            self.choices.update(self.record_mode)

            extract_path = os.path.join(EXTRACTFILES_DIR,
                                        os.path.splitext(filename)[0] +
                                        "-" +
                                        str(int(time.time())) +
                                        EXTRACTFILES_EXT)

            subprocess.Popen(['parecord',
                              '--channels=1',
                              '-d', 
                              RECORDING_SINK,                          
                              extract_path], shell=False)

            self.recording = True
            
            source_path = os.path.join(TOPICFILES_DIR, filename)
            timestamp = status['elapsed']

            # What if no file is returned
            topic = (session
                     .query(TopicFile)
                     .filter_by(filepath=source_path)
                     .one_or_none())

            if topic is not None:
                topic.extractfiles.append(ExtractFile(extract_filepath=extract_path,
                                                      topicfile_startstamp=timestamp))
                session.commit()
                print("rec")
            else:
                print("Source file {} for extract {} not found in DB".format(source_path, extract_path))
    
    @click_two
    def delete_extract(self):
        if self.current_playlist in ['global extract queue',
                                     'local extract queue']:

            if self.clozing is False:
                with self.mpd_connection():
                    relative_fp = self.client.currentsong()['file']
                filepath = os.path.join(EXTRACTFILES_DIR,
                                        os.path.basename(relative_fp))
                extract = (session
                           .query(ExtractFile)
                           .filter_by(extract_filepath=filepath)
                           .one_or_none())

                if extract:
                    # TODO This only sets deleted column in the DB to True
                    # Doesn't actually delete the file

                    if os.path.exists(filepath):
                        extract.deleted = 1
                        session.commit()
                else:
                    print("Could not delete that file")
