import os


class Settings:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    pedidos_url = os.getenv("PEDIDOS_URL", "http://localhost:8003").rstrip("/")


settings = Settings()
