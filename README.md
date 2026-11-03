# mini-rag

A minimal FastAPI application that serves as a starting point for a RAG project. The current API provides a welcome endpoint; retrieval and generation features are not implemented yet.

## Requirements

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)

## Setup

Install the project dependencies:

```powershell
uv sync
```

Create a `.env` file in the project root with the application settings:

```dotenv
APP_NAME=mini-rag
APP_VERSION=0.1.0
```

## Run the API

Start the development server from the project root:

```powershell
uv run uvicorn mini_rag.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Endpoint

`GET /api/v1/` returns the configured application name and version:

```json
{
  "app_name": "mini-rag",
  "app_version": "0.1.0"
}
```