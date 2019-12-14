import mpd
from mpd import MPDClient
import time
import os
from typing import Dict, List
from config import HOST
from config import PORT
from config import AUDIOFILES_BASEDIR
from contextlib import contextmanager


class Mpd(object):

    """
    Mpd class implements all the functions
    needed to interact with the MPD daemon.
    """

    def __init__(self):

        """
        Host and port for the mpd client can be
        customised in the config.py file

        :host: defaults to localhost (127.0.0.1)
        :port: defaults to port 6060
        """
        self.host = HOST if HOST else "localhost"
        self.port = PORT if PORT else 6060
        self.client = MPDClient()

    @contextmanager
    def connection(self):

        """Create a temporary connection to the mpd
        client to execute a command and immediately
        disconnect
        """
        try:
            self.client.connect(self.host, self.port)
            yield
        finally:
            self.client.close()
            self.client.disconnect()

    def mpd_recognised(self, filepath: str) -> bool:
        """ Checks if mpd recognises the file
        Necessary just after creating a new Extract
        or Item """
        with self.connection():
            try:
                recognised = self.client.find('file', filepath)
                if recognised:
                    return True
            except mpd.base.CommandError:
                print("Mpd doesn't recognise {}"
                      .format(filepath))
        return False

    def load_playlist(self, playlist: List[str]):
        """ Loads a playlist
        :playlist: An iterable of audio files,
        relative to the mpd base directory
        """
        if playlist:
            with self.connection():
                self.client.clear()
                for file in playlist:
                    self.client.add(file)
            print("Playlist loaded:")
            print(playlist)
        else:
            print("Error loading playlist - No files")

    def remove_stop_state(self):
        """MPD state can be play, pause or stop.
        Stop state blocks play/pause toggles and
        throws an exception if you query the current
        file.
        Always called from within self.connection
        context, so not needed here.
        """
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

    def current_song(self) -> Dict:
        """Get the currently playing song
        :returns: dict containing relative filepath,
        absolute filepath and time elapsed in seconds.miliseconds.
        """
        with self.connection():
            self.remove_stop_state()
            cur_song = self.client.currentsong()
            status = self.client.status()
            relative_fp = cur_song.get('file', None)
            elapsed = status.get('elapsed', 0.0)
            absolute_fp = os.path.join(AUDIOFILES_BASEDIR,
                                       relative_fp)

            song_info = {'relative_fp': relative_fp,
                         'absolute_fp': absolute_fp,
                         'elapsed': elapsed}
            return song_info

    def previous(self):
        """Play the previous track
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            self.client.previous()
        print("Previous")

    def next(self):
        """Play the next track
        :returns: TODO
        """
        with self.connection():
            self.remove_stop_state()
            self.client.next()
        print("Next")

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
