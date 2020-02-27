import youtube_dl
import subprocess
import os
from models import TopicFile, session
from config import (TOPICFILES_DIR,
                    ARCHIVE_FILE)
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(funcName)s():"
                              "%(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("models.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


class AudioDownloader(object):

    """Downloads audio from youtube videos via youtube_dl.
    """

    def __init__(self,
                 yt_id: str,
                 sm_element_id: int = -1,
                 sm_priority: float = -1,
                 playback_rate: float = 1.0):
        """
        :url: Url of the youtube video.
        :playback_rate: Desired playback rate for the audio track.
        :sm_element_id: the parent element extracts can be added under.
        :sm_priority: The priority of extracts exported into SM.
        """

        self.yt_id = yt_id
        self.playback_rate = playback_rate
        self.sm_element_id = sm_element_id
        self.sm_priority = sm_priority
        self.ydl_options = {
                'format': 'worstaudio/worst',
                # 'logger': logger(),
                'progress_hooks': [self.finished_hook],
                'download_archive': ARCHIVE_FILE,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'sub_lang': ['en'],
                'sub_format': 'vtt',
                'ignoreerrors': True,
                'outtmpl': os.path.join(TOPICFILES_DIR, '%(id)s.%(ext)s'),
                'max_downloads': 1
        }

    def download(self):
        """Download a youtube video's audio.
        """
        try:
            # TODO try except youtube_dl.utils.DownloadError
            with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
                ydl.download([self.yt_id])
        except youtube_dl.utils.DownloadError as e:
            logger.error(f"Attempt to download {self.yt_id} failed with "
                         f"exception {e}")
            return

    def set_playback_rate(self, filepath: str) -> bool:
        """Make a subprocess call to ffmpeg to set the playback rate.

        :filepath: The path to the downloaded audio file.
        :returns: True on success else False
        """
        # ffmpeg limited to range between 0.5 and 2
        if self.playback_rate < 0.5 or self.playback_rate > 2:
            logger.error(f"Requested playback rate was {self.playback_rate}, "
                         "but ffmpeg can only set playback rate "
                         "between 0.5 and 2.")
            return False
        if os.path.isfile(filepath):
            try:

                temp_output_file = f"tmp.{filepath}"
                p = subprocess.call(['ffmpeg',
                                     '-i',
                                     filepath,
                                     '-filter:a',
                                     f"atempo={str(self.playback_rate)}",
                                     '-vn',
                                     temp_output_file])

                if p != 0:
                    logger.error("Subprocess call to ffmpeg to "
                                 "change the playback rate failed.")
                    return False
                # success, remove filepath, rename tmp to filepath
                try:
                    os.remove(filepath)
                    os.rename(temp_output_file, filepath)
                except OSError as e:
                    logger.error("Attempt to clean up temp files after "
                                 "changing playback rate failed with "
                                 f"exception {e}")
                    return False
                
                return True

            except OSError as e:
                logger.error(f"Subprocess call to ffmpeg failed with "
                             f"exception {e}")
                return False

    def finished_hook(self, target):
        """Runs after each successful download.
        """

        if target['status'] == 'finished':
            filepath = target['filename']
            # Check filepath exists.

            if os.path.isfile(filepath):
                if self.playback_rate != 1:
                    if self.set_playback_rate(filepath):
                        self.add_topicfile(filepath)
                    else:
                        logger.error("Call to set_playback_rate failed.")
                        return
                self.add_topicfile(filepath)
            else:
                logger.error(f"Downloaded audio file {filepath} "
                             "does not exist.")
                return
    
    def add_topicfile(self, filepath: str):
        """Extract data and add to DB as a new TopicFile.
        :filepath: Audio filepath.
        """

        with youtube_dl.YoutubeDL({'playlist': False}) as ydl:
            info = ydl.extract_info(self.yt_id, download=False)

        if info:
            topic: TopicFile = TopicFile(filepath=filepath,
                                         title=info["title"],
                                         youtube_id=info["youtube_id"],
                                         duration=(info["duration"] / self.playback_rate),
                                         uploader=info["uploader"],
                                         uploader_id=info["uploader_id"],
                                         thumbnail_url=info["thumbnail_url"],
                                         upload_date=info["upload_date"],
                                         view_count=info["view_count"],
                                         like_count=info["like_count"],
                                         dislike_count=info["dislike_count"],
                                         average_rating=["average_rating"],
                                         downloaded=True,
                                         sm_element_id=self.sm_element_id,
                                         sm_priority=self.sm_priority,
                                         playback_rate=self.playback_rate)

            subs_file = os.path.splitext(filepath)[0] + ".en.vtt"
            if os.path.exists(subs_file):
                topic.transcript_filepath = subs_file
            
            session.add(topic)
            session.commit()
            logger.info(f"Successfully added {topic} to DB.")

        else:
            logger.error("YDL info extraction failed.")
            return


if __name__ == "__main__":
    AudioDownloader("xVJwVrm1I60").download()