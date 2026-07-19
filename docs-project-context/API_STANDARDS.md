# API_STANDARDS.md

# DevSphere ERP

## Official API Standards

Version: 1.0

Status: Approved

---

# Purpose

This document defines the official API standards for the DevSphere ERP platform.

All backend APIs must follow these standards to ensure consistency, security, scalability, maintainability, and predictable behavior.

This document is the single source of truth for API design.

---

# API Style

The DevSphere ERP uses:

* REST API
* JSON
* HTTPS
* OpenAPI 3.x
* Swagger UI

GraphQL is not used.

---

# API Versioning

All APIs must be versioned.

Example

```text
/api/v1/auth/login
/api/v1/companies
/api/v1/users
```

Future versions:

```text
/api/v2/...
```

Older versions remain supported according to the deprecation policy.

---

# URL Naming Rules

URLs must:

* Use lowercase
* Use nouns
* Use plural resources
* Use hyphens where required
* Never contain verbs

Correct

```text
/api/v1/users
/api/v1/companies
/api/v1/purchase-orders
/api/v1/inventory-items
```

Wrong

```text
/api/v1/getUsers
/api/v1/createCompany
/api/v1/deleteInvoice
```

---

# HTTP Methods

## GET

Retrieve data.

Example

```http
GET /api/v1/users
```

---

## POST

Create resources.

Example

```http
POST /api/v1/users
```

---

## PUT

Replace entire resource.

Example

```http
PUT /api/v1/users/{id}
```

---

## PATCH

Partial update.

Example

```http
PATCH /api/v1/users/{id}
```

---

## DELETE

Delete resource.

Example

```http
DELETE /api/v1/users/{id}
```

---

# Resource Naming

Examples

```text
users
companies
roles
permissions
inventory-items
purchase-orders
sales-orders
customers
suppliers
installments
reports
```

Use nouns only.

---

# Standard Response Format

Every successful response should follow:

```json
{
    "success": true,
    "message": "Operation completed successfully.",
    "data": {}
}
```

---

# Error Response Format

Every error response should follow:

```json
{
    "success": false,
    "message": "Validation failed.",
    "errors": [
        {
            "field": "email",
            "message": "Email already exists."
        }
    ]
}
```

Never return inconsistent response structures.

---

# Pagination Standard

Large collections must always support pagination.

Example

```http
GET /api/v1/users?page=1&page_size=25
```

Response

```json
{
    "success": true,
    "data": {
        "items": [],
        "pagination": {
            "page": 1,
            "page_size": 25,
            "total_items": 105,
            "total_pages": 5
        }
    }
}
```

Default page size:

25

Maximum page size:

100

---

# Sorting

Example

```http
GET /api/v1/users?sort=name
```

Descending

```http
GET /api/v1/users?sort=-created_at
```

Use "-" prefix for descending order.

---

# Filtering

Examples

```http
GET /api/v1/users?status=active
```

```http
GET /api/v1/users?company_id=12
```

```http
GET /api/v1/products?category=electronics
```

Multiple filters may be combined.

---

# Searching

Global search parameter

```http
GET /api/v1/customers?search=Ali
```

Search should support:

* Name
* Email
* Code
* Phone

when applicable.

---

# Field Selection (Future)

Optional support

Example

```http
GET /api/v1/users?fields=id,name,email
```

Only requested fields are returned.

---

# Includes (Future)

Example

```http
GET /api/v1/users?include=company,roles
```

Avoid unnecessary additional requests.

---

# HTTP Status Codes

## 200 OK

Successful GET

---

## 201 Created

Resource created.

---

## 202 Accepted

Long-running task accepted.

---

## 204 No Content

Successful delete.

---

## 400 Bad Request

Malformed request.

---

## 401 Unauthorized

Authentication required.

---

## 403 Forbidden

Authenticated but insufficient permissions.

---

## 404 Not Found

Resource does not exist.

---

## 409 Conflict

Duplicate resource.

Example

Duplicate email.

---

## 422 Unprocessable Entity

Validation errors.

---

## 429 Too Many Requests

