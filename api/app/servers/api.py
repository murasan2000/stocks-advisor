from fastapi import FastAPI

app = FastAPI(
    title="Stocks Advanced API",
    version="1.0.0",
    description="An advanced API for stock market data and analysis.",
)

@app.get("/hello-world")
async def hello_world():
    return {"message": "Hello, World!"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)