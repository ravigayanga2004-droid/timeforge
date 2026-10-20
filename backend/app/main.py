from fastapi import FastAPI

app = FastAPI(title="TimeForge", version="1.0.0")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "timeforge"}
