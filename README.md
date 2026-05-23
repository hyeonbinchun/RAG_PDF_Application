# RAG PDF Application

A Retrieval-Augmented Generation (RAG) pipeline that ingests PDFs and answers questions about them. Built with Inngest for workflow orchestration, Qdrant for vector storage, OpenAI for embeddings and LLM inference, and Streamlit for the frontend.

---

## Architecture

```
Streamlit UI  →  Inngest Events  →  FastAPI + Inngest Functions
                                            │
                                 ┌──────────┴──────────┐
                            PDF Ingestion           Query Pipeline
                                 │                      │
                            OpenAI Embeddings       OpenAI Embeddings
                                 │                      │
                            Qdrant Upsert           Qdrant Search
                                                        │
                                                    GPT-4o-mini
```

**Ingest flow:** Upload a PDF → chunk it → embed chunks → store in Qdrant.

**Query flow:** Ask a question → embed the question → retrieve top-k chunks → answer with GPT-4o-mini.

---

## Project Structure

```
├── main.py               # FastAPI app + Inngest function definitions
├── data_loader.py        # PDF loading, chunking, and OpenAI embedding
├── vector_db.py          # Qdrant client wrapper (upsert + search)
├── custom_types.py       # Pydantic models for inter-step data
├── frontend/
│   └── app.py            # Streamlit frontend (upload + Q&A)
└── mcp_server/
     └── server.py         # MCP server tools
```

---

## Prerequisites

- Python 3.10+
- [Inngest Dev Server](https://www.inngest.com/docs/dev-server) running locally
- [Qdrant](https://qdrant.tech/documentation/quick-start/) running locally

Start Qdrant with Docker:
```bash
docker run -d --name qdrantRagDb -p 6333:6333 -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

Start the Inngest dev server:
```bash
npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
```

---

## Installation

```bash
uv add fastapi inngest llama-index-readers-file python-dotenv qdrant-client uvicorn streamlit openai
```

---

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
```

---

## Running the App

Start the FastAPI backend (registers Inngest functions):
```bash
uv run uvicorn main:app
```

In a separate terminal, start the Streamlit frontend:
```bash
streamlit run frontend/app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Usage

1. **Ingest a PDF** — Use the top section of the UI to upload a PDF. The file is chunked, embedded, and stored in Qdrant.
2. **Ask a question** — Type a question in the bottom section and choose how many chunks to retrieve (`top_k`). The app returns an answer grounded in the PDF content, along with the source filenames.

---

## Key Design Decisions

- **Inngest steps** — Each function is split into discrete `step.run` calls so that failures retry only the failed step, not the whole pipeline.
- **Throttling** — The ingest function is throttled to 3 runs per minute to avoid hitting OpenAI rate limits.
- **Deterministic IDs** — Chunk IDs are `uuid5` hashes of `source_id + index`, so re-ingesting the same PDF upserts rather than duplicates.
- **Embedding model** — Uses `text-embedding-3-large` (3072 dimensions) for high-quality semantic search.