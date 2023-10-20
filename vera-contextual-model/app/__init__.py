from flask import Flask

from .apis.hello import hello
from .apis.contextual_model import contextual


def create_app():
    app = Flask(__name__)
    # Registering routes
    app.register_blueprint(hello)
    app.register_blueprint(contextual)
    return app
