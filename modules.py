from pydantic import BaseModel, Field, HttpUrl
import requests, time, re, aiohttp, asyncio, os, cv2
from bs4 import BeautifulSoup


class Movie(BaseModel):
    code: str = ""
    title: str = ""
    actors: list[str] = []
    tags: list[str] = []
    uncensored: bool = False
    magnet: str = ""
    url: str = ""
    local_existance: bool = False


class Actor(BaseModel):
    name: str = ""
    second_name: str = ""
    url: str = ""
    uncensored: bool = False
    movie_urls: list[str] = []
    total_movies: int = -1


class MovieManager:
    def __init__(self, movie_path: str = "", capture_path: str = "", time_interval: float = 20) -> None:
        with open("cookie.txt", "r", encoding="utf-8") as file:
            cookie = file.read()

        self.headers: dict = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
            "Cookie": cookie,
        }
        self.time_interval: float = time_interval

        self.movie_path = movie_path
        self.capture_path = capture_path

    async def get_soup(self, url: str):
        with requests.Session() as session:
            response = session.get(url, headers=self.headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        return soup

    async def get_one_movie_info(self, movie_url: str, uncensored: bool = False) -> Movie:
        print(f"开始抓取 {movie_url}")
        movie_soup = await self.get_soup(movie_url)

        try:
            info_panel = movie_soup.find("nav", class_="panel movie-panel-info")
        except AttributeError:  # movie_soup返回None
            print(f"{movie_url} 未获取影片信息，可能是FC2页面登陆失败，请检查cookie是否过期")
            return

        movie_info = Movie()
        movie_info.uncensored = uncensored
        movie_info.url = movie_url
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
                movie_info.code = f"{first_code}{last_code}"

            elif block_name == "類別:":
                tags = block.find_all("a")
                for tag in tags:
                    movie_info.tags.append(tag.text)
                    if tag == "無碼破解":
                        cracked = True

            elif block_name == "演員:":
                if not block.find("div", class_="control ranking-tags"):
                    actors = block.find_all("a")
                    for actor in actors:
                        movie_info.actors.append(actor.text)

        # 获取标题（网页上默认显示的）
        movie_info.title = movie_soup.find("strong", class_="current-title").text

        # 获取磁链，磁链只保存一个优先选无码破解，字幕次之，都没有选第一个
        magnet_list = movie_soup.find_all("div", class_="magnet-name column is-four-fifths")
        if len(magnet_list) > 0:
            if cracked:
                for magnet in magnet_list:
                    magnet_name = magnet.find("span", class_="name").text
                    if re.search("无码", magnet_name):
                        movie_info.magnet = magnet.find("a")["href"]

            # 没有无码破解
            if movie_info.magnet == "":
                for magnet in magnet_list:
                    magnet_tags = magnet.find_all("span", class_="tag is-primary is-small is-light")
                    for magnet_tag in magnet_tags:
                        if re.search("字幕", magnet_tag.text):
                            movie_info.magnet = magnet.find("a")["href"]
                            break

            # 没有无码也没有字幕，找到第一个
            if movie_info.magnet == "":
                movie_info.magnet = magnet_list[0].find("a")["href"]

        await asyncio.sleep(self.time_interval)
        return movie_info

    async def get_one_movie_image(self, movie_url: str, movie_code: str, path: str):
        movie_soup = await self.get_soup(movie_url)
        try:
            cover_url = movie_soup.find("img", class_="video-cover")["src"]
        except AttributeError:
            print("未获取影片信息，可能是FC2页面登陆失败，请检查cookie是否过期")
            return
        with requests.Session() as session:
            response = session.get(cover_url, headers=self.headers)

        with open(f"{path}\\{movie_code}-fanart.jpg", "wb") as file:
            file.write(response.content)
        with open(f"{path}\\{movie_code}-cover.jpg", "wb") as file:
            file.write(response.content)

        await asyncio.sleep(self.time_interval)
        return

    async def get_one_actor_info(self, actor_url: str) -> Actor:
        base_url = "https://javdb.com"

        soup = await self.get_soup(actor_url)

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
            await asyncio.sleep(self.time_interval)

        actor_info = Actor()
        actor_info.name = actor_name
        actor_info.second_name = second_name
        actor_info.url = actor_url
        actor_info.movie_urls = url_list
        actor_info.total_movies = total_movies
        actor_info.uncensored = uncensored

        return actor_info

    async def get_favourite_actors_url(self) -> list[str]:
        soup = await self.get_soup("https://javdb.com/users/collection_actors")

        # 获取收藏演员信息框
        actor_boxes = soup.find_all("div", class_="box actor-box")
        actor_urls = []
        for box in actor_boxes:
            actor_sub_url = box.find("a")["href"]
            actor_urls.append(f"https://javdb.com{actor_sub_url}")

        return actor_urls

    async def search_code_and_get_info(self, code: str, uncensored: bool = False) -> dict:
        base_url = "https://javdb.com"
        search_url = f"https://javdb.com/search?q={code}&f=all"
        soup = await self.get_soup(search_url)

        movie_container = soup.find("div", class_="movie-list h cols-4 vcols-8")
        if not movie_container:
            movie_container = soup.find("div", class_="movie-list h cols-4 vcols-5")
        if not movie_container:
            print("搜索无结果")
            return
        movie = movie_container.find("div", class_="item", recursive=False)
        sub_url = movie.find("a")["href"]

        movie_info = await self.get_one_movie_info(f"{base_url}{sub_url}", uncensored)
        return movie_info

    async def get_file_list(self, path: str, size_threshold: int = 524288000):
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

    async def generate_nfo(self, movie_info: dict, path: str):
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
