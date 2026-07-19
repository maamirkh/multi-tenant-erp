# DEVELOPMENT_WORKFLOW.md

# DevSphere ERP

## Official Development Workflow

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official development workflow for the DevSphere ERP project.

Every feature, bug fix, enhancement, and refactor must follow this workflow.

This ensures:

* Consistent development
* Predictable releases
* Enterprise-level quality
* AI-friendly implementation
* Easy collaboration
* Minimal technical debt

---

# Development Philosophy

The project follows:

* Spec-Driven Development
* AI-Assisted Development
* Test-Driven Mindset
* Incremental Delivery
* Small Reviewable Changes
* Documentation First

Development should never start without an approved specification.

---

# Project Workflow

The implementation hierarchy is:

```text
Vision

↓

Requirements

↓

Epics

↓

Stories

↓

Tasks

↓

Implementation

↓

Testing

↓

Review

↓

Release
```

No implementation should skip any level.

---

# Spec-Driven Development (SDD)

The entire project follows Spec-Driven Development.

Every feature begins with:

* Requirements
* Acceptance Criteria
* Technical Design
* Database Impact
* API Design
* UI Design (if applicable)
* Testing Requirements

Only after approval can implementation begin.

---

# Epic Workflow

Every Epic follows the same lifecycle.

```text
Epic

↓

Stories

↓

Tasks

↓

Implementation Phases

↓

Testing

↓

Review

↓

Completed
```

Each Epic is implemented independently.

---

# Story Workflow

Each Story must include:

* Business Goal
* User Story
* Acceptance Criteria
* Dependencies
* Technical Notes

Stories should be independently testable.

---

# Task Workflow

Each task should:

* Solve one problem
* Be reviewable
* Be testable
* Be independently verifiable

Avoid combining multiple unrelated tasks.

---

# Implementation Phases

Every Epic should be divided into phases.

Example

```text
Phase 1

Foundation

↓

Phase 2

Backend

↓

Phase 3

Frontend

↓

Phase 4

Testing

↓

Phase 5

Documentation
```

Large Epics may contain additional phases.

---

# AI Development Workflow

AI should receive:

* One Epic
* One Phase
* One set of Tasks

Never ask AI to implement the entire ERP in a single prompt.

Preferred workflow:

```text
Epic

↓

Phase

↓

Prompt

↓

Implementation

↓

Review

↓

Next Phase
```

---

# Prompt Standards

Every implementation prompt should include:

* Objective
* Scope
* Tasks
* Constraints
* Files to Modify
* Acceptance Criteria
* Rules
* Deliverables

The prompt must clearly define what AI should and should not implement.

---

# Branch Strategy

Main branches

```text
main

develop
```

Feature branches

```text
feature/authentication

feature/companies

feature/inventory
```

Bug fixes

```text
bugfix/login-validation
```

Hotfixes

```text
hotfix/jwt-expiration
```

---

# Git Workflow

Recommended process

```text
Create Branch

↓

Implement

↓

Run Tests

↓

Commit

↓

Push

↓

Pull Request

↓

Review

↓

Merge
```

Direct commits to `main` are prohibited.

---

# Commit Message Convention

Format

```text
type(scope): description
```

Examples

```text
feat(auth): implement JWT refresh token rotation

fix(users): prevent duplicate email creation

refactor(companies): simplify repository queries

docs(api): update authentication examples

test(auth): add login integration tests
```

---

# Pull Request Requirements

Every Pull Request must include:

* Summary
* Related Epic
* Related Story
* Related Tasks
* Testing Performed
* Screenshots (UI changes)
* Migration Notes (if applicable)
* Breaking Changes (if any)

---

# Code Review Checklist

Reviewers must verify:

* Requirements satisfied
* Acceptance criteria met
* Architecture followed
* Naming conventions followed
* Tests passing
* Security considered
* Documentation updated
* No duplicated code
* Performance acceptable

---

# Database Workflow

Schema changes require:

1. Update SQLAlchemy Models
2. Generate Alembic Migration
3. Review Migration
4. Apply Migration
5. Test Upgrade
6. Test Downgrade (where practical)

Never modify production tables manually.

---

# Migration Rules

Migration files must:

* Be small
* Be reversible where possible
* Have descriptive names
* Be committed with related code

Never edit previously applied migrations in shared environments.

---

# API Workflow

Every new endpoint requires:

* Route
* Schema
* Service
* Repository
* Tests
* Swagger Documentation

Endpoints must comply with `API_STANDARDS.md`.

---

# Frontend Workflow

Every UI feature should follow:

```text
Design

↓

Component

↓

Hook

↓

API Integration

↓

Validation

↓

Testing
```

Avoid embedding business logic inside UI components.

---

# Testing Workflow

Every phase ends with testing.

Testing layers

* Unit Tests
* Integration Tests
* API Tests
* UI Tests (where applicable)
* Manual Verification

Critical business logic must be covered by automated tests.

---

# Linting & Formatting

Before every commit run:

```text
Backend

ruff check

black .

mypy

pytest
```

Frontend

```text
npm run lint

npm run type-check

npm run test
```

No code should be merged with failing checks.

---

# Documentation Workflow

Documentation must be updated when:

* API changes
* Database changes
* Environment variables change
* Folder structure changes
* Architecture changes
* Business rules change

Documentation is part of the implementation.

---

# Definition of Ready (DoR)

A task is ready only when:

* Requirements are clear
* Acceptance criteria defined
* Dependencies identified
* Technical approach approved
* Required designs available
* Risks understood

Implementation should not start before DoR.

---

# Definition of Done (DoD)

A task is complete only when:

* Code implemented
* Tests passing
* Lint passing
* Type checks passing
* Documentation updated
* Code reviewed
* Acceptance criteria satisfied
* No critical issues remain

---

# Release Workflow

Release process

```text
Develop

↓

Testing

↓

Bug Fixes

↓

Release Candidate

↓

Production Deployment

↓

Monitoring
```

Every release must have release notes.

---

# Bug Fix Workflow

Process

```text
Identify

↓

Reproduce

↓

Fix

↓

Test

↓

Review

↓

Deploy
```

Every bug should include a root cause analysis.

---

# Refactoring Policy

Refactoring is allowed only when:

* Behavior does not change
* Tests continue to pass
* Documentation remains accurate

Large refactors should be planned separately from feature work.

---

# AI Review Policy

AI-generated code must always be:

* Reviewed
* Tested
* Refactored if necessary
* Verified against project standards

AI accelerates development but does not replace engineering judgment.

---

# Release Checklist

Before every production release verify:

* All tests pass
* Database migrations verified
* Environment variables configured
* Security checks completed
* Performance acceptable
* Documentation updated
* Backup completed
* Rollback plan prepared

---

# Continuous Improvement

After each Epic:

* Review implementation
* Record lessons learned
* Improve prompts
* Improve documentation
* Reduce technical debt

The workflow should evolve without compromising stability.

---

# Single Source of Truth

This document defines the official development workflow for DevSphere ERP.

Every developer, reviewer, and AI assistant must follow this workflow throughout the lifecycle of the project.
