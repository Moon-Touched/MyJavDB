from mongoengine import Document, BooleanField, StringField, IntField, ListField, NotUniqueError
import time
from bs4 import BeautifulSoup
from typing import Union
import json
import re
import requests


class Movie(Document):
    code = StringField(required=True)
    title = StringField(required=True)
    actors = ListField(StringField())
    tags = ListField(StringField())
    uncensored = BooleanField(required=True)
    magnet = StringField(required=True)
    url = StringField(required=True)


class Scraper:
    def __init__(self, cookie: str = "", time_interval: float = 1) -> None:
        self.headers: dict = {"Cookie": cookie}
        self.time_interval: float = time_interval
        return

    def get_favorite_actors(self, save_info: bool = False, save_avatar: bool = False, avatar_path: str = "") -> dict:
        # 打开收藏演员页面的html
        with open("favourite actors.html", "r", encoding="utf-8") as file:
            html_content = file.read()

        # 使用BeautifulSoup解析HTML内容
        soup = BeautifulSoup(html_content, "html.parser")

        # 获取收藏演员信息框
        actor_boxes = soup.find_all("div", class_="box actor-box")
        all_actor_info: dict = {}
        for box in actor_boxes:
            actor_sub_url = box.find("a")["href"]
            actor_url = f"https://javdb.com{actor_sub_url}"
            actor_info = self.get_actor_info(actor_url, save_avatar, avatar_path)
            all_actor_info.update(actor_info)

        # 如果需要就保存为json格式，之后可以从文件中读取。
        if save_info:
            with open("actor_info.json", "w", encoding="utf-8") as file:
                json.dump(all_actor_info, file, ensure_ascii=False, indent=4)

        return all_actor_info

    def get_actor_info(self, actor_url: str, save_avatar: bool = False, avatar_path: str = ""):
        response = requests.get(actor_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到演员网址")

        actor_info: dict = {}
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
            response = requests.get(page_url)
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

        actor_info[actor_name] = {
            "second_name": second_name,
            "actor_url": actor_url,
            "uncensored": uncensored,
            "total_movies": total_movies,
        }
        # 如果需要就保存头像，头像需要设置保存路径
        if save_avatar:
            # 检查头像存储路径
            if avatar_path == "":
                raise ValueError("avatar_path 不能为空")
            style = soup.find("span", class_="avatar")["style"]
            start = style.find("url(") + 4  # 加4是因为要跳过"url("这四个字符
            end = style.find(")", start)
            avatar_url = style[start:end]

            response = requests.get(avatar_url)
            if response.status_code == 200:
                with open(f"{avatar_path}/{actor_name}.jpg", "wb") as file:
                    file.write(response.content)
        print(actor_info)
        return actor_info

    # 获取给定影片详情页url的信息
    def get_one_movie_info(self, movie_url: str, uncensored: bool, to_database: bool = False) -> dict:
        response = requests.get(movie_url)
        if response.status_code == 200:
            movie_soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到电影网址")

        # FC2需要登陆才能查看，如果获取不到就尝试使用cookie登录
        info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
        if info_panel == None:
            with requests.Session() as session:
                if self.headers["Cookie"] != "":
                    response = session.get(movie_url, headers=self.headers)
                    movie_soup = BeautifulSoup(response.text, "html.parser")
                    info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
                # 如果还获取不到
                if info_panel == None:
                    print(f"{movie_url} 未找到影片详情，请检查url")
                    return

        movie_info: dict = {
            "番号": "",
            "标题": "",
            "演员": [],
            "标签": [],
            "是否无码": uncensored,
            "磁链": "",
            "网址": movie_url,
        }

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
                movie_info["番号"] = f"{first_code}{last_code}"

            elif block_name == "類別:":
                tags = block.find_all("a")
                for tag in tags:
                    movie_info["标签"].append(tag.text)
                    if tag == "無碼破解":
                        cracked = True

            elif block_name == "演員:":
                actors = block.find_all("a")
                for actor in actors:
                    movie_info["演员"].append(actor.text)

        # 获取标题（网页上默认显示的）
        movie_info["标题"] = movie_soup.find("strong", class_="current-title").text

        # 获取磁链，磁链只保存一个优先选无码破解，字幕次之，都没有选第一个
        magnet_list = movie_soup.find_all("div", class_="magnet-name column is-four-fifths")
        if len(magnet_list) > 0:
            if cracked:
                for magnet in magnet_list:
                    magnet_name = magnet.find("span", class_="name").text
                    if re.search("无码", magnet_name):
                        movie_info["磁链"] = magnet.find("a")["href"]

            # 没有无码破解
            if movie_info["磁链"] == "":
                for magnet in magnet_list:
                    magnet_tags = magnet.find_all("span", class_="tag is-primary is-small is-light")
                    for magnet_tag in magnet_tags:
                        if re.search("字幕", magnet_tag.text):
                            movie_info["磁链"] = magnet.find("a")["href"]
                            break

            # 没有无码也没有字幕，找到第一个
            if movie_info["磁链"] == "":
                movie_info["磁链"] = magnet_list[0].find("a")["href"]

        if to_database:
            self.write_to_MongoDB(movie_info)
        return movie_info

    # 获取一个演员的所有影片
    def get_actor_movie_info(
        self,  actor_url: str, uncensored: bool, to_database: bool = False
    ) -> list[dict]:

        base_url = "https://javdb.com"

        # 获取html
        response = requests.get(actor_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到演员网址")

        all_movie_info = []
        i = 1
        # 拼接每页url并获取影片连接
        while True:
            page_url = f"{actor_url}?page={i}"
            response = requests.get(page_url)
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
                    #print(f"出现重复条目{exist_movie.code}，已跳过。")
                    continue

                all_movie_info.append(self.get_one_movie_info(movie_url, uncensored, to_database))
                time.sleep(self.time_interval)
            i = i + 1

        return all_movie_info

    def write_to_MongoDB(self, info: dict):
        # 创建并保存一个新的Movie实例
        new_movie = Movie(
            code=info["番号"],
            title=info["标题"],
            actors=info["演员"],
            tags=info["标签"],
            uncensored=info["是否无码"],
            magnet=info["磁链"],
            url=info["网址"],
        )
        new_movie.save()
        return
    
    def check_movie_count(self,actor_url:str)->int:

        base_url = "https://javdb.com"

        # 获取html
        response = requests.get(actor_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到演员网址")

        i = 1
        # 拼接每页url并获取影片连接
        while True:
            page_url = f"{actor_url}?page={i}"
            response = requests.get(page_url)
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
                if exist_movie==None:
                    print(f"{movie_url} 在数据库中未找到")
                    continue

                time.sleep(self.time_interval)
            i = i + 1
