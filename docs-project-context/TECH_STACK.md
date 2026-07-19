# TECH_STACK.md

# DevSphere ERP

## Official Technology Stack

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official technology stack used throughout the DevSphere ERP platform.

It serves as the single source of truth for all approved frameworks, libraries, tools, languages, and infrastructure.

No developer should introduce a new technology without official approval.

---

# Technology Principles

The technology stack must always be:

* Stable
* Modern
* Long-term supported
* Open Source where possible
* Cloud Ready
* Docker Friendly
* Enterprise Grade
* AI Assisted Development Compatible

---

# Backend Stack

## Language

Python 3.12.x

Reason

* Excellent ecosystem
* FastAPI compatibility
* Long-term support
* SQLAlchemy compatibility
* AI ecosystem maturity

---

## Framework

FastAPI

Purpose

* REST APIs
* Validation
* Dependency Injection
* OpenAPI
* Swagger Documentation

---

## ASGI Server

Uvicorn

Purpose

* Development Server
* Production ASGI Runtime

---

## Data Validation

Pydantic v2

Purpose

* Request validation
* Response validation
* Configuration
* DTOs

---

## ORM

SQLAlchemy 2.x

Purpose

* Database Models
* Query Builder
* Relationships
* Transactions

---

## Database Migration

Alembic

Purpose

* Schema versioning
* Migration history
* Rollback support

---

## Authentication

JWT

Refresh Tokens

Argon2id Password Hashing

Purpose

* Secure authentication
* Token-based authorization
* Session management

---

## Rate Limiting

SlowAPI

Purpose

* Brute-force protection
* API abuse prevention

---

## Testing

Pytest

Pytest Asyncio

HTTPX

Coverage

Purpose

* Unit Testing
* Integration Testing
* API Testing

---

## Code Quality

Black

Ruff

MyPy

Purpose

* Formatting
* Linting
* Static Type Checking

---

## Package Manager

Poetry

Purpose

* Dependency management
* Virtual environments
* Lock file management
* Reproducible builds

All backend dependencies must be managed through Poetry.

---

# Frontend Stack

## Framework

Next.js

App Router

Purpose

* Enterprise frontend
* Server Components
* Client Components
* Routing
* API Integration

---

## Language

TypeScript

Purpose

* Strong typing
* Better maintainability
* Reduced runtime bugs

---

## UI Library

React

Purpose

* Component Architecture
* State Management
* Reusable UI

---

## Styling

Tailwind CSS

Purpose

* Utility-first styling
* Responsive Design
* Maintainability

---

## UI Components

shadcn/ui

Purpose

* Accessible components
* Consistent design system
* Enterprise UI

---

## Icons

Lucide React

Purpose

* Modern SVG icons
* Lightweight
* Consistent styling

---

## Forms

React Hook Form

Purpose

* High-performance forms
* Validation
* Easy integration

---

## Schema Validation

Zod

Purpose

* Client-side validation
* Shared validation rules
* Type-safe forms

---

## HTTP Client

Native Fetch API

Purpose

* Backend communication
* REST API requests

No Axios unless officially approved.

---

# Database

Primary Database

PostgreSQL

Purpose

* Enterprise relational database
* ACID compliance
* High performance
* Multi-tenant support

---

# Caching

Redis

Future Module

Purpose

* Session caching
* Rate limiting
* Background jobs
* Performance optimization

Redis is optional during initial development and becomes mandatory for production scaling.

---

# File Storage

Development

Local Storage

Production

Cloud Object Storage

Examples

* AWS S3
* Cloudflare R2
* Azure Blob Storage

No files should be stored directly inside the application container in production.

---

# Email Service

SMTP

Future Support

Possible Providers

* Amazon SES
* SendGrid
* Mailgun

Purpose

* Email verification
* Password reset
* Notifications

---

# Background Jobs

Future Technology

Celery

or

RQ

Purpose

* Email sending
* Report generation
* Scheduled tasks
* Long-running operations

---

# API Standard

REST API

JSON

OpenAPI 3.x

Swagger UI

Purpose

* Internal APIs
* Frontend communication
* Third-party integrations

---

# Security Stack

Authentication

JWT

Authorization

RBAC

Password Hashing

Argon2id

Transport

HTTPS

CORS

Enabled

Rate Limiting

Enabled

Security Headers

Enabled

Audit Logging

Enabled

---

# Deployment Stack

Containerization

Docker

Reverse Proxy

Nginx

SSL

Let's Encrypt

CI/CD

GitHub Actions

Deployment Targets

* Ubuntu Server
* Docker Host
* VPS
* Cloud VM

---

# Development Tools

Primary IDE

Visual Studio Code

Recommended Extensions

* Python
* Pylance
* Ruff
* Black Formatter
* Tailwind CSS IntelliSense
* ESLint
* Prettier
* Docker
* GitLens

---

# Version Control

Git

Repository

GitHub

Branch Strategy

* main
* develop
* feature/*
* hotfix/*
* release/*

Pull Requests are mandatory before merging into main.

---

# Documentation

Markdown

Purpose

* Specifications
* Architecture
* API Documentation
* Development Guides

All project documentation must remain under version control.

---

# AI Development Tools

Primary AI Assistant

ChatGPT

Purpose

* Architecture
* Planning
* Specifications
* Code Reviews
* Refactoring

Supporting Tools

* Claude Code
* GitHub Copilot (Optional)

AI-generated code must always be reviewed before merging.

---

# Monitoring (Future)

Recommended Stack

* Prometheus
* Grafana

Purpose

* Metrics
* Performance
* Alerts
* Resource Monitoring

---

# Logging

Python Logging

Structured Logs

Future Support

Centralized Logging

Examples

* Loki
* ELK Stack

Logs must never expose passwords, tokens, or sensitive user information.

---

# Performance Guidelines

* Async endpoints where appropriate.
* Database connection pooling.
* Efficient SQL queries.
* Proper indexing.
* Pagination for large datasets.
* Lazy/Eager loading only when justified.
* Avoid N+1 query problems.

Performance optimizations must preserve correctness.

---

# Upgrade Policy

Technology upgrades must follow these rules:

* Upgrade only to stable releases.
* Test in development first.
* Update documentation.
* Update lock files.
* Verify compatibility.
* Maintain backward compatibility whenever possible.

No dependency should be upgraded directly in production.

---

# Approved Core Stack Summary

Backend

* Python 3.12
* FastAPI
* SQLAlchemy
* Alembic
* Pydantic
* Poetry
* Uvicorn

Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* shadcn/ui
* React Hook Form
* Zod

Infrastructure

* PostgreSQL
* Docker
* Nginx
* GitHub Actions

Security

* JWT
* Argon2id
* RBAC
* HTTPS
* SlowAPI

---

# Single Source of Truth

This document is the official technology stack specification for DevSphere ERP.

Every implementation, dependency, framework, and deployment decision must conform to the standards defined in this document.
