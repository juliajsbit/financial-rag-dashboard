import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from app.core.config import get_settings

settings = get_settings()


def fetch_ticker_data(ticker: str, period: str = "3mo") -> List[Document]:
    """Fetch stock data from Yahoo Finance and convert to LangChain Documents."""
    stock = yf.Ticker(ticker)
    
    # Price history
    hist = stock.history(period=period)
    info = stock.info
    
    docs = []

    # One document per week of price data
    hist.index = pd.to_datetime(hist.index)
    weekly = hist.resample("W").agg({
        "Open": "first",
        "Close": "last",
        "High": "max",
        "Low": "min",
        "Volume": "sum",
    }).dropna()

    for date, row in weekly.iterrows():
        change_pct = ((row["Close"] - row["Open"]) / row["Open"]) * 100
        content = (
            f"{ticker} week ending {date.strftime('%Y-%m-%d')}: "
            f"open ${row['Open']:.2f}, close ${row['Close']:.2f}, "
            f"high ${row['High']:.2f}, low ${row['Low']:.2f}, "
            f"volume {int(row['Volume']):,}, "
            f"weekly change {change_pct:+.1f}%."
        )
        docs.append(Document(
            page_content=content,
            metadata={"ticker": ticker, "date": date.isoformat(), "type": "price_history"},
        ))

    # Company summary document
    name = info.get("longName", ticker)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    market_cap = info.get("marketCap", 0)
    summary = info.get("longBusinessSummary", "")
    pe_ratio = info.get("trailingPE", "N/A")
    week_52_high = info.get("fiftyTwoWeekHigh", "N/A")
    week_52_low = info.get("fiftyTwoWeekLow", "N/A")

    company_doc = Document(
        page_content=(
            f"{name} ({ticker}) is a {sector} company in {industry}. "
            f"Market cap: ${market_cap:,}. "
            f"P/E ratio: {pe_ratio}. "
            f"52-week range: ${week_52_low} - ${week_52_high}. "
            f"{summary[:500]}"
        ),
        metadata={"ticker": ticker, "type": "company_info"},
    )
    docs.append(company_doc)

    return docs


def get_vectorstore() -> PGVector:
    """Return a PGVector instance connected to our database."""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return PGVector(
        embeddings=embeddings,
        collection_name="financial_docs",
        connection=settings.database_url,
    )


async def ingest_ticker(ticker: str, period: str = "3mo") -> int:
    """Fetch + embed + store documents for a ticker. Returns doc count."""
    docs = fetch_ticker_data(ticker, period)
    vectorstore = get_vectorstore()
    vectorstore.add_documents(docs)
    return len(docs)
