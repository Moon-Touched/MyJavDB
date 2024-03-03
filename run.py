from tools import Movie, Scraper
import json
from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


connect(db="MyJavDB", host="mongodb://localhost:27017")


with open("actor_info.json", "r", encoding="utf-8") as file:
    actor_info = json.load(file)
with open("cookie.txt", "r", encoding="utf-8") as file:
    cookie = file.read()

scraper = Scraper(time_interval=20, cookie=cookie, to_database=True, save_FC2=True)

for actor_name, info in actor_info.items():
    if actor_name[-4:] == "(無碼)":
        actor_name = actor_name[:-4]
    second_name = info["second_name"]
    actor_url = info["actor_url"]
    uncensored = info["uncensored"]
    total_movies = info["total_movies"]
    count1 = Movie.objects(actors=actor_name, uncensored=uncensored).count()
    count2 = Movie.objects(actors=second_name, uncensored=uncensored).count()
    count = max(count1, count2)
    print(f"{actor_name}(无码{uncensored})共有{total_movies}部，已记录{count}部")
    if count == total_movies:
        print("全部抓取完成，已跳过")
        continue

    all_movie_info = scraper.get_actor_movie_info(actor_url, uncensored, count)

    count1 = Movie.objects(actors=actor_name, uncensored=uncensored).count()
    count2 = Movie.objects(actors=second_name, uncensored=uncensored).count()
    count = max(count1, count2)
    print(f"{actor_name}(无码{uncensored})共有{total_movies}部，抓取后已有{count}部")
