"""
Main method for connaisseur. It starts the web server.
"""
import os
from logging.config import dictConfig
from connaisseur.flask_server import APP

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

    # the host needs to be set to `0.0.0.0` so it can be reachable from outside the
    # container
    APP.run(
        host="0.0.0.0",  # nosec
        ssl_context=("/app/certs/tls.crt", "/app/certs/tls.key"),
    )
