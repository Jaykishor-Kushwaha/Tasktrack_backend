from pymongo import MongoClient
import os

# MongoDB connection
def get_database():
    connection_string = os.environ.get('DATABASE_URL', 'mongodb://localhost:27017/tasktrack')
    client = MongoClient(connection_string)
    return client.get_default_database()

# Get database instance
db = get_database()
