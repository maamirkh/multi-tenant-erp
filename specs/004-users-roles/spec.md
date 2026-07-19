# Feature Specification: Users & Roles (Epic 4)

**Feature Branch**: `004-users-roles`
**Created**: 2026-07-16
**Status**: Draft
**Epic**: 4 — Users & Roles
**Input**: Enterprise Users & Roles module for DevSphere ERP — user management, role-based access control, permission definitions, company membership, and user profile management.

---

## 1. Overview

### 1.1 Purpose

The Users & Roles module establishes the organisational identity layer of DevSphere ERP. It governs **who** can operate within a company, **what** they are permitted to do, and **how** their lifecycle is managed. This module transforms the current single-owner company model into a fully collaborative, multi-user, role-based workspace suitable for small businesses through large enterprises.

DevSphere ERP operates on a **two-tier identity architecture**: a Platform Identity Layer that governs the SaaS platform itself, and a Company Identity Layer that governs individual tenant organisations. This Epic defines both layers architecturally, while implementing only the Company Identity Layer.

### 1.2 Business Value

- **Collaboration**: Multiple users can work within the same company, each with appropriate access levels.
- **Security**: Role-based access control (RBAC) ensures users only access what they are authorised for.
- **Compliance**: Immutable audit trails record every user and role lifecycle event.
- **Scalability**: The permission architecture supports future fine-grained access control, SaaS multi-tenancy, and enterprise delegation.
- **Operational Efficiency**: Administrators can manage teams, departments, and roles without developer intervention.

### 1.3 Scope

**In Scope**:
- Company membership management (add, remove, update members)
- User profile and preferences management
- User avatar upload and management
- Employee information (job title, department, notes)
- User lifecycle management (invite, activate, deactivate, suspend, archive, soft-delete)
- System-defined roles with fixed permission sets
- Custom role creation per company
- Role hierarchy and inheritance
- Role assignment and revocation
- Permission definition and registration (structural model only)
- User audit logging for all lifecycle and role events
- Company-scoped data isolation enforcement
- Integration with existing Authentication (Epic 2) and Companies (Epic 3) modules

**Out of Scope**:
- Authentication (login, JWT, token management) — Epic 2, already implemented
- Authorization engine / runtime permission evaluation — Future Epic
- Fine-grained permission enforcement middleware — Future Epic
- Single Sign-On (SSO), OAuth, SAML — Future Epic
- Multi-Factor Authentication (MFA) — Future Epic
- Payroll, HR, attendance, leave management — Future Epics
- Organisation chart / reporting hierarchy — Future Epic
- Team/group management — Future Epic
- User-to-user messaging or notifications — Future Epic
- Billing / subscription user limits enforcement — Future Epic (SaaS)

> **Architectural Foundation**: Although authentication, authorization engine, SSO, MFA, and billing enforcement are out of scope for implementation, Epic 4 establishes the structural identity and role foundations upon which all of these future capabilities will be built. The data model, role hierarchy, permission registry, and tenant isolation patterns defined here are designed to support these future extensions without schema-breaking changes.

### 1.4 Identity Architecture

DevSphere ERP distinguishes between two independent identity layers:

```
Platform Layer (SaaS Infrastructure)
│
├── Platform Super Admin       — Full platform governance
├── Platform Support (Future)  — Customer support operations
├── Platform Auditor (Future)  — Compliance and audit oversight
└── Platform Operations (Future) — Infrastructure and monitoring

Company Layer (Tenant Organisations)
│
├── Company Owner       — Ultimate company authority
├── Company Admin       — Daily administrative operations
├── Manager             — Department-level operations
├── Accountant          — Financial operations
├── Cashier             — Point-of-sale operations
├── Salesperson         — Sales operations
├── Store Keeper        — Inventory/warehouse operations
└── Viewer              — Read-only access
```

**Key Architectural Principles**:

- **Separation of concerns**: Platform users and company users are entirely distinct identity scopes. A Platform Super Admin is NOT a company member and is NOT stored in the company membership table.
- **Platform scope**: Platform users manage the SaaS platform itself — tenant provisioning, system health, cross-tenant support operations, and compliance auditing.
- **Company scope**: Company users manage only their own company — members, roles, business data, and operational workflows.
- **No identity bleed**: A platform-level identity does not automatically grant company-level access. Platform Super Admin accesses company data through explicit platform-level override, not through company membership.
- **This Epic implements**: The Company Identity Layer (company membership, roles, permissions, lifecycle). The Platform Identity Layer is architecturally defined here and implemented in a future Epic.

### 1.5 Role Hierarchy (Conceptual)

The following hierarchy represents the complete authority structure across both identity layers:

```
Platform Super Admin          (Platform Layer — future implementation)
       ↓
Company Owner                 (Rank 100 — ultimate company authority)
       ↓
Company Administrator         (Rank 80 — daily administration)
       ↓
Department Manager            (Rank 60 — department operations)
       ↓
Operational Roles             (Rank 21–59 — Accountant, Cashier,
  (Accountant, Cashier,         Salesperson, Store Keeper,
   Salesperson, Store Keeper,   and custom roles)
   Custom Roles)
       ↓
Viewer                        (Rank 20 — read-only access)
```

**Hierarchy Rules** (conceptual — enforcement deferred to Authorization Engine):
- A higher-ranked user can manage (assign roles, change status) any lower-ranked user.
- A user cannot elevate another user to a rank equal to or higher than their own.
- A user cannot modify their own role.
- Platform Super Admin operates outside the company rank hierarchy entirely.
- Custom roles occupy ranks between 1–99, allowing organisations to position them precisely within the hierarchy.

### 1.6 Identity & Access Architecture

The following conceptual hierarchy defines the complete identity and access model for DevSphere ERP. Every future ERP module inherits this identity model without exception:

```
Platform
  ↓
Tenant (Company)
  ↓
Organisation Structure (Departments, Branches — future)
  ↓
Department
  ↓
User (Login Identity)
  ↓
Company Membership (User ↔ Company join)
  ↓
Role (Assigned per membership)
  ↓
Permission (Granted via role)
  ↓
Active Company Context (Session-scoped)
  ↓
Session (Authenticated interaction)
  ↓
Audit Trail (Immutable record of all actions)
```

**Key Relationships**:
- A **Platform** hosts multiple **Tenants** (Companies).
- Each **Company** has its own organisational structure, departments, and members.
- A **User** is a login identity that may hold memberships in multiple companies.
- A **Membership** binds a User to a Company with exactly one Role.
- A **Role** grants a set of Permissions within the company context.
- The **Active Company Context** determines which membership, role, and permissions apply during a session.
- Every action within a session produces an **Audit Trail** entry scoped to the active company.

### 1.7 Employee vs User Distinction

DevSphere ERP distinguishes between two related but independent concepts:

| Concept | Definition | System Representation |
|---------|------------|----------------------|
| **Employee** | A person employed by a company. May or may not have system access. | Employee information fields on the CompanyMember entity (job title, department, employee ID, hire date). |
| **User** | A login identity in the system. Always represents a person who can authenticate. | User entity (Epic 2) with email, password hash, account status. |

**Key Principles**:
- An employee does not necessarily require system access. A company may record employee information (job title, department, hire date) for a person who never logs in.
- A system user always represents a login identity — someone who can authenticate and operate within the ERP.
- The CompanyMember entity bridges both concepts: it carries employee information (organisational) and role assignment (system access).
- Future HR modules may manage employees independently from user accounts, supporting scenarios where companies track hundreds of employees but only a subset have ERP login access.

### 1.8 Department Model (Conceptual)

Departments represent organisational subdivisions within a company. In this Epic, department is a free-text field on the membership entity (FR-022). The conceptual department model is documented here for future reference:

**Standard ERP Departments** (examples):
- Sales
- Accounts / Finance
- Warehouse / Inventory
- Purchase / Procurement
- HR / Human Resources
- Administration
- IT / Technology
- Customer Support

**Conceptual Rules**:
- Departments belong to Companies — each company defines its own department structure.
- A user may belong to one or more departments (future: when Department becomes a first-class entity).
- Managers manage departments rather than arbitrary sets of users — department assignment determines management scope.
- Department-based access control (e.g., "Manager can only view records in their department") is a future ABAC capability built on the foundation this Epic provides.
- In this Epic, department is a simple text label. Promotion to a first-class entity with hierarchy, managers, and budget centres is a documented future enhancement (Section 18).

### 1.9 Organisational Hierarchy (Conceptual)

The following hierarchy represents the **reporting structure** within a company. This is an organisational concept, distinct from the authorization role hierarchy:

```
Company Owner
  ↓
Company Administrator
  ↓
Department Manager
  ↓
Team Lead (Future)
  ↓
Employee / Staff
```

**Clarifications**:
- This hierarchy represents **reporting relationships**, not authorization. A Department Manager reports to the Administrator organisationally, but authorization is governed by role rank (Section 1.5).
- Team Lead is a future concept — this Epic does not implement team or group management.
- The organisational hierarchy informs future features such as: approval workflows (a purchase order escalates up the hierarchy), delegated administration (a manager administers only their department), and organisation chart visualisation.
- This Epic captures the department field on membership and the role hierarchy, which together provide the foundation for full organisational hierarchy in future Epics.

