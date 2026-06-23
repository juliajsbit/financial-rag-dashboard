from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
from app.core.tracing import enable_langsmith

settings = get_settings()

# Trace live chat requests to LangSmith when configured (no-op without a key).
if enable_langsmith("financial-rag-app"):
    print("LangSmith tracing enabled")

app = FastAPI(
    title="Financial RAG Dashboard API",
    description="LLM-powered Q&A over real financial data",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
