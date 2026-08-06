# Multi-Tenant Data Chat Platform

A secure, multi-tenant backend platform that enables authenticated users to query approved relational database data, search uploaded documents, and combine both sources through document, database, and hybrid chat workflows.

The platform applies tenant isolation, encrypted credentials, permission-aware SQL validation, read-only execution, structured row filters, column masking, document retrieval with pgvector, persisted citations, execution history, and sanitized audit logging.

## Project Status

The platform currently includes:

- Tenant-aware authentication and authorization
- Encrypted runtime database connections
- PostgreSQL connection testing and metadata synchronization
- Table-level, column-level, role-level, user-level, and row-level permissions
- Permission-filtered database schemas
- SQLGlot validation and mandatory row-filter injection
- Safe read-only PostgreSQL query execution
- Column masking and result limits
- MinIO-backed document storage
- Multi-format document extraction
- Deterministic text chunking
- Sentence-transformer embeddings
- pgvector semantic retrieval
- Document, database, and hybrid conversations
- Persisted messages, citations, query executions, and audit logs
- OpenAPI and Swagger documentation
- Automated test coverage

## Key Features

### Authentication and Multi-Tenancy

- Access and refresh JWT authentication
- Active-user and active-tenant checks
- Tenant-scoped repositories and services
- Tenant administrator authorization
- Safe `404` behavior for inaccessible cross-tenant resources

### Runtime Database Connections

- Tenant-scoped connection management
- PostgreSQL connection support
- Fernet-encrypted database passwords and connection strings
- Safe connection testing with timeouts
- No credential fields in API responses
- Schema, table, column, primary-key, and foreign-key discovery
- Idempotent metadata synchronization

### Database Permissions

- Permissions assigned directly to users or roles
- Table read, insert, update, and delete flags
- Column read, filter, and aggregate flags
- Structured row-filter rules
- Column masking options:
  - Full mask
  - Partial mask
  - Email mask
  - SHA-256 hash mask
- Permission-filtered schemas for SQL generation and validation

### SQL Security

The SQL security pipeline:

1. Resolves the authenticated user's effective permissions.
2. Builds a schema containing only approved tables and columns.
3. Parses generated or proposed SQL with SQLGlot.
4. Rejects unsafe, destructive, or unauthorized SQL.
5. Injects mandatory row filters as SQL expressions.
6. Validates the secured SQL a second time.
7. Applies a maximum result limit.
8. Executes the SQL inside a read-only transaction.
9. Applies column masks before returning results.
10. Records safe execution metadata and citations.

The validator rejects:

- `INSERT`, `UPDATE`, `DELETE`, `MERGE`, and `COPY`
- `CREATE`, `ALTER`, `DROP`, `GRANT`, and `REVOKE`
- Multiple statements
- SQL comments
- `SELECT *`
- System schemas
- Unauthorized tables
- Unauthorized columns
- Disallowed filtering
- Disallowed aggregation
- Invalid or excessive limits

### Document RAG

- Tenant-scoped MinIO object storage
- Safe file-name normalization
- File-size and file-extension validation
- SHA-256 duplicate detection
- TXT extraction
- CSV extraction
- PDF text extraction
- DOCX extraction
- XLSX extraction
- XLS extraction
- Deterministic text chunking with overlap
- Sentence-transformer embeddings
- PostgreSQL `vector(384)` storage
- HNSW cosine-similarity index
- Tenant-scoped semantic retrieval
- Document citations with page, section, chunk, and similarity metadata

### Chat and Traceability

- Document conversations
- Database conversations
- Hybrid conversations
- Persisted user and assistant messages
- Document citations
- Database query citations
- Query execution history
- Sanitized tenant-scoped audit logs

## Technology Stack

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- pgvector
- asyncpg
- Redis
- MinIO
- SQLGlot
- Sentence Transformers
- PyPDF
- python-docx
- openpyxl
- xlrd
- Docker
- Docker Compose
- Pytest
- Ruff

## Architecture

```text
Client / Swagger
        |
     FastAPI
        |
Authentication and tenant isolation
        |
  +-----+----------------------+
  |                            |
SQL security pipeline       Document RAG
  |                            |
Runtime databases         MinIO object storage
  |                            |
Schema and permissions    Document parsers
  |                            |
SQLGlot validation        Text chunking
  |                            |
Row-filter injection      Embeddings
  |                            |
Read-only execution       PostgreSQL + pgvector
  |                            |
Masked results            Semantic retrieval
  +-------------+--------------+
                |
         Chat orchestration
                |
 Conversations, messages, citations,
 query executions, and audit logs
```

A renderable Mermaid version is available in `docs/architecture.md` when included with the final project documentation.

## Security Design

The platform uses defense in depth:

