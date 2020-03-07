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
from typing import Union, Optional


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

    def find_file(self, filepath: str) -> Optional[Union[TopicFile,
                                                         ItemFile,
                                                         ExtractFile]]:
        """Search TopicFile, ExtractFile and ItemFile tables to find the row
        corresponding to the filepath.
        """

        # Search TopicFile table
        topic: TopicFile = (session
                            .query(TopicFile)
                            .filter_by(filepath=filepath)
                            .one_or_none())
        if topic:
            logger.info(f"Found currently playing {topic}.")
            return topic
        
        else:
            # Search ExtractFile table
            extract: ExtractFile = (session
                                    .query(ExtractFile)
                                    .filter_by(filepath=filepath)
                                    .one_or_none())
            if extract:
                logger.info(f"Found currently playing {extract}.")
                return extract

            else:
                # Search ItemFile table
                item: ItemFile = (session
                                  .query(ItemFile)
                                  .filter_by(question_filepath=filepath)
                                  .one_or_none())

                if item:
                    logger.info(f"Found currently playing {item}.")
                    return item

        return None

    def heartbeat_loop(self):
        """Polls the MPD server, for events.
        """
        while True:
            cur_time = time.time()
            with self.connection():
                status = self.client.status()
                event = status['state']
                timestamp = status.get('elapsed')
                filepath = self.current_track()['abs_fp']
            if event != "stop":
                if timestamp:
                    if filepath:
                        self.find_file(filepath)

            if event != "stop" and timestamp and filepath:
                file = self.find_file(filepath)
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
                            logger.info(f"Updated last event {last_event}.")
                    # Create a new event
                    if file.add_event(event_type=event,
                                      timestamp=timestamp,
                                      duration=0):
                        session.commit()
                        logger.info(f"Added new {event} event for file {file}.")
                    else:
                        logger.error(f"Call to add_event on {file} failed.")
                else:
                    logger.error("Currently playing track not found in DB.")
            time.sleep(self.interval)


if __name__ == "__main__":
    heartbeat = MpdHeartbeat()
    heartbeat.heartbeat_loop()
