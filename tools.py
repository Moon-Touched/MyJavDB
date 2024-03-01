from mongoengine import Document, BooleanField, StringField, IntField, ListField, NotUniqueError
import time
from bs4 import BeautifulSoup
from typing import Union
import json
import re
import requests


class Movie(Document):
    code = StringField(required=True, unique=True)
    title = StringField(required=True)
    actors = ListField(StringField())
    tags = ListField(StringField())
    uncensored = BooleanField(required=True)
    magnet = StringField(required=True)
    url = StringField(required=True)


class Scraper:
    def get_favorite_actors(
        self, save_info: bool = False, save_avatar: bool = False, avatar_path: str = ""
    ) -> dict[str, dict[str, Union[str, bool]]]:
        # 打开收藏演员页面的html
        with open("favourite actors.html", "r", encoding="utf-8") as file:
            html_content = file.read()

        # 使用BeautifulSoup解析HTML内容
        soup = BeautifulSoup(html_content, "html.parser")

        # 获取演员信息框
        actor_boxes = soup.find_all("div", class_="box actor-box")
        actor_info: dict[str, dict[str, Union[str, bool]]] = {}
        for box in actor_boxes:
            actor_name = box.find("strong").text
            actor_sub_url = box.find("a")["href"]
            if box.find("span") != None:
                uncensored = True
                actor_name = f"{actor_name}_无码"
            else:
                uncensored = False
            actor_info[actor_name] = {"actor_sub_url": actor_sub_url, "uncensored": uncensored}
            # 如果需要就保存头像，头像需要设置保存路径
            if save_avatar:
                # 检查头像存储路径
                if avatar_path == "":
                    raise ValueError("avatar_path 不能为空")
                avatar_url = box.find("img")["src"]
                response = requests.get(avatar_url)
                if response.status_code == 200:
                    with open(f"{avatar_path}/{actor_name}.jpg", "wb") as file:
                        file.write(response.content)

        # 如果需要就保存为json格式，之后可以从文件中读取。
        if save_info:
            with open("actor_info.json", "w", encoding="utf-8") as file:
                json.dump(actor_info, file, ensure_ascii=False, indent=4)

        return actor_info

    # 获取给定影片详情页url的信息
    def get_one_movie_info(self, movie_url: str, uncensored: bool, to_database: bool = False) -> dict:
        response = requests.get(movie_url)
        if response.status_code == 200:
            movie_soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到电影网址")

        movie_info: dict = {
            "番号": "",
            "标题": "",
            "演员": [],
            "标签": [],
            "是否无码": uncensored,
            "磁链": "",
            "网址": movie_url,
        }

        # 抓取信息
        info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
        if info_panel == None:
            print(f"{movie_url} 未找到影片详情，请检查url")
            return

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
        self, time_interval: float, actor_sub_url: str, uncensored: bool, to_database: bool = False
    ) -> list[dict]:
        # 拼接演员页面url(同时也是演员页面首页)
        base_url = "https://javdb.com"
        url = f"{base_url}{actor_sub_url}"

        # 获取html
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            print("未找到女优网址")

        # 获取一共有几页
        pagination = soup.find("ul", class_="pagination-list")
        if not pagination:
            total_pages = 1
        else:
            total_pages = len(pagination.find_all("li", recursive=False))

        all_movie_info = []
        # 拼接每页url并获取影片连接
        for i in range(1, total_pages + 1):
            page_url = f"{url}?page={i}"
            response = requests.get(page_url)
            soup = BeautifulSoup(response.text, "html.parser")

            # 获取影片列表中的所有条目
            movie_container = soup.find("div", class_="movie-list h cols-4 vcols-8")
            if not movie_container:
                movie_container = soup.find("div", class_="movie-list h cols-4 vcols-5")
            movie_list = movie_container.find_all("div", class_="item", recursive=False)

            for movie in movie_list:
                # 获取电影详情页面
                movie_sub_url = movie.find("a")["href"]
                movie_url = f"{base_url}{movie_sub_url}"
                all_movie_info.append(self.get_one_movie_info(movie_url, uncensored, to_database))
                time.sleep(time_interval)

        return all_movie_info

    def write_to_MongoDB(self, info: dict):
        try:
            # 尝试创建并保存一个新的Movie实例
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
        except NotUniqueError:
            # 如果出现NotUniqueError，说明存在重复条目，此处可以记录日志或者简单跳过
            print(f"出现重复条目{info['番号']}，已跳过。")
        return
