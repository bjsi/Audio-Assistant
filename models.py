from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer,
                        String, DateTime,
                        Text,
                        ForeignKey, Boolean,
                        Float)
import datetime
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI, QUESTIONFILES_DIR
from typing import List, Optional
import os
import logging
import subprocess
from subprocess import DEVNULL

engine = create_engine(DATABASE_URI, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)


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


def delete_file(file) -> bool:
    """Deletes a file.
    :returns: True if the file was deleted else False.
    """
    # Check file exists
    if os.path.isfile(file):
        try:
            os.remove(file)
            logger.info(f"Removed file {file}.")
            return True
        except OSError as e:
            logger.error(f"Exception {e} when attempting "
                         f"to delete {file}.")
            return False
    logger.error(f"Attempted to delete file \"{file}\" "
                 "but it does not exist.")
    return False


##############################
# Topics, Extracts and Items #
##############################

##########
# Topics #
##########


class TopicFile(Base):
    """Topics are full youtube audio files.

    TopicFiles are parents of ExtractFiles.
    """

    __tablename__ = 'topicfiles'

    id: int = Column(Integer, primary_key=True)
    filepath: str = Column(String, nullable=False, unique=True)
    downloaded: bool = Column(Boolean, nullable=False)
    sm_element_id: int = Column(Integer, default=-1)
    sm_priority: float = Column(Float, default=-1)
    # Can be set by the user at runtime
    # Can be set automatically if completion > 90%
    archived: bool = Column(Boolean, default=False)
    # If no outstanding extracts and archived is True,
    # Topic will be deleted by a script and deleted will be set to 1
    deleted: bool = Column(Boolean, default=False)
    youtube_id: str = Column(String)
    title: str = Column(String)
    duration: float = Column(Float)
    uploader_id: str = Column(String)
    uploader: str = Column(String)
    upload_date: str = Column(String)
    thumbnail_url: str = Column(String)
    view_count: int = Column(Integer)
    like_count: int = Column(Integer)
    dislike_count: int = Column(Integer)
    average_rating: float = Column(Float)  # 0 to 5 float
    playback_rate: float = Column(Float, default=1.0)  # eg. 1, 1.25, 1.5
    cur_timestamp: float = Column(Float, default=0)  # seconds.miliseconds
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    transcript_filepath: str = Column(Text)  # webvtt format if available

    # One to many File |-< Extract
    extracts: List["ExtractFile"] = relationship("ExtractFile",
                                                 back_populates="topic")

    # One to many File |-< Activity
    events: List["TopicEvent"] = relationship("TopicEvent",
                                              back_populates="topic")

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished TopicFiles.

        Removes the audio filepath and subs file.
        """
        topics: List[TopicFile] = (session
                                   .query(TopicFile)
                                   .filter_by(deleted=False)
                                   .all())
        if topics:
            for topic in topics:
                if topic.is_finished():
                    delete_file(topic.transcript_filepath)
                    if delete_file(topic.filepath):
                        topic.deleted = True
                        session.commit()
        
    def add_event(self, event_type: str, timestamp: float, duration: float):
        """Add an event to the TopicFile.
        :returns: True on success else False.
        """
        if event_type in ["stop", "play", "pause"]:
            event = TopicEvent(event=event_type,
                               timestamp=timestamp,
                               duration=duration)
            self.events.append(event)
            session.commit()
            logger.debug(f"Added {event_type} event to {self} with "
                         f"duration {duration}s.")
            return True
        return False

    def is_finished(self) -> bool:
        """A finished TopicFile fulfils the following criteria.
        
        1. Over 90% completed according to the current timestamp.

        2. TopicFile.archived is True.

        3. No outstanding extracts.

        :returns: True if the file is finished else False.
        """
        if (self.cur_timestamp / self.duration) < 0.9:
            if self.archived:
                extracts = self.extracts
                if extracts:
                    if all(extract.deleted for extract in extracts):
                        return True
                    else:
                        return False
                return True
        return False

    def progress(self) -> float:
        """
        :returns: Percentage listened to.
        """
        return (self.cur_timestamp / self.duration) * 100

    def __repr__(self) -> str:
        return f"<TopicFile: title={self.title}>"


class ExtractFile(Base):
    """ Recorded sections from TopicFiles
    ExtractFiles are all descendants of a TopicFile
    ItemFiles are all descendants of an ExtractFile"""

    __tablename__ = "extractfiles"

    id: int = Column(Integer, primary_key=True)
    filepath: str = Column(String, nullable=False, unique=True)
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    startstamp: float = Column(Float, nullable=False)  # Seconds.miliseconds
    endstamp: float = Column(Float)  # Seconds.miliseconds
    # Set by the user at runtime.
    archived: bool = Column(Boolean, default=False)
    # Archived extracts are deleted if they have no outstanding child items
    # Archived extracts with child items are deleted after export
    deleted: bool = Column(Boolean, default=False)
    exported: bool = Column(Boolean, default=False)  # True if exported to SM.
    # True if should be exported to SM, set at runtime.
    to_export: bool = Column(Boolean, default=False)  

    # One to one ExtractFile (child) |-| TopicFile (parent)
    topic_id: int = Column(Integer, ForeignKey('topicfiles.id'))
    topic: TopicFile = relationship("TopicFile", back_populates="extracts")

    # One to many ExtractFile |-< ItemFiles
    items: List["ItemFile"] = relationship("ItemFile",
                                           back_populates="extract")

    # One to many ExtractFile |-< ExtractEvent
    events = relationship("ExtractEvent", back_populates="extract")

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished ExtractFiles.
        """
        extracts: List[ExtractFile] = (session
                                       .query(ExtractFile)
                                       .filter_by(deleted=False)
                                       .all())
        if extracts:
            for extract in extracts:
                if extract.is_finished():
                    if delete_file(extract.filepath):
                        extract.deleted = True
                        session.commit()
        
    def add_event(self, event_type: str, timestamp: float, duration: float):
        """Add an event to the ExtractFile.
        :returns: True on success else False.
        """
        if event_type in ["stop", "play", "pause"]:
            event = ExtractEvent(event=event_type,
                                 timestamp=timestamp,
                                 duration=duration)
            self.events.append(event)
            session.commit()
            logger.debug(f"Added {event_type} event to {self} with "
                         f"duration {duration}s.")
            return True
        return False

    def is_finished(self) -> bool:
        """A finished ExtractFile fulfils the following criteria.

        1. Extract.exported is True

        or
        
        2. Extract.archived is True.

        and
    
        3. No outstanding child items.

        :returns: True if the file is finished else False.
        """
        if self.exported:
            return True
        if self.archived and all(item.archived or item.deleted for item in self.items):
            return True
        return False

    def length(self) -> float:
        """
        :returns: Length of the extract if start and end else 0.0
        """
        if self.startstamp and self.endstamp:
            return (self.endstamp - self.startstamp)
        return 0

    def __repr__(self) -> str:
        return f"<ExtractFile: filepath={self.filepath} " \
               f"startstamp={self.startstamp} endstamp={self.endstamp} " \
               f"length={self.length()}>"


