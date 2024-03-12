from pydantic import BaseModel, Field, HttpUrl


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
    movie_urls: list[HttpUrl] = []
    total_movies: int = -1