---

## 2. User Scenarios & Testing

### User Story 1 — Owner Adds a New Member to the Company (Priority: P1)

As a **Company Owner**, I want to add a new user to my company and assign them a role, so that they can access the ERP system and perform their duties.

**Why this priority**: Without the ability to add members, the company remains single-user. This is the foundational capability that unlocks all collaborative features.

**Independent Test**: Can be fully tested by creating a company, then adding a user with a role. The new user should appear in the member list with the correct role and be able to access company-scoped resources.

**Acceptance Scenarios**:

1. **Given** an active company with an Owner, **When** the Owner adds a new member with email and role "Staff", **Then** a company membership record is created, the user is linked to the company, and the member appears in the company member list with status "active".
2. **Given** an active company, **When** the Owner attempts to add a member whose email is already a member of this company, **Then** the system rejects the request with a duplicate membership error.
3. **Given** an active company, **When** the Owner adds a member with an email not yet registered in the system, **Then** the system creates the user account with status "pending_invitation" and sends an invitation (future: email notification).
4. **Given** a company at its maximum member limit, **When** the Owner attempts to add another member, **Then** the system rejects the request with a member limit exceeded error.

---

### User Story 2 — Admin Manages User Roles (Priority: P1)

As a **Company Admin**, I want to assign, change, and revoke roles for company members, so that I can control what each person is permitted to do within the ERP.

**Why this priority**: Role assignment is the core RBAC operation. Without it, all members would have identical access, defeating the purpose of the role system.

**Independent Test**: Can be tested by assigning a role to a member, verifying the role appears on their profile, changing it, and confirming the change is reflected.

**Acceptance Scenarios**:

1. **Given** an Admin and a company member with role "Staff", **When** the Admin changes the member's role to "Manager", **Then** the member's role is updated and an audit log entry is created recording the change (before/after state).
2. **Given** a company member who is the sole Owner, **When** an Admin attempts to remove the Owner role, **Then** the system rejects the request because a company must always have at least one Owner.
3. **Given** a company member, **When** an Admin assigns a role that does not exist in the company's role registry, **Then** the system rejects the request with an invalid role error.
4. **Given** a member with role "Admin", **When** a member with role "Staff" attempts to change the Admin's role, **Then** the system rejects the request because Staff cannot manage users with higher-ranked roles.

---

### User Story 3 — Owner Creates Custom Roles (Priority: P2)

As a **Company Owner**, I want to create custom roles with specific permission sets tailored to my business, so that I can model my organisation's access structure precisely.

**Why this priority**: System roles cover common cases, but enterprises need custom roles to match their unique organisational structures.

**Independent Test**: Can be tested by creating a custom role with selected permissions, assigning it to a member, and verifying the role appears in the role registry.

**Acceptance Scenarios**:

1. **Given** an Owner, **When** the Owner creates a custom role named "Warehouse Supervisor" with selected permissions, **Then** the role is saved to the company's role registry and becomes available for assignment.
2. **Given** an existing custom role "Warehouse Supervisor", **When** the Owner updates its permissions, **Then** the permission set is updated and an audit log records the change.
3. **Given** a custom role currently assigned to 3 members, **When** the Owner attempts to delete the role, **Then** the system warns that 3 members have this role and requires confirmation or reassignment before deletion.
4. **Given** an Owner, **When** the Owner attempts to create a role with the same name as an existing role (case-insensitive), **Then** the system rejects the request with a duplicate role name error.

---

### User Story 4 — User Updates Their Profile (Priority: P2)

As a **Company Member**, I want to view and update my own profile information (display name, phone, avatar, preferences), so that my colleagues can identify me and the system adapts to my needs.

**Why this priority**: User profiles are essential for collaboration and personalisation, but not blocking for basic RBAC functionality.

**Independent Test**: Can be tested by logging in, navigating to the profile page, updating fields, and verifying changes are persisted and displayed.

**Acceptance Scenarios**:

1. **Given** an authenticated member, **When** the member updates their display name and phone number, **Then** the changes are saved and reflected in their profile.
2. **Given** an authenticated member, **When** the member uploads a valid avatar image (JPEG/PNG, ≤ 2 MiB), **Then** the avatar is stored and the avatar URL is updated on their profile.
3. **Given** an authenticated member, **When** the member uploads an avatar that exceeds 2 MiB, **Then** the system rejects the upload with a file size error.
4. **Given** an authenticated member, **When** the member updates their preferences (language, timezone, date format), **Then** the preferences are saved and applied to subsequent interactions.

---

### User Story 5 — Admin Manages User Lifecycle (Priority: P2)

As a **Company Admin**, I want to deactivate, suspend, reactivate, and archive users, so that I can manage employee turnover and access control as business needs change.

**Why this priority**: Lifecycle management is critical for security (revoking access) and compliance (retaining records), but depends on basic membership being functional first.

**Independent Test**: Can be tested by deactivating a member, confirming they lose access, then reactivating them and confirming access is restored.

**Acceptance Scenarios**:

1. **Given** an active member, **When** an Admin deactivates the member, **Then** the member's status changes to "inactive", all active sessions are revoked, and the member can no longer authenticate against this company.
2. **Given** an inactive member, **When** an Admin reactivates the member, **Then** the member's status changes to "active" and they can authenticate and access company resources again.
3. **Given** an active member, **When** an Admin suspends the member with a reason, **Then** the member's status changes to "suspended", all sessions are revoked, and the suspension reason is recorded.
4. **Given** a member who is the sole Owner, **When** an Admin attempts to deactivate or suspend them, **Then** the system rejects the request because a company must always have at least one active Owner.
5. **Given** an inactive member, **When** an Admin soft-deletes the member with a reason, **Then** the member's status changes to "archived", a `deleted_at` timestamp is set, and the deletion reason is recorded. The member's data is retained for the configured retention period.

---

### User Story 6 — Admin Views and Searches Company Members (Priority: P2)

As a **Company Admin**, I want to view a paginated list of all company members with filtering and search capabilities, so that I can efficiently manage the workforce.

**Why this priority**: Essential for operational management of members, but not as critical as the ability to add members and assign roles.

**Independent Test**: Can be tested by listing members with various filters (role, status, department) and confirming accurate results and pagination.

**Acceptance Scenarios**:

1. **Given** a company with 50 members, **When** an Admin requests the member list with page_size=20, **Then** the system returns the first 20 members with pagination metadata (total count, page number, total pages).
2. **Given** a company with members across multiple departments, **When** an Admin filters by department "Engineering", **Then** only members in the Engineering department are returned.
3. **Given** a company with members of various statuses, **When** an Admin filters by status "active", **Then** only active members are returned.
4. **Given** a search term "john", **When** an Admin searches members, **Then** members whose display name or email contains "john" (case-insensitive) are returned.

---

### User Story 7 — Admin Manages Employee Information (Priority: P3)

As a **Company Admin**, I want to record and update employee information (job title, department, employee ID, hire date, notes) for each company member, so that organisational structure is reflected in the system.

**Why this priority**: Employee metadata enriches the user model but is not required for basic RBAC or member management.

**Independent Test**: Can be tested by setting a member's job title, department, and employee ID, then retrieving the member and confirming the information is displayed.

**Acceptance Scenarios**:

1. **Given** an Admin and a company member, **When** the Admin sets the member's job title to "Senior Engineer" and department to "Engineering", **Then** the information is saved and visible on the member's profile.
2. **Given** a member with employee information, **When** the Admin updates the department from "Engineering" to "Product", **Then** the change is saved and an audit log records the update.
3. **Given** a member with an employee ID, **When** the Admin attempts to assign the same employee ID to another member within the same company, **Then** the system rejects the request with a duplicate employee ID error.

---

### User Story 8 — View Role Details and Permissions (Priority: P3)

As a **Company Admin**, I want to view all available roles, their descriptions, and assigned permissions, so that I can make informed decisions about role assignments.

**Why this priority**: Transparency into the role/permission structure supports better administration but is secondary to actual role management operations.

**Independent Test**: Can be tested by listing all roles for a company, selecting one, and viewing its permission set.

**Acceptance Scenarios**:

1. **Given** a company with system roles and custom roles, **When** an Admin requests the role list, **Then** all roles are returned with their name, description, type (system/custom), and member count.
2. **Given** a specific role, **When** an Admin views the role details, **Then** the full permission set is displayed, grouped by module.
3. **Given** a system role (e.g., "Owner"), **When** an Admin attempts to modify it, **Then** the system rejects the request because system roles are immutable.

---

### Edge Cases

- What happens when a user is a member of multiple companies? — Each membership is independent; role assignments, status, and profile extensions are per-company.
- What happens when a company is suspended? — All member access to that company is suspended; memberships are preserved but inactive.
- What happens when a user's auth account is locked (failed logins)? — Account locking is authentication-level (Epic 2); it affects access to ALL companies, not per-company.
- What happens when the last Admin demotes themselves? — The system prevents removal of the last Owner; Admin demotion is allowed if at least one Owner remains.
- What happens when a soft-deleted member's email is re-invited? — The system reactivates the archived membership rather than creating a duplicate.
- What happens when a role is deleted that has active assignments? — The system requires reassignment of affected members before deletion, or the role can be deactivated instead of deleted.
- How does a user switch between companies? — The user selects a company context; all subsequent API calls are scoped to that company via the `company_id` in the request/session context.

