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
        "yt_id": fields.String,
        "playback_rate": fields.Float,
        "sm_element_id": fields.Integer,
        "sm_priority": fields.Float,
        })

download_progress = api.model("Download Progress", {
    "yt_id": fields.String,
    "progress": fields.Integer,
    "error": fields.Boolean
})


@assistant_ns.route("/ping")
class Ping(Resource):
    @api.response(200, "Pinged the audio assistant API")
    def get(self):
        """Check if API is online.
        """
        return "ping", 200


@assistant_ns.route("/download")
class Youtube(Resource):
    @api.response(201, "Successfully downloaded audio file to pi")
    @api.expect(download_request)
    def post(self):
        """Start a youtube_dl download
        """
        dl_req = request.get_json()
        if dl_req:
            # TODO wait for the finished hook return status somehow
            app.config[dl_req["yt_id"]] = {}
            app.config[dl_req["yt_id"]]["updated"] = False
            app.config[dl_req["yt_id"]]["progress"] = 0
            app.config[dl_req["yt_id"]]["error"] = False
            AudioDownloader(config=app.config, **dl_req).download()
            return dl_req, 201
        return dl_req, 404


@assistant_ns.route("/progress/<yt_id>")
class Progress(Resource):
    @api.response(200, "Successfully polled download progress")
    def get(self, yt_id: str):
        """Poll the progress of the current youtube-dl download.
        """
        if app.config.get(yt_id):
            if app.config[yt_id].get('updated'):
                app.config[yt_id]["updated"] = False
                return {
                    "yt_id": yt_id,
                    "progress": app.config[yt_id]["progress"],
                    "error": app.config[yt_id]["error"]
                }


if __name__ == "__main__":
    app.run(debug=True, threading=True)