from flask_restplus import Resource, Api
import os
from flask import Blueprint, request, Flask, render_template
from flask_restplus import fields
from models import session, TopicFile, ExtractFile, ItemFile
from flask_restplus import reqparse
from flask_cors import CORS

# blueprint = Blueprint('api', __name__)

app = Flask(__name__)
CORS(app)

api = Api(app,
          title="Audio Assistant",
          version="0.1",
          description="API documentation for Audio Assistant")

# Split Topics, Extracts and Items into separate namespaces

assistant_ns = api.namespace('assistant',
                             decription="Operations for controlling "
                                        "Audio Assistant via the API")
topic_ns = api.namespace('topics',
                         description="Operations for retrieving Topic-related "
                                     "information from the database")
extract_ns = api.namespace('extracts',
                           description="Operations for retrieving Extract-related "
                                       "information from the database")
item_ns = api.namespace('items',
                        description="Operations for retrieving Item-related "
                                    "information from the database")
activity_ns = api.namespace('activities',
                            description="Operations for retrieving "
                                        "Activity-related information from "
                                        "the database")

item_model = api.model('Item', {
    'id': fields.Integer,
    'created_at': fields.DateTime,
    'question_filepath': fields.String,
    'cloze_filepath': fields.String,
    'deleted': fields.Boolean,
    'cloze_startstamp': fields.Float,
    'cloze_endstamp': fields.Float,
    'extractfile': fields.Integer,
    })

extract_model = api.model('Extract', {
    'id': fields.Integer,
    # TODO switch to just filepath
    'extract_filepath': fields.String,
    'created_at': fields.DateTime,
    'topicfile_startstamp': fields.Float,
    'topicfile_endstamp': fields.Float,
    # TODO switch to just transcript
    'extract_transcript': fields.String,
    'deleted': fields.Boolean,
    # A list of ItemFile ids
    'itemfiles': fields.List(fields.Nested(item_model)),
    # Parent topic id
    'topicfile': fields.Integer,
    })

topic_model = api.model('Topic', {
    'id': fields.Integer,
    'upload_id': fields.String,
    'filepath': fields.String,
    'downloaded': fields.Boolean,
    'deleted': fields.Boolean,
    'title': fields.String,
    'duration': fields.Integer,
    'uploader': fields.String,
    'upload_date': fields.String,
    'thumbnail_url': fields.String,
    'view_count': fields.Integer,
    'like_count': fields.Integer,
    'average_rating': fields.Float,
    'cur_timestamp': fields.Float,
    'created_at': fields.DateTime,
    'transcript': fields.String,
    # A list of ExtractFile ids
    'extractfiles': fields.List(fields.Nested(extract_model)),
    # A list of youtube tags
    'yttags': fields.List(fields.String),
    # A list of my own tags (term extracted from transcript)
    'mytags': fields.List(fields.String),
    # TODO activities: a list of events like activity watch
    'rendered': fields.String
    })


# TODO activity model

activity_model = api.model('Activity', {
    'id': fields.Integer,
    'created_at': fields.DateTime,
    'activity': fields.String,
    'duration': fields.Float,
    })

archive_model = api.model('Archive', {
    'source': fields.String,
    'id': fields.String
    })


# add a datetime / timestamp filter to these
# Add a way to filter by tags
# TODO Get items by tag
# TODO Get items by transcript?
# Filter extracts and items by deleted and whether they have a cloze_endstamp /
# topicfile endstamp or not
# Add a way to get logs
# Add a way to start downloads from the API


#############
# Assistant #
#############

@assistant_ns.route('/youtube/archive/')
class Assistant(Resource):
    @api.marshal_with(archive_model, as_list=True)
    @api.response(200, 'Successfully read the archive file')
    def get(self):
        """ Get all items in the youtube archive
        Allows the user to read a list of all previously
        downloaded items which will be skipped by youtube-dl
        in the future"""
        if os.path.isfile('youtube_archive'):
            with open('youtube_archive', 'r') as f:
                lines = f.readlines()
                if lines:
                    archive_list = [
                                    {
                                        'source': line.split(" ")[0].strip(),
                                        'id': line.split(" ")[1].strip()
                                    }
                                    for line in lines
                                   ]

                    return archive_list


##########
# Topics #
##########

# By default arguments are not required
# Arguments default to None

# Deleted filter didn't work
parser = reqparse.RequestParser()
parser.add_argument('start',
                    type=str,
                    help='Find topics after this time',
                    location='list')
parser.add_argument('end',
                    type=str,
                    help='Find topics before this time',
                    location='list')


