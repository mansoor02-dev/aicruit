"""FastAPI application composition and stable ASGI entry point."""

import logging

from fastapi import FastAPI

from .api.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Interview Report Generator",
    description="LLM-powered interview report generation.",
    version="2.1.0",
)
app.include_router(router)
