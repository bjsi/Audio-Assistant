from flask_restplus import Resource, Api
import os
from flask import Blueprint, request, Flask, render_template, url_for
from flask_restplus import fields
from flask_sqlalchemy import SQLAlchemy
from config import DATABASE_URI
from flask_cors import CORS
from AudioDownloader import AudioDownloader


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

assistant_ns = api.namespace('assistant',
                             description="Operations for controlling "
                                         "Audio Assistant via the API")

download_request = api.model('Download Request', {
        "id": fields.String,
        "playback_rate": fields.Float,
        "sm_element_id": fields.Integer,
        "sm_priority": fields.Float,
        })


@assistant_ns.route("/ping")
class Ping(Resource):
    @api.response(200, "Pinged the audio assistant API")
    def get(self):
        """
        """
        return "ping", 200


@assistant_ns.route("/download")
class Youtube(Resource):
    @api.response(201, "Successfully downloaded audio file to pi")
    @api.expect(download_request)
    def post(self, youtube_id):
        """Start a youtube_dl download
        """
        if download_request:
            # TODO wait for the finished hook return status somehow
            AudioDownloader(**download_request).download()
        return download_request, 404


if __name__ == "__main__":
    app.run(debug=True)