@topic_ns.route('/')
class Topics(Resource):
    @api.marshal_with(topic_model, as_list=True)
    @api.response(200, 'Successfully read all outstanding topics')
    @api.expect(parser)
    def post(self):
        """ Get outstanding Topics
        Allows the user to read a list of all topic files
        in the database that have not been deleted"""

        # including extracts in the topics model

        args = parser.parse_args()

        if args['start'] and args['end']:
            topics = (session
                      .query(TopicFile)
                      .filter(TopicFile.created_at > args['start'])
                      .filter(TopicFile.created_at < args['end'])
                      .all())

        else:
            topics = (session
                      .query(TopicFile)
                      .order_by(TopicFile.created_at.desc())
                      .all())
        if topics:
            topics = [
                        {
                            'id': topic.id,
                            'upload_id': os.path.splitext(os.path.basename(topic.filepath))[0],
                            'thumbnail_url': topic.thumbnail_url,
                            'filepath': topic.filepath,
                            'downloaded': topic.downloaded,
                            'deleted': topic.deleted,
                            'title': topic.title,
                            'duration': topic.duration,
                            'uploader': topic.uploader,
                            'upload_date': topic.upload_date,
                            'view_count': topic.view_count,
                            'like_count': topic.like_count,
                            'average_rating': topic.average_rating,
                            'cur_timestamp': topic.cur_timestamp,
                            'created_at': topic.created_at,
                            'transcript': topic.transcript,
                            'extractfiles': [
                                                {
                                                  "id": extract.id,
                                                  "extract_filepath": extract.extract_filepath,
                                                  "created_at": extract.created_at,
                                                  "topicfile_startstamp": extract.topicfile_startstamp,
                                                  "topicfile_endstamp": extract.topicfile_endstamp,
                                                  "deleted": extract.deleted,
                                                  "itemfiles": [
                                                                {
                                                                    'id': item.id,
                                                                    'created_at': item.created_at,
                                                                    'question_filepath': item.question_filepath,
                                                                    'cloze_filepath': item.cloze_filepath,
                                                                    'deleted': item.deleted,
                                                                    'cloze_startstamp': item.cloze_startstamp,
                                                                    'cloze_stopstamp': item.cloze_endstamp,
                                                                    'extractfile': item.extractfile.id
                                                                }
                                                                for item in extract.itemfiles
                                                               ],
                                                  "topicfile": topic.id
                                                }
                                                for extract in topic.extractfiles
                                                # Not working?
                                                if extract.topicfile_endstamp is not None
                                            ],

                            'yttags': [
                                        tag.tag
                                        for tag in topic.yttags
                                      ],

                            'mytags': [
                                        tag.tag
                                        for tag in topic.mytags
                                      ],

                            'rendered': render_template("topic.html", topic=topic)
                        }
                        for topic in topics
                    ]

            return topics


@topic_ns.route('/extracts/<int:topic_id>')
class TopicExtracts(Resource):
    @api.marshal_with(extract_model, as_list=True)
    @api.response(200, "Successfully read child "
                       "extracts")
    def get(self, topic_id):
        """ Get topic extracts
        Allows the user to read a list of child
        extracts from the parent topic"""
        topic = (session
                 .query(TopicFile)
                 .filter_by(id=topic_id)
                 .one_or_none())
        if topic:
            extracts = topic.extractfiles
            if extracts:
                extracts = [
                            {
                              "id": extract.id,
                              "extract_filepath": extract.extract_filepath,
                              "created_at": extract.created_at,
                              "topicfile_startstamp": extract.topicfile_startstamp,
                              "topicfile_endstamp": extract.topicfile_endstamp,
                              "deleted": extract.deleted,
                              "itemfiles": [
                                            item.id
                                            for item in extract.itemfiles
                                           ],
                              "topicfile": topic.id
                            }
                            for extract in extracts
                           ]
                return extracts


@topic_ns.route('/topic/<int:topic_id>')
class Topic(Resource):
    @api.marshal_with(topic_model)
    @api.response(200, "Successfully read topic")
    def get(self, topic_id):
        """ Get a single topic
        Allows the user to get a single topic according
        to the topic id"""
        topic = (session
                 .query(TopicFile)
                 .filter_by(id=topic_id)
                 .one_or_none())
        if topic:
            topic = {
                        'id': topic.id,
                        'filepath': topic.filepath,
                        'downloaded': topic.downloaded,
                        'deleted': topic.deleted,
                        'title': topic.title,
                        'duration': topic.duration,
                        'uploader': topic.uploader,
                        'upload_date': topic.upload_date,
                        'view_count': topic.view_count,
                        'like_count': topic.like_count,
                        'average_rating': topic.average_rating,
                        'cur_timestamp': topic.cur_timestamp,
                        'created_at': topic.created_at,
                        'transcript': topic.transcript,
                        'extractfiles': [
                                           extract.id
                                           for extract in topic.extractfiles
                                        ],

                        'yttags': [
                                    tag.tag
                                    for tag in topic.yttags
                                  ],

                        'mytags': [
                                    tag.tag
                                    for tag in topic.mytags
                                  ]
                    }

            return topic


@topic_ns.route('/yttags/')
class TopicTags(Resource):
    @api.marshal_with(topic_model, as_list=True)
    @api.response(200, "Successfully filtered topics by tags")
    # TODO add an expect decorator
    def post(self):
        pass


