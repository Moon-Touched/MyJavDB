from tools import Movie, Scraper, Actor, Movie_Manager
import json
from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


def update(actor_name: str):

    actor = Actor.objects(name=actor_name).first()
    if actor == None:
        actor_info = scraper.search_actor(actor_name)
        if actor_info != None:
            actor = Actor(**actor_info)
    uncensored = actor.uncensored
    if uncensored:
        actor_name = actor.name[:-4]
    second_name = actor.second_name
    actor_url = actor.url
    total_movies = actor.total_movies
    count1 = Movie.objects(actors=actor_name, uncensored=uncensored).count()
    count2 = Movie.objects(actors=second_name, uncensored=uncensored).count()
    count = max(count1, count2)
    print(f"{actor_name}(无码{uncensored})共有{total_movies}部，已记录{count}部")
    if count >= total_movies:
        print("全部抓取完成，已跳过")
        return

    all_movie_info = scraper.get_actor_all_movie_info(actor_url, uncensored, count)

    count1 = Movie.objects(actors=actor_name, uncensored=uncensored).count()
    count2 = Movie.objects(actors=second_name, uncensored=uncensored).count()
    count = max(count1, count2)
    print(f"{actor_name}(无码{uncensored})共有{total_movies}部，抓取后已有{count}部")
    return all_movie_info


def get_image_by_actor(actor_name: str):
    movies = Movie.objects(actors=actor_name)
    for movie in movies:
        scraper.get_one_movie_image(movie.url, actor_name, movie.code)


scraper = Scraper(time_interval=20, movie_image_path="E:\啊啊啊\预览backup")
manager = Movie_Manager(scraper, True)
info = scraper.search_code("DAZD_176")
print(info)
