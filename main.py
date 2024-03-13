from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from settings import MongoDB_Setting
from api.movie_api import movie_api
from api.filter_api import filter_api
from api.manager_api import manager_api
import motor
import uvicorn


client = motor.motor_asyncio.AsyncIOMotorClient(MongoDB_Setting["host"])
database = client[MongoDB_Setting["db"]]
movie_collection = database.get_collection("movie")

app = FastAPI()
app.include_router(movie_api, prefix="/movie")
app.include_router(filter_api, prefix="/filter")
app.include_router(manager_api, prefix="/manager")


@app.get("/")
async def root():
    return {"welcome"}


if __name__ == "__main__":

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
