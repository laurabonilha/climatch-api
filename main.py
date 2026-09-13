from fastapi import FastAPI

app = FastAPI(title="Climatch API", description="API para consulta de clima e armazenamento de resultados", version="1.0.0")

@app.get("/health")
def health_check():
    return {"status": "ok"}
