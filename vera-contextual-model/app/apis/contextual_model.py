from flask import Blueprint
from app.controller.contextual_model import create_embeddings, find_similar_matching

contextual = Blueprint('contextual-model', __name__,
                       url_prefix='/v1/contextual-model')

# Route to create embeddings


@contextual.route("/create-embeddings")
async def embeddings():
    response = await create_embeddings()
    return response

# route to find similarities


@contextual.route("/find-similarity")
async def find_similarity():
    response = await find_similar_matching()
    return response
