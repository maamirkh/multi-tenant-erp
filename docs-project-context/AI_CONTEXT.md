# AI_CONTEXT.md

# DevSphere ERP

## AI Context File

Version: 1.0

Status: Active

---

# Purpose

This document provides a condensed project context for AI assistants.

It should be shared at the beginning of every new AI session.

Its purpose is to quickly establish the project's architecture, standards, constraints, and current development state without requiring every project document.

This file is **not** a replacement for the official documentation. It is a navigation and context guide.

---

# Project Overview

Project Name

```text
DevSphere ERP
```

Project Type

```text
Enterprise Multi-Tenant SaaS ERP
```

Architecture

```text
Modular Monolith
```

Future

```text
Microservice Ready
```

Deployment Model

```text
Multi-Tenant SaaS
```

---

# Primary Goals

Build a professional ERP platform that can support:

* Small Businesses
* Medium Businesses
* Large Enterprises

The platform should eventually become a globally deployable SaaS product.

---

# Current Development Status

Current Version

```text
v1.0
```

Current Epic

```text
Epic 002
Authentication & Identity
```

Current Development Strategy

```text
Epic

↓

Phase

↓

Story

↓

Tasks

↓

Implementation

↓

Testing
```

Every phase is completed before moving to the next.

---

# Technology Stack

Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Poetry

Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* shadcn/ui

Authentication

* JWT
* Refresh Tokens
* Argon2id

Testing

* Pytest
* React Testing Library

Infrastructure

* Docker
* GitHub
* Vercel
* VPS / Cloud

---

# Architecture

Architecture Style

```text
Client

↓

API Layer

↓

Service Layer

↓

Repository Layer

↓

Database
```

Business logic belongs only inside the Service Layer.

Repositories only access the database.

Routes never contain business logic.

---

# Design Principles

Always follow

* SOLID
* DRY
* KISS
* Clean Architecture
* Separation of Concerns
* Dependency Injection

---

# Multi-Tenant Rules

Every record belongs to a company.

Every query must filter by

```text
company_id
```

No tenant can access another tenant's data.

Tenant isolation is mandatory.

---

# Authentication Rules

Authentication system includes

* JWT Access Tokens
* Refresh Tokens
* Remember Me
* Email Verification
* Password Reset
* Session Management
* Account Lockout
* Audit Logging

Passwords use

```text
Argon2id
```

---

# Database

Database

```text
PostgreSQL
```

Migrations

```text
Alembic
```

Never modify schema manually.

Every schema change requires a migration.

---

# Folder Structure

Backend

```text
api/

core/

modules/

migrations/

tests/
```

Frontend

```text
app/

components/

hooks/

lib/

services/

types/
```

---

# Coding Rules

Always

* Use Type Hints
* Use DTOs
* Use Repository Pattern
* Use Services
* Use Dependency Injection

Never

* Put SQL in Routes
* Put Business Logic in Controllers
* Duplicate Code
* Hardcode Secrets

---

# API Rules

Every endpoint requires

* Validation
* Authentication
* Authorization
* Typed Schemas
* Error Handling
* Tests

---

# UI Rules

Frontend follows

* Design System
* Responsive Design
* Accessibility
* Dark Mode
* Reusable Components

---

# Performance Rules

Always

* Paginate
* Index
* Optimize Queries
* Avoid N+1
* Cache when appropriate

Never

* SELECT *
* Load entire tables
* Return huge payloads

---

# Security Rules

Always

* Validate Input
* Hash Passwords
* Protect Secrets
* Use Environment Variables
* Log Security Events

Never

* Log Passwords
* Store Plain Text Secrets
* Disable Authentication

---

# Testing Rules

Every feature requires

* Unit Tests
* Integration Tests
* API Tests

Critical modules require high coverage.

---

# Documentation Rules

If implementation changes

* Architecture
* API
* Database
* Security
* Environment Variables

Update documentation.

---

# AI Assistant Instructions

Before generating code

1. Read this file.
2. Follow project standards.
3. Respect folder structure.
4. Reuse existing patterns.
5. Preserve naming conventions.
6. Avoid introducing new architecture.
7. Do not redesign existing code unless explicitly instructed.

When unsure, ask for clarification rather than making assumptions.

---

# AI Prompt Format

Implementation prompts should include

* Epic
* Phase
* Story
* Tasks
* Acceptance Criteria
* Files to Create
* Files to Modify
* Files Not to Modify
* Constraints
* Completion Checklist

---

# Current Documentation

Official project documents include

* PROJECT_CONTEXT.md
* BUSINESS_REQUIREMENTS.md
* SYSTEM_ARCHITECTURE.md
* DATABASE_DESIGN.md
* EPICS.md
* TECH_STACK.md
* CODING_STANDARDS.md
* CODING_PATTERNS.md
* FOLDER_STRUCTURE.md
* API_STANDARDS.md
* SECURITY_GUIDELINES.md
* DEVELOPMENT_WORKFLOW.md
* DEPLOYMENT_GUIDE.md
* TESTING_STRATEGY.md
* UI_UX_GUIDELINES.md
* PERFORMANCE_GUIDELINES.md
* CONTRIBUTING.md
* ROADMAP.md
* PROJECT_RULES.md

Refer to those documents whenever detailed implementation guidance is required.

---

# Current Vision

DevSphere ERP aims to become a complete enterprise business platform including

* Inventory
* Sales
* Purchases
* Accounting
* HR
* CRM
* Manufacturing
* Projects
* Reporting
* AI Assistant
* AI Automation
* Mobile Apps
* Public APIs
* Marketplace

---

# Success Criteria

Every implementation should be

* Correct
* Secure
* Scalable
* Performant
* Maintainable
* Well Tested
* Well Documented

Consistency is more important than cleverness.

---

# Single Source of Truth

This file is the official quick-start context for AI assistants.

Read this document first.

Then consult the relevant project documents for implementation details.
