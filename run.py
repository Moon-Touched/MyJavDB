from tools import Movie, Scraper
import json
from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


connect(db="MyJavDB", host="mongodb://localhost:27017")


with open("actor_info.json", "r", encoding="utf-8") as file:
    actor_info = json.load(file)

scraper = Scraper()

for actor_name, info in actor_info.items():
    actor_sub_url = info["actor_sub_url"]
    uncensored = info["uncensored"]
    all_movie_info = scraper.get_actor_movie_info(1.0, actor_sub_url, uncensored, True)
