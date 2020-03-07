from config import (HOST,
                    PORT)
from models import (TopicFile,
                    ExtractFile,
                    ItemFile,
                    session)
import time
import mpd
from contextlib import contextmanager
from sqlalchemy import or_
import logging
from MPD.MpdBase import Mpd
from typing import Union


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s:%(name)s:%(funcName)s():%(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("heartbeat.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class MpdHeartbeat(Mpd, object):

    def __init__(self, interval=5):
        """
        :interval: Seconds between polls.
        """
        super().__init__()
        self.interval = interval

    def heartbeat_loop(self):
        """Polls the MPD server, for events.
        """
        while True:
            cur_time = time.time()
            with self.connection():
                status = self.client.status()
                event = status['state']
                timestamp = status.get('elapsed')
                filepath = self.current_track['abs_fp']
            if event != "stop" and timestamp and filepath:
                file: Union[TopicFile, ExtractFile, ItemFile] = \
                        (session
                         .query(TopicFile, ItemFile, ExtractFile)
                         .filter(or_(TopicFile.filepath == filepath,
                                     ExtractFile.filepath == filepath,
                                     ItemFile.question_filepath == filepath))
                         .one_or_none())
                if file:
                    events = file.events
                    if events:
                        last_event = max(events,
                                        key=lambda event: event.created_at)
                        # Check if same event
                        if last_event.event == event:
                            # Update duration
                            duration = cur_time - (last_event
                                                   .created_at
                                                   .timestamp())
                            last_event.duration = duration
                            last_event.timestamp = timestamp
                            session.commit()
                            logger.info(f"Updated {event} event for file {file}.")
                    # Create a new event
                    file.add_event(event=event, timestamp=timestamp)
                    session.commit()
                    logger.info(f"Added new {event} event for file {file}.")
                else:
                    logger.error("Currently playing track not found in DB.")
            time.sleep(self.interval)


if __name__ == "__main__":
    heartbeat = MpdHeartbeat()
    heartbeat.heartbeat_loop()
