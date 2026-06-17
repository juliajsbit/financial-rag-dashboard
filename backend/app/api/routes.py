from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from app.services.rag import stream_answer, get_sources
from app.services.ingestion import ingest_ticker
import yfinance as yf
import json

router = APIRouter()


# -- Request / Response models ----------------------------------------------

class ChatRequest(BaseModel):
    question: str
    tickers: Optional[List[str]] = []


class IngestRequest(BaseModel):
    ticker: str
    period: str = "3mo"  # 1mo, 3mo, 6mo, 1y


class TickerPriceResponse(BaseModel):
    ticker: str
    prices: List[dict]  # [{date, open, close, high, low, volume}]
    info: dict


# -- Chat - streaming SSE ---------------------------------------------------

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream LLM answer as Server-Sent Events."""
    async def generate():
        try:
            async for token in stream_answer(req.question):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/sources")
async def chat_sources(req: ChatRequest):
    """Return source documents for a question (for citations UI)."""
    try:
        sources = await get_sources(req.question)
        return {"sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -- Data ingestion ---------------------------------------------------------

@router.post("/ingest")
async def ingest(req: IngestRequest):
    """Fetch + embed + store data for a ticker."""
    try:
        count = await ingest_ticker(req.ticker.upper(), req.period)
        return {"ticker": req.ticker.upper(), "documents_stored": count, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -- Price data for charts --------------------------------------------------

@router.get("/prices/{ticker}")
async def get_prices(ticker: str, period: str = "3mo"):
    """Return OHLCV price history for charting."""
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=period)
        info = stock.info

        prices = [
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "close": round(row["Close"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "volume": int(row["Volume"]),
            }
            for date, row in hist.iterrows()
        ]

        return {
            "ticker": ticker.upper(),
            "prices": prices,
            "info": {
                "name": info.get("longName", ticker),
                "sector": info.get("sector"),
                "marketCap": info.get("marketCap"),
                "currentPrice": info.get("currentPrice"),
                "pe": info.get("trailingPE"),
                "week52High": info.get("fiftyTwoWeekHigh"),
                "week52Low": info.get("fiftyTwoWeekLow"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
