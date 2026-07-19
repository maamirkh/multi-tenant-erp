# FOLDER_STRUCTURE.md

# DevSphere ERP

## Official Monorepo Folder Structure

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official folder structure for the DevSphere ERP monorepo.

The objective is to keep the project:

* Consistent
* Modular
* Scalable
* Easy to navigate
* Enterprise-ready

No developer should introduce new top-level folders without approval.

---

# Repository Structure

```text
devsphere-erp/

├── backend/
├── frontend/
├── docs/
├── scripts/
├── docker/
├── .github/
├── .vscode/
├── .gitignore
├── README.md
├── LICENSE
```

---

# Root Directory

The root folder contains only project-level files.

Allowed files:

* README.md
* LICENSE
* docker-compose.yml
* .gitignore
* .editorconfig
* .env.example

No application code should exist in the root.

---

# backend/

Contains the complete FastAPI backend.

```text
backend/

├── api/
├── core/
├── modules/
├── migrations/
├── tests/
├── main.py
├── alembic.ini
├── pyproject.toml
├── poetry.lock
├── .env
├── .env.example
```

---

# backend/api/

Contains HTTP entry points only.

Responsibilities

* Routers
* Dependency Injection
* API Versioning
* Middleware
* Request lifecycle

Example

```text
api/

├── deps.py
├── middleware.py
├── router.py
└── v1/
```

Business logic is NOT allowed here.

---

# backend/core/

Contains reusable platform infrastructure.

```text
core/

├── auth/
├── config/
├── database/
├── exceptions/
├── logging/
├── middleware/
├── security/
├── services/
├── utils/
└── validators/
```

---

## core/auth/

Authentication infrastructure.

Example

```text
auth/

jwt.py
password.py
permissions.py
tokens.py
```

---

## core/config/

Application configuration.

```text
config/

settings.py
```

Loads environment variables.

---

## core/database/

Database infrastructure.

```text
database/

base.py
session.py
```

Responsibilities

* SQLAlchemy Base
* Session Factory
* Database Engine

---

## core/exceptions/

Custom application exceptions.

Example

```text
AuthenticationException
ValidationException
ConflictException
NotFoundException
```

---

## core/logging/

Central logging configuration.

---

## core/security/

Security helpers.

Examples

* Encryption
* Hashing
* Security utilities

---

## core/services/

Reusable platform services.

Examples

* Email
* File Storage
* Notification

---

## core/utils/

Pure utility functions.

No business logic.

---

## core/validators/

Shared validators.

---

# backend/modules/

Every business module lives here.

Example

```text
modules/

auth/
companies/
users/
inventory/
purchase/
sales/
accounting/
crm/
installments/
reports/
```

Every module is isolated.

---

# Standard Module Structure

Every module follows the same layout.

```text
module/

api/
schemas/
models/
repositories/
services/
validators/
tests/
```

Consistency across modules is mandatory.

---

## api/

Contains routers only.

---

## schemas/

Contains Pydantic models.

Examples

* Request DTOs
* Response DTOs

---

## models/

Contains SQLAlchemy models.

Database tables only.

---

## repositories/

Contains database queries.

Responsibilities

* CRUD
* Queries
* Transactions

No business logic.

---

## services/

Contains business rules.

Responsibilities

* Validation
* Workflows
* Domain logic

---

## validators/

Module-specific validation.

---

## tests/

Module unit tests.

---

# backend/migrations/

Alembic migration files.

```text
migrations/

env.py

versions/
```

Only Alembic should modify this folder.

---

# backend/tests/

Project-wide integration tests.

Example

```text
tests/

integration/

performance/

fixtures/
```

---

# frontend/

Contains the complete Next.js application.

```text
frontend/

src/

public/

package.json

next.config.ts

tailwind.config.ts

tsconfig.json
```

---

# frontend/src/

Application source code.

```text
src/

app/

components/

hooks/

lib/

providers/

services/

types/

utils/

styles/
```

---

# app/

App Router.

Contains

* layouts
* pages
* route groups

---

# components/

Reusable UI components.

```text
components/

ui/

forms/

tables/

charts/

layout/
```

---

# hooks/

Custom React hooks.

Example

```text
useAuth()

useCompany()

usePagination()
```

---

# lib/

Infrastructure.

Examples

```text
api/

auth/

constants/

config/
```

---

# providers/

React Providers.

Examples

```text
ThemeProvider

AuthProvider

QueryProvider
```

---

# services/

Frontend service layer.

Responsible for calling backend APIs.

No UI code.

---

# types/

Shared TypeScript interfaces.

---

# utils/

Pure helper functions.

---

# styles/

Global styling.

---

# public/

Static assets.

Examples

* Images
* Logos
* Icons
* Fonts

---

# docs/

Project documentation.

Example

```text
docs/

architecture/

epics/

specs/

api/

deployment/

standards/
```

Every important decision must be documented.

---

# scripts/

Automation scripts.

Examples

* Seed Database
* Backup
* Restore
* Generate Data

---

# docker/

Docker configuration.

Example

```text
docker/

backend/

frontend/

nginx/
```

---

# .github/

GitHub configuration.

```text
.github/

workflows/

ISSUE_TEMPLATE/

PULL_REQUEST_TEMPLATE.md
```

---

# .vscode/

Recommended VS Code settings.

Examples

* Extensions
* Formatting
* Debugging

---

# Environment Files

Backend

```text
backend/.env
backend/.env.example
```

Frontend

```text
frontend/.env.local
frontend/.env.example
```

Secrets must never be committed.

---

# Naming Rules

Folders

snake_case

Examples

```text
user_roles

sales_orders

purchase_orders
```

Files

snake_case (Python)

kebab-case or lowercase (frontend configuration where appropriate)

Components

PascalCase

Example

```text
UserTable.tsx
CompanyCard.tsx
```

---

# Module Independence

Each module should be independently maintainable.

Modules communicate through:

* Services
* Interfaces
* Shared infrastructure

Direct coupling between modules should be minimized.

---

# Shared Code Rules

Shared code belongs only inside:

Backend

```text
core/
```

Frontend

```text
src/lib/

src/utils/

src/types/
```

Never duplicate shared functionality.

---

# Future Expansion

New ERP modules should only be added inside:

```text
backend/modules/

frontend/src/modules/ (if introduced later)
```

Existing folder conventions must be preserved.

---

# Directory Ownership

| Folder     | Responsibility                |
| ---------- | ----------------------------- |
| backend    | FastAPI backend               |
| frontend   | Next.js frontend              |
| docs       | Documentation                 |
| docker     | Containers                    |
| scripts    | Automation                    |
| .github    | CI/CD                         |
| core       | Shared backend infrastructure |
| modules    | Business domains              |
| migrations | Database schema history       |
| tests      | Testing                       |

---

# Folder Creation Rules

Before creating a new folder ask:

* Does this already exist elsewhere?
* Is it reusable?
* Does it belong to a module?
* Does it belong in core?
* Will another module use it?

Avoid unnecessary nesting.

Prefer clarity over deep directory trees.

---

# Single Source of Truth

This document defines the official folder structure for DevSphere ERP.

Every new file and folder added to the project must follow this structure.
