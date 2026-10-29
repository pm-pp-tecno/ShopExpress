import os


class Settings:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "shopexpress")


settings = Settings()
