from pymongo import MongoClient
import os

# MongoDB connection
def get_database():
    connection_string = os.environ.get('DATABASE_URL', 'mongodb://localhost:27017/')
    client = MongoClient(connection_string)
    # Specify database name explicitly
    database_name = os.environ.get('DATABASE_NAME', 'tasktrack')
    return client[database_name]

# Get database instance
db = get_database()