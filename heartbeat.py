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

# TODO Maybe use my own Mpd class

client = mpd.MPDClient()


@contextmanager
def connection():
    """ Connect to mpd client to execute command """
    try:
        client.connect(HOST, PORT)
        yield
    finally:
        client.close()
        client.disconnect()


while True:
    cur_time = time.time()

    with connection():
        # Ignore stop state
        status = client.status()
        event = status['state']
        if event == "stop":
            continue

        # Get current file info
        timestamp = status['elapsed']
        filepath = client.currentsong()['file']

    # Find the current file in DB
    file = (session
            .query(TopicFile, ItemFile, ExtractFile)
            .filter(or_(TopicFile.filepath == filepath,
                        ExtractFile.filepath == filepath,
                        ItemFile.question_filepath == filepath))
            .one_or_none())

    if file:
        events = file.events
        if events:
            last_event = max(events, key=lambda event: event.created_at)
            # Check if same event
            if last_event.event == event:
                # Update duration
                duration = cur_time - last_event.created_at.timestamp()
                last_event.duration = duration
                last_event.timestamp = timestamp
                session.commit()
                continue
        # Create a new event
        file.add_event(event=event, timestamp=timestamp)
    else:
        # TODO Log severe error
        print("ERROR: Currently playing file not found in DB")

    time.sleep(4)
