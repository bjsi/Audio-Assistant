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

engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Many to many association table

yt_topicfile_tags = Table('yt_topicfile_tags', Base.metadata,

                          Column('topicfile_id',
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
                          UniqueConstraint('topicfile_id', 'yttag_id'))


# Many to many association table

my_topicfile_tags = Table('my_topicfile_tags', Base.metadata,

                          Column('topicfile_id',
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
                          UniqueConstraint('topicfile_id', 'mytag_id'))


class TopicFile(Base):
    """ In the old version of the project this was called
        all_files """

    __tablename__ = 'topicfiles'

    id = Column(Integer,
                primary_key=True)

    filepath = Column(String,
                      nullable=False,
                      unique=True)
    # Set manually
    # If you just extract info; False
    # If you extract info and download audio; True
    downloaded = Column(Boolean, nullable=False)

    deleted = Column(Boolean,
                     default=False)

    # Retrieved using youtube-dl info_extractor
    title = Column(String)
    duration = Column(Integer)
    uploader_id = Column(String)
    uploader = Column(String)
    upload_date = Column(String)
    thumbnail_url = Column(String) # Maybe switch to a BLOB of the actual file
    view_count = Column(Integer)
    like_count = Column(Integer)
    dislike_count = Column(Integer)
    average_rating = Column(Float)  # 0 to 5 float

    # timestamp in seconds float
    cur_timestamp = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.datetime.now())
    # created using .en.vtt subtitle files from youtube-dl
    transcript = Column(Text)

    # One to many File <-> Extract
    extractfiles = relationship("ExtractFile",
                            back_populates="topicfile")
    # One to many File <-> Activity
    activities = relationship("Activity",
                              back_populates="topicfile")
    # Many to many File <-> Tag
    # Includes 'categories' and 'tags' from ydl
    yttags = relationship('YoutubeTag',
                          secondary=yt_topicfile_tags,
                          back_populates='topicfiles')

    # Many to many File <-> Tag
    # My own added tags (based on the transcript)
    mytags = relationship('MyTag',
                          secondary=my_topicfile_tags,
                          back_populates='topicfiles')

    def __repr__(self):
        return '<File: title=%r filepath=%r>' % (self.title, self.filepath)


class ExtractFile(Base):
    """ In the old version of the project this was called
        extract_files """

    __tablename__ = "extractfiles"

    id = Column(Integer, primary_key=True)
    extract_filepath = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now())
    topicfile_startstamp = Column(Float, nullable=False) # Seconds.miliseconds
    topicfile_endstamp = Column(Float) # Seconds.miliseconds

    # Excerpt from the topicfiles transcript that overlaps
    # with the extract
    extract_transcript = Column(Text, nullable=True)

    deleted = Column(Boolean, default=False)

    # Relationships
    itemfiles = relationship("ItemFile",
                             back_populates="extractfile")


    topicfile_id = Column(Integer, ForeignKey('topicfiles.id'))
    topicfile = relationship("TopicFile",
                             back_populates="extractfiles")

    def __repr__(self):
        return '<TopicFile: filepath=%r created_at=%r>' % (self.filepath, self.created_at)


class ItemFile(Base):
    __tablename__ = "itemfiles"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now())
    question_filepath = Column(String, unique=True)
    cloze_filepath = Column(String, unique=True)
    deleted = Column(Boolean, default=False)
    cloze_startstamp = Column(Float) # seconds.miliseconds
    cloze_endstamp = Column(Float) # seconds.miliseconds
    # Relationships
    extract_id = Column(Integer, ForeignKey('extractfiles.id'))
    extractfile = relationship("ExtractFile",
                                back_populates="itemfiles")

    def __repr__(self):
        return '<ItemFile: question=%r cloze=%r>' % (self.question_filepath, self.cloze_filepath)


class Activity(Base):
    # The mpc_heartbeat script inserts into this table

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    activity = Column(String, nullable=False) # play, pause
    created_at = Column(DateTime, default=datetime.datetime.now())
    duration = Column(Float, default=0)

    # Relationships
    # Allow recording of item / extract activity as
    # well as topics
    topicfile_id = Column(Integer, ForeignKey('topicfiles.id'))
    topicfile = relationship("TopicFile",
                              back_populates="activities")

    def __repr__(self):
        return "<Activity: activity=%r timestamp=%r>" % (self.activity, self.timestamp)


class YoutubeTag(Base):
    __tablename__ = 'yttags'

    # Got it to work by removing the unique constraint on the
    # tag attribute

    id = Column(Integer, primary_key=True)
    tag = Column(String(50), nullable=False)
    topicfiles = relationship('TopicFile',
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
    topicfiles = relationship('TopicFile',
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