############
# Extracts #
############


@extract_ns.route('/')
class Extracts(Resource):
    @api.marshal_with(extract_model, as_list=True)
    @api.response(200, 'Successfully read all outstanding extracts')
    def get(self):
        """ Get outstanding extracts
        Allows the user to read a list of all outstanding extract
        files in the database that have not been archived or deleted"""
        extracts = (session
                    .query(ExtractFile)
                    .filter_by(deleted=False)
                    .all())
        if extracts:
            extracts = [
                        {
                          "id": extract.id,
                          "extract_filepath": extract.extract_filepath,
                          "created_at": extract.created_at,
                          "topicfile_startstamp": extract.topicfile_startstamp,
                          "topicfile_endstamp": extract.topicfile_endstamp,
                          "deleted": extract.deleted,
                          "itemfiles": [
                                        item.id
                                        for item in extract.itemfiles
                                       ],
                          "topicfile": extract.topicfile.id
                          }
                        for extract in extracts
                       ]
            return extracts


@extract_ns.route('/extract/<int:extract_id>')
class Extract(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read a single extract")
    def get(self, extract_id):
        """ Get a single extract
        Allows the user to read a single extract according to
        the extract id"""
        extract = (session
                   .query(ExtractFile)
                   .filter_by(id=extract_id)
                   .one_or_none())
        if extract:
            extract = {

                          "id": extract.id,
                          "extract_filepath": extract.extract_filepath,
                          "created_at": extract.created_at,
                          "topicfile_startstamp": extract.topicfile_startstamp,
                          "topicfile_endstamp": extract.topicfile_endstamp,
                          "deleted": extract.deleted,
                          "itemfiles": [
                                        item.id
                                        for item in extract.itemfiles
                                       ],
                          "topicfile": extract.topicfile.id
                      }
            return extract


@extract_ns.route('/topic/<int:extract_id>')
class ExtractParent(Resource):
    @api.marshal_with(topic_model)
    @api.response(200, "Successfully read the parent topic of extract")
    def get(self, extract_id):
        """ Get extract topic
        Allows the user to read the parent topic of an extract
        according to the extract id"""
        extract = (session
                   .query(ExtractFile)
                   .filter_by(id=extract_id)
                   .one_or_none())
        if extract:
            topic = extract.topicfile
            if topic:
                topic = {

                            'id': topic.id,
                            'filepath': topic.filepath,
                            'downloaded': topic.downloaded,
                            'deleted': topic.deleted,
                            'title': topic.title,
                            'duration': topic.duration,
                            'uploader': topic.uploader,
                            'upload_date': topic.upload_date,
                            'view_count': topic.view_count,
                            'like_count': topic.like_count,
                            'average_rating': topic.average_rating,
                            'cur_timestamp': topic.cur_timestamp,
                            'created_at': topic.created_at,
                            'transcript': topic.transcript,
                            'extractfiles': [
                                               extract.id
                                               for extract in topic.extractfiles
                                            ],

                            'yttags': [
                                        tag.tag
                                        for tag in topic.yttags
                                      ],

                            'mytags': [
                                        tag.tag
                                        for tag in topic.mytags
                                      ]
                        }
                return topic


#########
# Items #
#########


@item_ns.route('/')
class Item(Resource):
    @api.marshal_with(item_model, as_list=True)
    @api.response(200, "Successfully read the parent of extract")
    def get(self):
        """ Get outstanding items
        Allows the user to get a list of outstanding
        items that haven't been deleted or archived"""

        items = (session
                 .query(ItemFile)
                 .filter_by(deleted=False)
                 .all())
        if items:
            items = [
                        {
                            'id': item.id,
                            'created_at': item.question_filepath,
                            'cloze_filepath': item.cloze_filepath,
                            'deleted': item.deleted,
                            'cloze_startstamp': item.cloze_startstamp,
                            'cloze_stopstamp': item.cloze_endstamp,
                            'extractfile': item.extractfile.id
                        }

                        for item in items
                    ]
            return items


@item_ns.route('/extract/<int:item_id>')
class ItemParent(Resource):
    @api.marshal_with(extract_model)
    @api.response(200, "Successfully read the parent extract of item")
    def get(self, item_id):
        """ Get item extract
        Allows the user to get the parent extract of the item
        according to the item id"""

        item = (session
                .query(ItemFile)
                .filter_by(id=item_id)
                .one_or_none())

        if item:
            extract = item.extractfile
            extract = {
                          "id": extract.id,
                          "extract_filepath": extract.extract_filepath,
                          "created_at": extract.created_at,
                          "topicfile_startstamp": extract.topicfile_startstamp,
                          "topicfile_endstamp": extract.topicfile_endstamp,
                          "deleted": extract.deleted,
                          "itemfiles": [
                                        item.id
                                        for item in extract.itemfiles
                                       ],
                          "topicfile": extract.topicfile.id
                      }
            return extract




if __name__ == "__main__":
    # How to run network-wide
    app.run(debug=True)
