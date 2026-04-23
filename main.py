from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import router
from admin import router as admin_router
from web import router as web_router


app = FastAPI()
app.include_router(router)
app.include_router(admin_router)
app.include_router(web_router)

PICTURE_DIR = Path(__file__).resolve().parent / "picture"
PICTURE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/picture", StaticFiles(directory=str(PICTURE_DIR)), name="picture")
