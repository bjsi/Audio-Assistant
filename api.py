from flask_restplus import Resource, Api
import os
from flask import Blueprint, request, Flask, render_template, url_for
from flask_restplus import fields
from flask_sqlalchemy import SQLAlchemy
from config import DATABASE_URI
from flask_restplus import reqparse
from flask_cors import CORS


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
db = SQLAlchemy(app)
db.metadata.reflect(db.engine)
CORS(app)

# API object
api = Api(app,
          title="Audio Assistant",
          version="0.1",
          description="API documentation for Audio Assistant")

# API Namespaces
assistant_ns = api.namespace('assistant',
                             description="Operations for controlling "
                                         "Audio Assistant via the API")
topic_ns = api.namespace('topics',
                         description="Operations for retrieving Topic-related "
                                     "information from the database")
extract_ns = api.namespace('extracts',
                           description="Operations for retrieving "
                                       "Extract-related "
                                       "information from the database")
item_ns = api.namespace('items',
                        description="Operations for retrieving Item-related "
                                    "information from the database")
event_ns = api.namespace('events',
                         description="Operations for retrieving Topic, Extract and "
                                     "Item events")


##########################
# Pagination Mixin Class #
##########################

class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = query.paginate(page, per_page, False)
        data = {
                "data": [
                         item.to_dict()
                         for item in resources.items
                        ],
                "_meta": {
                          "page": page,
                          "per_page": per_page,
                          "total_pages": resources.pages,
                          "total_items": resources.total
                         },
                "_links": {
                           "self": url_for(endpoint, page=page,
                                           per_page=per_page,
                                           **kwargs),
                           "next": url_for(endpoint, page=page + 1,
                                           per_page=per_page,
                                           **kwargs) if resources.has_next else None,
                           "prev": url_for(endpoint, page=page - 1,
                                           per_page=per_page,
                                           **kwargs) if resources.has_prev else None
                          }
               }
        return data


##########################
# Tag Association Tables #
##########################

yt_topicfile_tags = db.Table('yt_topicfile_tags', db.metadata)
my_topicfile_tags = db.Table('my_topicfile_tags', db.metadata)


####################################
# TopicFile DB table and API Model #
####################################

class TopicFile(PaginatedAPIMixin, db.Model):

    """ Contains TopicFile attributes and relationships
    Allows you to use the sqlalchemy models in
    flask-sqlalchemy
    """

    __table__ = db.Model.metadata.tables['topicfiles']

    extracts = db.relationship("ExtractFile", back_populates="topic")
    events = db.relationship("TopicEvent", back_populates="topic")
    yttags = db.relationship('YoutubeTag',
                             secondary=yt_topicfile_tags,
                             back_populates='topics')
    mytags = db.relationship('MyTag',
                             secondary=my_topicfile_tags,
                             back_populates='topics')

    def to_dict(self):
        data = {
                'id':             self.id,
                'filepath':       self.filepath,
                'downloaded':     self.downloaded,
                'archived':       self.archived,
                'deleted':        self.deleted,
                'youtube_id':     self.youtube_id,
                'title':          self.title,
                'duration':       self.duration,
                'uploader':       self.uploader,
                'upload_date':    self.upload_date,
                'thumbnail_url':  self.thumbnail_url,
                'view_count':     self.view_count,
                'like_count':     self.like_count,
                'dislike_count':  self.dislike_count,
                'average_rating': self.average_rating,
                'playback_rate':  self.playback_rate,
                'cur_timestamp':  self.cur_timestamp,
                'created_at':     self.created_at,
                'transcript':     self.transcript,
                'rendered':       render_template("topic.html", topic=self),
                'yttags': [
                            tag.tag
                            for tag in self.yttags
                          ],
                'mytags': [
                            tag.tag
                            for tag in self.mytags
                          ],
                '_links': {
                        'self': url_for('topics_topic', id=self.id),
                        'extracts': url_for('topics_topic_extracts', id=self.id),
                        'events': url_for('topics_topic_events', id=self.id),
                }
               }
        return data


topic_links = api.model('Topic File Links', {
        'self':     fields.String,
        'extracts': fields.String,
        'events':   fields.String,
    })

