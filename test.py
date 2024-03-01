from mongoengine import Document, BooleanField, StringField, IntField, ListField, connect
from bs4 import BeautifulSoup
from typing import Union
import re
import json
import requests


# 获取给定影片详情页url的信息
def get_one_movie_info(movie_url: str, uncensored: bool) -> dict:
    response = requests.get(movie_url)
    if response.status_code == 200:
        movie_soup = BeautifulSoup(response.text, "html.parser")
    else:
        print("未找到电影网址")
    # 抓取信息
    info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
    if info_panel == None:
        print("未找到影片详情，请检查url")
        return

    # 开始抓取
    movie_info: dict = {"番号": "", "标题": "", "演员": [], "标签": [], "是否无码": uncensored, "磁链": ""}
    cracked = False
    blocks = info_panel.find_all("div", class_="panel-block", recursive=False)
    for block in blocks:
        if block.find("strong"):
            block_name = block.find("strong").text

        if block_name == "番號:":
            first_code = block.find("span").find("a").text
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

    return movie_info


# 获取一个女优的所有影片信息
def get_actor_movie_info(actor_sub_url: str, uncensored: bool) -> list[dict]:
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
    total_pages = len(pagination.find_all("li", recursive=False))

    all_movie_info = []
    # 拼接每页url并获取影片连接
    for i in range(1, total_pages + 1):
        url = f"{url}?page={i}"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        # 获取影片列表中的所有条目
        movie_list = soup.find("div", class_="movie-list h cols-4 vcols-8").find_all("div", class_="item", recursive=False)

        for movie in movie_list:
            # 获取电影详情页面
            movie_sub_url = movie.find("a")["href"]
            movie_url = f"{base_url}{movie_sub_url}"
            all_movie_info.append(get_one_movie_info(movie_url, uncensored))

    return all_movie_info


all_movie_info = get_actor_movie_info("/actors/k4eNz", False)

with open("test.json", "w", encoding="utf-8") as file:
    json.dump(all_movie_info, file, ensure_ascii=False, indent=4)
