from fastapi import APIRouter, HTTPException, Request, WebSocket, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from modules import Movie, MovieManager, Actor
from urllib.parse import unquote
from settings import MongoDB_Setting, PIKPAK_Setting
from pikpakapi import PikPakApi
import motor.motor_asyncio, re, json, os
from bson.objectid import ObjectId


client = motor.motor_asyncio.AsyncIOMotorClient(MongoDB_Setting["host"])
database = client[MongoDB_Setting["db"]]
movie_collection = database.get_collection("movie")
actor_collection = database.get_collection("actor")

manager_api = APIRouter()
templates = Jinja2Templates(directory="templates")
manager = MovieManager(time_interval=5)


class PathData(BaseModel):
    movie_path: str
    capture_path: str


@manager_api.get("/", summary="首页，输入本地路径", response_class=HTMLResponse)
async def manager_ini_page(request: Request):
    return templates.TemplateResponse("manager_ini_page.html", {"request": request, "base_path": "/manager"})


@manager_api.post("/api/update_local_path", summary="后台更新本地影片路径")
async def update_local_path(local_path: PathData):
    movie_path = local_path.movie_path
    print(movie_path)
    capture_path = local_path.capture_path
    if (not re.match(r"^[a-zA-Z]:\\.*$", movie_path)) or (not re.match(r"^[a-zA-Z]:\\.*$", capture_path)):
        raise HTTPException(status_code=400, detail="路径格式不正确")
    manager.movie_path = movie_path
    manager.capture_path = capture_path
    print(manager.capture_path)
    return


@manager_api.get("/function_list", response_class=HTMLResponse)
async def function_list(request: Request):
    return templates.TemplateResponse("function_list.html", {"request": request, "base_path": "/manager"})


# router路径/manager
@manager_api.get("/get_one_movie_info", summary="根据url获取一部影片的信息", response_class=HTMLResponse)
async def get_movie_info_page(request: Request):
    return templates.TemplateResponse("get_one_movie_info.html", {"request": request, "base_path": "/manager"})


