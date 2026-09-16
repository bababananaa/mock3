from flask import Blueprint, jsonify, request

from services.errors import ValidationError


def build_blueprint(service):
    bp = Blueprint("api", __name__)

    @bp.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @bp.get("/walkers")
    def list_walkers():
        return jsonify(service.list_walkers())

    @bp.get("/walkers/<int:walker_id>")
    def get_walker(walker_id):
        return jsonify(service.get_walker(walker_id))

    @bp.get("/walks")
    def list_walks():
        return jsonify(service.list_walks(
            walker_id=request.args.get("walker_id", type=int),
            status=request.args.get("status"),
        ))

    @bp.get("/walks/<int:walk_id>")
    def get_walk(walk_id):
        return jsonify(service.get_walk(walk_id))

    @bp.post("/walks")
    def create_walk():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValidationError("request body must be a JSON object")
        return jsonify(service.create_walk(payload)), 201

    @bp.post("/walks/<int:walk_id>/cancel")
    def cancel_walk(walk_id):
        return jsonify(service.cancel_walk(walk_id))

    return bp
