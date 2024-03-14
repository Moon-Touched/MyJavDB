from mongoengine import Document, BooleanField, StringField, IntField, ListField, NotUniqueError, connect
from pymongo.errors import ServerSelectionTimeoutError
from bs4 import BeautifulSoup
from typing import Union
from mylib.error import CookieUnavailableError, UrlRequestFailedError, NoneObjectError
from webdav3.client import Client
from pikpakapi import PikPakApi
import json, re, os, requests, time, copy, sys, urllib.parse, shutil, cv2


class Movie(Document):
    code = StringField(required=True)
    title = StringField(required=True)
    actors = ListField(StringField())
    tags = ListField(StringField())
    uncensored = BooleanField(required=True)
    magnet = StringField(required=True)
    url = StringField(required=True, unique=True)
    local_existance = BooleanField(default=False)


class Actor(Document):
    name = StringField(required=True)
    second_name = StringField(required=True)
    url = StringField(required=True, unique=True)
    uncensored = BooleanField(required=True)
    movie_urls = ListField(StringField())
    total_movies = IntField(required=True)


class Scraper:
    def __init__(self, time_interval: float = 20) -> None:
        connect(db="MyJavDB", host="mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        try:
            Movie.objects.count()
        except ServerSelectionTimeoutError:
            print("连接失败：无法连接到MongoDB服务器")
            sys.exit(1)

        try:
            with open("cookie.txt", "r", encoding="utf-8") as file:
                cookie = file.read()
        except FileNotFoundError:
            print("当前目录未找到cookie.txt")
            sys.exit(1)

        self.headers: dict = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
            "Cookie": cookie,
        }
        self.time_interval: float = time_interval
        self.cookie_available = False
        self.cookie_available = self.check_cookie()
        try:
            if not self.cookie_available:
                raise CookieUnavailableError("cookie无效，请更新")
        except CookieUnavailableError as e:
            print(e)
            sys.exit(1)

        self.actor_info_template: dict = {
            "name": "",
            "second_name": "",
            "url": "",
            "uncensored": False,
            "movie_urls": [],
            "total_movies": 0,
        }
        self.movie_info_template: dict = {
            "code": "",
            "title": "",
            "actors": [],
            "tags": [],
            "uncensored": False,
            "magnet": "",
            "url": "",
            "local_existance": False,
        }

    def get_one_actor_info(self, actor_url: str) -> dict:
        base_url = "https://javdb.com"

        soup = self.get_soup(actor_url)

        # 获取名字，是否无码
        actor_name_text = soup.find("span", class_="actor-section-name").text.split(", ")
        actor_name = actor_name_text[0]
        second_name = actor_name_text[0]
        if actor_name_text[-1][-4:] == "(無碼)":
            uncensored = True
            second_name = actor_name[:-4]
        else:
            uncensored = False

        # 有些有多个名字，在获取一个备用
        if len(actor_name_text) > 1:
            second_name = actor_name_text[1]

        # 获取一共有多少部
        total_movies = 0
        url_list = []
        i = 1
        while True:
            page_url = f"{actor_url}?page={i}"
            with requests.Session() as session:
                response = session.get(page_url, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")
            if soup.find("div", class_="empty-message"):
                break

            # 获取影片列表中的所有条目
            movie_container = soup.find("div", class_="movie-list h cols-4 vcols-8")
            if not movie_container:
                movie_container = soup.find("div", class_="movie-list h cols-4 vcols-5")

            movie_list = movie_container.find_all("div", class_="item", recursive=False)
            n = len(movie_list)
            total_movies = total_movies + n
            for movie in movie_list:
                movie_url = base_url + movie.find("a")["href"]
                url_list.append(movie_url)
            i = i + 1
            time.sleep(self.time_interval)

        actor_info = copy.deepcopy(self.actor_info_template)
        actor_info["name"] = actor_name
        actor_info["second_name"] = second_name
        actor_info["url"] = actor_url
        actor_info["movie_urls"] = url_list
        actor_info["total_movies"] = total_movies
        actor_info["uncensored"] = uncensored

        self.write_actor(actor_info)
        print(actor_info)
        return actor_info

    def get_favorite_actors_info(self, from_url: bool = True, is_update: bool = False) -> dict:

        # 使用cookie登录收藏页面
        if from_url:
            soup = self.get_soup("https://javdb.com/users/collection_actors")

        else:
            # 打开本地的html
            try:
                with open("favourite actors.html", "r", encoding="utf-8") as file:
                    html_content = file.read()
                soup = BeautifulSoup(html_content, "html.parser")
            except FileNotFoundError:
                print("当前目录未找到favourite actors.html")
                return

        # 获取收藏演员信息框
        actor_boxes = soup.find_all("div", class_="box actor-box")
        all_actor_info: dict = {}
        for box in actor_boxes:
            actor_sub_url = box.find("a")["href"]
            actor_url = f"https://javdb.com{actor_sub_url}"

            exist_actor = Actor.objects(url=actor_url).first()
            if exist_actor and (not is_update):
                print(f"{exist_actor.name}已在数据库中，已跳过。")
                continue

            actor_info = self.get_one_actor_info(actor_url)
            try:
                all_actor_info.update(actor_info)
            except TypeError:
                print(f"未获取到 {actor_url} 的信息，已跳过")

        return all_actor_info

    def get_one_movie_info(self, movie_url: str, uncensored: bool) -> dict:
        print(f"开始抓取 {movie_url}")
        movie_soup = self.get_soup(movie_url)

        try:
            info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
        except AttributeError:  # movie_soup返回None
            print(f"{movie_url} 未获取影片信息，可能是FC2页面登陆失败，请检查cookie是否过期")
            return

        movie_info = copy.deepcopy(self.movie_info_template)
        movie_info["uncensored"] = uncensored
        movie_info["url"] = movie_url
        # 开始抓取
        cracked = False
        blocks = info_panel.find_all("div", class_="panel-block", recursive=False)
        for block in blocks:
            if block.find("strong"):
                block_name = block.find("strong").text

            if block_name == "番號:":
                span = block.find("span")
                if span.find("a"):
                    first_code = span.find("a").text
                else:
                    first_code = span.text
                last_code = block.find("span").text.split(first_code)[1]
                movie_info["code"] = f"{first_code}{last_code}"

            elif block_name == "類別:":
                tags = block.find_all("a")
                for tag in tags:
                    movie_info["tags"].append(tag.text)
                    if tag == "無碼破解":
                        cracked = True

            elif block_name == "演員:":
                if not block.find("div", class_="control ranking-tags"):
                    actors = block.find_all("a")
                    for actor in actors:
                        movie_info["actors"].append(actor.text)

        # 获取标题（网页上默认显示的）
        movie_info["title"] = movie_soup.find("strong", class_="current-title").text

        # 获取磁链，磁链只保存一个优先选无码破解，字幕次之，都没有选第一个
        magnet_list = movie_soup.find_all("div", class_="magnet-name column is-four-fifths")
        if len(magnet_list) > 0:
            if cracked:
                for magnet in magnet_list:
                    magnet_name = magnet.find("span", class_="name").text
                    if re.search("无码", magnet_name):
                        movie_info["magnet"] = magnet.find("a")["href"]

            # 没有无码破解
            if movie_info["magnet"] == "":
                for magnet in magnet_list:
                    magnet_tags = magnet.find_all("span", class_="tag is-primary is-small is-light")
                    for magnet_tag in magnet_tags:
                        if re.search("字幕", magnet_tag.text):
                            movie_info["magnet"] = magnet.find("a")["href"]
                            break

            # 没有无码也没有字幕，找到第一个
            if movie_info["magnet"] == "":
                movie_info["magnet"] = magnet_list[0].find("a")["href"]

        self.write_movie(movie_info)
        time.sleep(self.time_interval)
        return movie_info

    def get_one_movie_image(self, movie_url: str, movie_code: str, path: str):
        movie_soup = self.get_soup(movie_url)
        try:
            cover_url = movie_soup.find("img", class_="video-cover")["src"]
        except AttributeError:
            print("未获取影片信息，可能是FC2页面登陆失败，请检查cookie是否过期")
            return
        with requests.Session() as session:
            response = session.get(cover_url, headers=self.headers)

        with open(f"{path}\\{movie_code}-fanart.jpg", "wb") as file:
            file.write(response.content)
        image = cv2.imread(f"{path}\\{movie_code}-fanart.jpg")
        cover = image[:, 425:]
        if cover.shape[0] > 0 and cover.shape[1] > 0:
            print(cover.shape)
            cv2.imwrite(f"{path}\\{movie_code}-cover.jpg", cover)

        time.sleep(self.time_interval)
        return

    def get_actor_all_movie_info(self, actor_name: str) -> list[dict]:
        all_movie_info = []
        actor = Actor.objects(name=actor_name).first()
        url_list = actor.movie_urls
        for movie_url in url_list:
            movie = Movie.objects(url=movie_url).first()
            if not movie:
                movie_info = self.get_one_movie_info(movie_url, actor.uncensored)
                all_movie_info.append(movie_info)
            else:
                print(f"{movie_url} 在数据库中已有")
        return all_movie_info

    def search_code_and_get_info(self, code: str, uncensored: bool = False) -> dict:
        base_url = "https://javdb.com"
        search_url = f"https://javdb.com/search?q={code}&f=all"
        try:
            with requests.Session() as session:
                response = session.get(search_url, headers=self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError("获取网页失败，请重试")
        except UrlRequestFailedError as e:
            print(e)
            return

        movie_container = soup.find("div", class_="movie-list h cols-4 vcols-8")
        if not movie_container:
            movie_container = soup.find("div", class_="movie-list h cols-4 vcols-5")
        if not movie_container:
            print("搜索无结果")
            return
        movie = movie_container.find("div", class_="item", recursive=False)
        sub_url = movie.find("a")["href"]

        movie_info = self.get_one_movie_info(f"{base_url}{sub_url}", uncensored)
        return movie_info

    # 根据演员名字搜索，并获取该演员信息
    def search_actor_and_get_info(self, actor_name: str) -> dict:
        search_url = f"https://javdb.com/search?q={actor_name}&f=actor"

        try:
            with requests.Session() as session:
                response = session.get(search_url, headers=self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError("获取网页失败，请重试")
        except UrlRequestFailedError as e:
            print(e)
            return

        try:
            actor_box = soup.find("div", class_="box actor-box")
            if actor_box == None:
                raise NoneObjectError(f"演员 {actor_name} 未搜索到结果")
        except NoneObjectError as e:
            print(e)
            return

        sub_url = actor_box.find("a")["href"]
        actor_url = f"https://javdb.com/{sub_url}"
        actor_info = self.get_one_actor_info(actor_url)
        return actor_info

    def get_soup(self, movie_url: str):
        try:
            with requests.Session() as session:
                response = session.get(movie_url, headers=self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError("电影网址请求失败")
        except UrlRequestFailedError as e:
            print(e)
            return

        return soup

    def write_movie(self, movie_info: dict):
        try:
            new_movie = Movie(**movie_info)
            new_movie.save()
        except NotUniqueError:
            code = movie_info["code"]
            url = movie_info["url"]
            print(f"{code}，网址 {url} 已存在")
        return

    def write_actor(self, actor_info: dict):
        try:
            new_actor = Actor(**actor_info)
            new_actor.save()
        except NotUniqueError:
            name = actor_info["name"]
            url = actor_info["url"]
            print(f"{name}，网址 {url} 已存在")
        return

    def check_cookie(self):
        test_url = "https://javdb.com/v/W1vx2Q"

        try:
            with requests.Session() as session:
                response = session.get(test_url, headers=self.headers)
                if response.status_code == 200:
                    movie_soup = BeautifulSoup(response.text, "html.parser")
                    info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
                else:
                    raise UrlRequestFailedError("请求网页失败，请检查网络连接")
        except UrlRequestFailedError as e:
            print(e)
            return False

        # 如果还获取不到
        if info_panel == None:
            return False
        else:
            return True


class Movie_Manager:
    def __init__(self, scraper: Scraper, movie_path: str, capture_path: str, use_mongoDB: bool = True) -> None:
        if use_mongoDB:
            connect(db="MyJavDB", host="mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            try:
                Movie.objects.count()
            except ServerSelectionTimeoutError:
                print("连接失败：无法连接到MongoDB服务器")
                sys.exit(1)
        self.movie_path = movie_path
        self.capture_path = capture_path

        self.scraper = scraper

    def match_info(self):

        files = self.get_file_list(self.capture_path)
        for file in files:
            file_name = file.split("\\")[-1]
            code, _, ext = file_name.rpartition(".")
            db_item = Movie.objects(code=code).first()
            if db_item == None:
                print("数据库中没有相应数据，开始抓取")
                movie_info = self.scraper.search_code_and_get_info(code)
                db_item = Movie.objects(code=code).first()
            else:
                movie_info = db_item.to_mongo().to_dict()

            db_item.update(set__local_existance=True)
            title = movie_info["title"]
            for i in range(len(title) - 1):
                if title[i] == ":" and i > 2:
                    a, _, b = title.rpartition(":")
                    title = f"{a}{b}"
            target_folder = os.path.join(self.movie_path, "capture done", f"{code} - {title}")

            if len(target_folder) > 80:
                target_folder = target_folder[:80]
            target_folder = target_folder.rstrip()
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            target_file = f"{target_folder}\\{file_name}"
            self.generate_nfo(movie_info, target_folder)
            self.scraper.get_one_movie_image(movie_url=movie_info["url"], movie_code=movie_info["code"], path=target_folder)

            os.rename(file, target_file)
        return

    def get_file_list(self, path: str, size_threshold: int = 524288000):
        files = []
        f = os.walk(path)
        root, movie_folders, file_names = next(f)

        for folder in movie_folders:
            large_files = []
            for root, dirs, file_names in os.walk(os.path.join(path, folder)):
                for file_name in file_names:
                    file_path = os.path.join(root, file_name)
                    if os.path.getsize(file_path) > size_threshold:
                        large_files.append({"file_path": file_path, "file_name": file_name})

            if len(large_files) == 1:
                name, _, ext = large_files[0]["file_name"].rpartition(".")
                new_name = f"{folder}.{ext}"
                new_path = os.path.join(path, folder, new_name)
                os.renames(large_files[0]["file_path"], new_path)
                files.append(new_path)
            else:
                print(f"{large_files[0]['file_path']}有多个大文件")
        return files

    def generate_nfo(self, movie_info: dict, path: str):
        nfo_content = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<movie>\n'
        nfo_content += f"<title>{movie_info['code']}{movie_info['title']}</title>\n"
        for tag in movie_info["tags"]:
            nfo_content += f"<genre>{tag}</genre>\n"

        for tag in movie_info["tags"]:
            nfo_content += f"<tag>{tag}</tag>\n"

        for actor in movie_info["actors"]:
            nfo_content += "<actor>\n"
            nfo_content += f"<name>{actor}</name>\n"
            nfo_content += "</actor>\n"

        nfo_content += "</movie>\n"

        with open(f"{path}\\{movie_info['code']}.nfo", "w", encoding="utf-8") as file:
            file.write(nfo_content)
        return

    def get_magnet_list(self, movie_query_set: str) -> list[dict]:
        magnet_list = []
        for movie in movie_query_set:
            if movie.local_existance:
                print(f"{movie.code}已有本地文件")
                continue
            else:
                if movie.magnet != "":
                    magnet_dict = {"code": movie.code, "magnet": movie.magnet}
                    magnet_list.append(magnet_dict)

        return magnet_list

    async def save_to_pikpak(self, task_list: list[dict], username: str, password: str):
        client = PikPakApi(username=username, password=password)
        await client.login()
        for task in task_list:
            code = task["code"]
            magnet = task["magnet"]
            res = await client.create_folder(code)
            id = res["file"]["id"]
            res = await client.offline_download(magnet, parent_id=id)
            print(json.dumps(res, indent=4))
            print("=" * 50)
        return
