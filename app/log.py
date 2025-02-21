import os
import watchtower
import logging

from app import app

from boto3.session import Session
from flask import abort, current_app, jsonify, make_response, request
from time import strftime
from app_common_python import LoadedConfig, isClowderEnabled


 
if isClowderEnabled():
    cfg = LoadedConfig

    AWS_LOG_GROUP = cfg.logging.cloudwatch.logGroup
    AWS_ACCESS_KEY_ID = cfg.logging.cloudwatch.accessKeyId
    AWS_SECRET_ACCESS_KEY = cfg.logging.cloudwatch.secretAccessKey
    AWS_REGION_NAME = cfg.logging.cloudwatch.region
else:
    AWS_LOG_GROUP = os.getenv("AWS_LOG_GROUP")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")

logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.INFO))


class Cache:
    active_stream_handlers = {}
    allowed_streams = os.getenv("CLOUD_WATCH_ALLOWED_STREAMS", "").split(",")


@app.route("/ping")
def ping():
    return {"status": "available"}, 200


@app.route("/log/<log_stream>", methods=["POST"])
def log(log_stream):
    validate_log_stream(log_stream)
    logger = logging.getLogger(log_stream)
    add_handler(log_stream, logger)
    logger.info(request.get_json(force=True))
    return {"status": "accepted"}, 202


def validate_log_stream(log_stream):
    if log_stream not in Cache.allowed_streams:
        abort(
            make_response(
                jsonify(message=f"{log_stream} is not a valid CloudWatch log stream."),
                403,
            )
        )


def add_handler(log_stream, logger):
    if not Cache.active_stream_handlers.get(log_stream):
        Cache.active_stream_handlers[log_stream] = logger
        logger.addHandler(
            watchtower.CloudWatchLogHandler(
                log_group=AWS_LOG_GROUP,
                stream_name=log_stream,
                boto3_session=session(),
            )
        )


def session():
    return Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION_NAME,
    )


@app.after_request
def after_request(response):
    timestamp = strftime("[%Y-%b-%d %H:%M:%S]")
    current_app.logger.info(
        f"{timestamp} {request.remote_addr} {request.method} {request.full_path} {request.scheme} {response.status}"
    )
    return response
