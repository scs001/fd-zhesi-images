"""哲思门面 API（骨架期）。

/healthz 探活、/api/version 版本。骨架期 CORS 全开（照 fd-lex 骨架先例），
接线期收敛。个人层 API（立场卡等，task 3.x）后续在此挂载。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .cards import router as cards_router
from .contract import router as contract_router
from .loops import router as loops_router
from .synthesis import router as synthesis_router

app = FastAPI(title="fd-zhesi-api", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards_router)
app.include_router(contract_router)
app.include_router(loops_router)
app.include_router(synthesis_router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "fd-zhesi-api", "version": __version__}


@app.get("/api/version")
def version() -> dict:
    return {"service": "fd-zhesi-api", "version": __version__}
