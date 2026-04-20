from fastapi import FastAPI
from bridge.router import router

app = FastAPI()
app.include_router(router)
