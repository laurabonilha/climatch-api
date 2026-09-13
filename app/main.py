from fastapi import FastAPI
from app.database import Base, engine
from app import models  # importa mesmo sem usar diretamente — é isso que "registra" a tabela

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Climatch API")

@app.get("/health")
def health_check():
    return {"status": "ok"}