---

## 3. Functional Requirements

### 3.1 Company Membership

- **FR-001**: The system MUST support a many-to-many relationship between users and companies via a membership entity.
- **FR-002**: A user MUST be able to belong to multiple companies simultaneously, each with independent role assignments and membership status.
- **FR-003**: Each membership MUST track: the user, the company, the assigned role, the membership status, the user who invited/added them, and timestamps.
- **FR-004**: The system MUST enforce that a company always has at least one member with the Owner role.
- **FR-005**: The system MUST prevent duplicate memberships (same user + same company).
- **FR-006**: The system MUST enforce a configurable maximum member count per company (default: 100, configurable via settings).
- **FR-007**: The system MUST support the following membership statuses: `active`, `inactive`, `suspended`, `locked`, `pending_invitation`, `archived`.

### 3.2 User Profile & Preferences

- **FR-010**: The system MUST allow users to update their own profile information: display name, phone number, and avatar.
- **FR-011**: The system MUST support avatar upload to S3-compatible object storage with the same patterns established in Epic 3 (company logos).
- **FR-012**: Avatar uploads MUST be limited to JPEG and PNG formats, maximum 2 MiB file size.
- **FR-013**: The system MUST support user preferences including: preferred language (ISO 639-1), preferred timezone (IANA), preferred date format, preferred number format, and notification preferences (JSONB for future extensibility).
- **FR-014**: User preferences MUST have sensible defaults that can be overridden per-user.
- **FR-015**: Display name changes MUST be reflected in all system displays (member lists, audit logs, etc.).

### 3.3 Employee Information

- **FR-020**: The system MUST support per-membership employee information: job title, department, employee ID, hire date, and admin notes.
- **FR-021**: Employee ID MUST be unique within a company (nullable — not all companies use employee IDs).
- **FR-022**: Department MUST be a free-text field (not a separate entity) to avoid premature schema complexity.
- **FR-023**: Admin notes MUST be visible only to members with Admin or Owner roles.
- **FR-024**: The system SHOULD support recording a phone number (direct/work) at the membership level, separate from the user's personal phone.

### 3.4 User Lifecycle Management

- **FR-030**: Admins MUST be able to deactivate a member, which sets their membership status to "inactive" and revokes all active sessions for that company.
- **FR-031**: Admins MUST be able to reactivate an inactive member, restoring their status to "active".
- **FR-032**: Admins MUST be able to suspend a member with a mandatory reason, setting status to "suspended" and revoking all sessions.
- **FR-033**: Admins MUST be able to soft-delete (archive) a member with a mandatory reason, setting status to "archived" and recording a `deleted_at` timestamp.
- **FR-034**: The system MUST NOT allow deactivation, suspension, or archival of the last remaining Owner of a company.
- **FR-035**: When a member is deactivated, suspended, or archived, all their active sessions and refresh tokens for that company MUST be revoked.
- **FR-036**: Archived members MUST be retained for a configurable retention period (default: 90 days) before they become eligible for permanent deletion.
- **FR-037**: The system MUST support reactivation of archived members within the retention period, restoring their previous role and employee information.

### 3.5 Role Management

- **FR-040**: The system MUST provide the following system-defined roles, created automatically for every new company:

  | Role | Rank | Description | Responsibilities |
  |------|------|-------------|------------------|
  | Owner | 100 | Full control. Ultimate company authority. | Owns the company. Billing & subscription. Transfer ownership. Company settings. Final authority. Can appoint/remove admins. |
  | Admin | 80 | Daily administration. Cannot delete company or transfer ownership. | User management. Role assignment. Department management. Operational settings. Daily administration. |
  | Manager | 60 | Department-level operations. Can view team members. | Department operations. Team oversight. Resource management within assigned scope. |
  | Accountant | 55 | Financial operations access. | Financial record management. Journal entries. Financial reporting. Tax operations. |
  | Salesperson | 50 | Sales operations access. | Customer management. Sales orders. Quotations. Sales reporting. |
  | Cashier | 45 | Point-of-sale operations. | Payment processing. Receipt management. Cash register operations. |
  | Store Keeper | 42 | Inventory and warehouse operations. | Stock management. Goods receipt. Warehouse operations. Inventory counting. |
  | Viewer | 20 | Read-only access to permitted modules. Cannot create, update, or delete records. | View-only access across permitted modules. |

  > **Note**: The legacy "Staff" role (rank 40) is superseded by the more specific operational roles above (Accountant, Salesperson, Cashier, Store Keeper). Existing implementations referencing "Staff" should map to the appropriate operational role. These are **default ERP system roles** — organisations may create additional custom roles in future to match their unique structures.

- **FR-041**: System roles MUST be immutable — they cannot be renamed, deleted, or have their rank changed. Their permission sets are defined by the system.
- **FR-042**: The system MUST support custom roles created by Owners or Admins, with a configurable rank between 1 and 99 (must not conflict with system role ranks: 20, 42, 45, 50, 55, 60, 80, 100).
- **FR-043**: Custom roles MUST have: a unique name (within the company, case-insensitive), a description, a rank (1–99), a permission set, and a flag indicating whether it is a system or custom role.
- **FR-044**: A user MUST be assigned exactly one role per company membership. Multiple role assignments per membership are not supported in this version to maintain simplicity.
- **FR-045**: Role rank determines the management hierarchy: a user can only manage (assign, change, deactivate) members whose role rank is strictly lower than their own.
- **FR-046**: Custom roles MUST be deletable only if no active members are currently assigned to that role. The system MUST require reassignment before deletion.
- **FR-047**: Custom roles MUST support deactivation (soft disable) as an alternative to deletion, preventing new assignments while preserving existing ones.
- **FR-048**: The system MUST enforce a maximum of 50 custom roles per company.

### 3.6 Permission Model (Definition Only)

- **FR-050**: The system MUST define a permission registry — a catalogue of all available permissions in the system.
- **FR-051**: Each permission MUST have: a unique code (e.g., `companies.update`, `inventory.create`), a human-readable label, a module grouping, and a description.
- **FR-052**: Permissions MUST follow the naming convention: `{module}.{action}` where action is one of: `create`, `read`, `update`, `delete`, `manage`, `export`.
- **FR-053**: The system MUST support mapping permissions to roles via a role-permission association entity.
- **FR-054**: System roles MUST have predefined, immutable permission sets. Custom roles allow Owners/Admins to compose permission sets from the registry.
- **FR-055**: The permission registry MUST be seeded at application startup and extended via migrations as new modules are added (future Epics).
- **FR-056**: This Epic defines the **structural model** for permissions (entities, relationships, seed data). Runtime permission evaluation (authorization middleware) is deferred to a future Epic.

### 3.7 Company Context & Multi-Tenant Isolation

- **FR-060**: Every API operation within this module MUST be scoped to a specific company, identified by `company_id` in the authenticated context.
- **FR-061**: A user MUST NOT be able to access, view, or modify members, roles, or permissions of a company they do not belong to.
- **FR-062**: Membership queries MUST filter by `company_id` to guarantee data isolation.
- **FR-063**: The system MUST validate that the authenticated user has an active membership in the target company before processing any request.
- **FR-064**: Super Admin (platform-level) MAY bypass company scoping for administrative operations. Super Admin is a platform-level concept, not a company role.
- **FR-065**: A single user MAY belong to multiple companies simultaneously. Each company membership MUST carry independent role assignment, independent permission scope, and independent membership status. There is no inheritance or leakage between memberships.
- **FR-066**: Only one company context MUST be active during a user session at any time. Switching company context MUST change the active authorization scope entirely.
- **FR-067**: Every permission evaluation MUST occur within the context of the active company. A user's permissions in Company A have no bearing on their access in Company B.
- **FR-068**: Every audit log entry MUST belong to a specific company. Cross-company audit queries are prohibited except for Platform Super Admin.
- **FR-069**: Every future ERP module (Inventory, Sales, Purchase, Accounting, CRM, etc.) MUST inherit the tenant isolation patterns established in this Epic. No future module may bypass company scoping.

### 3.8 Search and Listing

- **FR-070**: The system MUST provide paginated listing of company members with configurable page size (default: 25, max: 100).
- **FR-071**: Member listing MUST support filtering by: status, role, department, and date range (created_at).
- **FR-072**: Member listing MUST support text search across: display name and email (case-insensitive, substring match).
- **FR-073**: Member listing MUST support sorting by: display name, email, role rank, created_at, and updated_at.
- **FR-074**: Role listing MUST return all roles (system + custom) for a company with member counts per role.

### 3.9 Key Entities