Rate limit exceeded.

---

## 500 Internal Server Error

Unexpected server error.

Never expose internal stack traces.

---

# Authentication

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

Missing or invalid tokens return:

401 Unauthorized

---

# Refresh Token

Refresh endpoint

```text
POST /api/v1/auth/refresh
```

Receives:

Refresh Token

Returns:

New Access Token

New Refresh Token (rotation)

---

# Logout

```text
POST /api/v1/auth/logout
```

Refresh token must be revoked.

---

# Content Type

Requests

```http
Content-Type: application/json
```

Responses

```http
Content-Type: application/json
```

---

# Date Format

Always use:

ISO 8601

Example

```text
2026-07-14T15:30:45Z
```

Never use locale-specific formats.

---

# Time Zone

All timestamps must be stored and transmitted in UTC.

Frontend converts to local timezone.

---

# ID Format

Primary keys

UUID

Example

```text
4d30d4df-a531-4dc9-bfd9-0af1dc93b403
```

Avoid exposing sequential IDs in public APIs where practical.

---

# Validation

Every endpoint must validate:

* Required fields
* Data types
* Length
* Format
* Business rules

Validation happens before business logic.

---

# Error Messages

Good

```text
Email already exists.
```

Bad

```text
IntegrityError
```

Never expose database errors.

---

# Rate Limiting

Authentication endpoints

Strict limits.

Example

5 requests/minute

General APIs

Higher limits.

Example

60 requests/minute

Configured centrally.

---

# Idempotency

POST endpoints that may be retried (payments, financial postings, imports) should support an **Idempotency-Key** header.

Example

```http
Idempotency-Key: 91b3c8f6-4d3a-4f65-bb73-2cb4db6dddb2
```

Duplicate requests with the same key must not create duplicate records.

---

# Soft Delete

Business data should normally use soft delete.

Fields

```text
deleted_at
deleted_by
```

Deleted records remain recoverable unless permanent deletion is explicitly required.

---

# Audit Logging

Sensitive operations must be logged.

Examples

* Login
* Logout
* Password Change
* User Creation
* Role Assignment
* Company Creation
* Financial Posting
* Inventory Adjustment

Audit logs are immutable.

---

# Bulk Operations

Bulk endpoints should exist where appropriate.

Example

```http
POST /api/v1/users/bulk-delete
```

Response should include:

* Success Count
* Failure Count
* Individual Errors

---

# File Upload

Use

```http
multipart/form-data
```

Allowed examples

* Company Logo
* Product Images
* Documents
* Import Files

Validate:

* Size
* Extension
* MIME Type

---

# API Documentation

Every endpoint must define:

* Summary
* Description
* Request Schema
* Response Schema
* Error Responses
* Authentication Requirement
* Permission Requirement
* Example Request
* Example Response

Swagger documentation must remain synchronized with implementation.

---

# Performance Rules

APIs should:

* Avoid N+1 queries
* Use pagination
* Minimize payload size
* Return only required data
* Cache safe GET requests where appropriate

---

# Security Rules

Every endpoint must:

* Validate JWT
* Validate Tenant Context
* Validate User Status
* Validate Permissions
* Sanitize Inputs
* Prevent SQL Injection
* Prevent XSS where applicable
* Use parameterized queries through SQLAlchemy

---

# Multi-Tenant Rules

Every protected endpoint must ensure users can only access data belonging to their own company (tenant).

Cross-tenant access is strictly prohibited unless performed by an authorized Super Admin.

---

# API Deprecation Policy

Deprecated endpoints must:

* Be documented
* Return deprecation headers when applicable
* Remain available for an announced transition period
* Provide replacement endpoints

Breaking changes require a new API version.

---

# Testing Requirements

Every endpoint must have:

* Unit Tests
* Integration Tests
* Authentication Tests
* Authorization Tests
* Validation Tests
* Error Handling Tests

Critical endpoints should also include performance testing.

---

# Single Source of Truth

This document defines the official API standards for DevSphere ERP.

Every API endpoint implemented in the project must comply with these standards.
