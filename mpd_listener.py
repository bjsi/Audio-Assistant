import time
from MPD.MpdBase import Mpd
from models import (session,
                    TopicFile)
import logging
from typing import Optional

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

    def find_file(self, filepath: str) -> Optional[TopicFile]:
        """Attempts to find the row corresponding to the filepath
        in the TopicFile table.
        """
        # Find the topic
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=filepath)
                            .one_or_none())
        if topic:
            logger.info(f"Found currently playing {topic}.")
            return topic
        return None

    def listen_loop(self):
        """Polls the MPD server, updates TopicFile current timestamp.
        """
        while True:
            with self.connection():
                status = self.client.status()
                cur_song = self.current_track()
            
            state = status["state"]
            abs_fp = cur_song["abs_fp"]
            cur_timestamp = float(status.get("elapsed", 0))

            if state not in ["pause", "stop"] and abs_fp and cur_timestamp:
                if abs_fp:
                    topic = self.find_file(abs_fp)
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
