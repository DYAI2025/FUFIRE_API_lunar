import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("bazi_engine.app:app", host="0.0.0.0", port=port, log_level="info")
