from flask import Blueprint, jsonify

from ..models import Site

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/stats")
def stats():
    return jsonify({"site_count": Site.query.count()})
