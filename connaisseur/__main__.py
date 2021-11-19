"""
Main method for Connaisseur. Start the web server.
"""
import os
from logging.config import dictConfig

from cheroot.server import HTTPServer
from cheroot.wsgi import Server
from cheroot.ssl.builtin import BuiltinSSLAdapter

from connaisseur.flask_application import APP
from connaisseur.logging_wrapper import ConnaisseurLoggingWrapper


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
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                }
            },
            "root": {"level": LOG_LEVEL, "handlers": ["wsgi"]},
        }
    )

    HTTPServer.ssl_adapter = BuiltinSSLAdapter(
        certificate="/app/certs/tls.crt", private_key="/app/certs/tls.key"
    )

    # wrap Connaisseur with a layer that logs HTTP requests
    app = ConnaisseurLoggingWrapper(APP, LOG_LEVEL)

    # the host needs to be set to `0.0.0.0` so it can be reachable from outside the container
    server = Server(("0.0.0.0", 5000), app)  # nosec
    server.start()