- **CompanyMember**: Join entity between Users and Companies. Carries role assignment, membership status, employee information, and lifecycle timestamps. Central entity of this module.
- **Role**: Named permission set within a company. System roles are immutable and replicated per company. Custom roles are created by Owners/Admins.
- **Permission**: Global registry entry representing a single action on a single module. Not company-scoped.
- **RolePermission**: Join entity mapping permissions to roles.
- **UserPreference**: Per-user display and notification preferences (1:1 with User).

---

## 4. Business Rules

### 4.1 Ownership Rules

- **BR-001**: Every company MUST have at least one Owner at all times. The system MUST reject any operation that would leave a company with zero Owners.
- **BR-002**: Only an Owner can transfer ownership to another member. Ownership transfer is an atomic operation that simultaneously assigns Owner role to the target and optionally demotes the current Owner.
- **BR-003**: The Company's `owner_id` field (from Epic 3) MUST remain synchronised with the Owner role in the membership table. If ownership is transferred, `owner_id` is updated.
- **BR-004**: The Company's `primary_admin_id` field (from Epic 3) SHOULD be set when an Admin is designated as the primary administrative contact.

### 4.2 Role Assignment Rules

- **BR-010**: A member can only be assigned a role that exists in the company's role registry (system or custom).
- **BR-011**: A member can only manage (assign, change role, deactivate) other members whose role rank is strictly lower than their own.
- **BR-012**: An Owner (rank 100) can manage all members. An Admin (rank 80) can manage Managers, Accountants, Salespersons, Cashiers, Store Keepers, Viewers, and custom roles ranked below 80.
- **BR-013**: A member CANNOT change their own role. Role changes must be performed by another member with sufficient rank.
- **BR-014**: When a role is changed, the previous role and new role MUST be recorded in the audit log with before/after state.

### 4.3 Lifecycle Rules

- **BR-020**: Membership status transitions follow this state machine:

  ```
  pending_invitation → active        (invitation accepted / admin activation)
  active             → inactive      (admin deactivation)
  active             → suspended     (admin suspension, requires reason)
  active             → locked        (system auto-lock or admin manual lock)
  inactive           → active        (admin reactivation)
  suspended          → active        (admin lift suspension)
  locked             → active        (admin unlock)
  locked             → suspended     (admin escalation, requires reason)
  active             → archived      (admin soft-delete, requires reason)
  inactive           → archived      (admin soft-delete, requires reason)
  suspended          → archived      (admin soft-delete, requires reason)
  locked             → archived      (admin soft-delete, requires reason)
  archived           → active        (admin restore, within retention period)
  ```

  **Lifecycle Diagram**:

  ```
  Invitation → Pending → Active → Suspended → Archived → Soft Deleted
                           ↓                      ↑
                         Locked ─────────────────→┘
                           ↓
                        Inactive ────────────────→┘
  ```

- **BR-021**: The `pending_invitation` status is set when a member is added to a company but has not yet accepted or completed their account setup.
- **BR-022**: Suspended members MUST have a suspension reason recorded.
- **BR-023**: Archived members MUST have a deletion reason recorded and a `deleted_at` timestamp set.
- **BR-024**: No status transition is allowed from `archived` after the retention period expires. The record becomes eligible for permanent purge.
- **BR-025**: The `locked` status represents a security-triggered restriction (e.g., failed login attempts, suspicious activity). Unlike `suspended` (which is an administrative action with a reason), `locked` may be triggered automatically by the system. Locked members MUST have all active sessions revoked.

### 4.4 Uniqueness Rules

- **BR-030**: A user can have at most one active (non-archived) membership per company.
- **BR-031**: A custom role name MUST be unique within a company (case-insensitive comparison).
- **BR-032**: An employee ID MUST be unique within a company (among non-archived memberships).
- **BR-033**: A permission code MUST be globally unique across the entire system.

### 4.5 Deletion Rules

- **BR-040**: Members are soft-deleted (archived) by default. Hard deletion is a system-level maintenance operation and MUST NOT be exposed via the API.
- **BR-041**: Archived memberships exclude the user from member lists, role assignment, and access checks, but retain the data for audit and compliance purposes.
- **BR-042**: Custom roles can only be deleted if they have zero active (non-archived) member assignments.
- **BR-043**: System roles MUST NEVER be deleted.
- **BR-044**: If a re-invitation is sent to an email that has an archived membership in the same company, the system MUST reactivate the existing membership rather than creating a duplicate.

### 4.6 Multi-Tenant Isolation Rules

- **BR-050**: All membership, role, and permission queries MUST include `company_id` in the WHERE clause. This is a non-negotiable architectural invariant.
- **BR-051**: Custom roles are company-scoped; they do not leak across companies.
- **BR-052**: System roles are replicated per company (each company gets its own set of system role records) so that member counts and role queries remain company-scoped.
- **BR-053**: Audit logs for user/role events MUST include `company_id` to enable company-scoped audit queries.
- **BR-054**: Every business operation across all ERP modules MUST be company-scoped. No operation may execute without an active company context (except platform-level operations by Platform Super Admin).
- **BR-055**: Cross-company data access is strictly prohibited for all company-level users. Only Platform Super Admin (future) may access data across company boundaries, and only through explicit platform-level operations — never through normal API endpoints.
- **BR-056**: Every future ERP module (Inventory, Purchase, Sales, Accounting, CRM, Reports, etc.) MUST inherit and enforce the tenant isolation patterns established by this Epic. Module developers MUST NOT create queries that omit `company_id` filtering.
- **BR-057**: Company switching MUST be an explicit user action that changes the active authorization scope. The system MUST NOT allow implicit cross-company operations (e.g., referencing a resource from Company A while operating in Company B context).

### 4.7 Invitation Lifecycle

The invitation process follows a conceptual flow from creation to fully active membership:

```
Invitation Created (Admin/Owner initiates)
  ↓
Invitation Sent (Future: email delivery)
  ↓
Invitation Pending (Awaiting acceptance; status = pending_invitation)
  ↓
Invitation Accepted (User accepts and creates account if new)
  ↓
Password Created (New users set their credentials via Auth module)
  ↓
First Login (User authenticates for the first time)
  ↓
Profile Completion (Optional: user fills display name, avatar, preferences)
  ↓
Active User (Membership status = active; fully operational)
```

**Invitation Rules**:
- **BR-060**: Invitations MUST have a configurable expiry period (default: 7 days). Expired invitations remain as `pending_invitation` records but are no longer actionable until re-invited.
- **BR-061**: An Admin or Owner MAY re-invite an expired invitation, which resets the expiry window.
- **BR-062**: If the invited email belongs to an existing user (already registered via another company), the system MUST create a new membership without requiring a new account — the user simply accepts the company invitation.
- **BR-063**: If the invited email has an archived membership in the same company, the system MUST reactivate the archived membership (per BR-044) rather than creating a duplicate.
- **BR-064**: In this Epic, invitation delivery (email) is out of scope. The system records the invitation and sets `pending_invitation` status; actual notification is a future capability.

### 4.8 Membership vs User Status

User status and membership status are independent concepts that operate at different scopes:

| Aspect | User Status (Auth-Level) | Membership Status (Company-Level) |
|--------|-------------------------|-----------------------------------|
| **Scope** | Global — affects access to ALL companies | Per-company — affects access to ONE company |
| **Managed by** | Authentication module (Epic 2) | Users & Roles module (Epic 4) |
| **States** | ACTIVE, INACTIVE, LOCKED, DELETED | active, inactive, suspended, locked, pending_invitation, archived |
| **Example** | User account locked due to failed logins → cannot access any company | Membership suspended in Company A → can still access Company B |

**Independence Rules**:
- **BR-070**: A user's auth-level account status and their per-company membership status are fully independent. Changing one does not automatically change the other.
- **BR-071**: Access to a company requires BOTH: (a) an active auth-level account status, AND (b) an active membership status in that company.
- **BR-072**: If a user's auth-level account is locked or deactivated, they cannot access ANY company — regardless of membership status. However, their membership records remain unchanged and become effective again when the auth-level status is restored.

---

## 5. Data Model (Conceptual)

### 5.1 Key Entities

#### CompanyMember (new entity)

Represents the membership of a user within a company. This is the central join entity between Users and Companies.

| Attribute | Description |
|-----------|-------------|
| id | Unique identifier (UUID) |
| company_id | FK to Companies — which company this membership belongs to |
| user_id | FK to Users — which user this membership belongs to |
| role_id | FK to Roles — which role is assigned to this member |
| status | Membership status: active, inactive, suspended, locked, pending_invitation, archived |
| employee_id | Optional company-internal employee identifier (unique within company) |
| job_title | Optional job title string |
| department | Optional department name string |
| work_phone | Optional work/direct phone number |
| hire_date | Optional date the employee was hired |
| notes | Optional admin-only notes (text) |
| invited_by | UUID of the user who added/invited this member |
| suspended_reason | Reason for suspension (populated when status = suspended) |
| deletion_reason | Reason for archival (populated when status = archived) |
| deleted_at | Timestamp when archived (soft-delete marker) |
| created_at | Immutable creation timestamp |
| updated_at | Auto-updated modification timestamp |

**Constraints**: Unique on (company_id, user_id) excluding archived records. Unique on (company_id, employee_id) where employee_id is not null, excluding archived records.

