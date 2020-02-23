from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer,
                        String, DateTime,
                        Table, Text,
                        ForeignKey, Boolean,
                        Float, UniqueConstraint)
import datetime
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URI, QUESTIONFILES_DIR
from typing import Optional, List
import os
import logging
import subprocess
from subprocess import DEVNULL

engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)


# TODO: Remove Tag tables?
# TODO Change all datetimes to datetime.datetime.utcnow()


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


# Many to many association table for youtube tags
yt_topicfile_tags = Table('yt_topicfile_tags', Base.metadata,
                          Column('topic_id',
                                 Integer,
                                 ForeignKey('topicfiles.id'),
                                 primary_key=True,
                                 nullable=False),
                          Column('yttag_id',
                                 Integer,
                                 ForeignKey('yttags.id'),
                                 primary_key=True,
                                 nullable=False),
                          # Intention: Prevent adding same tag
                          # to the same file twice
                          # TODO not working... Might not matter,
                          # esp if youtube removes
                          # duplicates automatically
                          UniqueConstraint('topic_id', 'yttag_id'))


# Many to many association table for my own tags
my_topicfile_tags = Table('my_topicfile_tags', Base.metadata,
                          Column('topic_id',
                                 Integer,
                                 ForeignKey('topicfiles.id'),
                                 primary_key=True,
                                 nullable=False),
                          Column('mytag_id',
                                 Integer,
                                 ForeignKey('mytags.id'),
                                 primary_key=True,
                                 nullable=False),
                          # TODO See above
                          # Might not matter if I do a term extraction and
                          # then remove duplicates
                          # myself...
                          UniqueConstraint('topic_id', 'mytag_id'))


##############################
# Topics, Extracts and Items #
##############################

def check_progress(context):
    """ Runs on the archived Column each time the Topic table is updated
    If progress > 90% set archived to True """
    cur_timestamp = context.get_current_parameters()['cur_timestamp']
    duration = context.get_current_parameters()['duration']
    if (cur_timestamp / duration > 0.9):
        return True
    else:
        return False


class TopicFile(Base):
    """ Topics are full youtube audio files
    Evevry ExtractFile is a descendant of
    a TopicFile"""

    __tablename__ = 'topicfiles'

    id: int = Column(Integer, primary_key=True)
    filepath: str = Column(String, nullable=False, unique=True)
    downloaded: bool = Column(Boolean, nullable=False)
    # Can be set by the user at runtime
    # Can be set automatically if completion > 90%
    archived: bool = Column(Boolean, default=False, onupdate=check_progress)
    # If no outstanding extracts and archived is True,
    # Topic will be deleted by a script and deleted will be set to 1
    deleted: bool = Column(Boolean, default=False)
    youtube_id: str = Column(String)
    title: str = Column(String)
    duration: int = Column(Integer)
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
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow())
    transcript: str = Column(Text)

    # One to many File |-< Extract
    # TODO: Can this be typed as List[ExtractFile]?
    extracts = relationship("ExtractFile",
                            back_populates="topic")

    # TODO: Can this be typed as List[TopicEvent]?
    # One to many File |-< Activity
    events = relationship("TopicEvent",
                          back_populates="topic")

    # Many to many File >-< Tag
    yttags = relationship('YoutubeTag',
                          secondary=yt_topicfile_tags,
                          back_populates='topics')

    # Many to many File >-< Tag
    mytags = relationship('MyTag',
                          secondary=my_topicfile_tags,
                          back_populates='topics')

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished TopicFiles.
        """
        topics: List[TopicFile] = (session
                                   .query(TopicFile)
                                   .filter_by(deleted=False)
                                   .all())
        count = 0
        if topics:
            for topic in topics:
                if topic.is_finished():
                    if topic.delete_file():
                        topic.deleted = True
                        count += 1
                        session.commit()
        if count > 0:
            logger.info(f"Deleted {count} finished TopicFiles.")
        
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
                    if all(extract.archived for extract in extracts):
                        return True
                    else:
                        return False
                return True
        return False

    def delete_file(self) -> bool:
        """
        :returns: True if the file was deleted else False.
        """
        # Check file exists
        if os.path.isfile(self.filepath):
            try:
                os.remove(self.filepath)
                return True
            except OSError as e:
                logger.error(f"Exception {e} when attempting to "
                             f"delete {self.filepath}")
                return False
        logger.error(f"Attempted to delete file {self.filepath} "
                     "but it does not exist.")
        return False

    def add_event(self, event: str, timestamp: float, duration: float):
        """ Add an event to the current TopicFile """
        # TODO data validation of parameters
        event = TopicEvent(event=event,
                           timestamp=timestamp,
                           duration=duration)
        self.append(event)
        session.commit()

    # TODO Should this be a property?

    def progress(self) -> float:
        """" Returns percentage listened to """
        return (self.cur_timestamp / self.duration) * 100

    def __repr__(self) -> str:
        return '<TopicFile: title=%r youtube_id=%r>' % \
                (self.title, self.youtube_id)


