from tools import Movie, Scraper
import json
from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


connect(db="MyJavDB", host="mongodb://localhost:27017")


with open("actor_info.json", "r", encoding="utf-8") as file:
    actor_info = json.load(file)

scraper = Scraper(
    cookie="list_mode=h; theme=auto; locale=zh; _ym_uid=170939089767775515; _ym_d=1709390897; _ym_isad=1; cf_clearance=qlBa7oj0ju0x6.3.O5usIvpjqRSBJb0aqrYNB1Vv8go-1709390898-1.0.1.1-_IZnxebinK91dX.fCjdmDwWlJTUPo10Z.uysXBYDbzvd0h3OSuFZSUFHKUBLvR7EBo_JJE0Ccn0c495oAKXRcA; over18=1; _rucaptcha_session_id=3c4e8d0aa0d5d9ca6065226f570302df; remember_me_token=eyJfcmFpbHMiOnsibWVzc2FnZSI6IklqZHpaSE5RYW5aWlEyWkZOSGc0YlZJMWFVdDRJZz09IiwiZXhwIjoiMjAyNC0wMy0wOVQxNDo0OToxMS4wMDBaIiwicHVyIjoiY29va2llLnJlbWVtYmVyX21lX3Rva2VuIn19--55e7db4009809119fa4d6e3a49951dc7596c5b21; _jdb_session=Wnf84WAYA9BU5Khx8qxJwr7EHDOfupzilK2%2BJzF6EZpCG%2BwN3FdzOYpSMrs%2BaIBnk%2FpNTEX6u7n1cojgdZ9%2BOcaStQSifS8LRlZstIoNgrzsI0iThoKZVs8jNFSkja7D0BW8aoq6FCMx2bOXMeBOD5q5OBICVMqC%2FOTsUgDX44jP3Xd%2FAihAfAcFdCflHG0rq8Gv7SXK%2FAHcst1YG%2BC3T6G5vy28l9iscmFYm5ng0T1LRQerHvECp%2B2%2By%2FJIiyAkmcVWEgAyR6elL95du0n1xqGL8YYhoSWG3Y4HLtzo3aFkjsuq8xwYjvn9c1ETqRkVRFrOqnATMv%2F08dWliDcC8m2FlYmtLYgPAI8h3UStlxEN5PnTzHXBCwYn1cVNXcf%2FV407ABSSt%2F0tZwoHlkyZBoHztFP415x21XBkAfBrkSNkiE9qr3vQ9rWgKH%2BUQlGkYV4e8EnM3UsN0BEUDOV8%2FerpcYHs%2Fx4tMNfa1usuAsLvaw%3D%3D--Yrm%2FPPts%2FZFerRwK--7NKZ3o1MFaL9QicgIFadqQ%3D%3D"
)

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

    all_movie_info = scraper.get_actor_movie_info(actor_url, uncensored, True)

    count1 = Movie.objects(actors=actor_name, uncensored=uncensored).count()
    count2 = Movie.objects(actors=second_name, uncensored=uncensored).count()
    count = max(count1, count2)
    print(f"{actor_name}(无码{uncensored})共有{total_movies}部，抓取后已有{count}部")
