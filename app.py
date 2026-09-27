import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

FAL_API_BASE = "https://queue.fal.run"
TOKEN = os.environ.get("FAL_TOKEN", "")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

app = FastAPI(title="fal-proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def get_token(request: Request) -> str:
    if TOKEN:
        return TOKEN
    h = request.headers.get("Authorization", "")
    if h.startswith("Key "):
        return h[4:].strip()
    return h.strip()


@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok", "service": "fal-proxy", "upstream": FAL_API_BASE}


@app.post("/v1/videos")
async def create_video(request: Request):
    token = get_token(request)
    if not token:
        return JSONResponse({"error": "Token fal.ai manquant"}, status_code=401)

    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"JSON invalide : {str(e)}"}, status_code=400)

    model_endpoint = body.get("model", "fal-ai/minimax/video-01")
    prompt = body.get("prompt", "")
    if not prompt:
        return JSONResponse({"error": "Prompt manquant"}, status_code=400)

    url = f"{FAL_API_BASE}/{model_endpoint}"
    payload = {"prompt": prompt}
    for key in ["aspect_ratio", "duration", "resolution", "seed", "prompt_optimizer"]:
        if key in body:
            payload[key] = body[key]

    headers = {
        "Authorization": f"Key {token}",
        "Content-Type": "application/json",
        "User-Agent": UA,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20)) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code in (200, 201, 202):
                return JSONResponse(r.json(), status_code=r.status_code)
            else:
                err = r.text[:300]
                return JSONResponse(
                    {"error": f"fal.ai HTTP {r.status_code}", "detail": err},
                    status_code=r.status_code,
                )
    except Exception as e:
        return JSONResponse({"error": f"Erreur : {str(e)}"}, status_code=502)


@app.get("/v1/videos/{request_id}")
async def get_video_status(request_id: str, request: Request):
    token = get_token(request)
    if not token:
        return JSONResponse({"error": "Token fal.ai manquant"}, status_code=401)

    url = f"{FAL_API_BASE}/fal-ai/minimax/video-01/requests/{request_id}/status"
    headers = {"Authorization": f"Key {token}", "User-Agent": UA}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return JSONResponse(r.json(), status_code=200)
            else:
                err = r.text[:200]
                return JSONResponse(
                    {"error": f"fal.ai status HTTP {r.status_code}", "detail": err},
                    status_code=r.status_code,
                )
    except Exception as e:
        return JSONResponse({"error": f"Erreur : {str(e)}"}, status_code=502)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