1. Every protected request requires a valid access token.
2. Access tokens and refresh tokens have distinct token types.
3. Active users must belong to active tenants.
4. Every tenant-scoped database query includes the tenant ID.
5. Runtime database credentials are encrypted at rest.
6. Credentials are decrypted only in memory when needed.
7. API response schemas exclude passwords and encrypted credentials.
8. SQL generation receives only permission-filtered metadata.
9. SQLGlot parses and validates every proposed database query.
10. Mandatory row filters are injected using expression trees rather than raw SQL concatenation.
11. Query execution uses read-only transactions, timeouts, limits, and result-size controls.
12. Sensitive columns can be hidden or masked.
13. Document retrieval is restricted by tenant and knowledge-base ID.
14. API responses exclude MinIO storage keys and embedding vectors.
15. Audit metadata is sanitized before storage.
16. Errors use safe messages that do not expose credentials or internal connection details.

## Repository Structure

```text
app/             Application configuration and dependencies
api/             FastAPI routers
core/            Security, encryption, permissions, and constants
db/              SQLAlchemy base classes and database sessions
docs/            Architecture documentation and screenshots
migrations/      Alembic migration history
models/          SQLAlchemy database models
repositories/    Tenant-scoped persistence operations
schemas/         Pydantic request and response models
scripts/         Bootstrap and verification scripts
services/        Domain services and orchestration
tests/           Unit and integration tests
Dockerfile       Production API image
docker-compose.yml Infrastructure and service orchestration
requirements.txt Python dependencies
```

## Prerequisites

Install:

- Python 3.12
- Docker Desktop
- Git

For Windows development, PowerShell is recommended.

## Environment Setup

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Generate a strong JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Generate a Fernet encryption key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set private values only in `.env`. Never commit `.env`.

Review the environment variable names in `.env.example`. Typical categories include:

- Application settings
- PostgreSQL credentials and database URL
- JWT settings
- Fernet encryption key
- Redis connection settings
- MinIO access settings
- Initial administrator settings
- SQL limits and timeouts
- Document upload limits
- Embedding model and dimension

## Local Installation

Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Start Infrastructure

```powershell
docker compose up -d
docker compose ps
```

The infrastructure includes:

- PostgreSQL with pgvector
- Redis
- MinIO

## Apply Database Migrations

```powershell
python -m alembic upgrade head
python -m alembic current
```

Verify migration consistency:

```powershell
python -m alembic check
```

Expected result:

```text
No new upgrade operations detected.
```

## Start the API Locally

```powershell
python -m uvicorn app.main:app --reload
```

Open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health endpoint: `http://127.0.0.1:8000/health`

## Production Docker Image

Build the application image:

```powershell
docker build -t multi-tenant-data-chat-platform .
```

The first build can take several minutes because PyTorch and Sentence Transformers are large dependencies.

Verify the image:

```powershell
docker image ls multi-tenant-data-chat-platform
```

Confirm the image runs as a non-root user:

```powershell
docker run --rm multi-tenant-data-chat-platform whoami
```

Expected result:

```text
appuser
```

Run the complete Compose stack after the API service is configured in `docker-compose.yml`:

```powershell
docker compose up -d --build
docker compose ps
```

When the API runs inside Compose, use Docker service names such as `postgres`, `redis`, and `minio` instead of `localhost` for inter-container connections.

## Administrator Bootstrap

Use the project's administrator bootstrap script or configured startup workflow after migrations are applied.

Administrator credentials must be provided through private environment variables and must not be committed to the repository.

After bootstrap, authenticate through:

```text
POST /api/auth/login
```

Use the returned access token with Swagger's Bearer authorization control. Paste only the token value.

## Typical API Workflow

### 1. Authenticate

