# PROJECT_RULES.md

# DevSphere ERP

## Global Project Rules

Version: 1.0

Status: Approved

---

# Purpose

This document defines the non-negotiable rules governing the DevSphere ERP project.

These rules apply to:

* Human Developers
* AI Assistants
* Code Reviewers
* Architects
* Future Contributors

This document has the highest priority after the approved project specifications.

---

# Core Philosophy

DevSphere ERP is designed as a long-term enterprise SaaS platform.

Every decision must favor:

* Maintainability
* Scalability
* Security
* Simplicity
* Consistency

Never sacrifice long-term quality for short-term convenience.

---

# Single Source of Truth

The following documents are authoritative.

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

If two documents conflict, the latest approved specification takes precedence.

---

# Architecture Rule

The approved architecture must never be changed without explicit approval.

Examples

Do NOT

* Replace Clean Architecture
* Replace Repository Pattern
* Replace Service Layer
* Replace Multi-Tenant Strategy

Architecture changes require formal approval.

---

# Tech Stack Rule

Approved technologies are fixed unless officially changed.

Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL

Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS

Infrastructure

* Docker
* GitHub
* Poetry
* Vercel (Frontend)
* VPS/Cloud (Backend)

Do not introduce alternative frameworks without approval.

---

# Multi-Tenant Rule

Every module must remain tenant-aware.

Every database query must isolate tenant data.

No feature may bypass tenant isolation except Super Admin functionality.

Tenant isolation is mandatory.

---

# Security Rule

Never compromise security for convenience.

Always

* Validate Input
* Authorize Requests
* Authenticate Users
* Hash Passwords
* Protect Secrets
* Audit Critical Events

Never disable security features during development.

---

# Database Rule

Database schema changes require:

* Updated Models
* Alembic Migration
* Migration Review
* Testing

Direct manual schema edits are prohibited.

---

# API Rule

Every endpoint requires:

* Validation
* Authentication
* Authorization
* Typed Schemas
* Standard Responses
* Error Handling
* Tests

---

# UI Rule

All frontend screens must follow the official Design System.

Never create one-off UI components.

Reuse shared components whenever possible.

---

# Coding Rule

Every implementation must follow:

* SOLID
* DRY
* KISS
* Clean Code
* Consistent Naming
* Layered Architecture

---

# Folder Rule

Never place files outside the approved project structure.

New folders require architectural approval.

---

# Naming Rule

Use descriptive names.

Avoid abbreviations unless industry standard.

Examples

Good

```text id="rule1"
InventoryService

PurchaseRepository

CustomerCreateSchema
```

Bad

```text id="rule2"
InvSvc

Repo1

DataModel
```

---

# Testing Rule

No feature is complete without testing.

Required

* Unit Tests
* Integration Tests
* API Tests

Critical modules require high coverage.

---

# Documentation Rule

Every major change must update documentation.

Documentation is part of the implementation.

---

# Performance Rule

Performance must be considered from the beginning.

Avoid

* N+1 Queries
* Duplicate Requests
* Large Payloads
* Blocking Operations

---

# Logging Rule

Log

* Important Business Events
* Errors
* Security Events

Never log

* Passwords
* Tokens
* Secrets
* Personal Sensitive Data

---

# Dependency Rule

Before adding any dependency verify

* Maintenance
* Security
* Community Adoption
* License
* Long-Term Support

Avoid unnecessary packages.

---

# AI Assistant Rule

AI assistants must:

* Read project context first
* Respect architecture
* Follow coding standards
* Reuse existing patterns
* Avoid inventing new conventions
* Preserve consistency

AI should extend the project—not redesign it.

---

# Prompt Rule

Every implementation prompt should include

* Epic
* Phase
* Story
* Acceptance Criteria
* Constraints
* Files to Modify
* Files to Create
* Files Not to Modify

Prompts should minimize ambiguity.

---

# Code Review Rule

Every review should verify

* Correctness
* Security
* Performance
* Readability
* Consistency
* Documentation
* Tests

---

# Release Rule

A release cannot proceed unless

* Tests Pass
* Lint Passes
* Migrations Verified
* Documentation Updated
* Security Reviewed

---

# Refactoring Rule

Refactoring is encouraged.

However

Refactoring must never change business behavior without approval.

---

# Backward Compatibility

Avoid breaking existing APIs.

If breaking changes are unavoidable

* Document them
* Version them
* Communicate them

---

# Configuration Rule

Configuration belongs only in

* Environment Variables
* Settings

Never hardcode environment-specific values.

---

# Git Rule

Every change must use

* Feature Branch
* Meaningful Commit
* Pull Request
* Code Review

Direct commits to main are prohibited.

---

# Definition of Success

A successful feature is

* Correct
* Secure
* Tested
* Documented
* Maintainable
* Performant
* Consistent

Not merely "working."

---

# Future Growth Rule

Every implementation should consider future scalability.

Ask

"Will this still work when there are 10,000 companies and millions of records?"

If the answer is no, redesign before implementation.

---

# Decision Hierarchy

When making technical decisions, follow this priority:

1. Approved Specifications
2. Project Rules
3. Architecture Documents
4. Coding Standards
5. Performance Guidelines
6. Personal Preference

Personal preference must never override project standards.

---

# Change Management

Any significant change to

* Architecture
* Database Design
* Security
* Authentication
* Multi-Tenant Logic
* API Standards

requires explicit approval before implementation.

---

# Final Principle

Consistency is more valuable than cleverness.

A predictable system is easier to maintain, easier to scale and easier for both humans and AI assistants to understand.

---

# Single Source of Truth

PROJECT_RULES.md is the master governance document for DevSphere ERP.

Every contributor, every AI assistant and every future implementation must comply with these rules.
