# RiseApp — Data Lineage Detection for XYZ Bank

RiseApp detects **data lineage** between **external** (regulatory) and **internal** (bank) policy documents. It chunks markdown from both sources, builds FAISS vector indexes, and uses a **Google ADK lineage-detection agent** to map each internal chunk to the external chunk(s) it interprets. Results are stored in SQLite for bidirectional querying (external → internal or internal → external).

---

## Introduction

**External documents** are publicly available regulatory policies. **Internal documents** are the bank’s interpretations and implementation guidance. RiseApp:

1. **Tracks** documents under `data/blob` (PDF, HTML, MD) in a SQLite `documents` table.
2. **Chunks** all `.md` files, embeds them (HuggingFace or Google), and stores chunks in SQLite plus a FAISS index under `data/vectordb`.
3. **Runs** a lineage agent per internal chunk: FAISS retrieves the closest matched external chunk (via vector similarity), the LLM determines if the internal chunk interprets that external chunk, and links are written to a `lineage` table.

The database supports joins to query lineage in both directions. The embedding implementation is **pluggable** (HuggingFace `all-MiniLM-L6-v2` or Google embeddings), and the lineage agent is runnable via **ADK web** for interactive testing.

### Key Features

- **Incremental Processing**: Each process tracks what has been processed and skips already-processed items on subsequent runs.
- **Force Mode**: Use `--force` flag to reprocess everything, clearing previous results.
- **Optimized LLM Calls**: Process-3 uses only the top-1 closest match from vector search, reducing LLM API costs.

---

## Architecture Overview

```mermaid
flowchart TB
  subgraph inputs [Inputs]
    Blob[(data/blob)]
  end

  subgraph processes [Processes]
    P1[Process-1: PDF Convert]
    P2[Process-2: Chunk and Store]
    P3[Process-3: Lineage Detection]
  end

  subgraph stores [Stores]
    SQL[(data/sql)]
    VDB[(data/vectordb)]
  end

  Blob -->|scan PDFs| P1
  P1 -->|write HTML, MD| Blob
  P1 -->|upsert| SQL
  Blob -->|read MD| P2
  P2 -->|chunks| SQL
  P2 -->|FAISS index| VDB
  SQL -->|internal chunks| P3
  VDB -->|external candidates| P3
  P3 -->|lineage_detect_agent| P3
  P3 -->|insert lineage| SQL
```

- **Process-1**: Scans `data/blob` for PDFs, converts to HTML/MD, updates `documents`.
- **Process-2**: Reads MD from blob (using `documents`), chunks, embeds, writes **chunks** to SQL and **vectors** to FAISS (`data/vectordb`).
- **Process-3**: Loads internal chunks from SQL, embeds and queries FAISS for external candidates, calls the lineage agent, writes **lineage** to SQL.

---

## Setup

### 1. Environment and packages (uv)

