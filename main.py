from fastapi import FastAPI

from api import router
from admin import router as admin_router
from web import router as web_router


app = FastAPI()
app.include_router(router)
app.include_router(admin_router)
app.include_router(web_router)