class ExtractFile(Base):
    """ Recorded sections from TopicFiles
    ExtractFiles are all descendants of a TopicFile
    ItemFiles are all descendants of an ExtractFile"""

    __tablename__ = "extractfiles"

    id: int = Column(Integer, primary_key=True)
    filepath: str = Column(String, nullable=False, unique=True)
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow())
    startstamp: float = Column(Float, nullable=False)  # Seconds.miliseconds
    endstamp: float = Column(Float)  # Seconds.miliseconds
    transcript: str = Column(Text, nullable=True)
    # Set by the user
    archived: bool = Column(Boolean, default=False)
    # Archived extracts are deleted if they have no outstanding child items
    # Archived extracts with child items are deleted after export
    deleted: bool = Column(Boolean, default=False)

    # One to one ExtractFile (child) |-| TopicFile (parent)
    topic_id: int = Column(Integer, ForeignKey('topicfiles.id'))
    # TODO: Can this be typed as TopicFile
    topic = relationship("TopicFile", back_populates="extracts")

    # TODO: Can this be typed as List[ItemFile]
    # One to many ExtractFile |-< ItemFiles
    items = relationship("ItemFile",
                         back_populates="extract")

    # One to many ExtractFile |-< ExtractEvent
    events = relationship("ExtractEvent",
                          back_populates="extract")

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished ExtractFiles.
        """
        extracts: List[ExtractFile] = (session
                                       .query(ExtractFile)
                                       .filter_by(deleted=False)
                                       .filter_by(archived=True)
                                       .all())
        count = 0
        if extracts:
            for extract in extracts:
                if extract.is_finished():
                    if extract.delete_file():
                        extract.deleted = True
                        count += 1
                        session.commit()
        if count > 0:
            logger.info(f"Deleted {count} finished TopicFiles.")
        
    def is_finished(self) -> bool:
        """A finished ExtractFile fulfils the following criteria.
        
        1. Extract.archived is True.

        2. No outstanding child items.

        :returns: True if the file is finished else False.
        """
        if self.archived:
            items = self.items
            if items:
                if all(item.archived for item in items):
                    return True
                else:
                    return False
            return True
        return False

    def delete_file(self) -> bool:
        """Delete ExtractFile.filepath.
        :returns: True if the file was deleted else False.
        """
        # Check file exists
        if os.path.isfile(self.filepath):
            try:
                os.remove(self.filepath)
                return True
            except OSError as e:
                logger.error(f"Exception {e} when attempting "
                             f"to delete {self.filepath}.")
                return False
        logger.error(f"Attempted to delete file {self.filepath} "
                     "but it does not exist.")
        return False

    def add_event(self, event: str, timestamp: float, duration: float):
        """ Add an event to the current TopicFile """
        # TODO data validation of parameters
        event = ExtractEvent(event=event,
                             timestamp=timestamp,
                             duration=duration)
        self.append(event)
        session.commit()
    
    # TODO Should this be a property
    @property
    def length(self) -> Optional[float]:
        """ Return the length of the extract or None """
        if self.startstamp and self.endstamp:
            return (self.endstamp - self.startstamp)
        return None

    def __repr__(self) -> str:
        return '<ExtractFile: filepath=%r startstamp=%r endstamp=%r length=%r>' % \
                (self.filepath, self.startstamp, self.endstamp, self.length)


class ItemFile(Base):
    """ ItemFile contains a question file and a cloze file
    Question file has a cloze (beep sound) over a word / phrase
    Cloze file is the unbeeped word / phrase from the extract file
    ItemFiles are are descendants of an ExtractFile
    """

    __tablename__ = "itemfiles"

    id: int = Column(Integer, primary_key=True)
    created_at: DateTime = Column(DateTime, default=datetime.datetime.utcnow())
    question_filepath: str = Column(String, unique=True)
    cloze_filepath: str = Column(String, unique=True)
    # Set by the user
    archived: bool = Column(Boolean, default=False)
    # Archived files deleted by script
    # Non-archived items archived and deleted after export
    deleted: bool = Column(Boolean, default=False)
    cloze_startstamp: float = Column(Float)  # seconds.miliseconds
    cloze_endstamp: float = Column(Float)  # seconds.miliseconds

    # One to one ItemFile (child) |-| ExtractFile (parent)
    extract_id: int = Column(Integer, ForeignKey('extractfiles.id'))
    # TODO: can this be typed as ExtractFile
    extract = relationship("ExtractFile", back_populates="items")

    # One to many ItemFile |-< ItemEvent
    # TODO: can this be typed as ItemEvent
    events = relationship("ItemEvent",
                          back_populates="item")

    @classmethod
    def remove_finished_files(cls) -> None:
        """Remove finished ItemFiles.
        """
        items: List[ItemFile] = (session
                                 .query(ItemFile)
                                 .filter_by(deleted=False)
                                 .filter_by(archived=True)
                                 .all())
        count = 0
        if items:
            for item in items:
                if item.is_finished():
                    if item.delete_file():
                        item.deleted = True
                        count += 1
                        session.commit()
            logger.info(f"Deleted {count} finished TopicFiles.")
        
    def is_finished(self) -> bool:
        """A finished ItemFile fulfils the following criteria.
        
        1. ItemFile.archived is True.

        :returns: True if the file is finished else False.
        """
        return self.archived

    def delete_file(self) -> bool:
        """Delete ItemFile.filepath.
        :returns: True if the file was deleted else False.
        """
        # Check file exists
        if os.path.isfile(self.filepath):
            try:
                os.remove(self.filepath)
                return True
            except OSError as e:
                logger.error(f"Exception {e} when attempting "
                             f"to delete {self.filepath}.")
                return False
        logger.error(f"Attempted to delete file {self.filepath} "
                     "but it does not exist.")
        return False

    def process_cloze(self) -> bool:
        """Creates a question and cloze from an ItemFile.
        """
        extract_fp = self.extract.filepath
        extract_length = self.extract.endstamp - self.extract.startstamp
        cloze_length = self.cloze_endstamp - self.cloze_starstamp
        cloze_start = self.cloze_startstamp
        cloze_end = self.cloze_endstamp
        basename = os.path.basename(self.extract.filepath)
        filename, ext = os.path.splitext(basename)

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
                    '[0:a]atrim=' + str(cloze_start) + ":" + str(cloze_end) + "[cloze]" + ";" + \
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
            return True
        except OSError as e:
            logger.error(f"Call to ffmpeg subprocess "
                         f"failed with exception {e}.")
            return False

    def add_event(self, event: str, timestamp: float, duration: float):
        """ Add an event to the current TopicFile """
        # TODO data validation of parameters
        event = ItemEvent(event=event,
                          timestamp=timestamp,
                          duration=duration)
        self.append(event)
        session.commit()

    # TODO Should this be a property
    @property
    def length(self) -> Optional[float]:
        """ Return the length of the cloze or none"""
        if self.cloze_startstamp and self.cloze_endstamp:
            return (self.cloze_startstamp - self.cloze_endstamp)
        return None

    def __repr__(self) -> str:
        return '<ItemFile: question=%r cloze=%r>' % \
                (self.question_filepath, self.cloze_filepath)

###################
# Activity Tables #
###################


class TopicEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "topicevents"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow())
    event = Column(String, nullable=False)  # play/pause/stop (mpd status)
    timestamp = Column(Float, nullable=False)  # seconds.miliseconds
    duration = Column(Float, default=0)  # seconds.miliseconds

    # Many to One TopicEvent >-| TopicFile
    topic_id = Column(Integer, ForeignKey('topicfiles.id'))
    topic = relationship("TopicFile",
                         back_populates="events")

    def __repr__(self):
        return "<TopicEvent: event=%r created_at=%r duration=%r>" % \
                (self.event, self.timestamp, self.duration)


class ExtractEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "extractevents"

    id = Column(Integer, primary_key=True)
    event = Column(String, nullable=False)  # play, pause
    timestamp = Column(Float, nullable=False)  # seconds.miliseconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow())
    duration = Column(Float, default=0)  # seconds.miliseconds

    # Many to one ExtractEvent >-| ExtractFile
    extract_id = Column(Integer, ForeignKey('extractfiles.id'))
    extract = relationship("ExtractFile",
                           back_populates="events")

    def __repr__(self):
        return "<ExtractEvent: event=%r created_at=%r duration=%r>" % \
                (self.event, self.timestamp, self.duration)


class ItemEvent(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "itemevents"

    id = Column(Integer, primary_key=True)
    event = Column(String, nullable=False)  # play/pause/stop (mpd state)
    timestamp = Column(Float, nullable=False)  # seconds.miliseconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow())
    duration = Column(Float, default=0)  # seconds.miliseconds

    # Many to one ItemEvent >-| ItemFile
    item_id = Column(Integer, ForeignKey('itemfiles.id'))
    item = relationship("ItemFile",
                        back_populates="events")

    def __repr__(self):
        return "<ItemEvent: event=%r created_at=%r duration=%r>" % \
                (self.event, self.timestamp, self.duration)

###########
# Tagging #
###########


class YoutubeTag(Base):
    __tablename__ = 'yttags'

    # Got it to work by removing the unique constraint on the
    # tag attribute

    id = Column(Integer, primary_key=True)
    tag = Column(String(50), nullable=False)
    topics = relationship('TopicFile',
                          secondary=yt_topicfile_tags,
                          back_populates='yttags')

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return '<YoutubeTag: tag=%r>' % (self.tag)


class MyTag(Base):
    __tablename__ = 'mytags'

    id = Column(Integer, primary_key=True)
    tag = Column(String(50), nullable=False)
    topics = relationship('TopicFile',
                          secondary=my_topicfile_tags,
                          back_populates='mytags')

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return '<MyTag: tag=%r>' % (self.tag)


###########
# Logging #
###########


class Log(Base):
    # Remove this?
    # How much does logging impact performance
    # Would logging to a text file work better?

    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    logger = Column(String)
    level = Column(String)
    trace = Column(String)
    msg = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow())

    def __repr__(self):
        return "<Log: %s - %s>" % (self.created_at.strftime("%Y-%m-%d %H:%M:%S"), self.msg[:50])


Base.metadata.create_all(engine)
session = Session()
