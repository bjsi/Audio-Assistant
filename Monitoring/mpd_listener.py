#!/usr/bin/env python3
import time
from contextlib import contextmanager
import mpd
from config import *
from models import *

# Should be working now!

client = mpd.MPDClient()

@contextmanager
def connection():
    try:
        client.connect(HOST,PORT)
        yield
    finally:
        client.close()
        client.disconnect()

while True:
    with connection():
        status = client.status()
        cur_song = client.currentsong()
    state = status['state']
    if state in ['pause', 'stop']:
        pass
    else:
        relative_fp = cur_song['file']
        filepath = os.path.join(TOPICFILES_DIR,
                                os.path.basename(relative_fp))
        cur_timestamp = float(status['elapsed'])
        file = (session
                .query(TopicFile)
                .filter_by(filepath=filepath)
                .one_or_none())
        if file:
            db_timestamp = file.cur_timestamp
            if cur_timestamp > db_timestamp:
                file.cur_timestamp = cur_timestamp
                session.commit()
    time.sleep(5)
