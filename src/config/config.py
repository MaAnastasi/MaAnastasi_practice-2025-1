import os
from dotenv import load_dotenv
from pydantic import BaseModel

class Config(BaseModel):
    BOT_TOKEN: str

def load_config(path: str) -> Config:
    load_dotenv(path)
    return Config(BOT_TOKEN=os.getenv('BOT_TOKEN'))
