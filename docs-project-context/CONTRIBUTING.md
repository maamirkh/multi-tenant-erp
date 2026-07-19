# CONTRIBUTING.md

# DevSphere ERP

## Contribution Guide

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official contribution process for the DevSphere ERP project.

Every contributor—whether human developer or AI assistant—must follow these standards.

The goals are:

* Consistency
* Maintainability
* High Quality
* Predictable Releases
* Professional Collaboration

---

# Who Can Contribute

Contributors may include:

* Core Developers
* Frontend Developers
* Backend Developers
* QA Engineers
* UI/UX Designers
* DevOps Engineers
* AI Assistants

Every contribution follows the same workflow.

---

# Project Philosophy

Before writing any code:

Understand

↓

Design

↓

Implement

↓

Test

↓

Review

↓

Merge

Never skip steps.

---

# Development Principles

Every contribution should be:

* Small
* Reviewable
* Well Tested
* Well Documented
* Independent

Large changes should be divided into multiple pull requests.

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

feature/inventory

feature/accounting

feature/crm
```

Bug fixes

```text
bugfix/login

bugfix/report-export
```

Hotfixes

```text
hotfix/security-patch
```

---

# Branch Naming Convention

Format

```text
feature/module-name

bugfix/module-name

hotfix/module-name

refactor/module-name

docs/document-name
```

Examples

```text
feature/auth-login

feature/purchase-orders

feature/product-images

bugfix/token-refresh

docs/api-standards
```

---

# Commit Message Convention

Format

```text
type(scope): short description
```

Examples

```text
feat(auth): implement refresh token rotation

fix(users): prevent duplicate emails

refactor(company): simplify tenant filtering

docs(api): update authentication examples

test(auth): add login integration tests
```

---

# Allowed Commit Types

```text
feat

fix

docs

style

refactor

perf

test

build

ci

chore
```

Keep commit messages short and meaningful.

---

# Pull Request Workflow

Implementation

↓

Testing

↓

Documentation

↓

Pull Request

↓

Review

↓

Approval

↓

Merge

---

# Pull Request Checklist

Every PR must include

* Summary
* Related Epic
* Related Story
* Related Tasks
* Testing Performed
* Database Changes
* API Changes
* Screenshots (UI)
* Documentation Updated

---

# Pull Request Size

Preferred

Small

Maximum

One Story

Avoid combining unrelated features.

---

# Code Review Requirements

Every review should verify

* Requirements satisfied
* Acceptance Criteria met
* Architecture respected
* Tests added
* Documentation updated
* Security considered
* Performance acceptable
* Naming consistent

---

# Review Checklist

Reviewer should ask

* Is the code readable?
* Is it maintainable?
* Is it secure?
* Is it testable?
* Does it follow project standards?
* Can duplication be reduced?

---

# Documentation Rule

Every feature affecting

* APIs
* Database
* Environment Variables
* Folder Structure
* Security
* Architecture

must update the corresponding documentation.

Documentation is mandatory.

---

# Testing Before Merge

Required

Backend

* Ruff
* Black
* MyPy
* Pytest

Frontend

* ESLint
* Type Check
* Unit Tests

No failing checks are allowed.

---

# Database Changes

Every schema change requires

* SQLAlchemy Model Update
* Alembic Migration
* Migration Review
* Migration Test

Never modify production schema manually.

---

# API Contributions

Every endpoint must include

* Route
* Request Schema
* Response Schema
* Validation
* Authorization
* Tests
* Documentation

---

# Frontend Contributions

Every screen must

* Use shared components
* Follow Design System
* Be responsive
* Support loading states
* Support empty states
* Handle API errors

---

# AI Contribution Rules

AI-generated code must

* Follow architecture
* Respect naming conventions
* Use existing patterns
* Avoid duplicate code
* Generate maintainable solutions

AI must not invent new project conventions.

---

# Code Style

Follow

* CODING_STANDARDS.md
* CODING_PATTERNS.md
* API_STANDARDS.md
* SECURITY_GUIDELINES.md

Never introduce conflicting styles.

---

# Security Rules

Never commit

* Secrets
* Passwords
* API Keys
* Tokens
* Certificates
* Database Credentials

Use environment variables.

---

# Dependency Management

Before adding a package

Verify

* Maintenance
* Community Support
* License
* Security
* Bundle Impact

Avoid unnecessary dependencies.

---

# Refactoring Rules

Refactoring is encouraged when

* Readability improves
* Duplication decreases
* Complexity decreases

Refactoring must not change business behavior.

---

# Bug Fix Policy

Every bug fix should include

* Root Cause
* Automated Test
* Manual Verification

Prevent future regressions.

---

# Performance Responsibility

Every contributor should consider

* Query Efficiency
* API Response Time
* Bundle Size
* Memory Usage

Performance is everyone's responsibility.

---

# Communication

When proposing changes

Explain

* Why
* What
* Impact
* Risks

Clear communication reduces review time.

---

# Definition of Ready

A task is ready when

* Requirements approved
* Acceptance Criteria defined
* Dependencies identified
* Design available

---

# Definition of Done

A contribution is complete only when

* Code implemented
* Tests passed
* Lint passed
* Type checks passed
* Documentation updated
* Code reviewed
* Approved
* Merged

---

# Release Responsibility

Before every release verify

* All tests pass
* Documentation updated
* Migrations verified
* Security reviewed
* Release notes prepared

---

# Professional Conduct

Every contributor should

* Respect coding standards
* Write readable code
* Accept constructive reviews
* Prioritize maintainability
* Keep discussions professional

---

# Continuous Improvement

The project encourages

* Better documentation
* Better testing
* Better architecture
* Better developer experience
* Better AI prompts

Improvements should strengthen long-term maintainability.

---

# Single Source of Truth

This document defines the official contribution process for DevSphere ERP.

Every contribution—from a one-line bug fix to a major feature—must comply with these standards.
