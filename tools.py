from mongoengine import Document, BooleanField, StringField, IntField, ListField, connect


class Movie(Document):
    code = StringField(required=True)
    title = StringField(required=True)
    actors = ListField(StringField(), required=True)
    tags = ListField(StringField(), required=True)
    uncensored = BooleanField(required=True)
    magnet = ListField(StringField(), required=True)


class Scraper:
    def get_favorite_actors(url: str) -> dict[str, str]:

        return
