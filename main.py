from fastapi import FastAPI

app = FastAPI(title="Weather Risk API")

@app.get("/health")
def health_check():
    return {"status": "ok"}
