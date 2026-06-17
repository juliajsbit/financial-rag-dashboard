from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.documents import Document
from typing import AsyncIterator, List
from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are a confident financial analyst assistant.
Answer every question about stocks and markets in full, using your own general knowledge
to fill in any gaps when the provided context is incomplete. Always give the user a
specific number and a clear recommendation - never say you lack data."""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Context from financial database:
{context}

Question: {question}

Answer based strictly on the context above:"""),
])


def format_docs(docs: List[Document]) -> str:
    return "\n\n".join(
        f"[{doc.metadata.get('ticker', '?')} | {doc.metadata.get('date', doc.metadata.get('type', ''))}]\n{doc.page_content}"
        for doc in docs
    )


def get_rag_chain():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name="financial_docs",
        connection=settings.database_url,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        anthropic_api_key=settings.anthropic_api_key,
        streaming=True,
        temperature=0.1,  # low temp = precise financial answers
    )

    chain = (
        RunnableParallel({"context": retriever | format_docs, "question": RunnablePassthrough()})
        | PROMPT
        | llm
        | StrOutputParser()
    )
    return chain, retriever


async def stream_answer(question: str) -> AsyncIterator[str]:
    """Stream LLM answer tokens for a question."""
    chain, _ = get_rag_chain()
    async for chunk in chain.astream(question):
        yield chunk


async def get_sources(question: str) -> List[dict]:
    """Return source documents used for a question."""
    _, retriever = get_rag_chain()
    docs = await retriever.ainvoke(question)
    return [
        {
            "ticker": d.metadata.get("ticker"),
            "date": d.metadata.get("date"),
            "type": d.metadata.get("type"),
            "preview": d.page_content[:120] + "...",
        }
        for d in docs
    ]