#### Role (new entity)

Represents a role within a company's role registry.

| Attribute | Description |
|-----------|-------------|
| id | Unique identifier (UUID) |
| company_id | FK to Companies — which company this role belongs to |
| name | Role name (unique within company, case-insensitive) |
| slug | URL-safe identifier derived from name |
| description | Human-readable description of the role's purpose |
| rank | Numeric rank (1–100) determining hierarchy. Higher rank = more authority. |
| is_system | Boolean flag — true for system-defined roles, false for custom roles |
| is_active | Boolean flag — false disables new assignments but preserves existing ones |
| permissions | Association to permission entities via role-permission join |
| created_at | Immutable creation timestamp |
| updated_at | Auto-updated modification timestamp |

**Constraints**: Unique on (company_id, lower(name)). System role ranks are fixed: Owner=100, Admin=80, Manager=60, Accountant=55, Salesperson=50, Cashier=45, Store Keeper=42, Viewer=20. Custom role ranks must be between 1 and 99 (excluding system role ranks).

#### Permission (new entity)

Represents a single permission in the system's permission registry.

| Attribute | Description |
|-----------|-------------|
| id | Unique identifier (UUID) |
| code | Unique permission code (e.g., `companies.update`, `inventory.create`) |
| label | Human-readable label (e.g., "Update Company Settings") |
| module | Module grouping (e.g., "companies", "inventory", "sales") |
| action | Action type: create, read, update, delete, manage, export |
| description | Detailed description of what this permission grants |
| created_at | Immutable creation timestamp |

**Constraints**: Unique on code. Permissions are global (not company-scoped) — they represent the catalogue of all possible permissions in the system.

#### RolePermission (new join entity)

Associates permissions with roles.

| Attribute | Description |
|-----------|-------------|
| id | Unique identifier (UUID) |
| role_id | FK to Roles |
| permission_id | FK to Permissions |
| created_at | Immutable creation timestamp |

**Constraints**: Unique on (role_id, permission_id).

#### UserPreference (extension to existing User entity)

Stores per-user display and notification preferences.

| Attribute | Description |
|-----------|-------------|
| id | Unique identifier (UUID) |
| user_id | FK to Users (1:1 relationship) |
| language | Preferred language (ISO 639-1 code, default: "en") |
| timezone | Preferred timezone (IANA identifier, default: "UTC") |
| date_format | Preferred date format (default: "YYYY-MM-DD") |
| number_format | Number formatting preferences (JSONB) |
| notification_preferences | Notification settings (JSONB, extensible for future use) |
| theme | UI theme preference: "light", "dark", "system" (default: "system") |
| created_at | Immutable creation timestamp |
| updated_at | Auto-updated modification timestamp |

### 5.2 Entity Relationships

```
Users (Epic 2)
  ├── 1:many → CompanyMember (a user can be a member of multiple companies)
  └── 1:1   → UserPreference (user-level display preferences)

Companies (Epic 3)
  ├── 1:many → CompanyMember (a company has many members)
  └── 1:many → Role (a company has its own set of roles)

CompanyMember
  ├── many:1 → Users
  ├── many:1 → Companies
  └── many:1 → Role (each member has exactly one role)

Role
  ├── many:1 → Companies
  ├── 1:many → CompanyMember (a role can be assigned to many members)
  └── many:many → Permission (via RolePermission)

Permission
  └── many:many → Role (via RolePermission)
```

### 5.3 Existing Entity Extensions

**Users table** (Epic 2 — existing):
- Add `avatar_url` (String, nullable) — URL to the user's avatar in object storage.
- Add `avatar_previous_url` (String, nullable) — URL of the previously uploaded avatar (for retention/cleanup).
- Add `phone` (String(20), nullable) — personal phone number.

**No changes** to the Companies table schema. The existing `owner_id` and `primary_admin_id` fields remain; their values are synchronised with the membership/role data by the service layer.

---

## 6. Permission Architecture

### 6.1 Permission Naming Convention

Permissions follow the pattern `{module}.{action}`:

| Module | Permissions |
|--------|-------------|
| companies | companies.read, companies.update, companies.delete, companies.manage |
| members | members.create, members.read, members.update, members.delete, members.manage |
| roles | roles.create, roles.read, roles.update, roles.delete |
| profile | profile.read, profile.update |

### 6.2 System Role Permission Matrix

| Permission | Owner | Admin | Manager | Accountant | Salesperson | Cashier | Store Keeper | Viewer |
|------------|-------|-------|---------|------------|-------------|---------|--------------|--------|
| companies.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| companies.update | ✓ | ✓ | — | — | — | — | — | — |
| companies.delete | ✓ | — | — | — | — | — | — | — |
| companies.manage | ✓ | — | — | — | — | — | — | — |
| members.create | ✓ | ✓ | — | — | — | — | — | — |
| members.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| members.update | ✓ | ✓ | — | — | — | — | — | — |
| members.delete | ✓ | ✓ | — | — | — | — | — | — |
| members.manage | ✓ | ✓ | — | — | — | — | — | — |
| roles.create | ✓ | ✓ | — | — | — | — | — | — |
| roles.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| roles.update | ✓ | ✓ | — | — | — | — | — | — |
| roles.delete | ✓ | ✓ | — | — | — | — | — | — |
| profile.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| profile.update | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

> **Note**: Module-specific permissions (e.g., `inventory.*`, `sales.*`, `accounting.*`) will be added as future Epics are implemented. Operational roles (Accountant, Salesperson, Cashier, Store Keeper) will receive their module-specific permissions at that time.

### 6.3 Future Permission Extensions

As new modules are added in future Epics, their permissions will be registered in the permission table and mapped to system roles via migrations. Examples:

- `inventory.create`, `inventory.read`, `inventory.update`, `inventory.delete`
- `sales.create`, `sales.read`, `sales.update`, `sales.delete`, `sales.export`
- `accounting.read`, `accounting.manage`, `accounting.export`
- `reports.read`, `reports.export`

The permission model is designed to be **additive** — new permissions never break existing role configurations.

### 6.4 Future Authorization Foundation

Epic 4 establishes the structural identity and permission foundation upon which the following future authorization capabilities will be built. These are **architecturally planned but NOT implemented** in this Epic:

| Capability | Description | Foundation Provided by Epic 4 |
|------------|-------------|-------------------------------|
| **RBAC** (Role-Based Access Control) | Runtime evaluation of role-permission mappings against protected resources | Role entity, Permission registry, RolePermission mapping, rank hierarchy |
| **ABAC** (Attribute-Based Access Control) | Policy evaluation using user attributes, resource attributes, and environmental conditions | User profile attributes, membership metadata, company context |
| **Feature Permissions** | Toggle access to entire application features per role | Permission registry with module grouping |
| **Module Permissions** | Control access to ERP modules (Inventory, Sales, Accounting, etc.) per role | Module-based permission naming convention (`{module}.{action}`) |
| **Record-Level Permissions** | Restrict access to individual records based on ownership, department, or custom rules | CompanyMember entity with department, role, and company context |
| **Field-Level Permissions** | Control visibility and editability of individual fields within a record | Permission action granularity (read, update, manage) |
| **Approval Workflows** | Multi-level approval chains for sensitive operations (e.g., purchase orders, expense approvals) | Role hierarchy with rank-based authority |
| **Delegation** | Temporary delegation of authority from one user to another | Membership lifecycle, role assignment model |
| **Temporary Permissions** | Time-bound permission grants that auto-expire | Permission-role association model (extensible with validity dates) |

The data model and architectural patterns in this Epic are designed to support all of the above without schema-breaking changes.

---

## 7. API Requirements (Conceptual)

### 7.1 Member Management Capabilities

- List company members (paginated, filtered, sorted, searchable)
- Get member details by member ID
- Add a new member to a company (with role assignment)
- Update member information (role, employee info, status)
- Change member role
- Deactivate / reactivate / suspend / archive a member
- Restore an archived member (within retention period)
- Remove a member (archive)

### 7.2 Role Management Capabilities

- List all roles for a company (system + custom, with member counts)
- Get role details with permission set
- Create a custom role with permissions
- Update a custom role (name, description, permissions)
- Deactivate / reactivate a custom role
- Delete a custom role (if no active assignments)

### 7.3 Permission Capabilities

- List all available permissions (grouped by module)
- Get permission details by code

### 7.4 User Profile Capabilities

- Get current user's profile
- Update current user's profile (display name, phone, avatar)
- Upload / replace avatar
- Delete avatar
- Get / update user preferences

### 7.5 Ownership Capabilities

- Transfer company ownership to another active member

### 7.6 API Design Constraints

- All endpoints MUST be prefixed with `/api/v1/`
- All endpoints (except profile/preferences) MUST require `company_id` in the path or context
- All list endpoints MUST support pagination (page, page_size)
- All mutating endpoints MUST return the updated resource
- All endpoints MUST follow the existing standard response envelope: `{ data, message, meta }`
- Error responses MUST follow the existing standard error format: `{ error: { code, message, details } }`
- Rate limiting MUST be applied to member creation (prevent bulk invite abuse)

