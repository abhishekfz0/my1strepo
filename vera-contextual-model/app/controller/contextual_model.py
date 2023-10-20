import asyncio
# import to load env variables
from dotenv import load_dotenv
import os
# Import related to embeddings and similarities
import json
import tensorflow_hub as hub
from sklearn.metrics.pairwise import cosine_similarity
# Import related to pinecone
import pinecone

from flask_pymongo import pymongo
from app.utils.db_connect_utils import db
from app.utils.jsonify import _jsonify
from flask import request

# Initial setup to make things working
JOHN_LEWIS = "John Lewis"
CATEGORIES = ["Womens Tshirt"]
COMPETITORS = ["Phase Eight", "Argos", "Amazon", "Next", "Mark Spencer"]
FIELDS_TO_ADD = ["product_title",
                 "product_brand",
                 "product_color",
                 "product_neckline",
                 "product_composition",
                 "product_sleevetype",
                 "product_pattern"]
PROVIDER = "product_provider"
CATEGORY = 'product_category'

# load env
load_dotenv()

# Model for encoder, Universal Sentence Encoder
module_url = "https://tfhub.dev/google/universal-sentence-encoder/4"
# competitor_data collection name

# Load Pinecone API key
api_key = os.getenv("PINECONE_KEY")
# Set Pinecone environment. Find next to API key in console
env = "us-west4-gcp"

pinecone.init(api_key=api_key, environment=env)

# Set a name for your index
index_name = 'product-matcher'


if index_name not in pinecone.list_indexes():
    pinecone.create_index(name=index_name, dimension=512, metric='cosine')

# now connect to the index
index = pinecone.Index(index_name)

# initialize mongo db collection
raw_inventory = pymongo.collection.Collection(db, "raw_inventory")
contextual_engine_response = pymongo.collection.Collection(
    db, "contextual_engine_response")

# This is encoder function for creating
# vector embeddings and returning vectors


async def create_vector_embeddings(product_json, model, metadata=False):
    # embbed the data and return the vector embeddings.
    properties_to_keep = FIELDS_TO_ADD

    new_dict = {key: product_json[key]
                for key in properties_to_keep if key in product_json}
    values_only = [value for value in new_dict.values()]
    product_text = json.dumps(values_only)
    # print(product_text)
    embeddings = model([product_text])
    if metadata is True:
        data = {
            'id': product_json['product_ID'],
            'values': embeddings[0].numpy(),
            'metadata': {
                **product_json,
                '_id': str(product_json["_id"])
            }
        }
        return data
    else:
        return embeddings[0].numpy().tolist()


async def create_embeddings():
    # Passing it as a query params to work only for that category
    category = request.args.get('category')
    # model is ready to use for vector encoding
    model = hub.load(module_url)
    # load the products from the mongo db for creating vector embeddings
    # pass the query for the category
    # .skip(1) add after find for skipping the records which
    # got successfully created
    skip = 0
    products = raw_inventory.find(
        {PROVIDER: {"$ne": JOHN_LEWIS},
            CATEGORY: category}).skip(skip)
    result = []
    for product in products:
        result.append({
            **product
        })
    # # code related to storing into vector db pinecone

    batch_size = 100

    # Iterate over the array in batches
    for i in range(0, len(result), batch_size):
        batches = result[i:i+batch_size]
        tasks = []
        for product in batches:
            task = asyncio.ensure_future(
                create_vector_embeddings(product, model, True))
            tasks.append(task)

        # Wait for all tasks to complete
        records = await asyncio.gather(*tasks)

        # upsert to Pinecone, max 100 can be upsert in one go
        index.upsert(vectors=records)
        print("Index", i)

    return _jsonify({"status": 'success'})


async def pineconeQuery(xq, filter_params):
    return index.query(vector=xq,
                       top_k=5,
                       include_metadata=True,
                       filter=filter_params)


async def oneProductSimilarMatching(query_product, model):
    # create the query vector
    vectorEmbedding = await create_vector_embeddings(query_product, model)

    similar = []
    tasks = []
    for competitor in COMPETITORS:
        # adding filters for the metadata
        filter_params = {
            PROVIDER: {'$eq': competitor},
            CATEGORY: {'$eq': query_product[CATEGORY]}
        }
        # now query
        task = asyncio.ensure_future(
            pineconeQuery(vectorEmbedding, filter_params))

        tasks.append(task)

    # Generating response based on best matches
    responses = await asyncio.gather(*tasks)

    for vectorMatches in responses:
        for item in vectorMatches['matches']:
            print(item)
            similar.append({
                'product_ID': item['id'],
                **item['metadata'],
                'product_code': str(item['metadata']['product_code']),
                'score': item['score']
            })

    # sorting it according to score in descending order
    similar.sort(key=lambda x: x['score'], reverse=True)
    # after finding similarities from all the competitor
    # store into collection
    print(query_product, similar)
    contextual_engine_response.update_one(
        {"_id": query_product["_id"]},
        {'$set': {**query_product, "similar": similar}},
        upsert=True)
    return query_product["_id"]


async def find_similar_matching():
    # model is ready to use for vector encoding
    category = request.args.get('category')
    print(category)
    model = hub.load(module_url)
    skip = 0
    products = raw_inventory.find(
        {PROVIDER: JOHN_LEWIS, CATEGORY: category}).skip(skip)
    result = []
    for product in products:
        result.append({**product})

    batch_size = 10
    # Iterate over the array in batches
    for i in range(0, len(result), batch_size):
        batches = result[i:i+batch_size]
        print('Batches', len(batches), 'Index', i)
        tasks = []

        for product in batches:
            # Query product
            query_product = {
                **product
            }

            task = asyncio.ensure_future(
                oneProductSimilarMatching(query_product, model))
            tasks.append(task)

        finalResult = await asyncio.gather(*tasks)
        print(finalResult)
    return _jsonify({"status": 'success'})
