from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/healthz")
def health_check():
    return {"status": "healthy", "module": "api_layer"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)