topic_model = api.model('Topic File', {
    'id':               fields.Integer,
    'filepath':         fields.String,
    'downloaded':       fields.Boolean,
    'archived':         fields.Boolean,
    'deleted':          fields.Boolean,
    'youtube_id':       fields.String,
    'title':            fields.String,
    'duration':         fields.Integer,
    'uploader_id':      fields.String,
    'uploader':         fields.String,
    'upload_date':      fields.String,
    'thumbnail_url':    fields.String,
    'view_count':       fields.Integer,
    'like_count':       fields.Integer,
    'dislike_count':    fields.Integer,
    'average_rating':   fields.Float,
    'playback_rate':    fields.Float,
    'cur_timestamp':    fields.Float,
    'created_at':       fields.DateTime,
    'transcript':       fields.String,
    'rendered':         fields.String,
    'yttags':           fields.List(fields.String),
    'mytags':           fields.List(fields.String),
    '_links':           fields.Nested(topic_links)
    })

paginated_topics_meta = api.model("Paginated Topics Meta", {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_topics_links = api.model("Paginated Topics Links", {
   "self":      fields.String,
   "next":      fields.String,
   "prev":      fields.String,
    })

paginated_topics_model = api.model('Paginated Topic Files', {
    "data":     fields.List(fields.Nested(topic_model)),
    "_meta":    fields.Nested(paginated_topics_meta),
    "_links":   fields.Nested(paginated_topics_links)
    })


######################################
# ExtractFile DB table and API Model #
######################################

class ExtractFile(PaginatedAPIMixin, db.Model):

    """ Contains ExtractFile attributes and relationships
    Allows you to use the sqlalchemy models in
    flask-sqlalchemy
    """

    __table__ = db.Model.metadata.tables['extractfiles']

    topic = db.relationship("TopicFile", back_populates="extracts")
    items = db.relationship("ItemFile", back_populates="extract")
    events = db.relationship("ExtractEvent", back_populates="extract")

    def to_dict(self):
        data = {
                "id":         self.id,
                "filepath":   self.filepath,
                "created_at": self.created_at,
                "startstamp": self.startstamp,
                "endstamp":   self.endstamp,
                "transcript": self.transcript,
                'archived':   self.archived,
                "deleted":    self.deleted,
                "rendered":   render_template("extract.html", extract=self),
                '_links': {
                    'self': url_for('extracts_extract', id=self.id),
                    'topic': url_for('extracts_extract_topic', id=self.id),
                    'items': url_for('extracts_extract_items', id=self.id),
                    'events': url_for('extracts_extract_events', id=self.id)
                    }
               }
        return data


extract_links = api.model('Extract Links', {
    'self': fields.String,
    'topic': fields.String,
    'items': fields.String,
    'events': fields.String
    })

extract_model = api.model('Extract File', {
    'id':               fields.Integer,
    'filepath':         fields.String,
    'created_at':       fields.DateTime,
    'startstamp':       fields.Float,
    'endstamp':         fields.Float,
    'transcript':       fields.String,
    'archived':         fields.Boolean,
    'deleted':          fields.Boolean,
    'rendered':         fields.String,
    '_links': fields.Nested(extract_links)
    })

paginated_extracts_meta = api.model('Paginated Extracts Meta', {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_extracts_links = api.model('Paginated Extracts Links', {
   "self":      fields.String,
   "next":      fields.String,
   "prev":      fields.String,
    })

paginated_extracts_model = api.model('Paginated Extract Files', {
    "data":     fields.List(fields.Nested(extract_model)),
    "_meta":    fields.Nested(paginated_extracts_meta),
    "_links":   fields.Nested(paginated_extracts_links)
    })


###############################
# ItemFile DB Model and Table #
###############################

class ItemFile(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['itemfiles']

    extract = db.relationship("ExtractFile", back_populates="items")
    events = db.relationship("ItemEvent", back_populates="item")

    def to_dict(self):
        data = {
                'id':                self.id,
                'created_at':        self.created_at,
                'question_filepath': self.question_filepath,
                'cloze_filepath':    self.cloze_filepath,
                'archived':          self.archived,
                'deleted':           self.deleted,
                'cloze_startstamp':  self.cloze_startstamp,
                'cloze_endstamp':    self.cloze_endstamp,
                'rendered':          render_template('item.html', item=self),
                '_links': {
                    'self': url_for('items_item', id=self.id),
                    'extract': url_for('items_item_extract', id=self.id),
                    'events': url_for('items_item_events', id=self.id)
                    }
               }
        return data


item_links = api.model('Item Links', {
    'self': fields.String,
    'extract': fields.String,
    'events': fields.String,
    })

item_model = api.model('Item File', {
    'id':                   fields.Integer,
    'created_at':           fields.DateTime,
    'question_filepath':    fields.String,
    'cloze_filepath':       fields.String,
    'archived':             fields.Boolean,
    'deleted':              fields.Boolean,
    'cloze_startstamp':     fields.Float,
    'cloze_endstamp':       fields.Float,
    'rendered':             fields.String,
    '_links': fields.Nested(item_links)
    })

paginated_items_meta = api.model("Paginated Items Meta", {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_items_links = api.model('Paginated Items Links', {
   "self":      fields.String,
   "next":      fields.String,
   "prev":      fields.String,
    })

paginated_items_model = api.model('Paginated Item Files', {
    "data":       fields.List(fields.Nested(item_model)),
    "_meta":    fields.Nested(paginated_items_meta),
    "_links":   fields.Nested(paginated_items_links)
    })


#######################################
# Topic Event DB tables and API Model #
#######################################

class TopicEvent(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['topicevents']
    topic = db.relationship("TopicFile", back_populates="events")

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'event':        self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    'self': url_for('events_event', id=self.id),
                    'topic': url_for('events_event_topic', id=self.id)
                    }
               }
        return data


topic_event_links = api.model('Topic Links', {
    'self':     fields.String,
    'topic':    fields.String
    })

topic_event_model = api.model('Topic Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': fields.Nested(topic_event_links)
    })

paginated_topic_events_meta = api.model('Paginated Topic Events Meta', {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_topic_events_links = api.model('Paginated Topic Events Links', {
   "self":   fields.String,
   "next":   fields.String,
   "prev":   fields.String,
    })

paginated_topic_events_model = api.model('Paginated Topic Events', {
    "data":     fields.List(fields.Nested(topic_event_model)),
    "_meta":    fields.Nested(paginated_topic_events_meta),
    "_links":   fields.Nested(paginated_topic_events_links)
    })


#########################################
# Extract Event DB tables and API Model #
#########################################

class ExtractEvent(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['extractevents']
    extract = db.relationship("ExtractFile", back_populates="events")

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'event':        self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    'self': url_for('events_event', id=self.id),
                    'extract': url_for('events_event_extract', id=self.id)
                    }
               }
        return data


extract_event_links = api.model('Extract Event Links', {
    'self':     fields.String,
    'extract':  fields.String
    })

extract_event_model = api.model('Extract Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': fields.Nested(extract_event_links)
    })

paginated_extract_events_meta = api.model('Paginated Extract Events Meta', {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_extract_events_links = api.model('Paginated Extract Events Links', {
   "self":   fields.String,
   "next":   fields.String,
   "prev":   fields.String,
    })

paginated_extract_events_model = api.model('Paginated Extract Events', {
    "data":     fields.List(fields.Nested(extract_event_model)),
    "_meta":    fields.Nested(paginated_extract_events_meta),
    "_links":   fields.Nested(paginated_extract_events_links)
    })


######################################
# Item Event DB tables and API Model #
######################################

class ItemEvent(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['itemevents']
    item = db.relationship("ItemFile", back_populates="events")

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'self':         self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    'self': url_for('events_event', id=self.id),
                    'item': url_for('events_event_item', id=self.id),
                }
               }
        return data


item_event_links = api.model('Item Event Links', {
    'self':     fields.String,
    'item':     fields.String
    })

item_event_model = api.model('Item Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': fields.Nested(item_event_links)
    })

paginated_item_events_meta = api.model('Paginated Item Events Meta', {
    "page":         fields.Integer,
    "per_page":     fields.Integer,
    "total_pages":  fields.Integer,
    "total_items":  fields.Integer
    })

paginated_item_events_links = api.model('Paginated Item Events Links', {
   "self":   fields.String,
   "next":   fields.String,
   "prev":   fields.String,
    })

paginated_item_events_model = api.model('Paginated Item Events', {
    "data":     fields.List(fields.Nested(item_event_model)),
    "_meta":    fields.Nested(paginated_item_events_meta),
    "_links":   fields.Nested(paginated_item_events_links)
    })


class YoutubeTag(db.Model):
    __table__ = db.Model.metadata.tables['yttags']
    topics = db.relationship('TopicFile',
                             secondary=yt_topicfile_tags,
                             back_populates='yttags')


class MyTag(db.Model):
    __table__ = db.Model.metadata.tables['mytags']
    topics = db.relationship('TopicFile',
                             secondary=my_topicfile_tags,
                             back_populates='mytags')



# add a datetime / timestamp filter to these
# Add a way to filter by tags both AND and OR
# TODO Get items by tag
# TODO Get items by transcript?
# Filter extracts and items by deleted and whether they have a cloze_endstamp /
# topicfile endstamp or not
# Add a way to get logs
# Add a way to start downloads from the API
# Add a way to record Events from the API
# Add logging
# Learn how to write proper APIs
# Add archived, deleted, datetime filters to the query string


##########
# Topics #
##########

@topic_ns.route('/')
class Topics(Resource):
    @api.marshal_with(paginated_topics_model)
    @api.response(200, 'Successfully read topics')
    # @api.expect(parser)
    def get(self):
        """ Get all Topics
        Allows the user to read a list of all topic files
        in the database that have not been deleted """

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = TopicFile.to_collection_dict(db.session.query(TopicFile),
                                            page, per_page,
                                            'topics_topics')
        return data


@topic_ns.route('/<int:id>/extracts')
class TopicExtracts(Resource):
    @api.marshal_with(paginated_extracts_model)
    @api.response(200, "Successfully read topic's extracts")
    def get(self, id):
        """ Get a topic's extracts
        Allows the user to read a list of child
        extracts from the parent topic"""

        topic = db.session.query(TopicFile).get_or_404(id)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        query = db.session.query(ExtractFile).filter_by(topic_id=topic.id)
        data = TopicFile.to_collection_dict(query, page, per_page,
                                            'topics_topic_extracts', id=id)
        return data


@topic_ns.route('/<int:id>')
class Topic(Resource):
    @api.marshal_with(topic_model)
    @api.response(200, "Successfully read topic")
    def get(self, id):
        """ Get a single topic
        Allows the user to get a single topic according
        to the topic id"""

        topic = db.session.query(TopicFile).get_or_404(id)
        return topic.to_dict()


@topic_ns.route('/<int:id>/events')
class TopicEvents(Resource):
    @api.marshal_with(paginated_topic_events_model)
    @api.response(200, "Successfully read topic's events")
    def get(self, id):
        """ Get a topic's events
        Allows the user to get a topic's events according
        to the topic id"""

        topic = db.session.query(TopicFile).get_or_404(id)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        query = db.session.query(TopicEvent).filter_by(topic_id=topic.id)
        data = TopicEvent.to_collection_dict(query, page, per_page,
                                             'topics_topic_events', id=id)
        return data

# @topic_ns.route('/yttags/')
# class TopicTags(Resource):
#     @api.marshal_with(topic_model, as_list=True)
#     @api.response(200, "Successfully filtered topics by tags")
#     # TODO add an expect decorator
#     def post(self):
#         pass


##########
# Events #
##########

@event_ns.route('/topics')
class TopicsEvents(Resource):
    @api.marshal_with(paginated_topic_events_model)
    @api.response(200, 'Successfully read topic events')
    def get(self):
        """ Get all topic events
        Allows the user to read a list of all events """
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = TopicEvent.to_collection_dict(db.session.query(TopicEvent),
                                             page, per_page,
                                             'events_topics_events')
        return data


@event_ns.route('/extracts')
class ExtractsEvents(Resource):
    @api.marshal_with(paginated_extract_events_model)
    @api.response(200, 'Successfully read extract events')
    def get(self):
        """ Get all extract events
        Allows the user to read a list of all extract events """

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = ExtractEvent.to_collection_dict(db.session.query(ExtractEvent),
                                               page, per_page,
                                               'events_extracts_events')
        return data


@event_ns.route('/items')
class ItemsEvents(Resource):
    @api.marshal_with(paginated_item_events_model)
    @api.response(200, 'Successfully read item events')
    def get(self):
        """ Get all item events
        Allows the user to read a list of all item events """

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = ItemEvent.to_collection_dict(db.session.query(ItemEvent),
                                            page, per_page,
                                            'events_items_events')
        return data


############
# Extracts #
############

@extract_ns.route('/')
class Extracts(Resource):
    @api.marshal_with(paginated_extracts_model)
    @api.response(200, 'Successfully read extracts')
    def get(self):
        """ Get outstanding extracts
        Allows the user to read a list of all outstanding extract
        files in the database that have not been archived or deleted"""
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = ExtractFile.to_collection_dict(db.session.query(ExtractFile).filter(ExtractFile.filepath != None).filter(ExtractFile.endstamp != None),
                                              page, per_page,
                                              'extracts_extracts')
        return data


@extract_ns.route('/<int:id>')
class Extract(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read a single extract")
    def get(self, id):
        """ Get a single extract
        Allows the user to read a single extract according to
        the extract id"""
        extract = db.session.query(ExtractFile).get_or_404(id)
        return extract.to_dict()


@extract_ns.route('/<int:id>/topic')
class ExtractTopic(Resource):
    @api.marshal_with(topic_model)
    @api.response(200, "Successfully read parent topic of extract")
    def get(self, id):
        """ Get extract topic
        Allows the user to read the parent topic of an extract
        according to the extract id"""
        extract = db.session.query(ExtractFile).get_or_404(id)
        return extract.topic.to_dict()


@extract_ns.route('/<int:id>/items')
class ExtractItems(Resource):
    @api.marshal_with(paginated_items_model)
    @api.response(200, "Successfully read child items of extract")
    def get(self, id):
        """ Get extract items
        Allows the user to read the parent topic of an extract
        according to the extract id"""
        extract = db.session.query(ExtractFile).get_or_404(id)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        query = db.session.query(ItemFile).filter_by(extract_id=extract.id)
        data = ItemFile.to_collection_dict(query,
                                           page, per_page,
                                           'extracts_extracts')
        return data
        return extract.topic.to_dict()


@extract_ns.route('/<int:id>/events')
class ExtractEvents(Resource):
    @api.marshal_with(paginated_extract_events_model)
    @api.response(200, "Successfully read extract's events")
    def get(self, id):
        """ Get extract's events
        Allows the user to read the events of the extract """
        extract = db.session.query(ExtractFile).get_or_404(id)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        query = db.session.query(ExtractEvent).filter_by(extract_id=extract.id)
        data = ExtractEvent.to_collection_dict(query,
                                               page, per_page,
                                               'extracts_extract_events',
                                               id=id)
        return data


#########
# Items #
#########

@item_ns.route('/')
class Items(Resource):
    @api.marshal_with(paginated_items_model)
    @api.response(200, "Successfully read the parent of extract")
    def get(self):
        """ Get outstanding items
        Allows the user to get a list of outstanding
        items that haven't been deleted or archived"""

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        data = ItemFile.to_collection_dict(db.session.query(ItemFile),
                                           page, per_page,
                                           'items_items')
        return data


@item_ns.route('/<int:id>')
class Item(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read the parent extract of item")
    def get(self, id):
        """ Get item extract
        Allows the user to get the parent extract of the item
        according to the item id"""

        item = db.session.query(ItemFile).get_or_404(id)
        return item.to_dict()


@item_ns.route('/<int:id>/extract')
class ItemExtract(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read the parent extract of item")
    def get(self, id):
        """ Get item extract
        Allows the user to get the parent extract of the item
        according to the item id"""

        item = db.session.query(ItemFile).get_or_404(id)
        return item.extract.to_dict()


@item_ns.route('/<int:id>/events')
class ItemEvents(Resource):
    @api.marshal_with(paginated_item_events_model)
    @api.response(200, "Successfully read the events of item")
    def get(self, id):
        """ Get item's events
        Allows the user to get the events of the item
        according to the item id"""

        item = db.session.query(ItemFile).get_or_404(id)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        query = db.session.query(ItemEvent).filter_by(item_id=item.id)
        data = ItemEvent.to_collection_dict(query,
                                            page, per_page,
                                            'items_item_events',
                                            id=id)
        return data


if __name__ == "__main__":
    app.run(debug=True)
