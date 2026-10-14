import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class DbConnector:
    def __init__(self):
        self.client = MongoClient(
            host="127.0.0.1",
            port=27017,
            username="tdt4225",
            password=os.environ["MONGO_PASSWORD"],
            authSource="tdt4225",
            serverSelectionTimeoutMS=5000
        )

        self.db = self.client["tdt4225"]

        try:
            self.db.command("ping")
        except Exception:
            self.client.close()
            raise

    def close_connection(self):
        self.client.close()
