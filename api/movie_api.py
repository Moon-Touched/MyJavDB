from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from modules import Movie
from urllib.parse import unquote
from settings import MongoDB_Setting
import motor.motor_asyncio
from bson.objectid import ObjectId


client = motor.motor_asyncio.AsyncIOMotorClient(MongoDB_Setting["host"])
database = client[MongoDB_Setting["db"]]
movie_collection = database.get_collection("movie")


movie_api = APIRouter()
templates = Jinja2Templates(directory="templates")


# router路径/movies
@movie_api.get("/", summary="获取当前数据库中所有电影的列表")
async def get_all_movies(request: Request):
    movies = movie_collection.find()
    movie_list = []
    async for m in movies:
        movie_list.append(Movie(**m))
    return templates.TemplateResponse("movie_list.html", {"request": request, "movies": movie_list})


@movie_api.get("/{movie_code}", summary="获取某一番号的信息")
async def get_movie_info(movie_code: str, request: Request):
    movie = await movie_collection.find_one({"code": movie_code})
    if movie == None:
        raise HTTPException(status_code=404, detail="数据库中未找到该番号")

    return templates.TemplateResponse("movie_info.html", {"request": request, "movie": movie})




# @movie_api.post("/add_new_movie", response_description="增加一个新电影", response_model=Movie)
# async def add_movie(movie: Movie) -> Movie:
#     new_movie = movie.model_dump()
#     existing_movie = await movie_collection.find_one({"url": movie.url})
#     if existing_movie:
#         raise HTTPException(status_code=409, detail="数据库出现相同url")

#     new_movie_id = await movie_collection.insert_one(new_movie)
#     created_movie = await movie_collection.find_one({"_id": new_movie_id.inserted_id})
#     return Movie(**created_movie)
