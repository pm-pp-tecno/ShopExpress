import os


class Settings:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    usuarios_url = os.getenv("USUARIOS_URL", "http://localhost:8001").rstrip("/")
    catalogo_url = os.getenv("CATALOGO_URL", "http://localhost:8002").rstrip("/")


settings = Settings()
