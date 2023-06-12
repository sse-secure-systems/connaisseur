import logging
from datetime import datetime as dt

from pythonjsonlogger import jsonlogger


class ConnaisseurLoggingWrapper:
    """
    Logging wrapper for a WSGI application that logs all HTTP requests
    """

    def __init__(self, app, log_level):
        self.logger = logging.getLogger(
            "wsgi"
        )  # has no handler and hence propagates logs to root logger
        self.logger.setLevel(log_level)
        self.app = app

    # mimic
    # https://github.com/cherrypy/cheroot/blob/d5790dc64d11dfedf2d1258246540d3e94c70279/cheroot/wsgi.py#L395
    def __call__(self, environ, start_response):
        status_codes = []

        # mimic
        # https://github.com/cherrypy/cheroot/blob/d5790dc64d11dfedf2d1258246540d3e94c70279/cheroot/wsgi.py#L152
        # can be called multiple times per request
        def custom_start_response(status, response_headers, exc_info=None):
            # status code will be e.g. '404 Not Found'
            status_codes.append(status.partition(" ")[0])
            return start_response(status, response_headers, exc_info)

        # calling the app may change the environ variable, so we must call the app first and then log
        result = self.app(environ, custom_start_response)
        # the server can "change it's mind" before sending the first response if exc_info is provided
        # hence we need to use the last status code provided

        extra_logs = {
            "client_ip": environ.get("REMOTE_ADDR", ""),
            "method": environ.get("REQUEST_METHOD", ""),
            "path": environ.get("PATH_INFO", ""),
            "query": environ.get("QUERY_STRING", ""),
            "protocol": environ.get("SERVER_PROTOCOL", ""),
            "status_code": status_codes[-1],
        }

        if environ.get("REQUEST_URI") in ["/ready", "/health"]:
            self.logger.debug("request log", extra=extra_logs)
        else:
            self.logger.info("request log", extra=extra_logs)
        return result


class JsonLogFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        if "timestamp" not in log_record:
            log_record["timestamp"] = str(dt.utcnow())

        for field in self._required_fields:
            log_record[field] = record.__dict__.get(field)
        log_record.update(message_dict)

        if log_record["message"] == "request log":
            del log_record["message"]

        jsonlogger.merge_record_extra(record, log_record, reserved=self._skip_fields)
