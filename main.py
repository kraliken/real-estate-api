from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import create_db_and_tables
from contextlib import asynccontextmanager
from routers import real_estate


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(real_estate.router, prefix="/api/v1")