---

## 8. UI Requirements (Screens)

### 8.1 Required Screens

| Screen | Description | Access Level |
|--------|-------------|-------------|
| Member List | Paginated table of company members with search, filters (status, role, department), sort, and bulk actions | Admin+ |
| Add Member | Form to add a new member: email, role selection, optional employee info | Admin+ |
| Member Details | Read-only view of a member's profile, role, employee info, and activity | Admin+ (self-view for all) |
| Edit Member | Form to update member's role, employee information, and status | Admin+ |
| Role List | Table of all roles (system + custom) with member counts and actions | Admin+ |
| Create Role | Form to create a custom role: name, description, rank, permission selection | Owner/Admin |
| Edit Role | Form to edit a custom role's name, description, and permissions | Owner/Admin |
| Role Details | Read-only view of a role's permission set and assigned members | Admin+ |
| My Profile | Self-service profile view/edit: display name, phone, avatar upload | All authenticated |
| My Preferences | Self-service preferences: language, timezone, date format, theme | All authenticated |
| Ownership Transfer | Confirmation dialog for transferring company ownership | Owner only |

### 8.2 UI Constraints

- All lists MUST show loading states during data fetch.
- All forms MUST show inline validation errors.
- Destructive actions (deactivate, suspend, archive, delete role) MUST require confirmation.
- Ownership transfer MUST require explicit confirmation with the target member's name displayed.
- Avatar upload MUST show a preview before saving.
- Role permission selection MUST be displayed as a grouped checklist (by module).

---

## 9. Validation Rules

### 9.1 Member Validation

| Field | Rule |
|-------|------|
| email | Required. Valid email format. Maximum 254 characters. |
| role_id | Required. Must reference an existing, active role in the same company. |
| employee_id | Optional. Maximum 50 characters. Unique within company (among non-archived). |
| job_title | Optional. Maximum 100 characters. |
| department | Optional. Maximum 100 characters. |
| work_phone | Optional. Maximum 20 characters. |
| hire_date | Optional. Must be a valid date. Must not be in the future. |
| notes | Optional. Maximum 2000 characters. |
| suspended_reason | Required when status is set to "suspended". Maximum 500 characters. |
| deletion_reason | Required when status is set to "archived". Maximum 500 characters. |

### 9.2 Role Validation

| Field | Rule |
|-------|------|
| name | Required. 2–100 characters. Must be unique within the company (case-insensitive). |
| description | Optional. Maximum 500 characters. |
| rank | Required for custom roles. Integer, 1–99. Must not equal a system role rank (20, 42, 45, 50, 55, 60, 80, 100). |
| permissions | At least one permission must be assigned to a custom role. |

### 9.3 Profile Validation

| Field | Rule |
|-------|------|
| display_name | Required. 1–255 characters. |
| phone | Optional. Maximum 20 characters. |
| avatar | Optional. JPEG or PNG. Maximum 2 MiB. Recommended dimensions: 256×256 to 1024×1024 pixels. |

### 9.4 Preference Validation

| Field | Rule |
|-------|------|
| language | Must be a valid ISO 639-1 code (e.g., "en", "es", "ar"). |
| timezone | Must be a valid IANA timezone identifier (e.g., "America/New_York", "Asia/Karachi"). |
| date_format | Must be one of the supported formats: "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY", "DD.MM.YYYY". |
| theme | Must be one of: "light", "dark", "system". |

---

## 10. Audit Requirements

### 10.1 Audited Events

Every event below MUST be recorded in the company audit log with: actor user ID, timestamp, action code, before state (where applicable), after state, IP address, user agent, and request ID.

| Event | Action Code | Trigger |
|-------|-------------|---------|
| Member added to company | MEMBER_CREATED | Admin/Owner adds a member |
| Member role changed | MEMBER_ROLE_CHANGED | Admin/Owner changes a member's role |
| Member deactivated | MEMBER_DEACTIVATED | Admin/Owner deactivates a member |
| Member reactivated | MEMBER_REACTIVATED | Admin/Owner reactivates a member |
| Member suspended | MEMBER_SUSPENDED | Admin/Owner suspends a member |
| Member suspension lifted | MEMBER_UNSUSPENDED | Admin/Owner lifts suspension |
| Member archived | MEMBER_ARCHIVED | Admin/Owner soft-deletes a member |
| Member restored | MEMBER_RESTORED | Admin/Owner restores an archived member |
| Member info updated | MEMBER_UPDATED | Admin/Owner updates employee information |
| Custom role created | ROLE_CREATED | Owner/Admin creates a custom role |
| Custom role updated | ROLE_UPDATED | Owner/Admin updates a custom role |
| Custom role deactivated | ROLE_DEACTIVATED | Owner/Admin deactivates a custom role |
| Custom role deleted | ROLE_DELETED | Owner/Admin deletes a custom role |
| Ownership transferred | OWNERSHIP_TRANSFERRED | Owner transfers ownership to another member |
| Profile updated | PROFILE_UPDATED | User updates their own profile |
| Avatar uploaded | AVATAR_UPLOADED | User uploads a new avatar |
| Avatar removed | AVATAR_REMOVED | User removes their avatar |
| Preferences updated | PREFERENCES_UPDATED | User updates their preferences |
| Invitation accepted | INVITATION_ACCEPTED | User accepts company invitation and membership becomes active |
| Company context switched | COMPANY_CONTEXT_SWITCHED | User switches active company context during session |
| Role permissions updated | ROLE_PERMISSIONS_UPDATED | Owner/Admin modifies the permission set of a custom role |
| Member locked | MEMBER_LOCKED | System or Admin locks a member (security trigger) |
| Member unlocked | MEMBER_UNLOCKED | Admin unlocks a previously locked member |

### 10.2 Audit Log Requirements

- Audit entries MUST be append-only and immutable.
- Audit entries MUST include `company_id` for company-scoped queries.
- Audit entries MUST survive the deletion of the actor or target user.
- Audit entries MUST be queryable by: company, actor, action, date range.
- Audit retention follows the existing `AUDIT_LOG_RETENTION_DAYS` setting (default: 90 days).

---

## 11. Non-Functional Requirements

### 11.1 Performance

- Member listing with 1,000 members MUST return within 500 milliseconds (p95).
- Role listing with 50 roles MUST return within 200 milliseconds (p95).
- Member creation MUST complete within 1 second (including audit log write).
- Avatar upload MUST complete within 5 seconds for a 2 MiB file.

### 11.2 Security

- All member management operations MUST verify the requester's role rank before processing.
- Company data isolation MUST be enforced at the repository layer (every query includes `company_id`).
- Admin notes MUST NOT be visible to members with Staff or Viewer roles.
- Avatar URLs MUST use pre-signed URLs or be served through an authenticated endpoint (no direct public S3 access).
- All password and credential data MUST remain in the auth module; this module MUST NOT access or duplicate credential data.
- Session revocation on status change MUST be immediate (not deferred).

### 11.3 Scalability

- The data model MUST support companies with up to 10,000 members.
- The permission registry MUST support up to 500 permissions without degradation.
- Role-permission lookups MUST be optimisable via caching in future iterations.

### 11.4 Maintainability

- The module MUST follow the established modular monolith pattern: `modules/users_roles/` with separate `models/`, `repositories/`, `services/`, `schemas/`, and router layers.
- All business logic MUST reside in the service layer, not in routes or repositories.
- The permission registry MUST be extendable via Alembic migrations as new modules are added.

### 11.5 Reliability

- Member status changes and session revocations MUST be atomic (single transaction).
- Ownership transfer MUST be atomic — no intermediate state where a company has zero Owners.
- Role deletion MUST verify zero active assignments within the same transaction.

### 11.6 Auditability

- Every state change to memberships, roles, and permissions MUST produce an audit log entry.
- Audit logs MUST capture before and after state for update operations.
- Audit logs MUST be queryable by company, actor, action, and date range.

### 11.7 Accessibility

- All UI screens MUST meet WCAG 2.1 AA standards.
- Form fields MUST have proper labels and error messages.
- Interactive elements MUST be keyboard-navigable.
- Colour MUST NOT be the sole indicator of status (use icons/text alongside).

---

## 12. Reporting Requirements (Future)

The following reports SHOULD be supported in future iterations. The data model defined in this Epic MUST support these queries:

| Report | Description |
|--------|-------------|
| Active Members | Count and list of active members by company |
| Inactive Members | Members deactivated or suspended, with reasons |
| Members by Department | Distribution of members across departments |
| Members by Role | Count of members per role |
| Recently Added Members | Members added in the last 30/60/90 days |
| Role Assignment History | Timeline of role changes for a specific member |
| Archived Members | List of archived members with deletion reasons and dates |
| Permission Coverage | Matrix of roles and their permission sets |

---

## 13. Dependencies

### 13.1 Depends On

| Dependency | Relationship |
|------------|-------------|
| Epic 2 — Authentication | Users table, sessions, JWT tokens, account status management |
| Epic 3 — Companies | Companies table, `owner_id`, `primary_admin_id`, company audit logs, S3 storage patterns |

### 13.2 Blocks (Future Epics)

