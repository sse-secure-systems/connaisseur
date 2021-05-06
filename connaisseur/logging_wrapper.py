import logging
import time


class ConnaisseurLoggingWrapper:
    """
    Logging wrapper for a WSGI application that logs all HTTP requests
    """

    def __init__(self, app, log_level):
        self.logger = logging.getLogger(
            "connaisseurRequestLogger"
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
        self.logger.info(_format_log(status_codes[-1], environ))
        return result


def _format_log(status_code, environ):
    """
    Recreate the Flask logging format
    """
    # See https://www.python.org/dev/peps/pep-0333/#environ-variables
    # and https://datatracker.ietf.org/doc/html/rfc3875#section-4.1
    client_ip = environ.get("REMOTE_ADDR", "")
    timestamp = time.strftime("%d/%b/%Y %H:%M:%S", time.localtime())
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    query = environ.get("QUERY_STRING", "")
    query = f"?{query}" if query else ""
    protocol = environ.get("SERVER_PROTOCOL", "")
    return f'{client_ip} - - [{timestamp}] "{method} {path}{query} {protocol}" {status_code} -'
