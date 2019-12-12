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
from config import *
from typing import Optional


engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)


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

                          # Intention: Prevent adding same tag to the same file twice
                          # TODO not working... Might not matter, esp if youtube removes
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
                          # Might not matter if I do a term extraction and then remove duplicates
                          # myself...
                          UniqueConstraint('topic_id', 'mytag_id'))


class TopicFile(Base):
    """ Topics are full youtube audio files
    Evevry ExtractFile is a descendant of
    a TopicFile"""

    __tablename__ = 'topicfiles'

    id = Column(Integer, primary_key=True)
    filepath = Column(String, nullable=False, unique=True)
    downloaded = Column(Boolean, nullable=False)
    deleted = Column(Boolean, default=False)
    youtube_id = Column(String)
    title = Column(String)
    duration = Column(Integer)
    uploader_id = Column(String)
    uploader = Column(String)
    upload_date = Column(String)
    thumbnail_url = Column(String)
    view_count = Column(Integer)
    like_count = Column(Integer)
    dislike_count = Column(Integer)
    average_rating = Column(Float)  # 0 to 5 float
    playback_rate = Column(Float, default=1.0)  # eg. 1, 1.25, 1.5
    cur_timestamp = Column(Float, default=0)  # seconds.miliseconds
    created_at = Column(DateTime, default=datetime.datetime.now())
    transcript = Column(Text)

    # One to many File |-< Extract
    extracts = relationship("ExtractFile",
                            back_populates="topic")
    # One to many File |-< Activity
    activities = relationship("Activity",
                              back_populates="topic")
    # Many to many File >-< Tag
    yttags = relationship('YoutubeTag',
                          secondary=yt_topicfile_tags,
                          back_populates='topics')
    # Many to many File >-< Tag
    mytags = relationship('MyTag',
                          secondary=my_topicfile_tags,
                          back_populates='topics')

    @property
    def progress(self) -> float:
        """" Returns percentage listened to """
        return (self.cur_timestamp / self.duration) * 100

    @property
    def url(self) -> str:
        """ Returns the youtube url of the video """
        return "https://youtube.com/watch?v=" + self.youtube_id

    @property
    def channel(self) -> str:
        """ Returns the url of the uploader's youtube channel """
        return "https://youtube.com/channel/" + self.channel_id

    def __repr__(self) -> str:
        return '<TopicFile: title=%r url=%r>' % (self.title, self.url)


class ExtractFile(Base):
    """ Recorded sections from TopicFiles
    ExtractFiles are all descendants of a TopicFile
    ItemFiles are all descendants of an ExtractFile"""

    __tablename__ = "extractfiles"

    id = Column(Integer, primary_key=True)
    filepath = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now())
    startstamp = Column(Float, nullable=False)  # Seconds.miliseconds
    endstamp = Column(Float)  # Seconds.miliseconds
    transcript = Column(Text, nullable=True)
    deleted = Column(Boolean, default=False)

    # One to one ExtractFile (child) |-| TopicFile (parent)
    topic_id = Column(Integer, ForeignKey('topicfiles.id'))
    topic = relationship("TopicFile", back_populates="extracts")

    # One to many ExtractFile |-< ItemFiles
    items = relationship("ItemFile",
                         back_populates="extract")

    @property
    def length(self) -> Optional[float]:
        """ Return the length of the extract or None """
        if self.startstamp and self.endstamp:
            return (self.endstamp - self.startstamp)
        return None

    def __repr__(self) -> str:
        return '<ExtractFile: filepath=%r startstamp=%r endstamp=%r length=%r>' % (self.filepath, self.startstamp, self.endstamp, self.length)


class ItemFile(Base):
    """ ItemFile contains a question file and a cloze file
    Question file has a cloze (beep sound) over a word / phrase
    Cloze file is the unbeeped word / phrase from the extract file
    ItemFiles are are descendants of an ExtractFile
    """

    __tablename__ = "itemfiles"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now())
    question_filepath = Column(String, unique=True)
    cloze_filepath = Column(String, unique=True)
    deleted = Column(Boolean, default=False)
    cloze_startstamp = Column(Float)  # seconds.miliseconds
    cloze_endstamp = Column(Float)  # seconds.miliseconds

    # One to one ItemFile (child) |-| ExtractFile (parent)
    extract_id = Column(Integer, ForeignKey('extractfiles.id'))
    extract = relationship("ExtractFile", back_populates="items")

    @property
    def length(self) -> Optional[float]:
        """ Return the length of the cloze or none"""
        if self.cloze_startstamp and self.cloze_endstamp:
            return (self.cloze_startstamp - self.cloze_endstamp)
        return None

    def __repr__(self) -> str:
        return '<ItemFile: question=%r cloze=%r>' % (self.question_filepath, self.cloze_filepath)


class Activity(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    activity = Column(String, nullable=False)  # play, pause
    created_at = Column(DateTime, default=datetime.datetime.now())
    duration = Column(Float, default=0)

    # Relationships
    # Allow recording of item / extract activity as
    # well as topics
    topic_id = Column(Integer, ForeignKey('topicfiles.id'))
    topic = relationship("TopicFile",
                         back_populates="activities")

    def __repr__(self):
        return "<Activity: activity=%r timestamp=%r>" % (self.activity, self.timestamp)


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
    created_at = Column(DateTime, default=datetime.datetime.now())

    def __repr__(self):
        return "<Log: %s - %s>" % (self.created_at.strftime("%Y-%m-%d %H:%M:%S"), self.msg[:50])


Base.metadata.create_all(engine)
session = Session()
