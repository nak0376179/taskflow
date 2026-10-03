"""TaskFlow のバックエンド。REST (/api) と MCP (/mcp) を 1 つのプロセスで出す。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp.utilities.lifespan import combine_lifespans

from . import bootstrap, mcp_server
from .api import router
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    bootstrap.run()
    yield


mcp_app = mcp_server.build().http_app(path="/mcp")

app = FastAPI(title="TaskFlow", lifespan=combine_lifespans(app_lifespan, mcp_app.lifespan))
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


# /mcp と OAuth の保護リソースのメタデータ (/.well-known/...) は FastMCP 側。
# 上の FastAPI のルートが先に一致するので、ルートにマウントしてよい
app.mount("/", mcp_app)
