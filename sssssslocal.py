from lib.tools import Movie_Manager, Scraper, Movie, Actor
import os
import asyncio

scraper = Scraper(time_interval=3)
manager = Movie_Manager(scraper=scraper, movie_path="E:\\啊啊啊", capture_path="E:\\啊啊啊\\to be capture")

# scraper.get_actor_all_movie_info("神木麗")
# task_list = manager.get_magnet_list(movie_query_set=Movie.objects(actors="神木麗"))
# asyncio.run(manager.save_to_pikpak(task_list,))

actors = Actor.objects()
for actor in actors:
    actor_name = actor.name
    scraper.get_actor_all_movie_info(actor_name)

# manager.match_info()
