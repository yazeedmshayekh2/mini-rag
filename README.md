# mini-rag

A minimal FastAPI application that serves as the foundation for a Retrieval-Augmented Generation (RAG) project.

The current version handles the **ingestion** side of the pipeline:

- Upload `.txt` and `.pdf` files into per-project folders
- Track projects, uploaded files (assets), and text chunks in MongoDB
- Split uploaded files into overlapping chunks with LangChain's `RecursiveCharacterTextSplitter`

Embedding, vector search, and answer generation are not implemented yet.

## Tech stack

- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- [MongoDB](https://www.mongodb.com/) through PyMongo's async client (`AsyncMongoClient`)
- [LangChain](https://python.langchain.com/) document loaders (`TextLoader`, `PyMuPDFLoader`) and text splitters
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration

## Requirements

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose, to run MongoDB

## Project structure

```text
mini-rag/
├── docker/
│   ├── docker-compose.yml     # MongoDB service
│   └── .env.example           # MongoDB root credentials
├── src/
│   ├── main.py                # FastAPI app and MongoDB lifespan
│   ├── helpers/config.py      # Settings loaded from .env
│   ├── routes/
│   │   ├── base.py            # GET /api/v1/
│   │   ├── data.py            # Upload and process endpoints
│   │   └── schemas/           # Request bodies (ProcessRequest)
│   ├── controllers/           # File validation, storage paths, chunking
│   ├── models/
│   │   ├── ProjectModel.py    # "projects" collection
│   │   ├── AssetModel.py      # "assets" collection
│   │   ├── ChunkModel.py      # "chunks" collection
│   │   ├── db_schemas/        # Pydantic documents and index definitions
│   │   └── enums/             # Response signals, file types, collection names
│   └── assets/files/          # Uploaded files, one folder per project
├── .env.example
└── pyproject.toml
```

## Setup

### 1. Install dependencies

```powershell
uv sync
```

### 2. Start MongoDB

Create `docker/.env` with the MongoDB root credentials:

```dotenv
MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=change-me
```

Then start the container:

```powershell
cd docker
docker compose up -d
```

MongoDB listens on host port **27007**, which maps to 27017 inside the container.

### 3. Configure the application

Create a `.env` file in the project root:

```dotenv
APP_NAME=mini-rag
APP_VERSION=0.1.0

# Allowed MIME types (JSON list) and maximum upload size in MB
FILE_ALLOWED_TYPES=["text/plain", "application/pdf"]
FILE_MAX_SIZE=10

# Bytes read per iteration when writing uploads to disk
FILE_DEFAULT_CHUNK_SIZE=512000

MONGO_URL=mongodb://admin:change-me@localhost:27007
MONGODB_DATABASE=mini-rag
```

| Variable | Description |
| --- | --- |
| `APP_NAME`, `APP_VERSION` | Returned by the welcome endpoint |
| `FILE_ALLOWED_TYPES` | MIME types accepted on upload |
| `FILE_MAX_SIZE` | Maximum upload size, in megabytes |
| `FILE_DEFAULT_CHUNK_SIZE` | Read buffer size, in bytes, used while saving uploads |
| `MONGO_URL` | MongoDB connection string |
| `MONGODB_DATABASE` | Database name |

## Run the API

Start the development server from the project root:

```powershell
uv run uvicorn src.main:app --reload
```

On startup the app connects to MongoDB and pings it, so the server fails to start if MongoDB is unreachable.

The API is available at `http://127.0.0.1:8000`. Interactive documentation is at `http://127.0.0.1:8000/docs`.

## API

All endpoints are under `/api/v1`. Error responses carry a `signal` field with a value from `ResponseEnum` ([src/models/enums/ResponseEnums.py](src/models/enums/ResponseEnums.py)).

### `GET /api/v1/`

Returns the configured application name and version.

```json
{
  "app_name": "mini-rag",
  "app_version": "0.1.0"
}
```

### `POST /api/v1/data/upload/{project_id}`

Uploads a file to a project. The project is created if it does not exist; `project_id` must be alphanumeric.

The file is saved as `src/assets/files/{project_id}/{random_key}_{clean_filename}` and recorded in the `assets` collection.

```powershell
curl -X POST "http://127.0.0.1:8000/api/v1/data/upload/demo1" -F "file=@notes.pdf"
```

```json
{
  "signal": "file_upload_success",
  "file_id": "aB3dE5fG7hJ9_notes.pdf"
}
```

| Status | Signal | Cause |
| --- | --- | --- |
| 400 | `file_type_not_supported` | MIME type is not in `FILE_ALLOWED_TYPES` |
| 400 | `file_size_exceeded` | File is larger than `FILE_MAX_SIZE` MB |
| 400 | `file_upload_failed` | Writing the file to disk failed |

### `POST /api/v1/data/process/{project_id}`

Splits a project's files into chunks and stores them in the `chunks` collection.

Request body (every field is optional):

```json
{
  "file_id": "aB3dE5fG7hJ9_notes.pdf",
  "chunk_size": 100,
  "overlap_size": 10,
  "do_reset": 0
}
```

| Field | Default | Description |
| --- | --- | --- |
| `file_id` | `null` | File to process. If omitted, all files in the project are processed. |
| `chunk_size` | `100` | Maximum characters per chunk |
| `overlap_size` | `10` | Characters shared between consecutive chunks |
| `do_reset` | `0` | Set to `1` to delete the project's existing chunks first |

```json
{
  "signal": "file_processing_success",
  "inserted_chunks": 42,
  "processed_files": 1,
  "failed_files": []
}
```

| Status | Signal | Cause |
| --- | --- | --- |
| 404 | `no_file_found_with_this_id` | `file_id` does not exist in this project |
| 404 | `no_files_to_process` | The project has no uploaded files |
| 400 | `file_processing_failed` | No chunks were produced; see `failed_files` |

## Data model

| Collection | Document | Key fields |
| --- | --- | --- |
| `projects` | `Project` | `project_id` (unique) |
| `assets` | `Asset` | `asset_project_id`, `asset_type`, `asset_name` (unique per project), `asset_size`, `asset_pushed_at` |
| `chunks` | `DataChunk` | `chunk_text`, `chunk_metadata`, `chunk_order`, `chunk_project_id`, `chunk_asset_id` |

Indexes are created on first use of each model.

## License

See [LICENSE](LICENSE).
