# Platform Architecture

```mermaid
flowchart TD
    Client[Client or Swagger UI] --> API[FastAPI API Layer]
    API --> Auth[JWT Authentication and Tenant Isolation]

    Auth --> DBFlow[Database Query Flow]
    Auth --> DocFlow[Document RAG Flow]
    Auth --> Chat[Chat Orchestration]

    DBFlow --> Connections[Encrypted Runtime Connections]
    Connections --> Discovery[Schema Discovery and Metadata Cache]
    Discovery --> Permissions[Effective Table, Column, and Row Permissions]
    Permissions --> SQLGlot[SQLGlot Validation]
    SQLGlot --> RowFilters[Mandatory Row Filter Injection]
    RowFilters --> Executor[Read-Only Query Executor]
    Executor --> Masking[Column Masking and Safe Results]

    DocFlow --> MinIO[MinIO Object Storage]
    MinIO --> Parsers[TXT, CSV, PDF, DOCX, XLSX, XLS Parsers]
    Parsers --> Chunking[Deterministic Text Chunking]
    Chunking --> Embeddings[Sentence Transformer Embeddings]
    Embeddings --> VectorDB[PostgreSQL and pgvector]
    VectorDB --> Retrieval[Cosine Similarity Retrieval]

    Masking --> Chat
    Retrieval --> Chat

    Chat --> Conversations[Conversations and Messages]
    Conversations --> Citations[Document and Database Citations]
    Conversations --> Executions[Query Execution History]
    Conversations --> Audit[Sanitized Audit Logs]
```

## Security Boundaries

1. Every protected request requires a valid access token.
2. Tenant filters are applied to every tenant-scoped repository query.
3. Database credentials are encrypted at rest.
4. SQL is validated before and after mandatory row-filter injection.
5. Runtime SQL executes in a read-only transaction.
6. Results are limited, size-controlled, serialized, and masked.
7. Document retrieval is restricted by tenant and knowledge base.
8. API responses exclude storage keys, credentials, and embedding vectors.
9. Audit metadata is sanitized before persistence.