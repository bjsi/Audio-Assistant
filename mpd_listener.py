import time
from MPD.MpdBase import Mpd
from models import (session,
                    TopicFile)
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(funcName)s():"
                              "%(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("mpd_listener.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class MpdListener(Mpd, object):

    def __init__(self, interval=5):
        """
        :interval: Seconds between polls.
        """
        super().__init__()
        self.interval = interval

    def listen_loop(self):
        """Polls the MPD server, updates TopicFile current timestamp.
        """
        while True:
            with self.connection():
                status = self.client.status()
                cur_song = self.client.currentsong()
            state = status["state"]
            if state not in ["pause", "stop"]:
                rel_fp = cur_song["file"]
                if rel_fp:
                    abs_fp = self.rel_to_abs(rel_fp)
                    cur_timestamp = float(status["elapsed"])
                    topic: TopicFile = (session
                                        .query(TopicFile)
                                        .filter_by(filepath=abs_fp)
                                        .one_or_none())
                    if topic:
                        db_timestamp = topic.cur_timestamp
                        if cur_timestamp > db_timestamp:
                            topic.cur_timestamp = cur_timestamp
                            session.commit()
                            logger.info("Updated TopicFile current timestamp.")
                    else:
                        logger.error("Currently playing track "
                                     "not found in DB.")
            time.sleep(self.interval)


if __name__ == "__main__":
    listener = MpdListener()
    listener.listen_loop()
