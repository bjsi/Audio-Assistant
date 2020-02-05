import mpd
from mpd import MPDClient
import time
import os
from config import HOST
from config import PORT
from config import AUDIOFILES_BASEDIR
from contextlib import contextmanager
from typing import List, Dict


class Mpd(object):

    """Music player daemon basic functions.
    """

    def __init__(self):

        """Check your mpd config and set custom host and port in config.py.
        """
        self.host = HOST if HOST else "localhost"
        self.port = PORT if PORT else 6060
        self.client = MPDClient()

    @contextmanager
    def connection(self):

        """Create temporary connection to mpd client.
        """
        if self.connected():
            return
            yield
        try:
            self.client.connect(self.host, self.port)
            yield
        finally:
            self.client.close()
            self.client.disconnect()

    @staticmethod
    def abs_to_rel(abs_fp: str) -> str:
        """ Convert an absolute filepath to a MPD base-relative filepath"""
        filename = os.path.basename(abs_fp)
        basedir = os.path.dirname(abs_fp)
        rel_dir = os.path.basename(basedir)
        return os.path.join(rel_dir, filename)
        
    @staticmethod
    def rel_to_abs(rel_fp: str) -> str:
        """ Convert an MPD-relative filepath to an absolute filepath """
        return os.path.join(AUDIOFILES_BASEDIR, rel_fp)

    def connected(self) -> bool:
        """Test connection to MPD server.
        :return: True if connected else False
        """
        try:
            self.client.ping()
            return True
        except mpd.base.ConnectionError:
            return False

    def mpd_recognised(self, rel_fp: str) -> bool:
        """Checks if mpd recognises the file.
        :rel_fp: MPD base-relative filepath.
        """
        with self.connection():
            try:
                if self.client.find('file', rel_fp):
                    return True
            except mpd.base.CommandError:
                print("Mpd doesn't recognise {}".format(rel_fp))
        return False

    def load_queue(self, queue: List[str]) -> bool:
        """Loads a queue of audio tracks.

        :queue: List of MPD base-relative filepaths.
        :returns: True on success, false on failure.
        """
        if queue:
            with self.connection():
                self.client.clear()
                for file in queue:
                    self.client.add(file)
            return True
        return False

    def remove_stop_state(self):
        """MPD state can be play, pause or stop.
        Stop state blocks play/pause toggles and status queries.
        """
        with self.connection():
            state = self.client.status()['state']
            if state == 'stop':
                self.client.play()
                self.client.pause(1)

    def toggle(self):
        """Toggle between play and pause."""
        with self.connection():
            self.remove_stop_state()
            self.client.pause()
        print("Play")

    def current_track(self) -> Dict:
        """Get the currently playing track
        :returns: relative filepath, absolute filepath and time elapsed.
        """
        with self.connection():
            # Get rel_fp of current track
            self.remove_stop_state()
            cur_song = self.client.currentsong()
            status = self.client.status()
            rel_fp = cur_song.get('file', None)
            # Get abs_fp of current track
            abs_fp = self.rel_to_abs(rel_fp)
            # Get elapsed of current track
            elapsed = status.get('elapsed', 0.0)

            return {
                'relative_fp': rel_fp,
                'absolute_fp': abs_fp,
                'elapsed': elapsed
            }

    def previous(self) -> str:
        """Play the previous track
        :returns: The song.
        """
        with self.connection():
            self.remove_stop_state()
            self.client.previous()
        print("Previous")
        return self.current_track()

    def next(self) -> str:
        """Play the next track
        :returns: The song.
        """
        with self.connection():
            self.remove_stop_state()
            self.client.next()
        return self.current_track()

    def seek_forward(self):
        """An improvement on the seeking command from
        mpd
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp + 6
            self.client.seekcur(seek_to)
        print("Seek forward")

    def seek_backward(self):
        """An improvement on the seeking command from
        mpd
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp - 6
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
        print("Seek backward")

    def volume_up(self):
        """Increase the volume
        :returns: TODO
        """
        print("vol up")
        with self.connection():
            status = self.client.status()
            cur_vol = int(status['volume'])
            new_vol = cur_vol + 5
            if new_vol > 100:
                return
            self.client.setvol(new_vol)
        print("Volume up")

    def volume_down(self):
        """Decrease the volume
        :returns: TODO

        """
        print("vol down")
        with self.connection():
            status = self.client.status()
            cur_vol = int(status['volume'])
            new_vol = cur_vol - 5
            if new_vol < 0:
                return
            self.client.setvol(new_vol)
        print("Volume down")

    def stutter_forward(self):
        """Seek forward frame-by-frame
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            # TODO Keep adjusting the seek amount
            seek_to = cur_timestamp - 0.165
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)
        print("Stutter forward")

    def stutter_backward(self):
        """Seek backward frame-by-frame
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp - 0.40
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)
        print("Stutter backward")

    def repeat(self, state: int):
        """Repeat if 1, do not repeat if 0
        """
        with self.connection():
            self.client.repeat(state)

    def single(self, state: int):
        """Single if 1, not single if 0
        """
        with self.connection():
            self.client.single(state)
