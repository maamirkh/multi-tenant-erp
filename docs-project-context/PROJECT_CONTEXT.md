# PROJECT_CONTEXT.md

# DevSphere ERP

## Master Project Context

Version: 1.0

Status: In Development

Current Epic: Epic 2 – Authentication

Current Phase: Phase 4

---

# 1. Project Overview

DevSphere ERP is a modern, enterprise-grade, AI-ready, cloud-native, multi-tenant ERP platform designed to support businesses of different industries through a single configurable system.

The ERP is **not** built specifically for Home Appliances. Instead, it is designed as a generic ERP platform that can be customized for multiple business domains including wholesalers, retailers, distributors, manufacturers, construction companies, service providers, trading companies and future business types.

The long-term objective is to build a commercial SaaS ERP platform capable of serving thousands of companies from a single codebase while maintaining complete tenant isolation, security, scalability and maintainability.

---

# 2. Project Vision

The goal is to build an ERP that is:

* Enterprise Grade
* Multi Tenant
* Cloud Native
* AI Ready
* Modular
* Highly Scalable
* Secure by Default
* API First
* Mobile Friendly
* Easy to Extend
* Easy to Maintain
* Suitable for SaaS Deployment
* Suitable for On-Premise Deployment

Every module must follow the same architecture and coding standards.

---

# 3. Development Methodology

The project follows **Specification Driven Development (SDD).**

Development order is always:

Constitution

↓

Specifications

↓

Tasks

↓

Implementation

↓

Testing

↓

Review

↓

Next Phase

No implementation should be done without an approved specification.

---

# 4. Project Architecture

The system follows Clean Architecture with strict separation of responsibilities.

Architecture layers include:

* API Layer
* Service Layer
* Repository Layer
* Database Layer
* Shared Core
* Infrastructure Layer

Business logic must never exist inside API routes.

Repositories are responsible only for database access.

Services contain business rules.

---

# 5. Technology Stack

## Backend

* Python 3.12
* FastAPI
* SQLAlchemy 2.x
* Alembic
* PostgreSQL
* Poetry
* Pydantic v2
* JWT Authentication
* Argon2id Password Hashing

## Frontend

* Next.js App Router
* React
* TypeScript
* Tailwind CSS

---

# 6. Database

Database Engine:

PostgreSQL

ORM:

SQLAlchemy 2.x

Migration Tool:

Alembic

Primary Keys:

UUID

Soft Delete:

Enabled where applicable.

Audit Logging:

Enabled.

---

# 7. Security Standards

Authentication:

JWT Access Token

Refresh Token Rotation

Argon2id Password Hashing

Email Verification

Password Reset

Session Management

Audit Logs

Account Lockout Protection

Rate Limiting

RBAC Authorization

Company Isolation

Security is considered a core feature of the platform.

---

# 8. Multi-Tenant Architecture

Every business operates as an independent tenant.

A tenant cannot access another tenant's data.

All business modules must enforce tenant isolation.

Future modules must always be designed with multi-tenancy in mind.

---

# 9. Development Rules

Every implementation must follow these principles:

* Clean Architecture
* SOLID Principles
* Repository Pattern
* Service Layer Pattern
* Dependency Injection
* Strong Typing
* Modular Design
* Production Ready Code
* Enterprise Coding Standards

No shortcuts are allowed.

No temporary code.

No placeholder business logic unless explicitly defined in the specification.

---

# 10. Quality Standards

Every implementation must:

* Pass Ruff
* Pass Black
* Pass MyPy
* Pass Tests
* Include Type Hints
* Include Docstrings where appropriate
* Avoid Code Duplication
* Follow Existing Project Structure

---

# 11. Development Workflow

Development always follows:

Epic

↓

Phase

↓

Implementation Prompt

↓

Implementation

↓

Code Review

↓

Testing

↓

Approval

↓

Next Phase

No future Epic should be implemented before completing the current Epic.

---

# 12. ERP Roadmap

The project consists of the following Epics:

Epic 0 — Constitution

Epic 1 — Foundation

Epic 2 — Authentication

Epic 3 — Companies

Epic 4 — Users & Roles

Epic 5 — Inventory

Epic 6 — Purchase

Epic 7 — Sales

Epic 8 — Accounting

Epic 9 — CRM

Epic 10 — Installments

Epic 11 — Reports

Epic 12 — Deployment

Each Epic is independently specified, implemented, tested and reviewed.

---

# 13. Current Project Status

Completed:

* Epic 0 — Constitution
* Epic 1 — Foundation

In Progress:

* Epic 2 — Authentication

Pending:

* Epic 3 — Companies
* Epic 4 — Users & Roles
* Epic 5 — Inventory
* Epic 6 — Purchase
* Epic 7 — Sales
* Epic 8 — Accounting
* Epic 9 — CRM
* Epic 10 — Installments
* Epic 11 — Reports
* Epic 12 — Deployment

---

# 14. AI Collaboration Rules

Whenever an AI assistant works on this project, it must:

* Read this document before implementation.
* Follow the approved specifications.
* Follow the Tasks document.
* Respect project architecture.
* Never redesign completed modules.
* Never modify completed Epics unless fixing a verified bug.
* Never implement future Epics unless explicitly instructed.
* Keep changes limited to the requested Phase.
* Produce production-ready code only.

This document acts as the master context for the entire DevSphere ERP project.
