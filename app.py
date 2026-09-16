from datetime import datetime

from flask import Flask, jsonify

from api.routes import build_blueprint
from services.errors import ServiceError
from services.walk_service import WalkService
from storage.csv_store import CsvStore


def create_app(store=None, clock=None):
    app = Flask(__name__)
    service = WalkService(store or CsvStore(), clock or datetime.now)
    app.register_blueprint(build_blueprint(service))

    @app.errorhandler(ServiceError)
    def handle_service_error(error):
        return jsonify({"error": error.message}), error.status_code

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