- **Python 3.11+**
- Install [uv](https://github.com/astral-sh/uv), then:

```bash
cd /path/to/RiseApp
uv sync
```

This installs dependencies from `pyproject.toml` (e.g. `google-adk`, `google-genai`, `pymupdf`, `faiss-cpu`, `sentence-transformers`).

### 2. `.env` and config

- **`.env`** (project root): API keys. Do not commit.

  - `GOOGLE_API_KEY` or `GEMINI_API_KEY` — used by the lineage agent and by Google embedding when `embedding.provider: google`.

- **`config/config.yaml`**: Paths, embedding, chunking, lineage, agents.

  - `data.blob`, `data.sql`, `data.vectordb`, `logs.dir`
  - `embedding.provider`: `huggingface` | `google`
  - `embedding.model`: e.g. `model/all-MiniLM-L6-v2` (local) or `sentence-transformers/all-MiniLM-L6-v2` or `gemini-embedding-001`
  - `chunking.size`, `chunking.overlap`
  - `lineage.top_k`
  - `agents.lineage_detect.model`

### 3. Compare UI (optional)

The **dual-document compare** UI is a React app in `frontend/`. Build it so the API can serve it at `/compare/`:

```bash
cd frontend
npm install
npm run build
```

The build writes to `static/compare/`. The API serves the compare app at **`/compare/`** (and `/compare`). Use the hash to pick two documents, e.g. **`/compare/#/1/2`** for document ID 1 vs 2. The compare UI uses the same origin for API calls (`/api`).

---

## Folder Structure

| Path | Purpose |
|------|---------|
| `config/` | YAML config |
| `data/blob/` | **External** (`external/`) and **internal** (`internal/`) docs. Per-doc folders contain `{name}.pdf`, `{name}.html`, `{name}.md` |
| `data/sql/` | SQLite DB (`riseapp.db`): `documents`, `chunks`, `lineage` |
| `data/vectordb/` | FAISS index and `meta.json` (chunk ids, doc types) |
| `exception/` | Custom exception classes |
| `logger/` | Logging setup; logs under `logs/` |
| `logs/` | Log files |
| `model/` | Optional local embedding model (e.g. `model/all-MiniLM-L6-v2`) |
| `src/` | Application code |
| `src/agents/` | `lineage_detect_agent` and `prompts/` |
| `src/chunking/` | MD chunking |
| `src/db/` | SQLite connection and repositories |
| `src/embedding/` | Embedding interface; HuggingFace and Google implementations |
| `src/api/` | FastAPI app: documents, content, chunks, process, upload |
| `src/processes/` | Process-1 (convert), Process-2 (chunk+store), Process-3 (lineage) |
| `src/vectordb/` | FAISS store |
| `static/` | Web UI: HTML, CSS, JS (upload, documents list, view, side-by-side lineage) |
| `static/compare/` | Dual-document compare React app (built from `frontend/`) |
| `frontend/` | Vite + React compare UI source; build output goes to `static/compare/` |
| `test/` | Pytest tests (including `test_api.py` for REST API) |
| `utils/` | Config loader, file I/O |

---

## Configuration Reference

| Key | Description | Example |
|-----|-------------|---------|
| `data.blob` | Root for external/internal docs | `data/blob` |
| `data.sql` | SQLite directory | `data/sql` |
| `data.vectordb` | FAISS output directory | `data/vectordb` |
| `logs.dir` | Log directory | `logs` |
| `embedding.provider` | `huggingface` or `google` | `huggingface` |
| `embedding.model` | Model name or local path | `model/all-MiniLM-L6-v2` |
| `chunking.size` | Chunk size (characters) | `512` |
| `chunking.overlap` | Overlap between chunks | `64` |
| `lineage.top_k` | Number of closest external chunks to pass to LLM | `1` |
| `agents.lineage_detect.model` | LLM for lineage agent | `gemini-2.0-flash` |

---

## Running the Web App

The web app provides a UI for uploading PDFs, running the pipeline, listing documents, viewing content (HTML/MD), downloading PDFs, and viewing chunk lineage side-by-side.

### Start the server

From the project root:

```bash
uv run uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in a browser. The app serves the API at `/api` and the static front-end at `/`.

### Upload & Processing

1. **Upload**: Choose **Policy (external)** or **Rules (internal)**, select a PDF, and click Upload. Files are saved under `data/blob/external/<name>/` or `data/blob/internal/<name>/`.
2. **Run pipeline**: After upload, use **Process 1 (Convert)**, **Process 2 (Chunk & Store)**, and **Process 3 (Lineage)**. If a step reports "Already processed", you can click **Yes, force** to reprocess.
3. **Documents**: List all documents or filter by External (policy) / Internal (rules). Each row shows status (Converted, Chunked) and actions: **View**, **Download PDF**.
4. **Viewing documents & lineage**: Open **View** to see the document in HTML or Markdown and a **Chunks** section. Each chunk lists **View linked chunk** links. Clicking one opens a **side-by-side** view: left = current chunk, right = linked chunk (from the other document).

### API Reference

Interactive API docs: **http://localhost:8000/docs** (Swagger UI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents` | List documents (optional `?doc_type=external` or `internal`) |
| GET | `/api/documents/{id}/content?format=html\|md\|pdf` | Document content or PDF download |
| GET | `/api/documents/{id}/chunks` | Chunks for a document with `linked_chunk_ids` |
| GET | `/api/chunks/{chunk_id}` | Full chunk content and document info |
| POST | `/api/process/1`, `/api/process/2`, `/api/process/3` | Run process (body: `{"force": false}`) |
| POST | `/api/upload` | Upload PDF (form: `file`, `doc_type=external\|internal`) |

---

## API Endpoints - Detailed Flows

This section provides detailed flow diagrams for each API endpoint, showing the complete execution path through the codebase including database operations, file system access, external service calls, and data transformations.

### 1. GET `/api/documents`

**Purpose**: Retrieve a list of all documents in the system with optional filtering by document type.

**Use Case**: The web UI uses this to populate the documents list page. Users can view all documents or filter to see only external (regulatory) or internal (bank policy) documents.

**Parameters**:
- `doc_type` (optional): Filter by `external` or `internal`

**Response**: Array of document objects with metadata, file availability flags, and processing timestamps.

```mermaid
flowchart TB
    Start([GET /api/documents]) --> InitDB[Initialize DB Schema]
    InitDB --> QueryDB[(Query documents table<br/>SELECT * FROM documents)]
    QueryDB --> CheckFilter{doc_type<br/>parameter?}
    CheckFilter -->|Yes| FilterDocs[Filter documents by type]
    CheckFilter -->|No| BuildResponse[Build response array]
    FilterDocs --> BuildResponse
    BuildResponse --> FormatData[Format each document:<br/>id, relative_path, doc_type,<br/>name, has_pdf, has_html,<br/>has_md, converted_at, chunked_at]
    FormatData --> Return([Return JSON array])

    style QueryDB fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildResponse fill:#E0F7FA,stroke:#00838F,color:#000
    style FormatData fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 2. GET `/api/documents/{doc_id}/content`

**Purpose**: Retrieve the actual content of a specific document in the requested format (HTML, Markdown, or PDF).

**Use Case**: When users click "View" on a document in the UI, this endpoint serves the document content. For PDFs, it triggers a download; for HTML/MD, it displays inline.

**Parameters**:
- `doc_id` (path): Document ID
- `format` (query): `html`, `md`, or `pdf`

**Response**: File content with appropriate Content-Type headers.

```mermaid
flowchart TB
    Start([GET /api/documents/id/content]) --> InitDB[Initialize DB Schema]
    InitDB --> QueryDoc[(Query document by ID<br/>SELECT * FROM documents<br/>WHERE id = ?)]
    QueryDoc --> CheckDoc{Document<br/>exists?}
    CheckDoc -->|No| Error404A[Return 404:<br/>Document not found]
    CheckDoc -->|Yes| DetermineExt[Determine file extension<br/>based on format parameter]
    DetermineExt --> BuildPath[Build file path:<br/>blob/relative_path.ext]
    BuildPath --> ValidatePath{Path safe?<br/>No traversal?}
    ValidatePath -->|No| Error404B[Return 404:<br/>Invalid path]
    ValidatePath -->|Yes| CheckFile{File<br/>exists?}
    CheckFile -->|No| Error404C[Return 404:<br/>File not found]
    CheckFile -->|Yes| SetHeaders[Set Content-Type and<br/>Content-Disposition headers]
    SetHeaders --> ReturnFile([Return FileResponse])

    style QueryDoc fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildPath fill:#FFF3E0,stroke:#E65100,color:#000
    style CheckFile fill:#FFF3E0,stroke:#E65100,color:#000
```

---

### 3. GET `/api/documents/{doc_id}/content-annotated`

**Purpose**: Retrieve document content along with all its chunks and their lineage relationships, providing a complete annotated view.

**Use Case**: Powers the document viewer with inline chunk highlighting and lineage links. The frontend can display which parts of the document have lineage connections to other documents.

**Parameters**:
- `doc_id` (path): Document ID
- `format` (query): `html` or `md` (default: `md`)

**Response**: JSON with document metadata, full content, and annotated chunks with lineage information.

```mermaid
flowchart TB
    Start([GET /api/documents/id/content-annotated]) --> InitDB[Initialize DB Schema]
    InitDB --> QueryDoc[(Query document by ID)]
    QueryDoc --> CheckDoc{Document<br/>exists?}
    CheckDoc -->|No| Error404[Return 404]
    CheckDoc -->|Yes| ReadFile[Read content file<br/>from blob directory]
    ReadFile --> QueryChunks[(Query chunks for document<br/>SELECT * FROM chunks<br/>WHERE document_id = ?)]
    QueryChunks --> LoopChunks[For each chunk]
    LoopChunks --> CheckDocType{Document<br/>type?}
    CheckDocType -->|internal| QueryExtLinks[(Query lineage table<br/>for external links<br/>WHERE internal_chunk_id = ?)]
    CheckDocType -->|external| QueryIntLinks[(Query lineage table<br/>for internal links<br/>WHERE external_chunk_id = ?)]
    QueryExtLinks --> GetLinkedChunks
    QueryIntLinks --> GetLinkedChunks[(Get linked chunk details<br/>and document names)]
    GetLinkedChunks --> BuildChunkObj[Build chunk object with:<br/>- Full content<br/>- Content preview 120 chars<br/>- Offsets start/end<br/>- Linked chunk IDs<br/>- Linked document info]
    BuildChunkObj --> MoreChunks{More<br/>chunks?}
    MoreChunks -->|Yes| LoopChunks
    MoreChunks -->|No| BuildResponse[Build response with:<br/>- Document metadata<br/>- Full content<br/>- Format<br/>- Annotated chunks array]
    BuildResponse --> Return([Return JSON])

    style QueryDoc fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryChunks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryExtLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryIntLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetLinkedChunks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style ReadFile fill:#FFF3E0,stroke:#E65100,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildResponse fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 4. GET `/api/documents/{doc_id}/chunks`

**Purpose**: Retrieve all chunks for a specific document with their lineage relationships, but without the full document content.

**Use Case**: Used by the UI to display the chunks section below document content, showing chunk previews and "View linked chunk" buttons.

**Parameters**:
- `doc_id` (path): Document ID

**Response**: Array of chunk objects with previews and linked chunk IDs.

```mermaid
flowchart TB
    Start([GET /api/documents/id/chunks]) --> InitDB[Initialize DB Schema]
    InitDB --> QueryDoc[(Query document by ID)]
    QueryDoc --> CheckDoc{Document<br/>exists?}
    CheckDoc -->|No| Error404[Return 404]
    CheckDoc -->|Yes| QueryChunks[(Query chunks<br/>WHERE document_id = ?)]
    QueryChunks --> LoopChunks[For each chunk]
    LoopChunks --> CheckType{Doc type?}
    CheckType -->|internal| GetExtLinks[(Get external linked chunks<br/>FROM lineage<br/>WHERE internal_chunk_id = ?)]
    CheckType -->|external| GetIntLinks[(Get internal linked chunks<br/>FROM lineage<br/>WHERE external_chunk_id = ?)]
    GetExtLinks --> CreatePreview
    GetIntLinks --> CreatePreview[Create content preview<br/>120 chars + ellipsis]
    CreatePreview --> BuildChunk[Build chunk object:<br/>- chunk_id, chunk_index<br/>- content_preview<br/>- start_offset, end_offset<br/>- linked_chunk_ids array]
    BuildChunk --> MoreChunks{More<br/>chunks?}
    MoreChunks -->|Yes| LoopChunks
    MoreChunks -->|No| Return([Return JSON array])

    style QueryDoc fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryChunks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetExtLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetIntLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildChunk fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 5. GET `/api/chunks/{chunk_id}`

**Purpose**: Retrieve detailed information about a single chunk, including its full content and parent document metadata.

**Use Case**: Used in the side-by-side lineage viewer when clicking "View linked chunk". Fetches both the source and target chunks to display them together.

**Parameters**:
- `chunk_id` (path): Chunk ID in format `{document_id}_{chunk_index}`

**Response**: JSON with chunk content and parent document information.

```mermaid
flowchart TB
    Start([GET /api/chunks/chunk_id]) --> ValidateID{Validate chunk_id<br/>format: digit_digit?}
    ValidateID -->|Invalid| Error400[Return 400:<br/>Invalid chunk_id format]
    ValidateID -->|Valid| InitDB[Initialize DB Schema]
    InitDB --> QueryChunk[(Query chunk by ID<br/>SELECT * FROM chunks<br/>WHERE id = ?)]
    QueryChunk --> CheckChunk{Chunk<br/>exists?}
    CheckChunk -->|No| Error404[Return 404:<br/>Chunk not found]
    CheckChunk -->|Yes| QueryDoc[(Query parent document<br/>SELECT * FROM documents<br/>WHERE id = chunk.document_id)]
    QueryDoc --> BuildDocInfo[Build document info:<br/>relative_path, doc_type, name]
    BuildDocInfo --> BuildResponse[Build response:<br/>- chunk_id<br/>- document_id<br/>- chunk_index<br/>- content full<br/>- document object]
    BuildResponse --> Return([Return JSON])

    style QueryChunk fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryDoc fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildResponse fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 6. POST `/api/chunk/related`

**Purpose**: Find all chunks related to a given chunk through lineage relationships, used for dual-document comparison.

**Use Case**: The React compare UI uses this to identify which chunks in document 2 are related to chunks in document 1, enabling synchronized scrolling and highlighting.

**Request Body**:
```json
{
  "source_document": "1",
  "chunk_id": "1_0"
}
```

**Response**: JSON with target document ID and related chunk IDs.

```mermaid
flowchart TB
    Start([POST /api/chunk/related]) --> ValidateID{Validate<br/>chunk_id format?}
    ValidateID -->|Invalid| Error400A[Return 400:<br/>Invalid chunk_id]
    ValidateID -->|Valid| InitDB[Initialize DB Schema]
    InitDB --> QueryChunk[(Query chunk by ID)]
    QueryChunk --> CheckChunk{Chunk<br/>exists?}
    CheckChunk -->|No| Error404A[Return 404:<br/>Chunk not found]
    CheckChunk -->|Yes| ValidateDoc{chunk.document_id<br/>matches source?}
    ValidateDoc -->|No| Error404B[Return 404:<br/>Chunk not in source doc]
    ValidateDoc -->|Yes| QueryDoc[(Query document)]
    QueryDoc --> CheckDocExists{Document<br/>exists?}
    CheckDocExists -->|No| Error404C[Return 404:<br/>Document not found]
    CheckDocExists -->|Yes| CheckType{Doc type?}
    CheckType -->|internal| GetExtLinks[(Get lineage links<br/>WHERE internal_chunk_id = ?)]
    CheckType -->|external| GetIntLinks[(Get lineage links<br/>WHERE external_chunk_id = ?)]
    GetExtLinks --> ExtractIDs[Extract related chunk IDs]
    GetIntLinks --> ExtractIDs
    ExtractIDs --> GetTarget{Related<br/>chunks exist?}
    GetTarget -->|Yes| QueryFirstRelated[(Query first related chunk<br/>to get target document_id)]
    GetTarget -->|No| SetEmpty[Set target_document = empty]
    QueryFirstRelated --> SetTarget[Set target_document ID]
    SetEmpty --> BuildResponse
    SetTarget --> BuildResponse[Build response:<br/>- relationship_group_id<br/>- target_document<br/>- related_chunks array]
    BuildResponse --> Return([Return JSON])

    style QueryChunk fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryDoc fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetExtLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetIntLinks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style QueryFirstRelated fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildResponse fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 7. POST `/api/process/1`

**Purpose**: Execute Process-1 (PDF conversion) to convert all PDFs in the blob directory to HTML and Markdown formats.

**Use Case**: After uploading PDFs via the web UI, users click "Process 1 (Convert)" to trigger conversion. This is the first step in the pipeline.

**Request Body**:
```json
{
  "force": false
}
```

**Response**: Status object indicating completion or already-processed state.

```mermaid
flowchart TB
    Start([POST /api/process/1]) --> ParseBody[Parse request body<br/>extract force flag]
    ParseBody --> InitDB[Initialize DB Schema]
    InitDB --> CheckForce{force = true?}
    CheckForce -->|No| CheckWork[Check if unconverted<br/>PDFs exist]
    CheckWork --> HasWork{Work<br/>needed?}
    HasWork -->|No| ReturnSkip[Return 200:<br/>already_processed<br/>force_available: true]
    HasWork -->|Yes| StartProcess
    CheckForce -->|Yes| StartProcess[Start Process-1]
    StartProcess --> ScanDirs[Scan blob/external<br/>and blob/internal]
    ScanDirs --> LoopDirs[For each document folder]
    LoopDirs --> FindPDF[Find PDF file]
    FindPDF --> HasPDF{PDF<br/>exists?}
    HasPDF -->|No| NextDir
    HasPDF -->|Yes| CheckConverted{force OR<br/>not converted?}
    CheckConverted -->|Skip| LogSkip[Log: skipping converted doc]
    CheckConverted -->|Convert| CallPyMuPDF[Call PyMuPDF to convert PDF]
    CallPyMuPDF --> ExtractHTML[Extract HTML from each page<br/>using page.get_text html]
    ExtractHTML --> ExtractText[Extract text from each page<br/>using page.get_text text]
    ExtractText --> WriteHTML[Write HTML file to<br/>doc_dir/name.html]
    WriteHTML --> WriteMD[Write MD file to<br/>doc_dir/name.md]
    WriteMD --> UpsertDB[(Upsert documents table<br/>with file flags)]
    UpsertDB --> MarkConverted[(Update converted_at<br/>timestamp)]
    MarkConverted --> NextDir
    LogSkip --> NextDir{More<br/>folders?}
    NextDir -->|Yes| LoopDirs
    NextDir -->|No| LogComplete[Log: Process-1 finished<br/>with counts]
    LogComplete --> ReturnSuccess([Return 200:<br/>status: completed])

    style CallPyMuPDF fill:#FFF3E0,stroke:#E65100,color:#000
    style WriteHTML fill:#FFF3E0,stroke:#E65100,color:#000
    style WriteMD fill:#FFF3E0,stroke:#E65100,color:#000
    style UpsertDB fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style MarkConverted fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style StartProcess fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 8. POST `/api/process/2`

**Purpose**: Execute Process-2 (chunking and embedding) to split documents into chunks, generate embeddings, and build the FAISS vector index.

**Use Case**: After conversion, users click "Process 2 (Chunk & Store)" to prepare documents for lineage detection. This creates the searchable vector database.

**Request Body**:
```json
{
  "force": false
}
```

**Response**: Status object indicating completion or already-processed state.

```mermaid
flowchart TB
    Start([POST /api/process/2]) --> ParseBody[Parse request body<br/>extract force flag]
    ParseBody --> InitDB[Initialize DB Schema]
    InitDB --> GetEmbedding[Get embedding provider<br/>from config]
    GetEmbedding --> CheckProvider{Provider?}
    CheckProvider -->|huggingface| LoadHF[Load HuggingFace model<br/>SentenceTransformer]
    CheckProvider -->|google| LoadGoogle[Initialize Google<br/>embedding client]
    LoadHF --> GetDim
    LoadGoogle --> GetDim[Get embedding dimension]
    GetDim --> InitFAISS[Initialize FAISS store<br/>IndexFlatIP]
    InitFAISS --> CheckForce{force = true?}
    CheckForce -->|Yes| ClearFAISS[Clear FAISS index]
    ClearFAISS --> GetAllDocs[(Get ALL documents with MD)]
    GetAllDocs --> DeleteAllChunks[(Delete all chunks<br/>from chunks table)]
    CheckForce -->|No| CheckWork[Check for unprocessed docs]
    CheckWork --> HasWork{Work<br/>needed?}
    HasWork -->|No| ReturnSkip[Return 200:<br/>already_processed]
    HasWork -->|Yes| GetUnprocessed
    DeleteAllChunks --> ProcessDocs
    GetUnprocessed[(Get unprocessed documents<br/>WHERE chunked_at IS NULL<br/>OR updated_at > chunked_at)] --> ProcessDocs[For each document]
    ProcessDocs --> ReadMD[Read MD file from blob]
    ReadMD --> ChunkText[Chunk text using chunker<br/>with size and overlap<br/>from config]
    ChunkText --> HasChunks{Chunks<br/>created?}
    HasChunks -->|No| MarkChunked1
    HasChunks -->|Yes| EmbedChunks[Embed all chunk texts]
    EmbedChunks --> CallEmbedding{Provider?}
    CallEmbedding -->|huggingface| HFEmbed[HuggingFace:<br/>model.encode texts]
    CallEmbedding -->|google| GoogleEmbed[Google API:<br/>embed_content with<br/>RETRIEVAL_DOCUMENT task]
    HFEmbed --> NormalizeVecs
    GoogleEmbed --> NormalizeVecs[Normalize vectors]
    NormalizeVecs --> InsertChunks[(Insert chunks to DB<br/>with content and offsets)]
    InsertChunks --> AddToFAISS[Add vectors to FAISS<br/>with chunk IDs and doc_types]
    AddToFAISS --> MarkChunked1[(Update chunked_at timestamp)]
    MarkChunked1 --> MoreDocs{More<br/>docs?}
    MoreDocs -->|Yes| ProcessDocs
    MoreDocs -->|No| SaveFAISS[Save FAISS index and<br/>metadata to disk]
    SaveFAISS --> LogComplete[Log: Process-2 finished]
    LogComplete --> ReturnSuccess([Return 200:<br/>status: completed])

    style LoadHF fill:#E8F5E9,stroke:#388E3C,color:#000
    style LoadGoogle fill:#E8F5E9,stroke:#388E3C,color:#000
    style HFEmbed fill:#E8F5E9,stroke:#388E3C,color:#000
    style GoogleEmbed fill:#E8F5E9,stroke:#388E3C,color:#000
    style InitFAISS fill:#FFF9C4,stroke:#F57C00,color:#000
    style ClearFAISS fill:#FFF9C4,stroke:#F57C00,color:#000
    style AddToFAISS fill:#FFF9C4,stroke:#F57C00,color:#000
    style SaveFAISS fill:#FFF9C4,stroke:#F57C00,color:#000
    style ReadMD fill:#FFF3E0,stroke:#E65100,color:#000
    style GetAllDocs fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style DeleteAllChunks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetUnprocessed fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InsertChunks fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style MarkChunked1 fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style ChunkText fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 9. POST `/api/process/3`

**Purpose**: Execute Process-3 (lineage detection) to identify relationships between internal and external document chunks using vector similarity and LLM validation.

**Use Case**: Final pipeline step. After chunking, users click "Process 3 (Lineage)" to detect which internal policy chunks interpret which external regulatory chunks.

**Request Body**:
```json
{
  "force": false
}
```

**Response**: Status object indicating completion or already-processed state.

```mermaid
flowchart TB
    Start([POST /api/process/3]) --> ParseBody[Parse request body<br/>extract force flag]
    ParseBody --> InitDB[Initialize DB Schema]
    InitDB --> CheckForce{force = true?}
    CheckForce -->|Yes| ClearLineage[(Delete all lineage entries<br/>DELETE FROM lineage)]
    ClearLineage --> GetAllInternal[(Get ALL internal chunks)]
    CheckForce -->|No| CheckWork[Check for unprocessed<br/>internal chunks]
    CheckWork --> HasWork{Work<br/>needed?}
    HasWork -->|No| ReturnSkip[Return 200:<br/>already_processed]
    HasWork -->|Yes| GetUnprocessed
    GetAllInternal --> LoadResources
    GetUnprocessed[(Get unprocessed internal chunks<br/>WHERE lineage_processed_at IS NULL)] --> LoadResources[Load embedding provider<br/>and FAISS store]
    LoadResources --> GetTopK[Get top_k from config<br/>default: 1]
    GetTopK --> LoopChunks[For each internal chunk]
    LoopChunks --> EmbedChunk[Embed chunk content]
    EmbedChunk --> CallEmbed{Provider?}
    CallEmbed -->|huggingface| HFEmbed[HuggingFace: encode]
    CallEmbed -->|google| GoogleEmbed[Google: embed_content]
    HFEmbed --> SearchFAISS
    GoogleEmbed --> SearchFAISS[Search FAISS for top-1<br/>external chunk<br/>with doc_type filter]
    SearchFAISS --> HasMatch{Match<br/>found?}
    HasMatch -->|No| MarkProcessed1
    HasMatch -->|Yes| GetChunk[(Query matched chunk<br/>from chunks table)]
    GetChunk --> ChunkExists{Chunk<br/>exists?}
    ChunkExists -->|No| MarkProcessed1
    ChunkExists -->|Yes| BuildPrompt[Build lineage detection prompt<br/>with internal chunk and<br/>external candidate]
    BuildPrompt --> CallAgent[Call Google ADK<br/>lineage_detect_agent]
    CallAgent --> InitSession[Create ADK session<br/>InMemorySessionService]
    InitSession --> RunAgent[Run agent with Gemini LLM<br/>using system and match prompts]
    RunAgent --> ParseResponse[Parse agent response<br/>extract external_chunk_ids<br/>and confidence]
    ParseResponse --> HasLineage{Lineage<br/>detected?}
    HasLineage -->|Yes| InsertLineage[(Insert lineage record<br/>internal_chunk_id,<br/>external_chunk_id, confidence)]
    HasLineage -->|No| MarkProcessed1
    InsertLineage --> MarkProcessed1[(Update lineage_processed_at<br/>timestamp)]
    MarkProcessed1 --> MoreChunks{More<br/>chunks?}
    MoreChunks -->|Yes| LoopChunks
    MoreChunks -->|No| LogComplete[Log: Process-3 finished<br/>with counts]
    LogComplete --> ReturnSuccess([Return 200:<br/>status: completed])

    style HFEmbed fill:#E8F5E9,stroke:#388E3C,color:#000
    style GoogleEmbed fill:#E8F5E9,stroke:#388E3C,color:#000
    style SearchFAISS fill:#FFF9C4,stroke:#F57C00,color:#000
    style CallAgent fill:#E3F2FD,stroke:#1976D2,color:#000
    style InitSession fill:#E3F2FD,stroke:#1976D2,color:#000
    style RunAgent fill:#E3F2FD,stroke:#1976D2,color:#000
    style ClearLineage fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetAllInternal fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetUnprocessed fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style GetChunk fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InsertLineage fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style MarkProcessed1 fill:#F3E5F5,stroke:#7B1FA2,color:#000
    style InitDB fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildPrompt fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 10. POST `/api/upload`

**Purpose**: Upload a PDF file to the blob directory, creating the necessary folder structure.

**Use Case**: Web UI upload form allows users to select a PDF and specify whether it's an external (regulatory) or internal (bank policy) document.

**Request**: Multipart form data with `file` and `doc_type` fields.

**Response**: JSON with uploaded file path and document type.

```mermaid
flowchart TB
    Start([POST /api/upload]) --> ParseForm[Parse multipart form data<br/>file and doc_type]
    ParseForm --> ValidateFile{File is PDF?<br/>Check extension}
    ValidateFile -->|No| Error400A[Return 400:<br/>PDF file required]
    ValidateFile -->|Yes| ExtractStem[Extract filename stem<br/>without extension]
    ExtractStem --> ValidateStem{Valid<br/>filename?}
    ValidateStem -->|No| Error400B[Return 400:<br/>Invalid filename]
    ValidateStem -->|Yes| GetBlobPath[Get blob root path<br/>from config]
    GetBlobPath --> BuildFolder[Build folder path:<br/>blob/doc_type/stem/]
    BuildFolder --> CreateFolder[Create folder structure<br/>mkdir with parents]
    CreateFolder --> BuildDestPath[Build destination path:<br/>folder/stem.pdf]
    BuildDestPath --> ReadFileContent[Read uploaded file content<br/>from request]
    ReadFileContent --> WriteFile[Write PDF to destination]
    WriteFile --> BuildRelPath[Build relative path:<br/>doc_type/stem/stem]
    BuildRelPath --> ReturnSuccess([Return 201:<br/>path, doc_type])

    style CreateFolder fill:#FFF3E0,stroke:#E65100,color:#000
    style WriteFile fill:#FFF3E0,stroke:#E65100,color:#000
    style ParseForm fill:#E0F7FA,stroke:#00838F,color:#000
    style BuildFolder fill:#E0F7FA,stroke:#00838F,color:#000
```

---

### 11. GET `/compare` and `/compare/`

**Purpose**: Serve the dual-document comparison React application for side-by-side document viewing.

**Use Case**: Users navigate to `/compare/#/1/2` to view documents 1 and 2 side-by-side with synchronized scrolling and lineage highlighting. Useful for comparing regulatory requirements with bank policies.

**Parameters**: None (uses hash routing in frontend, e.g., `#/1/2`)

**Response**: HTML page serving the React application.

```mermaid
flowchart TB
    Start([GET /compare or /compare/]) --> BuildPath[Build path to compare UI:<br/>static/compare/index.html]
    BuildPath --> CheckExists{index.html<br/>exists?}
    CheckExists -->|No| Error404[Return 404:<br/>Compare UI not built<br/>Run: cd frontend && npm run build]
    CheckExists -->|Yes| ReturnHTML([Return FileResponse<br/>Content-Type: text/html])
    ReturnHTML --> BrowserLoads[Browser loads React app]
    BrowserLoads --> ParseHash[React router parses<br/>hash route: #/doc1/doc2]
    ParseHash --> FetchDocs[React app calls:<br/>GET /api/documents/1/content-annotated<br/>GET /api/documents/2/content-annotated]
    FetchDocs --> FetchRelated[React app calls:<br/>POST /api/chunk/related<br/>for each chunk]
    FetchRelated --> RenderUI[Render side-by-side view<br/>with synchronized scrolling<br/>and lineage highlighting]

    style BuildPath fill:#FFF3E0,stroke:#E65100,color:#000
    style CheckExists fill:#FFF3E0,stroke:#E65100,color:#000
    style BrowserLoads fill:#E0F7FA,stroke:#00838F,color:#000
    style ParseHash fill:#E0F7FA,stroke:#00838F,color:#000
    style RenderUI fill:#E0F7FA,stroke:#00838F,color:#000
```

---

## Color Legend for Flow Diagrams

The mermaid diagrams above use the following color coding to distinguish different types of operations:

- **Light Blue** - External Services (Google ADK/Gemini LLM calls)
- **Light Green** - Embedding Models (HuggingFace or Google embeddings)
- **Light Yellow** - FAISS Vector Database operations
- **Light Purple** - SQLite Database operations
- **Light Orange** - File System operations
- **Light Cyan** - General processing and transformation nodes

---

## Running the Pipeline (CLI)

### What is `riseapp`?

The `riseapp` command is a CLI entrypoint defined in `pyproject.toml`:

```toml
[project.scripts]
riseapp = "main:main"
```

This means when you run `uv run riseapp`, it executes the `main()` function from `main.py`. The `uv run` command ensures the virtual environment is activated and dependencies are available.

### Basic Commands

From the project root:

```bash
uv run riseapp convert      # Process-1: PDF → HTML/MD, update documents
uv run riseapp chunk-store  # Process-2: Chunk, embed, store in DB + FAISS
uv run riseapp lineage      # Process-3: Lineage detection, store lineage
uv run riseapp all          # Run convert → chunk-store → lineage
```

Alternatively, run directly via Python:

```bash
uv run python main.py convert
uv run python main.py chunk-store
uv run python main.py lineage
uv run python main.py all
```

### Incremental vs Force Mode

By default, each process is **incremental** — it skips items that have already been processed:

- **Process-1**: Skips PDFs where `converted_at` is set and HTML/MD files exist
- **Process-2**: Skips documents where `chunked_at >= updated_at`
- **Process-3**: Skips internal chunks where `lineage_processed_at` is set

To **force reprocessing**, use the `--force` (or `-f`) flag:

```bash
uv run riseapp convert --force      # Re-convert all PDFs, overwrite HTML/MD
uv run riseapp chunk-store --force  # Clear vector store, re-chunk all documents
uv run riseapp lineage --force      # Clear lineage table, reprocess all chunks
uv run riseapp all --force          # Force all three processes
```

| Flag | Process-1 Effect | Process-2 Effect | Process-3 Effect |
|------|------------------|------------------|------------------|
| (none) | Skip converted docs | Skip chunked docs | Skip processed chunks |
| `--force` | Re-convert all PDFs | Clear FAISS, re-chunk all | Clear lineage, reprocess all |

### Lineage Agent (ADK Web)

To run the lineage agent in the ADK web UI for interactive testing:

```bash
uv run adk web --adk.agents.source-dir=src/agents/lineage_detect_agent
```

The agent exposes `root_agent` for discovery. Use the chat interface to exercise it.

---

## Database Schema and Lineage Queries

### Tables

- **`documents`**: Tracks all documents (PDFs) in the blob.
  - `id`, `relative_path`, `doc_type` (`external`|`internal`), `name`
  - `has_pdf`, `has_html`, `has_md` — flags for file existence
  - `created_at`, `updated_at` — timestamps
  - `converted_at` — timestamp when Process-1 converted the PDF (NULL if not converted)
  - `chunked_at` — timestamp when Process-2 chunked the document (NULL if not chunked)
  - `lineage_at` — reserved for future use

- **`chunks`**: Stores chunked content from MD files.
  - `id` (format: `{document_id}_{chunk_index}`), `document_id`, `chunk_index`, `content`, `metadata`
  - `created_at` — timestamp
  - `lineage_processed_at` — timestamp when Process-3 processed this chunk (NULL if not processed)

- **`lineage`**: Links internal chunks to external chunks they interpret.
  - `id`, `internal_chunk_id`, `external_chunk_id`, `confidence`, `created_at`

### Querying Lineage

**Internal → External**: Find external chunks that an internal chunk interprets:

```sql
SELECT l.*, c.content as external_content
FROM lineage l
JOIN chunks c ON c.id = l.external_chunk_id
WHERE l.internal_chunk_id = '2_0';
```

**External → Internal**: Find internal chunks that interpret an external chunk:

```sql
SELECT l.*, c.content as internal_content
FROM lineage l
JOIN chunks c ON c.id = l.internal_chunk_id
WHERE l.external_chunk_id = '1_0';
```

**Check Processing Status**:

```sql
-- Documents not yet converted
SELECT * FROM documents WHERE converted_at IS NULL;

-- Documents not yet chunked
SELECT * FROM documents WHERE has_md = 1 AND (chunked_at IS NULL OR updated_at > chunked_at);

-- Internal chunks not yet processed for lineage
SELECT c.* FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.doc_type = 'internal' AND c.lineage_processed_at IS NULL;
```

---

## Flows (Mermaid)

### End-to-end

```mermaid
flowchart TB
  P1[Process-1: PDF Convert]
  P2[Process-2: Chunk and Store]
  P3[Process-3: Lineage Detection]
  Blob[(data/blob)]
  SQL[(data/sql)]
  VDB[(data/vectordb)]

  Blob -->|scan PDFs| P1
  P1 -->|write HTML, MD| Blob
  P1 -->|upsert documents| SQL
  Blob -->|read MD| P2
  P2 -->|insert chunks| SQL
  P2 -->|add vectors| VDB
  P2 -->|save index| VDB
  SQL -->|internal chunks| P3
  VDB -->|search top-1 external| P3
  P3 -->|lineage_detect_agent| P3
  P3 -->|insert lineage| SQL
```

### Process-1: PDF Convert (with --force option)

```mermaid
flowchart TB
  A[Scan external/internal PDFs] --> B{--force?}
  B -->|Yes| D[Convert PDF to HTML/MD]
  B -->|No| C{Already converted?}
  C -->|Yes| Skip[Skip document]
  C -->|No| D
  D --> E[Write HTML/MD to folder]
  E --> F[Upsert documents table]
  F --> G[Set converted_at timestamp]
```

### Process-2: Chunk and Store (with --force option)

```mermaid
flowchart TB
  A[Start] --> B{--force?}
  B -->|Yes| C1[Clear FAISS index]
  C1 --> C2[Get ALL docs with MD]
  C2 --> C3[Delete all chunks]
  B -->|No| D[Get unprocessed docs]
  C3 --> E
  D --> E[For each document]
  E --> F[Read MD from blob]
  F --> G[Chunk MD]
  G --> H[Embed chunks]
  H --> I[Insert chunks to SQL]
  I --> J[Add vectors to FAISS]
  J --> K[Set chunked_at timestamp]
  K --> L{More docs?}
  L -->|Yes| E
  L -->|No| M[Save FAISS index]
```

### Process-3: Lineage Detection (with --force option)

```mermaid
flowchart TB
  A[Start] --> B{--force?}
  B -->|Yes| C1[Clear lineage table]
  C1 --> C2[Get ALL internal chunks]
  B -->|No| D[Get unprocessed internal chunks]
  C2 --> E
  D --> E[For each internal chunk]
  E --> F[Embed chunk]
  F --> G[FAISS search top-1 external]
  G --> H{Found match?}
  H -->|No| I[Mark as processed]
  H -->|Yes| J[Call lineage_detect_agent]
  J --> K[Insert lineage if matched]
  K --> L[Set lineage_processed_at]
  I --> M{More chunks?}
  L --> M
  M -->|Yes| E
  M -->|No| N[Done]
```

---

## Testing

### Run All Tests

```bash
uv run pytest test/ -v
```

Or with `pip` and a venv:

```bash
pip install -r requirements.txt
python -m pytest test/ -v
```

### Run Individual Test Modules

Each module can be tested independently:

```bash
# Test the chunker (text splitting logic)
uv run pytest test/test_chunker.py -v

# Test database operations (repositories, CRUD)
uv run pytest test/test_db.py -v

# Test embedding (HuggingFace model loading and embedding)
uv run pytest test/test_embedding.py -v

# Test vector database (FAISS operations)
uv run pytest test/test_vectordb.py -v

# Test Process-1 (PDF conversion flow)
uv run pytest test/test_process_1.py -v
```

### Run Specific Test Functions

```bash
# Run a specific test function
uv run pytest test/test_db.py::test_documents_crud -v

# Run tests matching a keyword
uv run pytest test/ -k "chunk" -v
```

### Test Coverage

| Test File | Module Tested | Description |
|-----------|---------------|-------------|
| `test_chunker.py` | `src/chunking/chunker.py` | Markdown chunking with size/overlap |
| `test_api.py` | `src/api/app.py` | REST API: documents, content, chunks, process, upload |
| `test_db.py` | `src/db/repositories.py` | SQLite CRUD for documents, chunks, lineage |
| `test_embedding.py` | `src/embedding/` | HuggingFace embedding model |
| `test_vectordb.py` | `src/vectordb/faiss_store.py` | FAISS index add/search/save/load |
| `test_process_1.py` | `src/processes/process_1_convert.py` | PDF → HTML/MD conversion |

### Testing Tips

- **Windows**: `faiss-cpu` may have no wheel; use WSL/conda or run only `test_chunker` and `test_db` if FAISS is unavailable.
- **Async tests**: Tests use `pytest-asyncio` with `asyncio_mode = "auto"` configured in `pyproject.toml`.
- **Isolated DB**: Tests use in-memory SQLite databases to avoid affecting production data.

---

## Verification Checklist

- **Setup**: `uv sync`; `.env` with `GOOGLE_API_KEY` or `GEMINI_API_KEY` if using Google embedding/agent.
- **Run**: `uv run python main.py all` (or `convert` → `chunk-store` → `lineage`).
- **Agent**: `uv run adk web --adk.agents.source-dir=src/agents/lineage_detect_agent`.

---

## Embedding and Lineage Agent

- **Embedding**: Implementations live in `src/embedding/`. The factory chooses HuggingFace or Google based on `embedding.provider`. Use a local model path (e.g. `model/all-MiniLM-L6-v2`) when the model is cloned under the project.
- **Lineage agent**: Implemented in `src/agents/lineage_detect_agent/`, with prompts in `src/agents/prompts/` (`lineage_detect_system.md`, `lineage_detect_match.md`). Process-3 calls `detect_lineage(internal_chunk, candidates)` and persists results to the `lineage` table.