| Future Epic / Module | How This Epic Enables It |
|----------------------|------------------------|
| Authorization Engine | Provides the role-permission model that the authorization middleware will evaluate at runtime |
| Inventory | Members with inventory permissions will access inventory features. Store Keeper role provides default access. |
| Sales | Members with sales permissions will access sales features. Salesperson role provides default access. |
| Purchase | Members with purchase permissions will access purchase features |
| Accounting | Members with accounting permissions will access financial features. Accountant role provides default access. |
| CRM | Members with CRM permissions will access customer management |
| Reports | Role-based report visibility. Permission registry supports `reports.read` and `reports.export` actions. |
| Installments | Payment plan management inherits company-scoped isolation and role-based access |
| AI Features | AI-driven insights and automation scoped to company context and user permissions |
| Notifications | Notification delivery targets company members with appropriate roles and preferences |
| Billing & Subscriptions | Member count per company feeds into subscription tier enforcement. Owner manages billing. |
| API Keys | Per-user or per-company API key management for external integrations, scoped by role permissions |
| Mobile App (Future) | Same identity model, roles, and permissions apply to mobile API consumers |
| External Integrations (Future) | Integration credentials and access scoped to company context and permission model |
| SSO / SAML / OAuth (Future) | Enterprise SSO maps external identities to company memberships and role assignments |
| Branches & Warehouses (Future) | Location-scoped access control inherits company isolation and role-based permissions |
| Document Management (Future) | Company-scoped document storage with permission-based access and audit trail |
| Workflow Engine (Future) | Configurable business process automation with role-based task routing and approval chains |
| Microservices Migration (Future) | Identity model designed for extraction into an Identity microservice if architecture evolves |

---

## 14. Integration Points

### 14.1 Authentication Module (Epic 2)

- **User creation**: When a new member is added with an unregistered email, this module creates the user account via the auth module's user creation service.
- **Session revocation**: When a member is deactivated/suspended, this module calls the auth module's session revocation service.
- **Account status sync**: The auth-level `account_status` (ACTIVE, INACTIVE, LOCKED, DELETED) and the membership-level `status` are independent. Auth-level status affects access to ALL companies; membership status affects access to ONE company.

### 14.2 Companies Module (Epic 3)

- **Owner synchronisation**: When ownership is transferred, this module updates the company's `owner_id` field.
- **Primary admin**: When an Admin is designated as primary, this module updates the company's `primary_admin_id` field.
- **Company status**: When a company is suspended or deleted, all memberships become functionally inactive (enforced at the access-check level, not by mutating membership records).
- **Audit logging**: Member and role events are written to the `company_audit_logs` table established in Epic 3.

### 14.3 Object Storage (S3/MinIO)

- **Avatar upload**: Follows the same S3 client and upload patterns established for company logos in Epic 3.
- **Avatar path convention**: `companies/{company_id}/avatars/{user_id}/{filename}`
- **Previous avatar retention**: Same retention mechanism as company logo replacement (configurable days).

---

## 15. Configuration

The following settings MUST be configurable via environment variables (with sensible defaults):

| Setting | Default | Description |
|---------|---------|-------------|
| COMPANY_MAX_MEMBERS | 100 | Maximum members per company. 0 = unlimited. |
| USER_AVATAR_MAX_BYTES | 2097152 | Maximum avatar file size in bytes (2 MiB). |
| AVATAR_RETENTION_DAYS | 7 | Days a replaced avatar is retained in storage before purging. |
| MEMBER_DELETION_RETENTION_DAYS | 90 | Days archived members are retained before permanent purge eligibility. |
| MAX_CUSTOM_ROLES_PER_COMPANY | 50 | Maximum number of custom roles per company. |
| INVITATION_EXPIRY_DAYS | 7 | Days before a pending invitation expires and requires re-invitation. |

---

## 16. Success Criteria

### Measurable Outcomes

- **SC-001**: An Owner can add a new member to a company and assign a role in under 30 seconds.
- **SC-002**: An Admin can change a member's role and see the change reflected immediately.
- **SC-003**: The system supports companies with up to 10,000 members without performance degradation on member listing (p95 < 500ms).
- **SC-004**: All member and role lifecycle events produce immutable audit log entries with complete before/after state.
- **SC-005**: No user can access data from a company they do not belong to, verified by isolation tests.
- **SC-006**: All system roles are automatically created when a new company is created, with the correct permission sets.
- **SC-007**: Custom roles can be created, assigned, updated, and deleted without affecting system roles.
- **SC-008**: 100% of member status transitions follow the defined state machine — invalid transitions are rejected.
- **SC-009**: The sole Owner of a company cannot be deactivated, suspended, or demoted under any circumstances.
- **SC-010**: Users can update their own profile and preferences independently without admin intervention.

---

## 17. Assumptions

- **A1**: Users are invited by email address. Email-based invitation is the only onboarding mechanism in this Epic. Self-registration is out of scope.
- **A2**: A user has one role per company. Multi-role assignment per company is deferred for simplicity; the schema supports future extension.
- **A3**: Department is a free-text field, not a separate entity. Department management as a module is a future enhancement.
- **A4**: The permission registry is seeded with permissions for modules defined in Epics 1–4 only. Future Epics add their own permissions via migrations.
- **A5**: Notification of invitation (email) is out of scope for this Epic. The system records `pending_invitation` status; actual email delivery is a future capability.
- **A6**: Platform Super Admin is architecturally defined in this Epic (Section 1.4) but implemented in a future Epic. Platform users are NOT stored as company memberships. They manage the SaaS platform itself through a separate identity scope.
- **A7**: Avatar images are stored as-is (no server-side resizing or cropping). Client-side cropping is recommended.
- **A8**: A single user may belong to multiple companies. Each company membership is fully independent — separate role, separate permissions, separate status. Only one company context is active per session.
- **A9**: The system roles defined in FR-040 (Owner, Admin, Manager, Accountant, Salesperson, Cashier, Store Keeper, Viewer) are default ERP roles seeded for every new company. Organisations may create additional custom roles to match their unique structures.

---

## 18. Future Enhancements

The following capabilities are intentionally deferred and documented for future Epics:

| Enhancement | Description |
|-------------|-------------|
| Authorization Middleware | Runtime permission evaluation — checking if a user has permission X for resource Y before allowing access |
| Fine-Grained Permissions | Object-level and field-level permissions (e.g., "can only edit their own department's records") |
| Permission Inheritance | Hierarchical permission model where higher-ranked roles automatically inherit lower-ranked permissions |
| Team / Group Management | Logical groupings of members within a company (e.g., "Engineering Team") |
| Department Entity | First-class Department entity with hierarchy, managers, and budget centres |
| Invitation Email | Automated email notification when a user is invited to a company |
| Bulk Operations | Bulk invite, bulk role change, bulk deactivation |
| Organisation Chart | Visual representation of reporting hierarchy |
| Delegated Administration | Allowing Managers to manage members within their department only |
| Activity Feed | Timeline of user actions across the company |
| Login Restrictions | Per-company IP whitelist, time-of-day restrictions |
| SSO / SAML / OAuth | Enterprise single sign-on integration |
| MFA Enforcement | Per-company MFA policy enforcement |
| User Import / Export | CSV/Excel import of bulk user data |
| API Keys per User | Service account / API key management for integrations |
| SaaS Tier Enforcement | Member count limits tied to subscription plans |
| Platform Super Admin Implementation | Full implementation of Platform Identity Layer — tenant provisioning, system health, cross-tenant support |
| ABAC (Attribute-Based Access Control) | Policy evaluation using user/resource attributes and environmental conditions |
| Record-Level Permissions | Access control on individual records based on ownership, department, or custom policies |
| Field-Level Permissions | Visibility and editability control at the individual field level |
| Approval Workflows | Multi-level approval chains for sensitive operations (purchase orders, expenses, etc.) |
| Permission Delegation | Temporary delegation of authority from one user to another with auto-expiry |
| Temporary Permissions | Time-bound permission grants with automatic expiration |
| Mobile App Identity | Extension of company identity model to mobile API consumers |
| Platform Support Role | Platform-level support agent with read-only cross-tenant access for customer support |
| Platform Auditor Role | Platform-level compliance and audit oversight across all tenants |
| Branches & Warehouses | Company sub-locations with location-scoped access control |
| Workflow Engine | Configurable business process automation with role-based task routing |
| Document Management | Company-scoped document storage with permission-based access |

---

## 19. Session Management Foundation (Future)

The following session and device management concepts are architecturally planned for future implementation. Epic 4 provides the membership and role foundation upon which these capabilities will be built:

