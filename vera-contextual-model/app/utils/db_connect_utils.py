from flask_pymongo import pymongo
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Access environment variables
DB_CONNECT = os.getenv("DB_CONNECT")
DB_NAME = os.getenv("DB_NAME")

client = pymongo.MongoClient(DB_CONNECT)
db = client.get_database(DB_NAME)