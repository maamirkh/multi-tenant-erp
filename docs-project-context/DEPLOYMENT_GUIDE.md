# DEPLOYMENT_GUIDE.md

# DevSphere ERP

## Official Deployment Guide

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official deployment strategy for the DevSphere ERP platform.

It covers:

* Local Development
* Testing
* Staging
* Production
* CI/CD
* Monitoring
* Backup
* Disaster Recovery
* Scaling

This document is the single source of truth for deployment.

---

# Deployment Philosophy

Every deployment must be:

* Automated
* Reproducible
* Secure
* Versioned
* Rollback Ready
* Zero Data Loss
* Observable

Manual production deployments should be avoided.

---

# Deployment Environments

The project supports four environments.

```text
Local Development

↓

Testing

↓

Staging

↓

Production
```

Each environment has independent configuration.

---

# Environment Configuration

Every environment has its own:

* Database
* Environment Variables
* Secrets
* Domain
* Logging
* Storage

Never share production credentials with development.

---

# Local Development

Purpose

Feature development.

Components

* Next.js
* FastAPI
* PostgreSQL
* Alembic
* Poetry
* Docker (optional)

Typical URLs

```text
Frontend
http://localhost:3000

Backend
http://localhost:8000

Swagger
http://localhost:8000/docs
```

---

# Testing Environment

Purpose

Automated testing.

Characteristics

* Disposable database
* Seed data
* Automated setup
* CI execution

No production data.

---

# Staging Environment

Purpose

Final validation before production.

Must mirror production as closely as possible.

Includes

* HTTPS
* Real authentication
* Production configuration
* Monitoring
* Logging

---

# Production Environment

Purpose

Live customer usage.

Characteristics

* High availability
* HTTPS only
* Monitoring enabled
* Backups enabled
* Automatic restart
* Secure configuration

---

# Recommended Architecture

```text
Internet

↓

Nginx

↓

Frontend (Next.js)

↓

Backend (FastAPI)

↓

PostgreSQL

↓

File Storage
```

Future additions

* Redis
* Background Workers
* Object Storage
* Search Engine

---

# Docker

Every service should support Docker.

Recommended containers

```text
frontend

backend

postgres

nginx
```

Optional

```text
redis

worker
```

---

# Docker Compose

Development should use Docker Compose.

Example services

```text
frontend

backend

postgres
```

One command should start the complete stack.

---

# Reverse Proxy

Production should use:

Nginx

Responsibilities

* HTTPS
* Compression
* Static files
* Reverse Proxy
* Rate Limiting
* Security Headers

---

# SSL

HTTPS is mandatory.

Certificates

Preferred

Let's Encrypt

Automatic renewal recommended.

---

# Environment Variables

Configuration belongs in:

```text
.env

.env.production

.env.example
```

Never hardcode:

* Passwords
* API Keys
* JWT Secrets
* Database Credentials

---

# Required Backend Variables

Examples

```text
DATABASE_URL

SECRET_KEY

JWT_SECRET_KEY

ENVIRONMENT

DEBUG

LOG_LEVEL

CORS_ORIGINS
```

---

# Required Frontend Variables

Examples

```text
NEXT_PUBLIC_API_URL

NEXT_PUBLIC_APP_NAME
```

Only public values may use the `NEXT_PUBLIC_` prefix.

---

# Database Deployment

Database engine

PostgreSQL

Schema management

Alembic

Deployment sequence

```text
Backup

↓

Migration

↓

Verification

↓

Application Start
```

Never skip database backups.

---

# Migration Workflow

Production deployment

```text
alembic upgrade head
```

Migration rules

* Review before deployment
* Backup first
* Test on staging
* Verify after execution

---

# Backend Deployment

Recommended server

Uvicorn behind Nginx.

Production command

```text
uvicorn main:app
```

Process manager

Recommended

* systemd
* Supervisor
* Docker
* Kubernetes

---

# Frontend Deployment

Framework

Next.js

Recommended hosting

* Vercel
* Self-hosted Node.js
* Docker

Build process

```text
npm install

↓

npm run build

↓

npm start
```

---

# Static Assets

Store

* Images
* Logos
* Documents

Large files should not live inside the application container.

Future recommendation

Object Storage

* AWS S3
* Cloudflare R2
* MinIO

