# SYSTEM_ARCHITECTURE.md

# DevSphere ERP

## System Architecture Specification

Version: 1.0

Status: Approved

---

# 1. Purpose

This document defines the official technical architecture of the DevSphere ERP platform.

Every backend service, frontend component, API endpoint, database model and future module must follow this architecture.

This document is the technical source of truth for the entire ERP.

---

# 2. Architecture Principles

The ERP follows:

* Clean Architecture
* Modular Monolith
* Domain Driven Design (Lightweight)
* API First Development
* Specification Driven Development
* SOLID Principles
* Separation of Concerns
* Dependency Injection
* Repository Pattern
* Service Layer Pattern

No module may violate these principles.

---

# 3. High-Level Architecture

```text
                Browser
                    │
                    ▼
          Next.js Frontend (React)
                    │
             REST API (HTTPS)
                    │
                    ▼
              FastAPI Backend
                    │
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
 Service Layer  Repository Layer  Core Services
     │              │              │
     └──────────────┼──────────────┘
                    │
             SQLAlchemy ORM
                    │
                    ▼
               PostgreSQL
```

---

# 4. Backend Architecture

The backend is divided into independent layers.

## API Layer

Responsibilities:

* Receive HTTP Requests
* Validate Input
* Authentication
* Authorization
* Return Responses

Must NOT contain:

* Business Logic
* SQL Queries
* Calculations

---

## Service Layer

Responsibilities:

* Business Rules
* Validation
* Workflow
* Transactions
* Domain Logic

Services coordinate repositories.

Services never return raw SQL.

---

## Repository Layer

Responsibilities:

* Database Operations
* CRUD
* Filtering
* Searching
* Pagination

Repositories never contain business rules.

---

## Database Layer

Responsibilities:

* SQLAlchemy Models
* Relationships
* Constraints
* Indexes

No business logic belongs here.

---

## Core Layer

Contains reusable infrastructure.

Examples:

* Security
* JWT
* Hashing
* Logging
* Configuration
* Exceptions
* Database Session
* Middleware
* Utilities

---

# 5. Frontend Architecture

Frontend responsibilities:

* UI Rendering
* Forms
* Validation
* State Management
* API Communication

Frontend must never contain business rules.

All important business decisions belong to backend services.

---

# 6. Module Architecture

Each ERP module follows exactly the same structure.

```text
modules/

    auth/
        api/
        schemas/
        services/
        repositories/
        models/
        dependencies.py

    companies/
        api/
        schemas/
        services/
        repositories/
        models/

    inventory/
        api/
        schemas/
        services/
        repositories/
        models/
```

Every future module must follow this layout.

---

# 7. Core Folder Structure

```text
core/

config/
database/
security/
exceptions/
middleware/
services/
utils/
logging/
```

Core contains only reusable platform components.

Business modules must not duplicate functionality already present in Core.

---

# 8. Request Flow

Every API request follows this flow.

```text
Client

↓

API Route

↓

Validation

↓

Authentication

↓

Authorization

↓

Service

↓

Repository

↓

Database

↓

Repository

↓

Service

↓

API Response

↓

Client
```

Business logic always executes inside the Service Layer.

---

# 9. Dependency Injection

FastAPI Dependency Injection must be used.

Dependencies include:

* Database Session
* Current User
* Current Company
* Permissions
* Services

Dependencies should remain lightweight.

Heavy business logic must stay inside Services.

---

# 10. Authentication Flow

Authentication flow:

```text
Login Request

↓

Credential Validation

↓

Password Verification

↓

User Status Validation

↓

Company Validation

↓

Generate JWT

↓

Generate Refresh Token

↓

Store Session

↓

Return Tokens
```

---

# 11. Authorization Flow

Authorization is based on RBAC.

```text
User

↓

Role

↓

Permissions

↓

Protected Endpoint

↓

Access Granted / Denied
```

Permissions are checked before business logic executes.

---

# 12. Database Access Rules

Allowed:

Service

↓

Repository

↓

Database

Not Allowed:

Route

↓

Database

Routes must never directly access SQLAlchemy.

---

# 13. Transaction Management

Transactions are controlled by Services.

A single business operation should succeed completely or fail completely.

Partial writes are not acceptable.

---

# 14. Error Handling

All errors must use centralized exception handling.

Standard exception categories:

* Validation Errors
* Authentication Errors
* Authorization Errors
* Business Rule Errors
* Resource Not Found
* Conflict Errors
* Internal Errors

No raw Python traceback should be exposed to API consumers.

---

# 15. Logging

Important operations must be logged.

Examples:

* Login
* Logout
* Password Reset
* User Creation
* Role Changes
* Company Creation
* Product Updates
* Financial Transactions

Sensitive information must never be written to logs.

---

# 16. Configuration

Application configuration must come from:

* Environment Variables
* .env
* Pydantic Settings

Configuration values must never be hardcoded.

---

# 17. API Standards

RESTful APIs.

General principles:

* Consistent URL naming
* Proper HTTP methods
* Proper status codes
* JSON responses
* Pagination support
* Filtering support
* Sorting support

Every endpoint must be documented.

---

# 18. Security Architecture

Security is implemented in multiple layers.

Includes:

* JWT Authentication
* Refresh Tokens
* Argon2id Password Hashing
* Rate Limiting
* Account Lockout
* Audit Logging
* Tenant Isolation
* Input Validation
* SQL Injection Protection
* CORS Protection

Security applies to every module.

---

# 19. Multi-Tenant Architecture

Every request belongs to exactly one company.

Business data must always be filtered by company.

Future modules must never expose data belonging to another company.

Tenant isolation is mandatory.

---

# 20. Extensibility

New modules must plug into the existing architecture without changing completed modules.

Future examples:

* POS
* Payroll
* Manufacturing
* HR
* Warehouse
* AI Assistant

Architecture must remain stable while modules evolve.

---

# 21. Performance Guidelines

* Use lazy loading where appropriate.
* Avoid N+1 queries.
* Use indexes.
* Paginate large datasets.
* Keep API responses efficient.
* Reuse database sessions correctly.

Performance optimizations must not reduce code readability.

---

# 22. Testing Strategy

Every module should support:

* Unit Tests
* Integration Tests
* API Tests

Business logic should be testable independently from API routes.

---

# 23. Development Workflow

Implementation order:

Specification

↓

Tasks

↓

Service

↓

Repository

↓

API

↓

Frontend

↓

Testing

↓

Review

No implementation should bypass this workflow.

---

# 24. Architecture Rules

Every contributor must follow these rules:

* No Business Logic in Routes
* No SQL in Routes
* No SQL in Services
* No Business Logic in Repositories
* No Circular Dependencies
* No Hardcoded Configuration
* No Duplicate Logic
* No Direct Database Access from Frontend

These rules are mandatory.

---

# 25. Single Source of Truth

This document defines the official technical architecture of DevSphere ERP.

All current and future implementations must follow this architecture.

Any architectural change requires an approved design decision before implementation.
