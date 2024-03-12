from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from settings import MongoDB_Setting
from api.movie import movie_api
from api.filter import filter_api
import motor.motor_asyncio


client = motor.motor_asyncio.AsyncIOMotorClient(MongoDB_Setting["host"])
database = client[MongoDB_Setting["db"]]
movie_collection = database.get_collection("movie")

app = FastAPI()
app.include_router(movie_api, prefix="/movie")
app.include_router(filter_api, prefix="/filter")


@app.get("/")
async def root():
    return {"welcome"}


# if __name__ == '__main__':
#     import uvicorn

#     uvicorn.run("main:app", host="127.0.0.1", port=8000,  reload=True)
