import mpd
from mpd import MPDClient
import time
import os
from config import HOST
from config import PORT
from config import AUDIOFILES_BASEDIR
from contextlib import contextmanager, ExitStack
from typing import List, Dict, Optional
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(funcName)s():"
                              "%(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("mpd_base.log")
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


class Mpd(object):

    """MPD basic functions.
    """

    def __init__(self):

        """Check your mpd config and set custom host and port in config.py.
        """

        self.host = HOST if HOST else "localhost"
        self.port = PORT if PORT else 6600
        self.client = MPDClient()

    @contextmanager
    def connection(self):

        """Create temporary connection to mpd client.
        """
        try:
            self.client.connect(self.host, self.port)
            yield
        finally:
            self.client.close()
            self.client.disconnect()

    @staticmethod
    def abs_to_rel(abs_fp: str) -> str:
        """Convert absolute filepath to an MPD base-relative filepath.
        """
        filename = os.path.basename(abs_fp)
        basedir = os.path.dirname(abs_fp)
        rel_dir = os.path.basename(basedir)
        return os.path.join(rel_dir, filename)
        
    @staticmethod
    def rel_to_abs(rel_fp: str) -> str:
        """Convert an MPD-relative filepath to an absolute filepath.
        """
        return os.path.join(AUDIOFILES_BASEDIR, rel_fp)

    def connected(self) -> bool:
        """Test connection to MPD server.
        :return: True if connected else False.
        """
        try:
            self.client.ping()
            return True
        except mpd.base.ConnectionError:
            return False

    def mpd_recognised(self, rel_fp: str) -> bool:
        """Checks if mpd recognises the file.

        :rel_fp: MPD base directory relative filepath.
        """

        with self.connection() if not self.connected() else ExitStack():
            try:
                if self.client.find('file', rel_fp):
                    return True
            except mpd.base.CommandError:
                logger.debug(f"MPD does not recognise file {rel_fp}.")
        return False

    def load_queue(self, queue: List[str]) -> bool:
        """Loads a queue of audio tracks.

        :queue: List of MPD base-relative filepaths.
        :returns: True on success, false on failure.
        """
        if queue:
            with self.connection() if not self.connected() else ExitStack():
                self.client.clear()
                for file in queue:
                    self.client.add(file)
            logger.info(f"Loaded a new queue with {len(queue)} tracks.")
            return True
        return False

    def remove_stop_state(self) -> None:
        """MPD state can be play, pause or stop.

        Stop state blocks play / pause toggles and status queries.
        """
        with self.connection() if not self.connected() else ExitStack():
            state = self.client.status()['state']
            if state == 'stop':
                self.client.play()
                self.client.pause(1)

    def toggle(self) -> None:
        """Toggle between play and pause.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            self.client.pause()
        logger.debug("Toggled play / pause.")

    # TODO: Better typing on the return dict
    def current_track(self) -> Dict:
        """Get the currently playing track.

        :returns: rel_fp, abs_fp and time elapsed (float).
        """
        
        with self.connection() if not self.connected() else ExitStack():
            # Get rel_fp of current track
            self.remove_stop_state()
            # if there is no currentsong, returns an empty dict
            cur_song = self.client.currentsong()
            status = self.client.status()
            rel_fp: Optional[str] = cur_song.get('file', None)
            # Get abs_fp of current track
            abs_fp: Optional[str] = self.rel_to_abs(rel_fp) if rel_fp else None
            # Get elapsed of current track
            elapsed = float(status.get('elapsed', 0.0))

            return {
                    'rel_fp': rel_fp,
                    'abs_fp': abs_fp,
                    'elapsed': elapsed
                   }

    def previous(self) -> None:
        """Play the previous track.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            self.client.previous()
        logger.debug("Playing previous track.")

    def next(self) -> None:
        """Play the next track.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            self.client.next()
        logger.debug("Playing the next track.")

    def seek_forward(self, seconds=6) -> None:
        """Seek forward by a number of seconds.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp + seconds
            self.client.seekcur(seek_to)
        logger.debug(f"Seeking forward {seconds} seconds.")

    def seek_backward(self, seconds=6) -> None:
        """Seek backward by a number of seconds.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp - seconds
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
        logger.debug(f"Seeking backward {seconds} seconds.")

    def volume_up(self, increment=5) -> None:
        """Increase the volume.
        """
        print("vol up")
        with self.connection() if not self.connected() else ExitStack():
            status = self.client.status()
            cur_vol = status.get('volume')
            if cur_vol:
                new_vol = int(cur_vol) + increment
                if new_vol > 100:
                    logger.debug(f"Max volume.")
                    return
                self.client.setvol(new_vol)
                logger.debug(f"Increasing volume {increment} points.")

    def volume_down(self, increment=5) -> None:
        """Decrease the volume.
        """
        with self.connection() if not self.connected() else ExitStack():
            status = self.client.status()
            cur_vol = status.get('volume')
            if cur_vol:
                new_vol = int(cur_vol) - increment
                if new_vol < 0:
                    logger.debug(f"Min volume.")
                    return
                self.client.setvol(new_vol)
                logger.debug(f"Decreasing volume {increment} points.")

    def stutter_forward(self) -> None:
        """Seek forward frame-by-frame for accurate clozing.

        Stutter forward and stutter backward require special attention
        because toggling play and pause cuts off a small section of audio
        before it starts playing through headphones.

        :returns: None
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            # TODO Keep adjusting the seek amount
            # This feels pretty much perfect.

            seek_to = cur_timestamp - 0.165
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)
            self.client.seekcur(seek_to + 0.2)
            logger.debug("Stutter forward.")

    def stutter_backward(self) -> None:
        """Seek backward frame-by-frame for accurate clozing.

        Stutter forward and stutter backward require special attention
        because toggling play and pause cuts off a small section of audio
        before it starts playing through headphones.

        :returns: None
        """
        with self.connection() if not self.connected() else ExitStack():
            self.remove_stop_state()
            status = self.client.status()
            cur_timestamp = float(status.get('elapsed', 0.0))
            seek_to = cur_timestamp - 0.165
            seek_to = cur_timestamp - 0.23
            if seek_to < 0:
                return
            self.client.seekcur(seek_to)
            self.client.pause(0)
            time.sleep(0.2)
            self.client.pause(1)
            self.client.seekcur(seek_to + 0.2)
        logger.debug("Stutter forward.")

    def repeat(self, state: int) -> None:
        """Repeat if 1, do not repeat if 0.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.client.repeat(state)

    def single(self, state: int):
        """Single if 1, not single if 0.
        """
        with self.connection() if not self.connected() else ExitStack():
            self.client.single(state)
