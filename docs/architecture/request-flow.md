# Request Flow

## Complete Request Lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant CORS as CORSMiddleware
    participant RID as RequestIDMiddleware
    participant AUTH as AuthHookMiddleware
    participant EH as Exception Handlers
    participant R as Route Handler
    participant SVC as Service Layer
    participant REPO as Repository Layer
    participant DB as PostgreSQL

    C->>CORS: HTTP Request
    CORS->>RID: add CORS headers
    RID->>RID: read/generate X-Request-ID
    RID->>RID: set REQUEST_ID_CONTEXT
    RID->>AUTH: forward request
    AUTH->>R: pass-through (stub)
    R->>SVC: call service method
    SVC->>REPO: call repository method
    REPO->>DB: execute SQL
    DB-->>REPO: result rows
    REPO-->>SVC: domain entity
    SVC-->>R: business result
    R-->>AUTH: StandardResponse
    AUTH-->>RID: response
    RID->>RID: add X-Request-ID to response header
    RID->>RID: reset REQUEST_ID_CONTEXT token
    RID-->>CORS: response
    CORS-->>C: HTTP Response (with X-Request-ID)
```

## Request ID Propagation

```mermaid
flowchart LR
    REQ[Request\nX-Request-ID: abc-123] --> MW[RequestIDMiddleware]
    MW --> CTX[REQUEST_ID_CONTEXT\n= 'abc-123']
    CTX --> LOG[Logger\nrequest_id: abc-123]
    CTX --> RESP[Response\nX-Request-ID: abc-123]
    CTX --> ERR[ErrorResponse\nmeta.request_id: abc-123]
```

## Error Flow

```mermaid
sequenceDiagram
    participant R as Route Handler
    participant EH as Exception Handler
    participant LOG as Logger
    participant C as Client

    R->>R: raises ApplicationException (e.g. NotFoundException)
    R->>EH: application_exception_handler(request, exc)
    EH->>LOG: logger.warning / logger.error
    EH->>C: JSONResponse(status=exc.http_status, body=ErrorResponse)
    Note over EH,C: X-Request-ID header always included
```

## API Layer Structure

```
GET /                     → root() — API metadata
GET /api/v1/health        → health_check() — combined liveness + readiness
GET /api/v1/health/live   → liveness() — always 200 while process is running
GET /api/v1/health/ready  → readiness() — 200 when DB is reachable
```

## Router Registration

```
FastAPI app
└── GET /                         (main._register_routers)
└── _IncludedRouter /api/v1
    ├── GET /health               (api.v1.router)
    ├── GET /health/live          (api.v1.router)
    └── GET /health/ready         (api.v1.router)
```
