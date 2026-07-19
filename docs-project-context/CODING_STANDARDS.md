# CODING_STANDARDS.md

# DevSphere ERP

## Official Coding Standards

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official coding standards for DevSphere ERP.

Every developer, AI assistant, and contributor must follow these standards to ensure consistency, maintainability, scalability, and enterprise-grade code quality.

No code should be merged unless it complies with this document.

---

# Engineering Principles

Every piece of code must be:

* Readable
* Predictable
* Maintainable
* Testable
* Secure
* Reusable
* Scalable
* Type Safe

Code is written for humans first, computers second.

---

# Architecture Principles

The ERP follows:

* Clean Architecture
* Layered Architecture
* Domain Driven Design (lightweight)
* SOLID Principles
* Separation of Concerns
* Dependency Injection
* Repository Pattern
* Service Layer Pattern

Business logic must never exist inside controllers or API routes.

---

# SOLID Principles

Every module must follow SOLID.

## S — Single Responsibility

Each class should have one responsibility.

Good

UserService

Bad

UserServiceThatAlsoSendsEmailsAndCreatesInvoices

---

## O — Open Closed

Classes should be extendable without modification.

Use interfaces and abstractions.

---

## L — Liskov Substitution

Derived classes must behave exactly like their parent contract.

---

## I — Interface Segregation

Small focused interfaces.

Avoid giant interfaces.

---

## D — Dependency Inversion

Depend on abstractions.

Never depend directly on implementations.

---

# Clean Code Rules

Always write code that is:

Simple

Readable

Explicit

Predictable

Avoid clever code.

Readable code is preferred over shorter code.

---

# Naming Conventions

## Variables

Use descriptive names.

Good

```python
customer_name
invoice_total
remaining_balance
```

Bad

```python
a
x
temp
abc
```

---

## Functions

Use verbs.

Good

```python
create_company()
calculate_tax()
verify_password()
```

Bad

```python
company()
tax()
password()
```

---

## Classes

Use PascalCase.

Example

```python
UserService
CompanyRepository
InvoiceController
```

---

## Constants

Use UPPER_CASE.

Example

```python
MAX_LOGIN_ATTEMPTS
DEFAULT_PAGE_SIZE
```

---

## Files

snake_case

Example

```
user_service.py
invoice_repository.py
company_routes.py
```

---

## Directories

snake_case

Example

```
modules/
shared/
repositories/
services/
```

---

# Python Standards

Follow:

PEP 8

Type Hints

Docstrings

Meaningful exceptions

Strict typing

Avoid wildcard imports.

Never disable lint rules without justification.

---

# Type Hint Policy

Every function must define parameter and return types.

Good

```python
def create_user(user: UserCreate) -> User:
```

Bad

```python
def create_user(user):
```

---

# Docstrings

Every public function must include a concise docstring.

Example

```python
def login(credentials: LoginRequest) -> TokenResponse:
    """Authenticate a user and return JWT tokens."""
```

---

# Comments

Comments should explain WHY.

Never explain obvious code.

Good

```python
# Prevent timing attacks during password verification.
```

Bad

```python
# Increment i.
i += 1
```

---

# Function Rules

Functions should:

Do one thing.

Be small.

Avoid deep nesting.

Maximum recommended length:

40 lines

If longer:

Refactor.

---

# Class Rules

Classes should represent one concept.

Avoid God Classes.

Prefer composition over inheritance.

---

# Error Handling

Never silently ignore exceptions.

Good

```python
raise AuthenticationException("Invalid credentials")
```

Bad

```python
except:
    pass
```

Always raise meaningful custom exceptions.

---

# Logging Standards

Log:

Errors

Warnings

Security events

Business events

Never log:

Passwords

JWT Tokens

Refresh Tokens

Secret Keys

Credit Card Numbers

Personally sensitive information

---

# Security Rules

Never hardcode:

Passwords

API Keys

Secrets

Database Credentials

JWT Secrets

Everything must come from environment variables.

---

# API Standards

Every endpoint must:

Validate input

Return consistent responses

Use HTTP status codes correctly

Handle exceptions

Document request/response models

---

# Response Format

All APIs should follow a consistent response structure.

Success

```json
{
  "success": true,
  "message": "Operation completed successfully.",
  "data": {}
}
```

Failure

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": []
}
```

---

# Database Rules

Never write raw SQL unless necessary.

Prefer SQLAlchemy ORM.

Always use transactions where appropriate.

Never commit partial business operations.

Use indexes intentionally.

Avoid N+1 queries.

---

# Repository Pattern

Repositories handle:

Database access only.

Never business logic.

Good

Repository

↓

Database

Business rules belong in Services.

---

# Service Layer

Services handle:

Business rules

Validation

Workflow

Transactions

Authorization decisions

Services should not know about HTTP.

---

# Dependency Injection

Always inject dependencies.

Avoid creating services directly inside controllers.

Good

```python
UserService(UserRepository)
```

Bad

```python
repo = UserRepository()
```

---

# Frontend Standards

Use:

Functional Components

TypeScript

Hooks

Composition

Reusable Components

Avoid duplicated UI.

---

# React Rules

Prefer:

Custom Hooks

Small Components

Server Components where appropriate

Client Components only when necessary

---

# State Management

Priority

1. React State

2. Context API

3. Server State

Introduce additional state libraries only when justified.

---

# Styling Rules

Tailwind CSS only.

No inline CSS unless absolutely necessary.

Create reusable UI components.

---

# Folder Organization

Each module should contain:

```
module/

    api/

    schemas/

    services/

    repositories/

    models/

    validators/

    tests/
```

Maintain the same structure across all modules.

---

# Testing Standards

Every Epic must include:

Unit Tests

Integration Tests

API Tests

Target coverage:

Minimum 80%

Critical authentication and financial logic should aim for higher coverage.

---

# Git Standards

Commit messages should be meaningful.

Good

```
Add refresh token rotation support
```

Bad

```
fix

update

changes
```

---

# Pull Request Standards

Every Pull Request should include:

Purpose

Scope

Screenshots (if UI)

Testing Notes

Migration Notes (if applicable)

Related Task

No direct commits to the main branch.

---

# Performance Guidelines

Avoid unnecessary database queries.

Avoid unnecessary renders.

Cache expensive operations where appropriate.

Paginate large datasets.

Optimize indexes before optimizing code.

---

# Documentation Standards

Every module must include:

README

API documentation

Architecture notes (if needed)

Complex business logic explanation

Documentation is part of the implementation.

---

# AI Generated Code Policy

AI may assist development.

However:

Every generated file must be:

Reviewed

Tested

Refactored if necessary

Documented

Developers remain responsible for all committed code.

---

# Code Review Checklist

Before merging verify:

* Code follows architecture.
* Naming conventions are correct.
* No duplicated logic.
* Tests pass.
* Lint passes.
* Types pass.
* Documentation updated.
* Security reviewed.
* Performance considered.
* No secrets committed.

---

# Definition of Done

A task is complete only when:

* Implementation finished.
* Tests passing.
* Lint passing.
* Type checking passing.
* Documentation updated.
* Code reviewed.
* Acceptance criteria satisfied.
* No critical warnings remain.

---

# Single Source of Truth

This document defines the official coding standards for DevSphere ERP.

Every line of code written for this project must comply with these standards.
