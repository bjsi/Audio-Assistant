from flask_restplus import Resource, Api
import os
from flask import Blueprint, request, Flask, render_template, url_for
from flask_restplus import fields
from flask_sqlalchemy import SQLAlchemy  # flask-sqlalchemy has easy pagination
from config import DATABASE_URI
from flask_restplus import reqparse
from flask_cors import CORS

# blueprint = Blueprint('api', __name__)

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
                                            **kwargs) if resources.has_next else None
                          }
               }
        return data


####################################
# TopicFile DB table and API Model #
####################################

class TopicFile(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['topicfiles']

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
                # TODO Change to url_for
                '_links': {
                        'self': 'http://audiopi:5000/topics/' + \
                                str(self.id),
                        'extracts': 'http://audiopi:5000/topics/' + \
                                    str(self.id) + '/extracts',
                        'events': 'http://audiopi:5000/topics/' + \
                                  str(self.id) + '/events',
                        'topic': 'http://audiopi:5000/topics/' + \
                                 str(self.topic_id)
                        'yttags': 'http://audiopi:5000/topics/' + \
                                  str(self.id) + '/yttags',
                        'mytags': 'http://audiopi:5000/topics/' + \
                                  str(self.id) + '/mytags',
                        'youtube_url': 'http://www.youtube.com/watch?v=' + \
                                       self.youtube_id,
                        'channel_url': 'httmp://www.youtube.com/channel/' + \
                                       self.uploader_id
                }
               }
        return data


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
    '_links': {
        'self':     fields.String,
        'extracts': fields.String,
        'events':   fields.String
        }
    })

paginated_topics_model = api.model('Paginated Topic Files', {
    "data":       fields.List(fields.Nested(topic_model)),
    "_meta": {
              "page":         fields.Integer,
              "per_page":     fields.Integer,
              "total_pages":  fields.Integer,
              "total_items":  fields.Integer
             },
    "_links": {
               "self":      fields.String,
               "next":      fields.String,
               "prev":      fields.String,
              }
    })


######################################
# ExtractFile DB table and API Model #
######################################

class ExtractFile(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['extractfiles']

    def to_dict(self):
        data = {
                "id":           self.id,
                "filepath":     self.filepath,
                "created_at":   self.created_at,
                "startstamp":   self.startstamp,
                "endstamp":     self.endstamp,
                "transcript":   self.transcript,
                'archived':     self.archived,
                "deleted":      self.deleted,
                'links': {
                    # TODO change to url_for
                    'self': 'http://audiopi:5000/extracts/' +
                            str(self.id),
                    'topic': 'http://audiopi:5000/topics/' +
                             str(self.topic_id),
                    'items': 'http://audiopi:5000/extracts/' +
                             str(self.id) + '/items',
                    'events': 'http://audiopi:5000/extracts/' +
                              str(self.id) + '/events'
                    }
               }
        return data


extract_model = api.model('Extract File', {
    'id':                   fields.Integer,
    'created_at':           fields.DateTime,
    'cloze_filepath':       fields.String,
    'question_filepath':    fields.String,
    'deleted':              fields.Boolean,
    'archived':             fields.Boolean,
    'cloze_startstamp':     fields.Float,
    'cloze_endstamp':       fields.Float,
    '_links': {
        'self': fields.String,
        'topic': fields.String,
        'items': fields.String,
        'events': fields.String
        }
    })

paginated_extracts_model = api.model('Paginated Extract Files', {
    "data":       fields.List(fields.Nested(extract_model)),
    "_meta": {
              "page":         fields.Integer,
              "per_page":     fields.Integer,
              "total_pages":  fields.Integer,
              "total_items":  fields.Integer
             },
    "_links": {
               "self":      fields.String,
               "next":      fields.String,
               "prev":      fields.String,
              }
    })


###############################
# ItemFile DB Model and Table #
###############################

class ItemFile(PaginatedAPIMixin, db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['itemfiles']

    def to_dict(self):
        data = {
                'id':                self.id,
                'created_at':        self.question_filepath,
                'question_filepath': self.question_filepath,
                'cloze_filepath':    self.cloze_filepath,
                'archived':          self.archived,
                'deleted':           self.deleted,
                'cloze_startstamp':  self.cloze_startstamp,
                'cloze_stopstamp':   self.cloze_endstamp,
                # TODO Change to url_for
                '_links': {
                    'self': 'http://audiopi:5000/items/' + self.id,
                    'extract': 'http://audiopi:5000/items/' + \
                               self.id + '/extract',
                    'events': 'http://audiopi:5000/items/' + \
                              self.id + '/events'
                    }
               }
        return data


item_model = api.model('Item File', {
    'id':                   fields.Integer,
    'created_at':           fields.DateTime,
    'question_filepath':    fields.String,
    'cloze_filepath':       fields.String,
    'archived':             fields.Boolean,
    'deleted':              fields.Boolean,
    'cloze_startstamp':     fields.Float,
    'cloze_endstamp':       fields.Float,
    '_links': {
        'self': fields.String,
        'extract': fields.String,
        'events': fields.String,
        }
    })

paginated_items_model = api.model('Paginated Item Files', {
    "data":       fields.List(fields.Nested(item_model)),
    "_meta": {
              "page":         fields.Integer,
              "per_page":     fields.Integer,
              "total_pages":  fields.Integer,
              "total_items":  fields.Integer
             },
    "_links": {
               "self":      fields.String,
               "next":      fields.String,
               "prev":      fields.String,
              }
    })

#######################################
# Topic Event DB tables and API Model #
#######################################

class TopicEvent(db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['topicevents']

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'event':        self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    # TODO Change to url_for
                    'self': 'http://audiopi:5000/topics/' + \
                            self.topic_id + '/events/' + self.id,
                    'topic': 'http://audiopi:5000/topics/' + self.topic_id
                    }
               }
        return data


topic_event_model = api.model('Topic Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': {
        'self':     fields.String,
        'topic':    fields.String
        }
    })


