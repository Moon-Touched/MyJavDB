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


filter_api = APIRouter()
templates = Jinja2Templates(directory="templates")


@filter_api.get("/", summary="筛选某一条件影片")
async def filter_movie_by_tag(request: Request, tag: str = None, actor: str = None):
    print(tag)

    filter_dict = {}
    if tag:
        filter_dict["tags"] = tag
    else:
        tag = "任意"
    if actor:
        filter_dict["actors"] = actor
    else:
        actor = "任意"
    movies = movie_collection.find(filter_dict)
    movie_list = []
    async for m in movies:
        movie_list.append(Movie(**m))
    return templates.TemplateResponse("movie_filtered_by_tag.html", {"request": request, "actor": actor, "tag": tag, "movies": movie_list})
