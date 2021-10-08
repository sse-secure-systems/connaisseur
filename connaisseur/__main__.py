"""
Main method for connaisseur. It starts the web server.
"""
import os
from logging.config import dictConfig
from connaisseur.falcon_server import APP
from cheroot.server import HTTPServer
from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server

if __name__ == "__main__":
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {"format": "[%(asctime)s] %(levelname)s: %(message)s"}
            },
            "handlers": {
                "wsgi": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://flask.logging.wsgi_errors_stream",
                    "formatter": "default",
                }
            },
            "root": {"level": LOG_LEVEL, "handlers": ["wsgi"]},
        }
    )

    HTTPServer.ssl_adapter = BuiltinSSLAdapter(
        certificate="/app/certs/tls.crt", private_key="/app/certs/tls.key"
    )

    # the host needs to be set to `0.0.0.0` so it can be reachable from outside the
    # container
    server = Server(("0.0.0.0", 5000), APP)
    server.start()