class ItemFile(Base):
    """ ItemFile contains a question file and a cloze file
    Question file has a cloze (beep sound) over a word / phrase
    Cloze file is the unbeeped word / phrase from the extract file
    ItemFiles are are descendants of an ExtractFile
    """

    __tablename__ = "itemfiles"

    id: int = Column(Integer, primary_key=True)
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    question_filepath: str = Column(String, unique=True)
    cloze_filepath: str = Column(String, unique=True)
    # Set by the user
    archived: bool = Column(Boolean, default=False)
    # Archived files deleted by script
    # Non-archived items archived and deleted after export
    deleted: bool = Column(Boolean, default=False)
    exported: bool = Column(Boolean, default=False)  # True if exported to SM
    cloze_startstamp: float = Column(Float)  # seconds.miliseconds
    cloze_endstamp: float = Column(Float)  # seconds.miliseconds
    extract_id: int = Column(Integer, ForeignKey('extractfiles.id'))

    # One to one ItemFile (child) |-| ExtractFile (parent)
    extract: ExtractFile = relationship("ExtractFile", back_populates="items")

    # One to many ItemFile |-< ItemEvent
    events: List["ItemEvent"] = relationship("ItemEvent", back_populates="item")

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished ItemFiles.
        
        A finished ItemFile fulfils the following criteria.
        
        1. ItemFile.archived is True.

        or

        2. ItemFile.exported is True.
        """
        items: List[ItemFile] = (session
                                 .query(ItemFile)
                                 .filter_by(deleted=False)
                                 .all())
        if items:
            for item in items:
                if item.archived or item.exported:
                    if delete_file(item.cloze_filepath) and delete_file(item.question_filepath):
                        item.deleted = True
                        session.commit()
        
    def add_event(self, event_type: str, timestamp: float, duration: float):
        """Add an event to the ItemFile.
        :returns: True on success else False.
        """
        if event_type in ["stop", "play", "pause"]:
            event = ItemEvent(event=event_type,
                              timestamp=timestamp,
                              duration=duration)
            self.events.append(event)
            session.commit()
            logger.debug(f"Added {event_type} event to {self} with "
                         f"duration {duration}s.")
            return True
        return False

    def process_cloze(self) -> bool:
        """Creates a question and cloze from an ItemFile.
        """
            
        if os.path.isfile(self.extract.filepath):
            extract_fp = self.extract.filepath
            basename = os.path.basename(self.extract.filepath)
            filename, ext = os.path.splitext(basename)
            if self.extract.endstamp and self.extract.startstamp and self.extract.length() > 0:
                extract_length = self.extract.length()
                if self.cloze_endstamp and self.cloze_startstamp and \
                   self.length() > 0:
                    cloze_start = self.cloze_startstamp
                    cloze_end = self.cloze_endstamp
                    cloze_length = self.length()

                    # Extend the output cloze length slightly to improve audio
                    # TODO Test this
                    output_cloze_start = cloze_start
                    output_cloze_end = cloze_end

                    if cloze_start > 0.3:
                        output_cloze_start -= 0.3

                    if cloze_end + 0.3 < self.extract.endstamp:
                        output_cloze_end += 0.3

                    question_fp = os.path.join(QUESTIONFILES_DIR,
                                               (filename + "-" +
                                                "QUESTION" + "-" +
                                                str(self.id) +
                                                ext))

                    cloze_fp = os.path.join(QUESTIONFILES_DIR,
                                            (filename + "-" +
                                             "CLOZE" + "-" +
                                             str(self.id) +
                                             ext))
                                         
                    # Non-blocking
                    try:
                        # TODO Test waiting for exit code?
                        subprocess.Popen([
                                # INPUTS
                                # The extract file
                                'ffmpeg',
                                '-i',
                                extract_fp,
                                # Sine wave beep generator
                                '-f',
                                'lavfi',
                                '-i',
                                'sine=frequency=1000:duration=' + str(cloze_length),
                                # FILTERS
                                '-filter_complex',
                                # Cut the beginning of the extract before the cloze
                                '[0:a]atrim=' + "0" + ":" + str(cloze_start) + "[beg]" + ";" + \
                                # Cut the beginning of the cloze to the end of the cloze
                                '[0:a]atrim=' + str(output_cloze_start) + ":" + str(output_cloze_end) + "[cloze]" + ";" + \
                                # Cut the end of the extract after the cloze
                                '[0:a]atrim=' + str(cloze_end) + ":" + str(extract_length) + "[end]" + ";" + \
                                # concatenate the files
                                # [1:0] is the sine wave
                                '[beg][1:0][end]concat=n=3:v=0:a=1[question]',
                                '-map',
                                # Output the clozed extract
                                '[question]',
                                question_fp,
                                '-map',
                                # Output the clozed word / phrase
                                '[cloze]',
                                cloze_fp
                        ], shell=False, stdout=DEVNULL)

                        self.question_filepath = question_fp
                        self.cloze_filepath = cloze_fp
                        logger.info("Created a new question / cloze pair.")
                        session.commit()
                        return True
                    except OSError as e:
                        logger.error(f"Call to ffmpeg subprocess "
                                     f"failed with exception {e}.")
                        return False
                else:
                    logger.error(f"Attempted to create cloze on "
                                 "item with invalid length.")
            else:
                logger.error(f"Attempted to create cloze on "
                             "extract with invalid length.")
        else:
            logger.error(f"Extract filepath does not exist.")
        return False

    def length(self) -> float:
        """
        :returns: Length of the cloze or 0.0
        """
        if self.cloze_startstamp and self.cloze_endstamp:
            return (self.cloze_endstamp - self.cloze_startstamp)
        return 0.0

    def topicfile_startstamp(self) -> Optional[float]:
        """
        :returns: Startstamp of the cloze in the topicfile if startstamp else None.
        """
        if self.cloze_startstamp:
            return self.extract.startstamp + self.cloze_startstamp
        return None

    def topicfile_endstamp(self) -> Optional[float]:
        """
        :returns: Endstamp of the cloze in the topicfile if endstamp else None.
        """
        if self.cloze_endstamp:
            return self.cloze_endstamp + self.extract.startstamp
        return None

    def __repr__(self) -> str:
        return f"<ItemFile: id={self.id} extract_id={self.extract_id} " \
               f"cloze_startstamp={self.cloze_startstamp} " \
               f"cloze_endstamp={self.cloze_endstamp}>"


###################
# Activity Tables #
###################


class TopicEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "topicevents"

    id: int = Column(Integer, primary_key=True)
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    event: str = Column(String, nullable=False)  # play/pause/stop (mpd status)
    timestamp: float = Column(Float, nullable=False)  # seconds.miliseconds
    duration: float = Column(Float, default=0)  # seconds.miliseconds

    # Many to One TopicEvent >-| TopicFile
    topic_id: int = Column(Integer, ForeignKey('topicfiles.id'))
    topic: TopicFile = relationship("TopicFile", back_populates="events")

    def __repr__(self):
        return f"<TopicEvent: event={self.event} " \
               f"created_at={self.created_at} " \
               f"duration={self.duration}>"


class ExtractEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "extractevents"

    id: int = Column(Integer, primary_key=True)
    event: str = Column(String, nullable=False)  # play, pause
    timestamp: float = Column(Float, nullable=False)  # seconds.miliseconds
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    duration: float = Column(Float, default=0)  # seconds.miliseconds

    # Many to one ExtractEvent >-| ExtractFile
    extract_id: int = Column(Integer, ForeignKey('extractfiles.id'))
    extract: ExtractFile = relationship("ExtractFile", back_populates="events")

    def __repr__(self):
        return f"<ExtractEvent: event={self.event} " \
               f"created_at={self.created_at} " \
               f"duration={self.duration}>"


class ItemEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "itemevents"

    id: int = Column(Integer, primary_key=True)
    event: str = Column(String, nullable=False)  # play/pause/stop (mpd state)
    timestamp: float = Column(Float, nullable=False)  # seconds.miliseconds
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow)
    duration: float = Column(Float, default=0)  # seconds.miliseconds

    # Many to one ItemEvent >-| ItemFile
    item_id: int = Column(Integer, ForeignKey('itemfiles.id'))
    item: ItemFile = relationship("ItemFile", back_populates="events")

    def __repr__(self):
        return f"<ItemEvent: event={self.event} " \
               f"created_at={self.created_at} " \
               f"duration={self.duration}>"


Base.metadata.create_all(engine)
session = Session()
