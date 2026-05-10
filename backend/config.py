from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'bike_store.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "troque_essa_chave_secreta"
