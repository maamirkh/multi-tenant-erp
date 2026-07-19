# CODING_PATTERNS.md

# DevSphere ERP

## Official Coding Patterns

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official coding patterns used throughout the DevSphere ERP platform.

The objective is to ensure that every module follows the same architecture, coding style, and implementation approach regardless of which developer or AI assistant writes the code.

These patterns are mandatory for every Epic.

---

# Core Principles

Every implementation must follow:

* SOLID Principles
* DRY (Don't Repeat Yourself)
* KISS (Keep It Simple)
* Separation of Concerns
* Single Responsibility Principle
* Dependency Injection
* Clean Architecture
* Composition over Inheritance

---

# Layered Architecture

Every backend module follows the same structure.

```text
API Layer

↓

Service Layer

↓

Repository Layer

↓

Database
```

Responsibilities must never overlap.

---

# API Layer

Responsibilities

* Receive Request
* Validate Input
* Call Service
* Return Response
* Handle HTTP Errors

Must NOT contain:

* Business Logic
* SQL Queries
* Complex Calculations

---

# Service Layer

Responsibilities

* Business Rules
* Workflows
* Validation
* Transactions
* Coordination

Must NOT contain:

* HTTP Logic
* SQL Statements
* Response Formatting

---

# Repository Layer

Responsibilities

* CRUD Operations
* SQLAlchemy Queries
* Database Access

Must NOT contain:

* Business Logic
* Authentication
* Validation

---

# Database Layer

Responsibilities

* ORM Models
* Constraints
* Relationships
* Indexes

Database models should never contain business workflows.

---

# Dependency Injection

Always inject dependencies.

Example

```text
API

↓

Service

↓

Repository
```

Never instantiate repositories directly inside business logic.

---

# Repository Pattern

Every module should expose one repository.

Example

```text
UserRepository

CompanyRepository

InventoryRepository

PurchaseRepository
```

Repository names should describe entities.

---

# Service Pattern

Every module should expose one primary service.

Examples

```text
AuthService

CompanyService

InventoryService

AccountingService
```

Services coordinate business rules.

---

# DTO Pattern

Every API should use dedicated DTOs.

Separate:

* Request DTO
* Response DTO
* Internal Model

Never expose database models directly.

---

# Validation Pattern

Validation occurs in three stages.

Stage 1

Schema Validation

↓

Stage 2

Business Validation

↓

Stage 3

Database Validation

Reject invalid data as early as possible.

---

# Exception Pattern

Use custom exceptions.

Examples

```text
ValidationException

NotFoundException

AuthenticationException

AuthorizationException

ConflictException
```

Never raise generic Exception in application code.

---

# Error Handling

Flow

```text
Repository

↓

Service

↓

API

↓

HTTP Response
```

Every exception should be translated into a user-friendly API response.

---

# Logging Pattern

Log only meaningful events.

Examples

* Login
* Logout
* Password Change
* Company Creation
* Purchase Posting
* Inventory Adjustment

Avoid excessive logging.

---

# Transaction Pattern

Use database transactions for operations involving multiple writes.

Example

```text
Create Invoice

↓

Create Ledger Entries

↓

Update Inventory

↓

Commit
```

Rollback on failure.

---

# Query Pattern

Repositories should expose reusable query methods.

Examples

```text
get_by_id()

get_by_email()

list_active()

search()

paginate()
```

Avoid duplicate query logic.

---

# Pagination Pattern

Every large list should support:

* Page
* Page Size
* Sorting
* Filtering
* Search

Do not return unbounded collections.

---

# Soft Delete Pattern

Business entities should use soft delete.

Fields

```text
deleted_at

deleted_by
```

Avoid permanent deletion unless explicitly required.

---

# Audit Pattern

Important changes must generate audit records.

Examples

* User Updated
* Role Changed
* Inventory Adjusted
* Financial Transaction

Audit logs are immutable.

---

# Authentication Pattern

Authentication flow

```text
Login

↓

Validate Password

↓

Generate JWT

↓

Store Refresh Token

↓

Return Tokens
```

Authentication logic belongs only in AuthService.

---

# Authorization Pattern

Every protected endpoint verifies:

* User Status
* Tenant
* Role
* Permission

Never trust frontend permissions.

---

# Multi-Tenant Pattern

Every query must be tenant-aware.

Pattern

```text
WHERE company_id = current_company
```

Tenant filtering is mandatory unless executed by Super Admin.

---

# Configuration Pattern

Configuration values must come from:

```text
Environment Variables

↓

Settings

↓

Application
```

Never hardcode configuration values.

---

# Utility Pattern

Utility modules should remain stateless.

Examples

* Date Helpers
* UUID Helpers
* Token Helpers
* File Helpers

Utilities should never access the database.

---

# Naming Pattern

Services

```text
UserService
```

Repositories

```text
UserRepository
```

Schemas

```text
UserCreateSchema
```

Models

```text
User
```

Routes

```text
users.py
```

Consistency is more important than creativity.

---

# Async Pattern

Use async only when it provides measurable benefits.

Avoid unnecessary async complexity.

Database strategy should remain consistent across the project.

---

# Testing Pattern

Every Service should have:

* Unit Tests
* Integration Tests

Repositories should be tested against the database.

API endpoints should have endpoint tests.

---

# Folder Ownership

Each module owns:

* Models
* Schemas
* Repository
* Service
* Routes
* Tests

Modules should have minimal coupling.

---

# Code Reuse

Prefer reusable abstractions.

Avoid copy-paste.

Shared functionality belongs in:

```text
core/
```

---

# Anti-Patterns

Avoid

* Fat Routes
* Fat Models
* God Classes
* Circular Imports
* Duplicate Logic
* Global Mutable State
* Hardcoded Secrets
* Direct SQL in API Layer

---

# Refactoring Rules

Refactor when:

* Code duplication appears
* Complexity increases
* Maintainability decreases

Refactoring must not change observable behavior.

---

# AI Coding Rules

When AI generates code it must:

* Follow project architecture
* Respect folder structure
* Use existing patterns
* Avoid unnecessary abstractions
* Preserve naming consistency
* Generate tests where applicable

AI-generated code is subject to the same review standards as human-written code.

---

# Definition of Good Code

Good code is:

* Readable
* Maintainable
* Testable
* Secure
* Performant
* Consistent
* Well-documented

---

# Single Source of Truth

This document defines the official coding patterns for DevSphere ERP.

Every backend and frontend implementation must comply with these patterns.