#########################################
# Extract Event DB tables and API Model #
#########################################

class ExtractEvent(db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['extractevents']

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'event':        self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    # TODO Change to url_for
                    'self': 'http://audiopi:5000/extracts/' + \
                            self.extract_id + '/events/' + self.id,
                    'extract': 'http://audiopi:5000/extracts/' + \
                               self.extract_id
                    }
               }
        return data


extract_event_model = api.model('Extract Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': {
        'self':     fields.String,
        'extract':  fields.String
        }
    })


######################################
# Item Event DB tables and API Model #
######################################

class ItemEvent(db.Model):
    """ TODO """
    __table__ = db.Model.metadata.tables['itemevents']

    def to_dict(self):
        data = {
                'id':           self.id,
                'created_at':   self.created_at,
                'self':         self.event,
                'timestamp':    self.timestamp,
                'duration':     self.duration,
                '_links': {
                    # TODO Change to url_for
                    'self': 'http://audiopi:5000/items/' + \
                            self.item_id + '/events/' + self.id,
                    'item': 'http://audiopi:5000/items/' + self.item_id,
                }
               }
        return data


item_event_model = api.model('Item Event', {
    'id':           fields.Integer,
    'created_at':   fields.DateTime,
    'event':        fields.String,
    'timestamp':    fields.Float,
    'duration':     fields.Float,
    '_links': {
        'self':     fields.String,
        'item':     fields.String
        }
    })


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

# By default arguments are not required
# Arguments default to None
# Deleted filter didn't work

# parser = reqparse.RequestParser()
# parser.add_argument('start',
#                     type=str,
#                     help='Find Topics after this time',
#                     location='list')
# parser.add_argument('end',
#                     type=str,
#                     help='Find topics before this time',
#                     location='list')


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
                                            'http://audiopi:5000/topics')
        return data


# @topic_ns.route('/<int:topic_id>/extracts')
# class TopicExtracts(Resource):
#     @api.marshal_with(paginated_extracts_model)
#     @api.response(200, "Successfully read child extracts")
#     def get(self, topic_id):
#         """ Get a topic's extracts
#         Allows the user to read a list of child
#         extracts from the parent topic"""
#
#         # TODO
#
#         pass


@topic_ns.route('/<int:topic_id>')
class Topic(Resource):
    @api.marshal_with(topic_model)
    @api.response(200, "Successfully read topic")
    def get(self, topic_id):
        """ Get a single topic
        Allows the user to get a single topic according
        to the topic id"""

        topic = db.session.query(TopicFile).get_or_404(topic_id)
        return topic.to_dict()


# @topic_ns.route('/yttags/')
# class TopicTags(Resource):
#     @api.marshal_with(topic_model, as_list=True)
#     @api.response(200, "Successfully filtered topics by tags")
#     # TODO add an expect decorator
#     def post(self):
#         pass


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
        data = ExtractFile.to_collection_dict(db.session.query(ExtractFile),
                                              page, per_page,
                                              'http://audiopi:5000/extracts')
        return data


@extract_ns.route('/<int:extract_id>')
class Extract(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read a single extract")
    def get(self, extract_id):
        """ Get a single extract
        Allows the user to read a single extract according to
        the extract id"""
        extract = db.session.query(ExtractFile).get_or_404()
        return extract.to_dict()


# @extract_ns.route('/<int:extract_id>/topic')
# class ExtractTopic(Resource):
#     @api.marshal_with(topic_model)
#     @api.response(200, "Successfully read parent topic of extract")
#     def get(self, extract_id):
#         """ Get extract topic
#         Allows the user to read the parent topic of an extract
#         according to the extract id"""
#
#         # TODO
#
#         pass


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
                                           'http://audiopi:5000/items')
        return data


@item_ns.route('/<int:item_id>')
class Item(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read the parent extract of item")
    def get(self, item_id):
        """ Get item extract
        Allows the user to get the parent extract of the item
        according to the item id"""

        item = db.session.query(ItemFile).get_or_404(item_id)
        return item.to_dict()


# @item_ns.route('/<int:item_id>/extract')
# class ItemParent(Resource):
#     @api.marshal_with(extract_model)
#     @api.response(200, "Successfully read the parent extract of item")
#     def get(self, item_id):
#         """ Get item extract
#         Allows the user to get the parent extract of the item
#         according to the item id"""
#
#         # TODO
#
#         pass



if __name__ == "__main__":
    app.run(debug=True)