| Concept | Description | Foundation from Epic 4 |
|---------|-------------|----------------------|
| **Active Session** | A user's current authenticated interaction with the system | Membership status determines session validity; status change triggers session revocation (FR-035) |
| **Trusted Device** | A device remembered by the system to reduce authentication friction | User identity and company context provide device-trust scope |
| **Remember Me** | Extended session duration for trusted devices | Session tied to membership — membership deactivation invalidates all remembered sessions |
| **Concurrent Sessions** | Multiple active sessions for the same user across devices | Multi-company membership enables concurrent sessions in different company contexts |
| **Session Revocation** | Immediate termination of a user's session(s) | Already specified: membership status changes trigger session revocation (FR-035, BR-025) |
| **Forced Logout** | Admin-initiated termination of a specific user's sessions | Admin/Owner can change membership status, which triggers revocation |
| **Device Tracking** | Recording device fingerprints for security monitoring | Audit log already captures IP address and user agent per event |
| **MFA Compatibility** | Multi-Factor Authentication integration | User identity and session model designed to accommodate MFA challenges at the authentication layer |

---

## 20. Future Delegation Model

The following delegation concepts extend the role and permission model established in this Epic. They are architecturally planned but NOT implemented:

| Capability | Description | Foundation from Epic 4 |
|------------|-------------|----------------------|
| **Permission Delegation** | A user temporarily grants specific permissions to another user | Permission registry and role-permission model support granular delegation |
| **Temporary Role Assignment** | Assigning a higher role to a user for a defined period, auto-reverting on expiry | Role assignment model on CompanyMember supports role changes; future: add validity dates |
| **Acting Manager** | A user temporarily assumes a Manager's responsibilities during absence | Role hierarchy and department assignment provide the management scope |
| **Leave Coverage** | Automatic delegation of approvals and responsibilities during planned absence | Membership lifecycle and role model identify who can act in a given capacity |
| **Approval Delegation** | Redirecting approval authority to a designated alternate | Role rank hierarchy determines approval authority; delegation extends this to alternates |

---

## 21. Data Ownership

Data ownership in DevSphere ERP follows a clear hierarchy aligned with the identity architecture:

| Owner | Data Scope | Examples |
|-------|-----------|---------|
| **Platform** | Platform-level configuration, tenant registry, system health metrics | Platform settings, company registry, system audit logs |
| **Company (Tenant)** | All business data within the company scope | Members, roles, transactions, inventory, sales records, company audit logs |
| **Department** | Operational structure within a company | Department assignments, department-scoped reports (future) |
| **User** | Personal preferences and profile information | Display name, avatar, language, timezone, theme, notification preferences |
| **Audit System** | Immutable records of all actions | Audit log entries — owned by the system, scoped to company, never modifiable by any user |

**Ownership Principles**:
- Company data is owned by the company entity, not by individual users. When a user leaves a company, their membership is archived but all records they created remain with the company.
- User preferences (Section 5.1, UserPreference) are user-owned and persist across company memberships.
- Audit logs are system-owned and immutable. No user — including Owner or Platform Super Admin — may modify or delete audit log entries. Retention-based purging is the only removal mechanism.

---

## 22. Security Principles

The following security principles govern the design and future implementation of the Users & Roles module:

| Principle | Description | How Epic 4 Applies It |
|-----------|-------------|----------------------|
| **Least Privilege** | Users receive only the minimum permissions required for their role | System roles have precisely scoped permission sets; custom roles allow fine-grained composition |
| **Need-to-Know** | Information is accessible only to those with a legitimate business need | Admin notes visible only to Admin/Owner (FR-023); company data isolated by membership |
| **Default Deny** | Access is denied unless explicitly granted by a permission | Permission model is opt-in; roles without a permission do not receive it |
| **Company Isolation** | No data leakage between tenants under any circumstances | Every query includes `company_id` (BR-050); cross-company access prohibited (BR-055) |
| **Immutable Audit** | All actions are recorded and cannot be altered | Audit entries are append-only (Section 10.2); audit log survives user/member deletion |
| **Defence in Depth** | Multiple layers of security controls | Auth-level status + membership status + role rank + company context = layered access control |
| **Secure by Default** | System defaults to the most secure configuration | New members receive the lowest reasonable role; system roles cannot be weakened |
| **Zero Trust Readiness** | Architecture assumes no implicit trust between components | Every request validates company membership and role independently; no cached trust |

---

## 23. Architectural Principles

The following architectural principles guide Epic 4 and all downstream modules:

| Principle | Description |
|-----------|-------------|
| **Single Source of Truth** | This specification is the definitive reference for Epic 4. All implementation plans, task breakdowns, and code MUST derive from this document. |
| **Company Isolation** | Every business operation, every query, every audit entry is scoped to a company. No exceptions. |
| **Identity Before Authorization** | The identity model (users, memberships, roles, permissions) MUST be established before authorization enforcement. Epic 4 defines identity; a future Epic enforces authorization. |
| **Role-Based Access** | Access control is role-based in the initial architecture. Roles group permissions; permissions gate actions. |
| **Future Attribute-Based Access** | The architecture anticipates ABAC (Attribute-Based Access Control) as a future extension, using user attributes, resource attributes, and environmental conditions for policy evaluation. |
| **Composition Over Duplication** | Permissions are composed into roles. Roles are assigned to memberships. No permission logic is duplicated across modules. |
| **Security by Design** | Security is not an afterthought. Tenant isolation, audit logging, session revocation, and rank-based management are built into the core identity model. |
| **Documentation First, Code Second** | The specification is written and approved before implementation begins. Code implements the spec, not the other way around. |
| **Specification-Driven Development** | Every feature, requirement, and business rule is traceable from spec → plan → tasks → code → tests. |
| **Enterprise Extensibility** | The identity model is designed to support future modules (Inventory, Sales, Accounting, CRM, HR, AI, Billing, Mobile, Integrations, SSO) without schema-breaking changes. |
| **Maintainability** | Clean Architecture, modular boundaries, service-layer business logic, and repository-layer persistence ensure long-term maintainability. |

---

## 24. Glossary

| Term | Definition |
|------|-----------|
| **Platform** | The SaaS infrastructure layer that hosts all tenants (companies). Managed by Platform Super Admin. |
| **Tenant** | A company (organisation) hosted on the DevSphere ERP platform. Each tenant has fully isolated data and configuration. Synonymous with "Company" in this specification. |
| **Company** | An organisation registered on the platform. The primary unit of data isolation and business operation scope. |
| **Department** | An organisational subdivision within a company (e.g., Sales, Accounts, Warehouse). In this Epic, a free-text field; future: a first-class entity. |
| **Employee** | A person employed by a company. May or may not have system access. Represented by employee information fields on CompanyMember. |
| **User** | A login identity in the system. Always represents a person who can authenticate. Defined in Epic 2. |
| **Member** | A user who belongs to a company via a CompanyMember record. Bridges the User and Company entities. |
| **Role** | A named set of permissions that can be assigned to a member within a company. |
| **Permission** | A specific action that can be performed on a specific module (e.g., `members.create`). |
| **System Role** | A predefined, immutable role that exists in every company (Owner, Admin, Manager, Accountant, Salesperson, Cashier, Store Keeper, Viewer). |
| **Custom Role** | A company-specific role created by an Owner or Admin with a custom permission set. |
| **Operational Role** | A system-defined role for specific business functions — Accountant, Cashier, Salesperson, Store Keeper. Positioned between Manager and Viewer in the rank hierarchy. |
| **Rank** | A numeric value (1–100) that determines the role hierarchy. Higher rank = more authority. |
| **Membership** | The relationship between a User and a Company, carrying role assignment, status, and employee information. |
| **Membership Status** | The lifecycle state of a member within a company (active, inactive, suspended, locked, pending_invitation, archived). |
| **Session** | An authenticated interaction between a user and the system, scoped to an active company context. |
| **Identity** | The combination of a user's authentication credentials and their company memberships that determine who they are in the system. |
| **Authorization** | The process of determining whether an authenticated user has permission to perform a specific action. Defined structurally in Epic 4; enforced at runtime in a future Epic. |
| **Authentication** | The process of verifying a user's identity (login). Implemented in Epic 2. |
| **Audit Trail** | The immutable, append-only record of all actions performed within the system, scoped to a company. |
| **Owner** | The highest-authority company role. Responsible for billing, ownership transfer, company settings, and final authority. |
| **Administrator** | A company role responsible for daily administration — user management, role assignment, department management, and operational settings. |
| **Platform Super Admin** | A platform-level administrator who manages the SaaS platform itself. NOT a company role. NOT stored as a company membership. Operates in the Platform Identity Layer. |
| **Platform Identity Layer** | The identity scope governing SaaS platform operations — tenant provisioning, system health, cross-tenant support. Separate from the Company Identity Layer. |
| **Company Identity Layer** | The identity scope governing individual tenant organisations — members, roles, permissions, and business operations within a single company. |
| **Company Context** | The active company under which all operations are scoped for a given request. Only one company context is active per session. |
| **Ownership Transfer** | The process of changing a company's Owner to another active member. |
| **Locked** | A security-triggered membership status (e.g., failed login attempts, suspicious activity). Unlike suspension, locking may be system-initiated. |
| **Tenant Isolation** | The architectural guarantee that no company's data, roles, permissions, or audit logs are accessible to another company's users. |
| **Delegation** | The future capability of temporarily transferring authority or permissions from one user to another. |

---

*This specification is the Single Source of Truth (SSOT) for Epic 4 — Users & Roles. All implementation decisions, architecture plans, and task breakdowns MUST derive from this document.*
