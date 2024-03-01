from mongoengine import Document, BooleanField, StringField, IntField, ListField, connect
from bs4 import BeautifulSoup
from typing import Union
import re
import json
import requests
from selenium import webdriver


def get_one_movie_info(movie_url: str, uncensored: bool, to_database: bool = False) -> dict:

    # 初始化WebDriver
    browser = webdriver.Edge()
    browser.get(movie_url)

    # 获取页面源代码
    html_source = browser.page_source

    # 使用BeautifulSoup解析
    movie_soup = BeautifulSoup(html_source, "html.parser")
    info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
    if info_panel == None:
        print(f"{movie_url} 未找到影片详情，请检查url")
        return

    print(info_panel)


get_one_movie_info("https://javdb.com/v/zn0RJ", False, False)
