import youtube_dl
import subprocess
import os
from models import TopicFile, session, Playlist
from config import (TOPICFILES_DIR,
                    ARCHIVE_FILE)
import logging
from typing import List


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
                 config=None,
                 language: str = 'en',
                 sm_element_id: int = -1,
                 sm_priority: float = -1,
                 playback_rate: float = 1.0,
                 max_downloads: int = 1):
        """
        :url: Url of the youtube video.
        :playback_rate: Desired playback rate for the audio track.
        :sm_element_id: the parent element extracts can be added under.
        :sm_priority: The priority of extracts exported into SM.
        """

        self.yt_id = yt_id
        self.language = language
        self.max_downloads = max_downloads
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
                'subtitleslangs': [language],
                'subtitlesformat': 'vtt',
                'ignoreerrors': True,
                'outtmpl': os.path.join(TOPICFILES_DIR, '%(id)s.%(ext)s'),
                'max_downloads': max_downloads
        }
        
        # For Flask API downloads
        if config:
            self.config = config
            self.ydl_options["progress_hooks"].append(self.download_progress_hook)

        # Playlist information
        self.is_playlist = False
        self.playlist_id = None

    def check_is_playlist(self, id: str) -> None:
        """Get ydl info dict for youtube id to check whether it is a playlist or video.
        """
        with youtube_dl.YoutubeDL({}) as ydl:
            info_dict = ydl.extract_info(id, download=False, process=False)
            if info_dict.get("_type") == "playlist":
                self.is_playlist = True
                self.playlist_uploader_id = info_dict["uploader_id"]
                self.playlist_id = info_dict["id"]
                self.playlist_title = info_dict["title"]
            else:
                self.is_playlist = False

    def download_progress_hook(self, target):
        """Update app.config['updated']
        """
        if target['status'] == 'downloading':
            if target.get('downloaded_bytes') and target.get('total_bytes'):
                if (target['downloaded_bytes'] / target['total_bytes']) != self.config['progress']:
                    self.config['updated'] = True
                    self.config["progress"] = int(target['downloaded_bytes'] / target['total_bytes'] * 100)
                    print('\n\n' + str(self.config["progress"]) + "%" + '\n\n')
        
        elif target['status'] == "error":
            self.config["updated"] = True
            self.config["error"] = True
        
        elif target['status'] == 'finished':
            self.config['updated'] = True
            self.config['progress'] = 100

    def download(self) -> None:
        """Download a youtube video's audio.
        """
        self.check_is_playlist(self.yt_id)
        try:
            with youtube_dl.YoutubeDL(self.ydl_options) as ydl:
                ydl.download([self.yt_id])
        except youtube_dl.utils.DownloadError as e:
            logger.error(f"Attempt to download {self.yt_id} failed with "
                         f"exception {e}")

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
                temp_dir_name = os.path.dirname(filepath)
                tmp_name, tmp_ext = os.path.splitext(os.path.basename(filepath))
                temp_file_name = tmp_name + ".tmp" + tmp_ext
                temp_output_file = os.path.join(temp_dir_name, temp_file_name)
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
                        return
                    else:
                        logger.error("Call to set_playback_rate failed.")
                        return
                self.add_topicfile(filepath)
                return
            else:
                logger.error(f"Downloaded audio file {filepath} "
                             "does not exist.")
                return
    
    def add_topicfile(self, filepath: str):
        """Extract data and add to DB as a new TopicFile.
        :filepath: Audio filepath.
        """

        with youtube_dl.YoutubeDL({}) as ydl:
            # find individual video id - depends on filename being id.ext
            video_id = os.path.splitext(os.path.basename(filepath))[0]
            info = ydl.extract_info(video_id, download=False)

        if info:
            topic: TopicFile = TopicFile(filepath=filepath,
                                         title=info["title"],
                                         youtube_id=info["id"],
                                         language=self.language,
                                         duration=(info["duration"] / self.playback_rate),
                                         uploader=info["uploader"],
                                         uploader_id=info["uploader_id"],
                                         thumbnail_url=info["thumbnail"],
                                         upload_date=info["upload_date"],
                                         view_count=info["view_count"],
                                         like_count=info["like_count"],
                                         dislike_count=info["dislike_count"],
                                         average_rating=info["average_rating"],
                                         downloaded=True,
                                         sm_element_id=self.sm_element_id,
                                         sm_priority=self.sm_priority,
                                         playback_rate=self.playback_rate)
            
            subs_file = os.path.splitext(filepath)[0] + f".{self.language}.vtt"
            if os.path.exists(subs_file):
                topic.transcript_filepath = subs_file

            if self.is_playlist:
                if self.playlist_id:

                    # Search for existing playlist in DB
                    # Don't add new playlists here
                    playlist: Playlist = (session
                                          .query(Playlist)
                                          .filter_by(playlist_id=self.playlist_id)
                                          .one_or_none())
                    # Inherit the playlist's language and priority
                    topic.sm_priority = playlist.sm_priority
                    topic.language = playlist.language
                    playlist.topics.append(topic)

                    #if not playlist:
                    #    playlist = Playlist(playlist_id=self.playlist_id,
                    #                        title=self.playlist_title,
                    #                        language=self.language,
                    #                        outstanding_target=self.max_downloads,
                    #                        uploader_id=self.playlist_uploader_id)
                    #    playlist.topics.append(topic)
                    #    session.add(playlist)
            
            session.add(topic)
            session.commit()
            logger.info(f"Successfully added {topic} to DB.")
        else:
            logger.error("YDL info extraction failed.")
            return


def get_new_playlist_items():
    """Get new playlist items for outstanding playlists.
    """
    playlists: List[Playlist] = (session
                                 .query(Playlist)
                                 .filter_by(archived=False)
                                 .all())

    if playlists:
        for playlist in playlists:
            outstanding = playlist.has_outstanding()
            target = playlist.outstanding_target
            if outstanding < target:
                # Number of oustanding topics for this playlist
                # is less than the number the user requested to
                # be in the TopicFile queue at any time, so
                # start download
                to_download = target - outstanding
                logger.debug(f"{playlist} has {outstanding} outstanding " 
                             f"TopicFiles. Outstanding target for this "
                             f"Playlist is {target}. Starting ydl download "
                             f"with max_downloads set to {to_download}.")
                AudioDownloader(yt_id=playlist.playlist_id,
                                max_downloads=to_download,
                                language=playlist.language).download()

        
if __name__ == "__main__":
    get_new_playlist_items()