---

# CI/CD

Every commit should trigger:

```text
Install

↓

Lint

↓

Type Check

↓

Tests

↓

Build

↓

Security Scan

↓

Deploy
```

Deployment only occurs if all checks pass.

---

# GitHub Actions

Recommended pipeline

```text
Checkout

↓

Setup Python

↓

Setup Node

↓

Install Dependencies

↓

Run Backend Tests

↓

Run Frontend Tests

↓

Build Backend

↓

Build Frontend

↓

Deploy
```

---

# Health Checks

Backend

```text
GET /health
```

Should verify

* API
* Database
* Version

Load balancers use health endpoints to determine service availability.

---

# Logging

Application logs should include

* Timestamp
* Level
* Service
* Request ID
* User ID (when available)

Never log

* Passwords
* Tokens
* Secrets

---

# Monitoring

Monitor

* CPU
* Memory
* Disk
* Database
* API Latency
* Error Rate
* Login Failures

Recommended tools

* Prometheus
* Grafana

Future integrations

* OpenTelemetry
* Sentry

---

# Backups

Database

Daily Incremental

Weekly Full

Retention

Minimum

30 days

Backups must be encrypted.

---

# Restore Testing

Backups are useful only if they can be restored.

Perform restore testing regularly.

Document the procedure.

---

# Disaster Recovery

Every production deployment requires

* Recovery Plan
* Rollback Plan
* Backup Verification
* Contact List

Define

Recovery Time Objective (RTO)

Recovery Point Objective (RPO)

---

# Scaling Strategy

Vertical Scaling

Increase

* CPU
* RAM

Horizontal Scaling

Multiple backend instances

Future additions

* Redis
* Load Balancer
* Kubernetes

---

# Caching

Future cache layer

Redis

Potential uses

* Sessions
* Rate Limiting
* Frequently accessed data
* Background queues

---

# Security During Deployment

Verify

* HTTPS enabled
* DEBUG disabled
* Strong secrets
* Restricted CORS
* Security headers enabled
* Database inaccessible from public internet
* Firewall configured

---

# Production Checklist

Before deployment verify

* Tests passed
* Build successful
* Migrations reviewed
* Backup completed
* Environment variables verified
* Secrets configured
* SSL active
* Monitoring active
* Logging active
* Rollback plan ready

---

# Rollback Strategy

If deployment fails

```text
Stop Deployment

↓

Rollback Application

↓

Rollback Database (only if safe)

↓

Verify Health

↓

Investigate
```

Rollback procedures should be documented and tested.

---

# Versioning

Every release should have

* Version Number
* Release Notes
* Migration Notes
* Breaking Changes
* Deployment Date

Example

```text
v1.0.0
```

---

# Release Notes

Every release should document

* New Features
* Improvements
* Bug Fixes
* Security Fixes
* Database Changes
* Known Issues

---

# Infrastructure as Code

Future infrastructure should be managed using

* Docker
* Docker Compose
* Terraform (optional)
* Ansible (optional)

Manual infrastructure changes should be minimized.

---

# Production Readiness Checklist

Application

* Build Successful
* Tests Passed
* Lint Passed
* Type Checks Passed

Database

* Backup Complete
* Migration Verified

Security

* HTTPS Enabled
* Secrets Verified
* DEBUG Disabled
* Security Headers Enabled

Operations

* Monitoring Enabled
* Logging Enabled
* Alerts Configured

Documentation

* Release Notes Updated
* Deployment Notes Updated

---

# Hosting Strategy (DevSphere ERP)

## Development

* Local Machine
* Docker Compose

## Staging

* Hetzner VPS (recommended)

## Production

Recommended options

* Hetzner Cloud
* DigitalOcean
* AWS
* Azure
* Google Cloud

Frontend may also be deployed separately on Vercel if desired.

---

# Future Cloud Architecture

```text
Cloud Load Balancer

↓

Nginx

↓

FastAPI (Multiple Instances)

↓

Redis

↓

PostgreSQL

↓

Object Storage

↓

Monitoring Stack
```

This architecture supports enterprise-scale growth.

---

# Single Source of Truth

This document defines the official deployment strategy for DevSphere ERP.

Every deployment—development, staging, or production—must comply with these standards.