```text
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

### 2. Configure a Database Connection

```text
POST /api/database-connections
GET  /api/database-connections
POST /api/database-connections/{connection_id}/test
POST /api/database-connections/{connection_id}/sync-schema
```

### 3. Review Cached Metadata

```text
GET /api/database-connections/{connection_id}/schemas
GET /api/database-connections/{connection_id}/tables
```

### 4. Configure Permissions

```text
POST /api/permissions
GET  /api/permissions
```

### 5. Execute an Approved Query

```text
POST /api/database-connections/{connection_id}/query
```

Example request:

```json
{
  "sql": "SELECT email FROM public.users"
}
```

The query is accepted only when the authenticated user's effective permissions allow the table and column. Limits, row filters, and masks are applied automatically.

### 6. Create a Knowledge Base

```text
POST /api/knowledge-bases
GET  /api/knowledge-bases
GET  /api/knowledge-bases/{knowledge_base_id}
```

### 7. Upload and Process a Document

```text
POST /api/knowledge-bases/{knowledge_base_id}/documents
GET  /api/knowledge-bases/{knowledge_base_id}/documents
POST /api/knowledge-bases/{knowledge_base_id}/documents/{document_id}/process
POST /api/knowledge-bases/{knowledge_base_id}/documents/{document_id}/embed
```

### 8. Search Documents

```text
POST /api/knowledge-bases/{knowledge_base_id}/search
```

### 9. Create Conversations

```text
POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{conversation_id}
```

Supported modes:

- `document`
- `database`
- `hybrid`

### 10. Send Chat Messages

```text
POST /api/conversations/{conversation_id}/messages
POST /api/conversations/{conversation_id}/database-messages
POST /api/conversations/{conversation_id}/hybrid-messages
GET  /api/conversations/{conversation_id}/messages
```

### 11. Review Audit Events

```text
GET /api/audit-logs
```

Only tenant administrators can list tenant audit events.

## Example Database Connection Request

Use real values only in private requests. Do not commit working credentials.

```json
{
  "name": "Platform PostgreSQL",
  "database_type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database_name": "data_chat",
  "username": "data_chat",
  "password": "REPLACE_WITH_PRIVATE_VALUE",
  "ssl_enabled": false,
  "ssl_settings": {},
  "connection_options": {}
}
```

When the API runs inside Docker Compose, replace `localhost` with the PostgreSQL service name when appropriate.

## Example Knowledge Base Request

```json
{
  "name": "Company Documents",
  "description": "Internal policies and operational documents.",
  "chunk_size": 800,
  "chunk_overlap": 120,
  "settings": {}
}
```

## Example Semantic Search Request

```json
{
  "query": "What is this document about?",
  "top_k": 5,
  "minimum_similarity": 0.0
}
```

## Supported Document Formats

- TXT
- CSV
- PDF with extractable text
- DOCX
- XLSX
- XLS

Scanned PDFs require OCR, which is not included in the current release.

## Document Processing Lifecycle

```text
pending
  |
processing
  |
chunked
  |
embedding
  |
completed
```

On a controlled processing error, the document status becomes `failed` with a safe processing message.

## Embeddings and Retrieval

The default configuration uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Embedding dimension:

```text
384
```

Document chunks are stored in PostgreSQL using:

```text
vector(384)
```

An HNSW index with cosine distance supports efficient semantic retrieval.

## Testing

Run the complete test suite:

```powershell
python -m pytest -q
```

Current verified result:

```text
110 passed
```

Run Ruff:

```powershell
python -m ruff check app api core db models repositories schemas services scripts tests
```

Format the project when needed:

```powershell
python -m ruff format app api core db models repositories schemas services scripts tests
```

Verify migrations:

```powershell
python -m alembic current
python -m alembic heads
python -m alembic check
```

Generate OpenAPI as a verification step:

```powershell
python -c "from app.main import app; schema = app.openapi(); print('Paths:', len(schema['paths'])); print('OpenAPI generated successfully')"
```

Current verified OpenAPI path count:

```text
26
```

## Security Verification Examples

Allowed query:

```json
{
  "sql": "SELECT email FROM public.users"
}
```

Blocked destructive query:

```json
{
  "sql": "DELETE FROM public.users"
}
```

Blocked star selection:

```json
{
  "sql": "SELECT * FROM public.users"
}
```

Blocked unauthorized column:

```json
{
  "sql": "SELECT password_hash FROM public.users"
}
```

Blocked multiple statements:

```json
{
  "sql": "SELECT email FROM public.users; DELETE FROM public.users"
}
```

## Data Exposure Protections

API responses do not expose:

- Plain-text database passwords
- Encrypted passwords
- Encrypted connection strings
- MinIO object storage keys
- Embedding vectors
- JWT secrets
- Fernet keys
- Password hashes

Screenshots and documentation must also exclude bearer tokens, authorization headers, credentials, private document content, and full vectors.

## Screenshots

Submission screenshots are stored in:

```text
docs/screenshots/
```

## Known Limitations

- PostgreSQL is the fully implemented runtime database connector.
- SQL is currently supplied explicitly to database and hybrid chat endpoints rather than generated by an external LLM provider.
- Scanned PDFs require an OCR service.
- The first Sentence Transformers model load may require additional time and internet access.
- Large embedding dependencies increase Docker image size and initial build time.
- Document processing runs synchronously and can be moved to background workers for larger production workloads.
- SSE streaming can be added if required by the deployment specification.

## Final Verification Checklist

Before release:

```powershell
docker compose ps
python -m pytest -q
python -m ruff check app api core db models repositories schemas services scripts tests
python -m alembic check
git status
```

Expected results:

```text
110 passed
All checks passed!
No new upgrade operations detected.
nothing to commit, working tree clean
```

## Release

Create the final release after documentation, Docker verification, and screenshot review:

```powershell
git tag -a v1.0.0 -m "Multi-tenant data chat platform v1.0.0"
git push origin v1.0.0
```

## License

This repository is intended for educational and project demonstration purposes.
