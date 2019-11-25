from config import *
from models import *
import datetime
import time
import mpd

client = mpd.MPDClient()

@connection
def connection():
    try:
        client.connect(HOST, PORT)
        yield
    finally:
        client.close()
        client.disconnect()

while True:
    with connection():
        state = client.status()['state']
        filepath = client.currentsong()['file']

    cur_time = time.time()
    cur_activity = (session
                   .query(Activity)
                   .order_by(Activity.timestamp)
                   .first())

    if not cur_activity or cur_activity.topicfiles.filepath != filepath:
        file = (session
               .query(TopicFile,ExtractFile)
               .filter(TopicFile.filepath=filepath)
               .filter(ExtractFile.extract_filepath=filepath)
               .one_or_none())
        if file:
            file.activities.append(Activity(activity=state))
            session.commit()

    elif cur_activity.topicfiles.filepath == filepath or \
            cur_activity.extractfiles.extract_filepath == filepath:
        if cur_activity.activity == state:
            # .timestamp() converts datetime objects to epoch time
            created_at = cur_activity.created_at.timestamp()
            duration = cur_time - created_at
            cur_activity.timestamp = duration
            session.commit()
    time.sleep(4)