@manager_api.websocket("/get_one_movie_info/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    movie_url = await websocket.receive_text()
    exist_movie = await movie_collection.find_one({"url": movie_url})
    if exist_movie:
        await websocket.send_text("数据库中已有该电影。")
        return
    else:
        movie_info = await manager.get_one_movie_info(movie_url)
        movie_info = movie_info.model_dump()

        res = await movie_collection.insert_one(movie_info)
        await websocket.send_text(f"{movie_info['code']}已存储")
        return


@manager_api.get("/get_one_actor_info", summary="根据url获取一位演员的信息", response_class=HTMLResponse)
async def get_actor_info_page(request: Request):
    return templates.TemplateResponse("get_one_actor_info.html", {"request": request, "base_path": "/manager"})


@manager_api.websocket("/get_one_actor_info/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    actor_url = await websocket.receive_text()
    exist_actor = await actor_collection.find_one({"url": actor_url})
    if exist_actor:
        await websocket.send_text("数据库中已有该演员。")
        return

    else:
        actor_info = await manager.get_one_actor_info(actor_url)
        actor_info = actor_info.model_dump()

        res = await actor_collection.insert_one(actor_info)
        await websocket.send_text(f"{actor_info['name']}已存储")
        return


@manager_api.get("/get_favourite_actors_info", summary="获取收藏页面所有演员的信息", response_class=HTMLResponse)
async def get_favourite_actors_info(request: Request):
    return templates.TemplateResponse("get_favourite_actors_info.html", {"request": request})


@manager_api.websocket("/get_favourite_actors_info/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    actor_urls = await manager.get_favourite_actors_url()
    for url in actor_urls:
        exist_actor = await actor_collection.find_one({"url": url})
        if exist_actor:
            await websocket.send_text("数据库中已有该演员。")
            continue
        actor_info = await manager.get_one_actor_info(url)
        actor_info = actor_info.model_dump()

        res = await actor_collection.insert_one(actor_info)
        await websocket.send_text(f"{actor_info['name']}已存储")
    return


@manager_api.get("/match_info", summary="匹配本地影片", response_class=HTMLResponse)
async def match_info(request: Request):
    return templates.TemplateResponse("match_info.html", {"request": request})


@manager_api.websocket("/match_info/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    files = await manager.get_file_list(manager.capture_path)
    for file in files:
        file_name = file.split("\\")[-1]
        code, _, ext = file_name.rpartition(".")
        movie_info = await movie_collection.find_one({"code": code})
        if movie_info == None:
            await websocket.send_text(f"数据库中没有{movie_info['code']}相应数据，开始抓取")
            movie_info = await manager.search_code_and_get_info(code)
            res = await movie_collection.insert_one(movie_info)
        res = await movie_collection.update_one({"code": code}, {"$set": {"local_existance": True}})
        ###到此信息获取完成，开始准备路径和重命名
        title = movie_info["title"]
        for i in range(len(title) - 1):
            if title[i] == ":" and i > 2:
                a, _, b = title.rpartition(":")
                title = f"{a}{b}"
        target_folder = os.path.join(manager.movie_path, "capture done", f"{code}")
        if len(target_folder) > 80:
            target_folder = target_folder[:80]
        target_folder = target_folder.rstrip()
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        target_file = f"{target_folder}\\{file_name}"
        await manager.generate_nfo(movie_info, target_folder)
        await manager.get_one_movie_image(movie_url=movie_info["url"], movie_code=movie_info["code"], path=target_folder)

        os.rename(file, target_file)
        await websocket.send_text(f"{file_name}整理完成")
    await websocket.send_text("done！！！！！！！！")
    return


@manager_api.get("/get_filtered_magnet", summary="筛选数据库中影片并获取磁链", response_class=HTMLResponse)
async def get_filtered_magnet(request: Request):
    actors = actor_collection.find()
    actor_list = []
    async for a in actors:
        actor_list.append(Actor(**a))
    return templates.TemplateResponse("get_filtered_magnet.html", {"request": request, "actors": actor_list})


@manager_api.websocket("/get_filtered_magnet/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()
    code = data["code"]
    actor = data["actor"]
    save_to_pikpak = data["save_to_pikpak"]
    if save_to_pikpak:
        client = PikPakApi(username=PIKPAK_Setting["username"], password=PIKPAK_Setting["password"])
        await client.login()

    filter_dict = {}
    if actor != "":
        filter_dict["actors"] = actor
    if code != "":
        filter_dict["code"] = code
    movies = movie_collection.find(filter_dict)

    magnet_str = ""
    async for m in movies:
        if m["magnet"] != "":
            magnet_str = magnet_str + f"{m['magnet']}<br>"
            if save_to_pikpak and not m["local_existance"]:
                res = await client.create_folder(m["code"])
                id = res["file"]["id"]
                res = await client.offline_download(m["magnet"], parent_id=id)
            await websocket.send_text(m["magnet"])
    await websocket.send_text("done！！！！！！")
    return


@manager_api.get("/get_one_actor_all_movie_info", summary="选择数据库中演员爬取所有影片信息", response_class=HTMLResponse)
async def get_one_actor_all_movie_info(request: Request):
    actors = actor_collection.find()
    actor_list = []
    async for a in actors:
        actor_list.append(Actor(**a))
    return templates.TemplateResponse("get_one_actor_all_movie_info.html", {"request": request, "actors": actor_list})


@manager_api.websocket("/get_one_actor_all_movie_info/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()
    actor_name = data["actor"]
    actor = await actor_collection.find_one({"name": actor_name})
    count = await movie_collection.count_documents({"actors": actor["second_name"]})
    await websocket.send_text(f"{actor_name}共有{actor['total_movies']}部，数据库中已有{count}部")
    if count < actor["total_movies"]:
        movie_urls = actor["movie_urls"]
        for url in movie_urls:
            exist_movie = await movie_collection.find_one({"url": url})
            if exist_movie:
                continue
            else:
                movie_info = await manager.get_one_movie_info(url, actor["uncensored"])
                movie_info = movie_info.model_dump()
                res = await movie_collection.insert_one(movie_info)
                await websocket.send_text(f"{movie_info['code']}已存储")
    count = await movie_collection.count_documents({"actors": actor["second_name"]})
    await websocket.send_text(f"{actor_name}共有{actor['total_movies']}部，数据库中已有{count}部")
