from mongoengine import Document, BooleanField, StringField, IntField, ListField, NotUniqueError, connect
from pymongo.errors import ServerSelectionTimeoutError
from bs4 import BeautifulSoup
from typing import Union
from error import CookieUnavailableError, UrlRequestFailedError, NoneObjectError
from webdav3.client import Client
from pathlib import Path
import json, re, os, requests, time, copy, sys, urllib.parse, shutil, cv2


class Movie(Document):
    code = StringField(required=True)
    title = StringField(required=True)
    actors = ListField(StringField())
    tags = ListField(StringField())
    uncensored = BooleanField(required=True)
    magnet = StringField(required=True)
    url = StringField(required=True, unique=True)


class Actor(Document):
    name = StringField(required=True)
    second_name = StringField(required=True)
    url = StringField(required=True, unique=True)
    uncensored = BooleanField(required=True)
    total_movies = IntField(required=True)


class Scraper:
    def __init__(self, time_interval: float = 20, save_avatar: bool = False, avatar_path: str = "") -> None:
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
        self.save_avatar: bool = save_avatar
        self.avatar_path: str = avatar_path
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
        }

    # 根据番号搜索并抓取电影信息
    def search_code(self, code: str, uncensored: bool = False) -> dict:
        base_url = "https://javdb.com"
        search_url = f"https://javdb.com/search?q={code}&f=all"
        with requests.Session() as session:
            try:
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
    def search_actor(self, actor_name: str) -> dict:
        search_url = f"https://javdb.com/search?q={actor_name}&f=actor"
        with requests.Session() as session:
            try:
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

    # 获取收藏列表中所有演员的信息
    def get_favorite_actors_info(self, from_url: bool = True, is_update: bool = False) -> dict:
        # 使用cookie登录收藏页面
        if from_url:
            with requests.Session() as session:
                try:
                    response = session.get("https://javdb.com/users/collection_actors", headers=self.headers)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                    else:
                        raise UrlRequestFailedError("演员收藏页面连接失败")
                except UrlRequestFailedError as e:
                    print(e)
                    return

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

    # 获取单个演员的信息
    def get_one_actor_info(self, actor_url: str) -> dict:
        try:
            response = requests.get(actor_url, self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError(f"{actor_url} 请求失败")
        except UrlRequestFailedError as e:
            print(e)
            return

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
        i = 1
        while True:
            page_url = f"{actor_url}?page={i}"
            response = requests.get(page_url, self.headers)
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
            i = i + 1
            time.sleep(self.time_interval)

        actor_info = copy.deepcopy(self.actor_info_template)
        actor_info["name"] = actor_name
        actor_info["second_name"] = second_name
        actor_info["url"] = actor_url
        actor_info["total_movies"] = total_movies
        actor_info["uncensored"] = uncensored
        # 如果需要就保存头像，头像需要设置保存路径
        if self.save_avatar:
            # 检查头像存储路径
            if self.avatar_path == "":
                print("avatar_path 不能为空，未保存")
            else:
                style = soup.find("span", class_="avatar")["style"]
                start = style.find("url(") + 4  # 加4是因为要跳过"url("这四个字符
                end = style.find(")", start)
                avatar_url = style[start:end]

                response = requests.get(avatar_url, self.headers)
                if response.status_code == 200:
                    with open(f"{self.avatar_path}/{actor_name}.jpg", "wb") as file:
                        file.write(response.content)

        self.write_actor(actor_info)

        return actor_info

    # 获取给定影片详情页url的信息
    def get_one_movie_info(self, movie_url: str, uncensored: bool) -> dict:
        movie_soup = self.get_one_movie_soup(movie_url)

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

    # 获取一个演员的所有影片
    def get_actor_all_movie_info(self, actor_url: str, uncensored: bool) -> list[dict]:

        base_url = "https://javdb.com"

        # 获取html
        try:
            response = requests.get(actor_url, headers=self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError("未找到演员网址")
        except UrlRequestFailedError as e:
            print(e)
            return

        all_movie_info = []
        i = 1
        # 拼接每页url并获取影片连接
        while True:
            page_url = f"{actor_url}?page={i}"
            try:
                response = requests.get(page_url, headers=self.headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                else:
                    raise UrlRequestFailedError(f"未找演员的第{i}页网址，已停止")
            except UrlRequestFailedError as e:
                print(e)
                break

            soup = BeautifulSoup(response.text, "html.parser")
            if soup.find("div", class_="empty-message"):
                break

            # 获取影片列表中的所有条目
            movie_container = soup.find("div", class_="movie-list h cols-4 vcols-8")
            if not movie_container:
                movie_container = soup.find("div", class_="movie-list h cols-4 vcols-5")

            movie_list = movie_container.find_all("div", class_="item", recursive=False)

            for movie in movie_list:
                # 获取电影详情页面
                movie_sub_url = movie.find("a")["href"]
                movie_url = f"{base_url}{movie_sub_url}"

                exist_movie = Movie.objects(url=movie_url).first()
                if exist_movie:
                    print(f"出现重复影片{exist_movie.code}，已跳过。")
                    continue

                all_movie_info.append(self.get_one_movie_info(movie_url, uncensored))
                if not self.cookie_available:
                    print("cookie失效，提前返回")
                    return all_movie_info
            i = i + 1
            time.sleep(self.time_interval)

        return all_movie_info

    def get_one_movie_image(self, movie_url: str, movie_code: str, path: str):

        movie_soup = self.get_one_movie_soup(movie_url)
        try:
            cover_url = movie_soup.find("img", class_="video-cover")["src"]
        except AttributeError:
            print("未获取影片信息，可能是FC2页面登陆失败，请检查cookie是否过期")
            return

        response = requests.get(cover_url, self.headers)

        with open(f"{path}\\{movie_code}-fanart.jpg", "wb") as file:
            file.write(response.content)
        image = cv2.imread(f"{path}\\{movie_code}-fanart.jpg")
        cover = image[:, 425:]
        if cover.shape[0] > 0 and cover.shape[1] > 0:
            cv2.imwrite(f"{path}\\{movie_code}-cover.jpg", cover)
        else:
            cv2.imwrite(f"{path}\\{movie_code}-cover.jpg", image)
        time.sleep(self.time_interval)
        return

    # 获取影片详情页html，供调用
    def get_one_movie_soup(self, movie_url: str):
        try:
            response = requests.get(movie_url, headers=self.headers)
            if response.status_code == 200:
                movie_soup = BeautifulSoup(response.text, "html.parser")
            else:
                raise UrlRequestFailedError("未找到电影网址")
        except UrlRequestFailedError as e:
            print(e)
            return

        login_message = movie_soup.find("div", class_="message-header")
        # 有登陆提示，说明是FC2，尝试cookie
        if login_message != None:
            session = requests.Session()
            response = session.get(movie_url, headers=self.headers)
            movie_soup = BeautifulSoup(response.text, "html.parser")

            login_message = movie_soup.find("div", class_="message-header")
        time.sleep(self.time_interval)
        return movie_soup

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
            return

        # 如果还获取不到
        if info_panel == None:
            return False
        else:
            return True


class Movie_Manager:
    def __init__(self, scraper: Scraper, use_mongoDB: bool = True) -> None:
        if use_mongoDB:
            connect(db="MyJavDB", host="mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            try:
                Movie.objects.count()
            except ServerSelectionTimeoutError:
                print("连接失败：无法连接到MongoDB服务器")
                sys.exit(1)

        self.scraper = scraper
        # self.options = {
        #     "webdav_hostname": "",
        #     "webdav_login": "",
        #     "webdav_password": "",
        #     "disable_check": ,
        # }
        # self.client = Client(self.options)
        # self.client.verify = False

    def get_need_capture_movie_files(self, path: str = "E:\\啊啊啊\\to be capture", size_threshold: int = 524288000):
        files = []
        for root, dirs, file_names in os.walk(path):
            for file_name in file_names:
                file_path = os.path.join(root, file_name)
                if os.path.getsize(file_path) > size_threshold:
                    name, _, ext = file_name.rpartition(".")
                    name = self.check_file_name(name)
                    if name:
                        new_file_name = f"{name}.{ext}"
                        new_file_path = os.path.join(root, new_file_name)
                        os.rename(file_path, new_file_path)
                        files.append(new_file_path)
        return files

    def check_file_name(self, file_name):
        # 删除[]及其中内容
        file_name = re.sub(r"\[.*?\]", "", file_name)
        # 删除@及其之前的内容
        file_name = re.sub(r"^.*?@", "", file_name)
        if file_name[-2:] == "-C" or file_name[-2:] == "-c":
            file_name = file_name[:-2]
        # 检查文件名是否只包含字母、数字和连字符
        valid_chars = re.compile(r"^[A-Za-z0-9\-]+$")
        if not valid_chars.match(file_name):
            print(f"{file_name}不合法")
            return None

        return file_name.upper()

    def match_info(self, path: str = "E:\\啊啊啊\\to be capture"):
        files = self.get_need_capture_movie_files(path)
        for file in files:
            file_name = file.split("\\")[-1]
            code, _, ext = file_name.rpartition(".")
            db_item = Movie.objects(code=code).first()
            if db_item == None:
                print("数据库中没有相应数据，开始抓取")
                movie_info = self.scraper.search_code(code)
            else:
                movie_info = db_item.to_mongo().to_dict()

            target_folder = os.path.join(path.rpartition("\\")[0], "done", ",".join(movie_info["actors"]), f"{code}{movie_info['title']}")
            if target_folder[-1] == " ":
                target_folder = target_folder[:-1]
                if not os.path.exists(target_folder):
                    os.makedirs(target_folder)
            target_file = f"{target_folder}\\{file_name}"
            self.generate_nfo(movie_info, target_folder)
            self.scraper.get_one_movie_image(movie_url=movie_info["url"], movie_code=movie_info["code"], path=target_folder)

            os.rename(file, target_file)
        return

    def generate_nfo(self, movie_info: dict, path: str):
        nfo_content = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<movie>\n'
        nfo_content += f"<title>{movie_info['code']}{movie_info['title']}</title>\n"
        for tag in movie_info["tags"]:
            nfo_content += f"<genre>{tag}</genre>\n"

        for tag in movie_info["tags"]:
            nfo_content += f"<tag>{tag}</tag>\n"

        nfo_content += "<actor>\n"
        for actor in movie_info["actors"]:
            nfo_content += f"<name>{actor}</name>\n"

        nfo_content += "</actor>\n"
        nfo_content += "</movie>\n"

        with open(f"{path}\\{movie_info['code']}.nfo", "w", encoding="utf-8") as file:
            file.write(nfo_content)
        return

    def get_magnet_links_by_actor(self, actor: str, path: str = "E:\\啊啊啊"):
        magnet_list = []
        movies = Movie.objects(actors=actor)
        file_list = []
        for root, dirs, files in os.walk(path):
            for file in files:
                name, ext = os.path.splitext(file)
                new_name = self.check_file_name(name)
                if new_name:
                    file_list.append(new_name)

        for movie in movies:
            code = movie.code
            if code in file_list:
                print(f"{code}已有本地文件")
                continue
            else:
                magnet_list.append(f"{movie.magnet}\n")
        with open(f"{path}\\{actor}.txt", "w", encoding="utf-8") as file:
            file.write("".join(magnet_list))
        return
