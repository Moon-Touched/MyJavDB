from tools import Movie_Manager, Scraper, Movie, Actor
import os

scraper = Scraper(time_interval=20)
manager = Movie_Manager(scraper)

actors = Actor.objects()
for actor in actors:
    count1 = Movie.objects(actors=actor.name).count()
    count2 = Movie.objects(actors=actor.second_name).count()
    count = max(count1, count2)
    if count < actor.total_movies:
        print(f"{actor.name}共有{actor.total_movies}部，数据库中已有{count}部")
        manager.scraper.get_actor_all_movie_info(actor.url, actor.uncensored)
    else:
        print(f"{actor.name}共有{actor.total_movies}部，全部抓取完成")
# manager.get_magnet_links_by_actor(actor="滝川まゆり")
# manager.get_magnet_links_by_actor(actor="星越かなめ")
# manager.get_magnet_links_by_actor(actor="椎名みう")
# manager.get_magnet_links_by_actor(actor="中澤チュリン")
# manager.get_magnet_links_by_actor(actor="七瀬るい")
# manager.get_magnet_links_by_actor(actor="蒼井湊")
# manager.get_magnet_links_by_actor(actor="桃谷りり")
# manager.match_info()
