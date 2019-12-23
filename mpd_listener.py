import time
import os
from contextlib import contextmanager
import mpd
from config import (HOST,
                    PORT,
                    TOPICFILES_DIR)
from models import (session,
                    TopicFile)


client = mpd.MPDClient()


@contextmanager
def connection():
    """ Connects to the mpd server to execute a command.
    """
    try:
        client.connect(HOST, PORT)
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
        filepath = os.path.join(AUDIOFILES_DIR,
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
