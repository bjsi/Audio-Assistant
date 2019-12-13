import youtube_dl
import os
import logging
import logging.config
import yaml
from Models.models import TopicFile, session, YoutubeTag
from config import TOPICFILES_DIR, ARCHIVE_FILE
from .transcript_funcs import vtt_to_text


# with open('logging.yaml', 'r') as f:
#     log_cfg = yaml.safe_load(f.read())
#
# logging.config.dictConfig(log_cfg)
# logger = logging.getLogger('ydl')


def finished_hook(target):
    if target['status'] == 'finished':

        filepath = target['filename']
        vid_id = os.path.splitext(os.path.basename(filepath))[0]

        with youtube_dl.YoutubeDL({}) as ydl:
            info = ydl.extract_info(vid_id, download=False)

        title = info['title']
        youtube_id = info['id']
        duration = info['duration']
        uploader = info['uploader']
        uploader_id = info['uploader_id']
        thumbnail_url = info['thumbnail']
        upload_date = info['upload_date']
        view_count = info['view_count']
        like_count = info['like_count']
        dislike_count = info['dislike_count']
        average_rating = info['average_rating']

        file = TopicFile(filepath=filepath,
                         title=title,
                         youtube_id=youtube_id,
                         duration=duration,
                         uploader=uploader,
                         uploader_id=uploader_id,
                         thumbnail_url=thumbnail_url,
                         upload_date=upload_date,
                         view_count=view_count,
                         like_count=like_count,
                         dislike_count=dislike_count,
                         average_rating=average_rating,
                         downloaded=True)

        tags = info['tags'] + info['categories']
        for tag in tags:
            file.yttags.append(YoutubeTag(tag))

        # Find subtitle file if exists, convert to plain text and add to DB
        subs_file = os.path.splitext(filepath)[0] + ".en.vtt"
        if os.path.exists(subs_file):
            transcript = vtt_to_text(subs_file)
            file.transcript = transcript

        # TODO Term extraction and add to my_tags
        # Basically:
        # terms = term_extract(subsfile)
        # file.mytags.extend(terms)

        session.add(file)
        session.commit()

        return


ydl_opts = {
        'format': 'worstaudio/worst',
        #'logger': logger(),
        'progress_hooks': [finished_hook],
        'download_archive': ARCHIVE_FILE,
        # if no batch file option
        # with open(BATCH_FILE) as f:
        #     urls = f.readlines() # remember to strip comments
        # then pass to the download call below (accepts [lists])
        # 'batch_file':
        'writesubtitles': True,
        'writeautomaticsub': True,
        'sub-lang': ['en'],
        # explicitly add that the subs should be en.vtt format
        'writeinfojson': True,
        'ignoreerrors': True,
        # output format
        # u'%(playlist_index)s-%(title)s.%(ext)s'
        'outtmpl': os.path.join(TOPICFILES_DIR, '%(id)s.%(ext)s'),
        # --add-metadata
        'max_downloads': 1,
}


with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download(["https://www.youtube.com/playlist?list=PLwmPBqRou8APdG6K-Ks0lV2yL0yqCFHOu"])
