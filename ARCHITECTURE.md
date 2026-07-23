# AgencyDesk — Frozen Architecture Specification

This document is the canonical architecture contract for AgencyDesk.
Every coding agent working on this repository must follow it exactly.

---

## 1. Technology Stack

| Layer | Technology | Version Guidance |
|---|---|---|
| Backend framework | FastAPI | Latest stable |
| ORM | SQLAlchemy 2.x (async) | 2.0+ mapped-column style |
| Migrations | Alembic | autogenerate enabled |
| Validation | Pydantic v2 | via FastAPI |
| Auth | python-jose (JWT) + passlib[bcrypt] | |
| DB driver | asyncpg (via sqlalchemy[asyncio]) | |
| Database | PostgreSQL | 14+ |
| Testing | pytest + httpx (AsyncClient) + factory-boy | |
| Frontend | React (Vite) | Latest stable |
| File storage | Local filesystem | Authenticated download endpoint |

No additional major dependencies without explicit justification.

---

## 2. Core Architecture Principles

1. **Tenant isolation is the primary requirement.** Every tenant-owned query includes `WHERE agency_id = :authenticated_agency_id`.
2. **Schema-enforced safety.** Composite foreign keys prevent cross-tenant data corruption at the database level.
3. **Safe defaults.** All visibility fields default to `INTERNAL`. Content must be explicitly promoted to `CLIENT`.
4. **Soft deactivation only.** Users and memberships are deactivated, never hard-deleted. Historical data is never cascade-destroyed.
5. **Minimal architecture.** No enterprise abstractions. No RLS. No background workers. No message queues. Simple, explicit, interview-defensible.

---

## 3. Domain Relationship Diagram

```
┌─────────┐
│  users  │  ← global identity (email, password_hash)
└────┬────┘
     │ 1:N (RESTRICT)
     ▼
┌──────────────────┐        ┌───────────┐
│agency_memberships│──CFk──▶│ agencies  │
│(role per agency) │  N:1   └─────┬─────┘
└──────────────────┘              │ 1:N
                                  ▼
                           ┌───────────┐
                    ┌─CFk─▶│  clients  │◀── agency_id
                    │      └─────┬─────┘
                    │            │ 1:N
                    │            ▼
┌──────────────────┐│     ┌───────────┐
│client_memberships││     │ projects  │◀── (client_id, agency_id) CFk
│(user ↔ client    │┘     └─────┬─────┘
│ per agency)      │            │ 1:N
└──────────────────┘            ▼
┌───────────────────┐     ┌───────────┐
│project_memberships│─CFk▶│   tasks   │◀── (project_id, agency_id) CFk
│(agency staff      │     │(visibility, assignee)
│ on projects)      │     └──┬──┬──┬──┘
└───────────────────┘        │  │  │
                    ┌────────┘  │  └────────┐
                    ▼           ▼            ▼
              ┌──────────┐ ┌───────────┐ ┌────────┐
              │ comments │ │time_entries│ │ files  │
              │(visibility)│(agency    │ │(visibility)
              └──────────┘ │ staff     │ └───┬────┘
                           │ only)     │     │ 1:N
                           └───────────┘     ▼
                                       ┌───────────────┐
                                       │file_approvals │
                                       │(client action)│
                                       └───────────────┘

┌─────────────┐
│ invitations │  (standalone, token-hash-based)
└─────────────┘

CFk = Composite Foreign Key (id, agency_id)
```

---

## 4. Final PostgreSQL Tables

### 4.1 `users`

Global identity. One row per human. No tenant coupling.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `email` | `VARCHAR(255)` | no | | |
| `password_hash` | `VARCHAR(255)` | no | | bcrypt |
| `full_name` | `VARCHAR(255)` | no | | |
| `is_active` | `BOOLEAN` | no | `true` | soft-deactivation flag |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (email)`

---

### 4.2 `agencies`

Tenant. Top-level isolation boundary.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | no | | |
| `slug` | `VARCHAR(100)` | no | | URL-friendly identifier |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (slug)`

---

### 4.3 `agency_memberships`

Links a user to an agency with a role. This is where role lives.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `user_id` | `UUID` FK | no | | → `users.id` |
| `agency_id` | `UUID` FK | no | | → `agencies.id` |
| `role` | `VARCHAR(20)` | no | | `agency_admin`, `agency_member`, `client_user` |
| `is_active` | `BOOLEAN` | no | `true` | soft-deactivation |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (user_id, agency_id)` — one role per user per agency
- `CHECK (role IN ('agency_admin', 'agency_member', 'client_user'))`
- **INDEX** on `agency_id`
- **INDEX** on `user_id`

---

### 4.4 `clients`

An agency's client company/entity. Tenant-owned.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `agency_id` | `UUID` FK | no | | → `agencies.id` ON DELETE CASCADE |
| `name` | `VARCHAR(255)` | no | | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (agency_id, name)` — no duplicate client names per agency
- `UNIQUE (id, agency_id)` — composite unique for FK referencing
- **INDEX** on `agency_id`

---

### 4.5 `client_memberships`

Links a `client_user` to the specific Client they represent within an agency.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `user_id` | `UUID` FK | no | | → `users.id` |
| `client_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (user_id, agency_id)` — one client per user per agency
- `UNIQUE (user_id, client_id)` — no duplicate membership per user per client
- `FOREIGN KEY (client_id, agency_id) REFERENCES clients (id, agency_id)` — composite tenant FK
- **INDEX** on `client_id`
- **INDEX** on `(agency_id, user_id)`

---

### 4.6 `projects`

A project belongs to a client, scoped to an agency.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `agency_id` | `UUID` | no | | composite FK part |
| `client_id` | `UUID` | no | | composite FK part |
| `name` | `VARCHAR(255)` | no | | |
| `description` | `TEXT` | yes | | |
| `status` | `VARCHAR(20)` | no | `'active'` | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (id, agency_id)` — composite unique for FK referencing
- `UNIQUE (agency_id, client_id, name)` — no duplicate project names per client
- `FOREIGN KEY (client_id, agency_id) REFERENCES clients (id, agency_id)` — composite tenant FK
- `CHECK (status IN ('active', 'archived', 'completed'))`
- **INDEX** on `agency_id`
- **INDEX** on `client_id`

---

### 4.7 `project_memberships`

Which agency staff are assigned to a project. Client users access projects through their client, not project membership.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `user_id` | `UUID` FK | no | | → `users.id` |
| `project_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (user_id, project_id)` — one membership per user per project
- `FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)` — composite tenant FK
- **INDEX** on `(agency_id, project_id)`
- **INDEX** on `user_id`

---

### 4.8 `tasks`

A work item within a project.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `project_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `title` | `VARCHAR(500)` | no | | |
| `description` | `TEXT` | yes | | |
| `status` | `VARCHAR(20)` | no | `'todo'` | |
| `priority` | `VARCHAR(10)` | no | `'medium'` | |
| `visibility` | `VARCHAR(10)` | no | `'internal'` | safe default |
| `assignee_id` | `UUID` FK | **yes** | `NULL` | → `users.id` ON DELETE SET NULL |
| `due_date` | `DATE` | yes | | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (id, agency_id)` — composite unique for FK referencing
- `FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)` — composite tenant FK
- `CHECK (status IN ('todo', 'in_progress', 'review', 'done'))`
- `CHECK (priority IN ('low', 'medium', 'high', 'urgent'))`
- `CHECK (visibility IN ('internal', 'client'))`
- **INDEX** on `agency_id`
- **INDEX** on `project_id`
- **INDEX** on `(agency_id, project_id, visibility)` — critical for client-filtered queries
- **INDEX** on `assignee_id`

---

### 4.9 `comments`

Comments on tasks. Carry their own visibility flag.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `task_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `author_id` | `UUID` FK | no | | → `users.id` |
| `content` | `TEXT` | no | | |
| `visibility` | `VARCHAR(10)` | no | `'internal'` | safe default |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)` — composite tenant FK
- `CHECK (visibility IN ('internal', 'client'))`
- **INDEX** on `(task_id, visibility)`
- **INDEX** on `agency_id`

---

### 4.10 `time_entries`

Agency staff log time against tasks. Client users cannot create these.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `task_id` | `UUID` | no | | composite FK part |
| `project_id` | `UUID` | no | | composite FK part (denormalized) |
| `agency_id` | `UUID` | no | | composite FK part |
| `user_id` | `UUID` FK | no | | → `users.id` |
| `duration_minutes` | `INTEGER` | no | | |
| `note` | `TEXT` | yes | | |
| `date` | `DATE` | no | | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)` — composite tenant FK
- `FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)` — composite tenant FK
- `CHECK (duration_minutes > 0)`
- **INDEX** on `(agency_id, project_id)`
- **INDEX** on `task_id`
- **INDEX** on `user_id`

---

### 4.11 `files`

File attachments on tasks.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `task_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `uploaded_by_id` | `UUID` FK | no | | → `users.id` |
| `filename` | `VARCHAR(500)` | no | | original filename |
| `storage_path` | `VARCHAR(1000)` | no | | server-side path (UUID-based) |
| `mime_type` | `VARCHAR(100)` | yes | | |
| `file_size_bytes` | `BIGINT` | yes | | |
| `visibility` | `VARCHAR(10)` | no | `'internal'` | safe default |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (id, agency_id)` — composite unique for FK referencing
- `FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)` — composite tenant FK
- `CHECK (visibility IN ('internal', 'client'))`
- **INDEX** on `(task_id, visibility)`
- **INDEX** on `agency_id`

---

### 4.12 `file_approvals`

Client approval actions on files. Separate table for audit trail and multi-reviewer support.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `file_id` | `UUID` | no | | composite FK part |
| `agency_id` | `UUID` | no | | composite FK part |
| `reviewer_id` | `UUID` FK | no | | → `users.id` |
| `status` | `VARCHAR(20)` | no | | |
| `note` | `TEXT` | yes | | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |

**Constraints:**
- `UNIQUE (file_id, reviewer_id)` — one approval per reviewer per file (upsert for re-review)
- `FOREIGN KEY (file_id, agency_id) REFERENCES files (id, agency_id)` — composite tenant FK
- `CHECK (status IN ('approved', 'needs_changes'))`
- **INDEX** on `file_id`
- **INDEX** on `agency_id`

---

### 4.13 `invitations`

Invite users to join an agency. Token stored as SHA-256 hash only.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` PK | no | `gen_random_uuid()` | |
| `agency_id` | `UUID` FK | no | | → `agencies.id` ON DELETE CASCADE |
| `email` | `VARCHAR(255)` | no | | invitee email |
| `role` | `VARCHAR(20)` | no | | intended role |
| `client_id` | `UUID` FK | **yes** | | → `clients.id`; required when role = `client_user` |
| `token_hash` | `VARCHAR(64)` | no | | SHA-256 hex digest |
| `status` | `VARCHAR(20)` | no | `'pending'` | |
| `invited_by_id` | `UUID` FK | no | | → `users.id` |
| `expires_at` | `TIMESTAMPTZ` | no | | |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `accepted_at` | `TIMESTAMPTZ` | yes | | |

**Constraints:**
- Partial unique index: `UNIQUE (agency_id, email) WHERE status = 'pending'` — one active invite per email per agency
- `CHECK (role IN ('agency_admin', 'agency_member', 'client_user'))`
- `CHECK (status IN ('pending', 'accepted', 'expired', 'revoked'))`
- **INDEX** on `token_hash`

---

## 5. Final Foreign Keys and ON DELETE Rules

### User References

Every FK pointing to `users.id` uses ON DELETE **RESTRICT** to prevent accidental destruction of historical data. The only exception is `tasks.assignee_id` which uses ON DELETE **SET NULL**.

| Table.Column | References | ON DELETE | Rationale |
|---|---|---|---|
| `agency_memberships.user_id` | `users.id` | RESTRICT | Must soft-deactivate |
| `client_memberships.user_id` | `users.id` | RESTRICT | Must soft-deactivate |
| `project_memberships.user_id` | `users.id` | RESTRICT | Must soft-deactivate |
| `tasks.assignee_id` | `users.id` | SET NULL | Unassign on delete (edge case) |
| `comments.author_id` | `users.id` | RESTRICT | Preserve audit trail |
| `time_entries.user_id` | `users.id` | RESTRICT | Preserve historical data |
| `files.uploaded_by_id` | `users.id` | RESTRICT | Preserve record |
| `file_approvals.reviewer_id` | `users.id` | RESTRICT | Preserve approval record |
| `invitations.invited_by_id` | `users.id` | RESTRICT | Preserve invitation record |

### Agency References

| Table.Column | References | ON DELETE |
|---|---|---|
| `agency_memberships.agency_id` | `agencies.id` | CASCADE |
| `clients.agency_id` | `agencies.id` | CASCADE |

### Cascade Through Tenant Hierarchy

When a parent entity is deleted, child entities cascade:

| Table.Column | References | ON DELETE |
|---|---|---|
| `projects → clients` | composite FK | RESTRICT (don't orphan projects) |
| `tasks → projects` | composite FK | CASCADE |
| `comments → tasks` | composite FK | CASCADE |
| `time_entries → tasks` | composite FK | CASCADE |
| `files → tasks` | composite FK | CASCADE |
| `file_approvals → files` | composite FK | CASCADE |
| `project_memberships → projects` | composite FK | CASCADE |

---

## 6. Composite Tenant Constraints

Every tenant-owned parent table has a `UNIQUE (id, agency_id)` constraint to support composite FK references from child tables.

### Composite Unique Constraints (for FK reference)

```sql
ALTER TABLE clients ADD CONSTRAINT uq_clients_id_agency UNIQUE (id, agency_id);
ALTER TABLE projects ADD CONSTRAINT uq_projects_id_agency UNIQUE (id, agency_id);
ALTER TABLE tasks ADD CONSTRAINT uq_tasks_id_agency UNIQUE (id, agency_id);
ALTER TABLE files ADD CONSTRAINT uq_files_id_agency UNIQUE (id, agency_id);
```

### Composite Foreign Keys

```sql
-- projects → clients (same agency)
FOREIGN KEY (client_id, agency_id) REFERENCES clients (id, agency_id)

-- tasks → projects (same agency)
FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)

-- comments → tasks (same agency)
FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)

-- files → tasks (same agency)
FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)

-- time_entries → tasks (same agency)
FOREIGN KEY (task_id, agency_id) REFERENCES tasks (id, agency_id)

-- time_entries → projects (same agency)
FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)

-- project_memberships → projects (same agency)
FOREIGN KEY (project_id, agency_id) REFERENCES projects (id, agency_id)

-- client_memberships → clients (same agency)
FOREIGN KEY (client_id, agency_id) REFERENCES clients (id, agency_id)

-- file_approvals → files (same agency)
FOREIGN KEY (file_id, agency_id) REFERENCES files (id, agency_id)
```

These constraints make it structurally impossible at the database level to create a child record in one agency that references a parent in another agency.

---

## 7. Identity Model

### Global Identity

The `users` table represents global identity. One row per email. Contains credentials. Contains **no** agency or role information.

### Agency Membership

The `agency_memberships` table links a user to an agency and holds the `role`. One user can belong to many agencies with different roles.

### Client Association

For users with `role = client_user`: the `client_memberships` table links the user to the specific `clients` row they represent. Constrained to one client per user per agency via `UNIQUE (user_id, agency_id)`.

### Multi-Agency Example

```
person@example.com (users.id = U1)
├─ agency_memberships: U1 → Agency A, role = agency_admin
└─ agency_memberships: U1 → Agency B, role = client_user
   └─ client_memberships: U1 → Client X (in Agency B)
```

---

## 8. Authentication Strategy

### Login Flow

1. User authenticates with email + password → verified against `users` table.
2. Query `agency_memberships` for this `user_id` → list of agencies + roles.
3. If exactly one agency: auto-select.
4. If multiple agencies: return list; frontend presents agency-selector. User picks one.
5. Issue JWT.

### JWT Claims

```json
{
  "sub": "<user_id>",
  "agency_id": "<selected_agency_id>",
  "role": "<role from agency_membership>",
  "client_id": "<client_id or null>",
  "iat": "<issued_at>",
  "exp": "<expiry, 30 minutes>"
}
```

### JWT Rules

- Token lifetime: **30 minutes**. No refresh token complexity.
- `agency_id` is baked into the token. Switching agencies requires a new token via a "switch agency" endpoint.
- The client cannot override `agency_id` or `role` via headers or request body.
- The JWT is the source of `agency_id` and `role` for authorization, but membership/user status is **revalidated per request** (see §9).

---

## 9. Tenant Context Resolution

### Per-Request Validation

Every authenticated request executes (via FastAPI dependency injection):

1. Decode JWT → extract `user_id`, `agency_id`, `role`, `client_id`.
2. Query database:
   ```sql
   SELECT am.is_active AS membership_active, u.is_active AS user_active
   FROM agency_memberships am
   JOIN users u ON u.id = am.user_id
   WHERE am.user_id = :user_id AND am.agency_id = :agency_id
   ```
3. If either `is_active = false` or no row exists → **401 Unauthorized**.
4. Proceed with `agency_id` and `role` from JWT for all subsequent authorization.

### Tenant Scoping Rule

Every query on tenant-owned data includes `WHERE agency_id = :authenticated_agency_id`.
The `agency_id` value comes exclusively from the authenticated JWT, never from request parameters.

### Resource Authorization Helpers

Resource-level authorization functions query with `WHERE id = :id AND agency_id = :agency_id`. If the resource does not match → **404 Not Found** (never 403, to prevent information leakage).

---

## 10. RBAC Matrix

| Resource | Action | `agency_admin` | `agency_member` | `client_user` |
|---|---|---|---|---|
| **Projects** | List | All in agency | Assigned only | Own client's only |
| **Projects** | Read | Any in agency | Assigned only | Own client's only |
| **Projects** | Create | ✅ | ❌ | ❌ |
| **Projects** | Update | ✅ | ❌ | ❌ |
| **Tasks** | List | All in project | All in assigned projects | `visibility=client` only |
| **Tasks** | Read | Any in agency | Any in assigned projects | `visibility=client` only |
| **Tasks** | Create | ✅ | ✅ (assigned projects) | ❌ |
| **Tasks** | Update status | ✅ | ✅ (assigned projects) | ❌ |
| **Tasks** | Update details | ✅ | ✅ (assigned projects) | ❌ |
| **Comments** | List | All on task | All (assigned projects) | `visibility=client` only |
| **Comments** | Create | ✅ (any visibility) | ✅ (any visibility) | ✅ (`client` only, visible tasks only) |
| **Time Entries** | List | All in agency | All in assigned projects | ❌ |
| **Time Entries** | Create | ✅ | ✅ (assigned projects) | ❌ |
| **Files** | List | All on task | All (assigned projects) | `visibility=client` only |
| **Files** | Upload | ✅ | ✅ (assigned projects) | ❌ |
| **File Approval** | Create/Update | ❌ | ❌ | ✅ (client-visible files, own projects) |
| **Dashboard** | View | Full counts + hours | Full counts + hours (assigned) | Client-visible counts only, no hours |
| **Invitations** | Send/Manage | ✅ | ❌ | ❌ |
| **Members** | Manage | ✅ | ❌ | ❌ |

---

## 11. Project Access Rules

### agency_admin

Full access to all projects in their agency. No `project_memberships` row required.

### agency_member

Access only to projects where they have an active `project_memberships` row. All project-level queries include:

```sql
AND EXISTS (
  SELECT 1 FROM project_memberships pm
  WHERE pm.project_id = projects.id
    AND pm.agency_id = :agency_id
    AND pm.user_id = :user_id
)
```

### client_user

Access only to projects belonging to their client:

```sql
AND projects.client_id = :client_id
```

Where `:client_id` comes from `client_memberships` (stored in JWT).

---

## 12. Client Visibility Rules

### Visibility Values

`INTERNAL` — agency-only. `CLIENT` — visible to both agency and client.

### Default

All visibility fields default to `INTERNAL`.

### Enforcement

| Code Path | Rule |
|---|---|
| Task list | Append `AND visibility = 'client'` for `client_user` |
| Task detail | Return 404 if `visibility = 'internal'` and viewer is `client_user` |
| Task search | Same filter as list — always include visibility filter for `client_user` |
| Comment list | `AND visibility = 'client'` for `client_user`; parent task must also be `client`-visible |
| Comment create (client) | Force `visibility = 'client'`; reject if parent task is `internal` |
| File list | `AND visibility = 'client'` for `client_user` |
| File download | Check visibility + tenant + client ownership before serving bytes |
| Dashboard task counts | Count only `visibility = 'client'` tasks for `client_user` |
| Dashboard hours | `client_user` sees no time entry data at all (field omitted from response) |

### Cascade Invariant

A `client`-visible child cannot exist on an `internal` parent:
- Cannot create a `client`-visible comment on an `internal` task → **reject**.
- Cannot create a `client`-visible file on an `internal` task → **reject**.
- Changing a task from `client` → `internal` is **blocked** if any `client`-visible children (comments or files) exist. Return an error listing the blocking items.

---

## 13. Task Assignment Rules

### Assignee Constraints (application-enforced)

At assignment time, validate:
1. The assignee belongs to the same agency (has `agency_memberships` row with matching `agency_id`).
2. The assignee has `role` of `agency_admin` or `agency_member` (not `client_user`).
3. The assignee has an active `project_memberships` row for the task's project.

### Schema Design

`tasks.assignee_id → users.id` ON DELETE SET NULL. Assignment validation is application-level.

### Unassignment on Member Removal

Handled by the explicit transaction in §18. Not by FK cascades.

---

## 14. Comment Rules

1. Agency staff (`agency_admin`, `agency_member`) can create comments with any visibility on tasks in projects they have access to.
2. `client_user` can create comments **only** on tasks with `visibility = 'client'` in projects belonging to their client.
3. Comments created by `client_user` are **forced** to `visibility = 'client'` regardless of request body.
4. Agency staff comments default to `visibility = 'internal'` (safe default).
5. `client_user` cannot see comments with `visibility = 'internal'`.

---

## 15. Time Entry Rules

1. Only `agency_admin` and `agency_member` can create time entries.
2. `client_user` cannot create, read, or list time entries.
3. Time entries are always agency-internal. There is no visibility flag.
4. Time entries survive project-member removal (historical data preserved).
5. `agency_member` can log time only against tasks in their assigned projects.
6. `project_id` is denormalized on `time_entries` for efficient per-project aggregation queries.

---

## 16. File and File Approval Rules

### File Upload

1. Only `agency_admin` and `agency_member` can upload files.
2. Files are attached to tasks. File visibility defaults to `internal`.
3. File storage uses UUID-based paths, not original filenames, to prevent URL guessing.
4. File download goes through an authenticated endpoint that checks agency, visibility, and client ownership.

### File Approval

1. Only `client_user` can create/update file approvals.
2. Authorization checklist (all must pass):
   - File exists and `file.agency_id = :authenticated_agency_id` (composite FK prevents cross-tenant)
   - `file.visibility = 'client'` (cannot approve internal file)
   - File's task's project belongs to the reviewer's client
   - Reviewer has `client_user` role
3. Approval status: `approved` or `needs_changes`.
4. `UNIQUE (file_id, reviewer_id)` — re-reviewing upserts the existing approval record.

---

## 17. Invitation Model and Race Handling

### Token Security

- Generate a cryptographically secure random token (e.g., `secrets.token_urlsafe(32)`).
- Return the raw token only once when the invitation is created or resent.
- Store only `SHA-256(raw_token)` in the `token_hash` column.
- Lookup: compute `SHA-256(submitted_token)` and query against `token_hash`.
- The raw token is never persisted in the database.

### Resend Idempotency

Partial unique index:
```sql
CREATE UNIQUE INDEX uq_pending_invitation
ON invitations (agency_id, email)
WHERE status = 'pending';
```

Resend uses UPSERT:
```sql
INSERT INTO invitations (id, agency_id, email, role, client_id, token_hash, status, invited_by_id, expires_at)
VALUES (...)
ON CONFLICT (agency_id, email) WHERE status = 'pending'
DO UPDATE SET token_hash = :new_hash, expires_at = :new_expires, invited_by_id = :inviter;
```

This refreshes the token and expiry without creating a duplicate. The new raw token is returned to the caller; the old token becomes invalid because the hash changed.

### Acceptance Transaction

```
BEGIN;

  -- 1. Lock the invitation
  SELECT * FROM invitations
  WHERE token_hash = sha256(:submitted_token)
    AND status = 'pending'
    AND expires_at > now()
  FOR UPDATE;

  -- If no row: check if an invitation exists with status = 'accepted'
  --   If yes → return 200 (idempotent success)
  --   If no  → return 400 "Invitation invalid or expired"

  -- 2. Find or create user
  INSERT INTO users (id, email, password_hash, full_name)
  VALUES (:id, :email, :hash, :name)
  ON CONFLICT (email) DO NOTHING;
  -- If no row returned: SELECT id FROM users WHERE email = :email

  -- 3. Create agency membership (idempotent)
  INSERT INTO agency_memberships (id, user_id, agency_id, role)
  VALUES (:id, :user_id, :agency_id, :role)
  ON CONFLICT (user_id, agency_id) DO NOTHING;

  -- 4. If role = 'client_user', create client membership (idempotent)
  INSERT INTO client_memberships (id, user_id, client_id, agency_id)
  VALUES (:id, :user_id, :client_id, :agency_id)
  ON CONFLICT (user_id, agency_id) DO NOTHING;

  -- 5. Mark invitation accepted
  UPDATE invitations
  SET status = 'accepted', accepted_at = now()
  WHERE id = :invitation_id;

COMMIT;
```

### Concurrency Safety

- `FOR UPDATE` on the invitation row serializes concurrent acceptance attempts.
- `ON CONFLICT DO NOTHING` on memberships prevents duplicate creation.
- The second concurrent request either waits for the lock (then sees `status = 'accepted'`) or finds membership already exists (idempotent success).

---

## 18. Project Member Removal Transaction

### Behavior

When an `agency_member` is removed from a project:
1. All tasks in that project assigned to the user become unassigned.
2. The `project_memberships` row is deleted.
3. Tasks are not deleted.
4. Historical time entries remain.
5. The operation is atomic.

### Transaction

```sql
BEGIN;

  -- 1. Unassign tasks
  UPDATE tasks
  SET assignee_id = NULL, updated_at = now()
  WHERE project_id = :project_id
    AND agency_id = :agency_id
    AND assignee_id = :user_id;

  -- 2. Remove membership
  DELETE FROM project_memberships
  WHERE project_id = :project_id
    AND user_id = :user_id
    AND agency_id = :agency_id;

COMMIT;
```

### Why This Works

- `time_entries.user_id → users.id` (not to `project_memberships`) — deleting the membership does not affect time entries.
- `tasks.assignee_id → users.id` (not to `project_memberships`) — unassignment is explicit in step 1.
- Both steps are in one transaction — no partial state.

---

## 19. Dashboard Authorization

### Task Counts by Status

**agency_admin / agency_member (with project access):**
```sql
SELECT status, COUNT(*) FROM tasks
WHERE project_id = :pid AND agency_id = :aid
GROUP BY status;
```

**client_user:**
```sql
SELECT status, COUNT(*) FROM tasks
WHERE project_id = :pid AND agency_id = :aid
  AND visibility = 'client'
GROUP BY status;
```

Client sees different totals. Internal tasks are invisible in counts.

### Hours Logged

**agency_admin / agency_member:**
```sql
SELECT COALESCE(SUM(duration_minutes), 0) FROM time_entries
WHERE project_id = :pid AND agency_id = :aid;
```

**client_user:** The hours field is **omitted from the response entirely**. Not zero — omitted. Time tracking is agency-internal.

### Security Invariant

A client must never be able to infer the existence of internal content through:
- Counts (filtered to `visibility = 'client'` only)
- Totals (time entries excluded entirely)
- Search results (visibility-filtered)
- Status distributions (only client-visible statuses shown)
- Empty vs non-empty responses (no information leakage in either case)

---

## 20. Required Security Tests

### Cross-Tenant Isolation (Tests 1–3)

| # | Test | Invariant |
|---|---|---|
| 1 | `GET /projects/:B_project` as Agency A user → 404 | Cross-tenant read blocked |
| 2 | `PATCH /projects/:B_project` as Agency A user → 404 | Cross-tenant write blocked |
| 3 | `GET /tasks/:B_task` as Agency A user → 404 | Cross-tenant ID guessing fails |

### Client Visibility (Tests 4–8)

| # | Test | Invariant |
|---|---|---|
| 4 | `GET /tasks/:internal_task` as `client_user` → 404 | Client cannot read internal task |
| 5 | `GET /projects/:pid/tasks` as `client_user` → no internal tasks | Client list excludes internal tasks |
| 6 | `GET /projects/:pid/tasks?search=internal_keyword` as `client_user` → no results | Client search excludes internal tasks |
| 7 | `GET /tasks/:visible_task/comments` as `client_user` → no internal comments | Internal comments hidden from client |
| 8 | `GET /tasks/:visible_task/files` as `client_user` → no internal files | Internal files hidden from client |

### Client Restrictions (Tests 9–11)

| # | Test | Invariant |
|---|---|---|
| 9 | `PATCH /tasks/:visible_task {status: done}` as `client_user` → 403 | Client cannot change task status |
| 10 | `POST /projects/:pid/tasks` as `client_user` → 403 | Client cannot create tasks |
| 11 | `POST /tasks/:tid/time-entries` as `client_user` → 403 | Client cannot log time |

### Role-Based Access (Tests 12–14)

| # | Test | Invariant |
|---|---|---|
| 12 | `GET /projects/:unassigned_project` as `agency_member` → 404 | Member cannot access unassigned project |
| 13 | `POST /files/:other_client_file/approvals` as `client_user` → 404 | Cross-client file approval blocked |
| 14 | `POST /files/:internal_file/approvals` as `client_user` → 404 | Internal file approval blocked |

### Invitation Integrity (Tests 15–17)

| # | Test | Invariant |
|---|---|---|
| 15 | Send invite → resend → assert one `pending` row | Resend is idempotent |
| 16 | Accept invite → accept same token again → assert one membership | Acceptance is idempotent |
| 17 | Concurrent accept (asyncio.gather, two requests) → assert exactly one membership | Race condition prevented |

### Member Removal (Tests 18–20)

| # | Test | Invariant |
|---|---|---|
| 18 | Remove member → `GET /projects/:pid` as that member → 404 | Access revoked |
| 19 | Remove member → assert formerly-assigned tasks have `assignee_id = NULL` | Tasks unassigned atomically |
| 20 | Remove member → assert their time entries still exist | Historical data preserved |

### Dashboard Security (Tests 21–22)

| # | Test | Invariant |
|---|---|---|
| 21 | `GET /projects/:pid/dashboard` as `client_user` → counts exclude internal tasks | Dashboard doesn't leak internal counts |
| 22 | `GET /projects/:B_project/dashboard` as Agency A user → 404 | Cross-tenant dashboard blocked |

### Schema-Level Integrity (Tests 23–24)

| # | Test | Invariant |
|---|---|---|
| 23 | Insert project with `agency_id=A`, `client_id` belonging to Agency B → DB error | Composite FK prevents cross-tenant corruption |
| 24 | Insert task with `agency_id=A`, `project_id` belonging to Agency B → DB error | Composite FK prevents cross-tenant corruption |

### Deactivation Enforcement (Tests 25–26)

| # | Test | Invariant |
|---|---|---|
| 25 | Deactivate membership → next API call with existing JWT → 401 | Membership deactivation is immediate |
| 26 | Deactivate user → next API call with existing JWT → 401 | User deactivation is immediate |

### Visibility Default Safety (Tests 27–28)

| # | Test | Invariant |
|---|---|---|
| 27 | `client_user` comments on visible task → comment visibility is `client` | Forced visibility for client comments |
| 28 | Agency user creates comment without specifying visibility → visibility is `internal` | Safe default prevents accidental exposure |

**Total: 28 tests.**

---

## 21. Repository Architecture

```
AgencyDesk/
├── AGENTS.md                         # Agent engineering rules
├── ARCHITECTURE.md                   # This document
├── DESIGN.md                         # Assignment deliverable (half-page write-up)
├── README.md                         # Setup instructions (< 10 min)
├── .env.example
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app, CORS, lifespan
│   │   ├── config.py                 # Settings from env vars
│   │   ├── database.py               # Async engine, session factory
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── agency.py
│   │   │   ├── client.py
│   │   │   ├── project.py
│   │   │   ├── task.py
│   │   │   ├── comment.py
│   │   │   ├── time_entry.py
│   │   │   ├── file.py
│   │   │   └── invitation.py
│   │   ├── schemas/                  # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── project.py
│   │   │   ├── task.py
│   │   │   ├── comment.py
│   │   │   ├── time_entry.py
│   │   │   ├── file.py
│   │   │   └── invitation.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # Auth + tenant dependencies
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── tasks.py
│   │   │   ├── comments.py
│   │   │   ├── time_entries.py
│   │   │   ├── files.py
│   │   │   ├── dashboard.py
│   │   │   └── invitations.py
│   │   ├── services/                 # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── project_service.py
│   │   │   ├── task_service.py
│   │   │   └── invitation_service.py
│   │   └── auth/
│   │       ├── __init__.py
│   │       ├── jwt.py
│   │       └── permissions.py
│   ├── tests/
│   │   ├── conftest.py               # Fixtures: test DB, agencies, users
│   │   ├── test_tenant_isolation.py
│   │   ├── test_client_visibility.py
│   │   ├── test_rbac.py
│   │   ├── test_invitations.py
│   │   ├── test_member_removal.py
│   │   └── test_dashboard.py
│   └── seed.py                       # Seed data: 2+ agencies, mix of content
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       ├── auth/
│       ├── components/
│       ├── pages/
│       └── styles/
```

---

## 22. Explicitly Out-of-Scope Features

| Feature | Status |
|---|---|
| PostgreSQL Row Level Security | Not for this take-home (discuss in interview) |
| Token refresh / rotation | 30-min lifetime, no refresh tokens |
| Redis / token blacklist | Per-request DB check instead |
| S3 / cloud file storage | Local filesystem with auth endpoint |
| Docker Compose | Local venv + createdb for simplicity |
| WebSocket / real-time | Not required |
| Background workers (Celery) | Not required |
| Client intake forms | Bonus — skip unless core is complete |
| Automations & notifications | Bonus — skip unless core is complete |
| Timeline / Gantt view | Discuss only — no build |
| Full CRM | Not in scope |
| File versioning | New upload = new file record |
| Pagination cursors | Simple limit/offset is sufficient |
| OAuth / SSO | Email + password only |

---

## 23. Non-Negotiable Rules for Coding Agents

1. **Every DB query on tenant-owned data MUST include `WHERE agency_id = :agency_id`** sourced from JWT, never from request params.
2. **Never return 403 for cross-tenant access — always 404.** Information leakage is a security failure.
3. **Every list endpoint for `client_user` MUST filter by `AND visibility = 'client'`.** No exceptions.
4. **`agency_id` is denormalized onto every tenant-owned table.** Do not rely on join chains for isolation.
5. **All visibility fields default to `internal`.** Content must be explicitly promoted to `client`.
6. **All write endpoints extract `agency_id` from JWT and inject it.** Request body `agency_id` is ignored/overridden.
7. **Resource authorization helpers return the object or raise 404.** Every route handler uses them.
8. **Invitation acceptance uses `SELECT ... FOR UPDATE` within a transaction.**
9. **Invitation tokens are stored as SHA-256 hashes only.** Raw tokens are never persisted.
10. **Member removal is a single transaction.** Unassign tasks + delete membership atomically.
11. **Users are never hard-deleted.** Use `is_active = false` for deactivation.
12. **Active membership and user status are revalidated per-request** via a DB check, even with a valid JWT.
13. **Client comments are forced to `visibility = 'client'`.** A `client_user` cannot create internal comments.
14. **Task assignee validation checks agency membership, role, and project membership** at assignment time.
15. **Composite FKs enforce tenant consistency at the database level.** Application validation is defense-in-depth, not the primary mechanism.
16. **File downloads go through an authenticated endpoint.** No static file serving. No guessable URLs.
17. **The 28-test security matrix is mandatory.** It is not aspirational or optional.

---

## 24. Interview-Defensible Architecture Decisions

| Decision | Likely Question | Defense |
|---|---|---|
| No PostgreSQL RLS | "Why not RLS for defense in depth?" | Async connection pooling complicates session-variable-based RLS. Composite FKs + application-layer tenant scoping + 28-test suite provide strong isolation that is transparent and testable. In production, I would add RLS as a second layer. |
| Denormalized `agency_id` everywhere | "Isn't that redundant?" | Deliberate. Every query self-contains its tenant scope. A missing JOIN can never leak cross-tenant data. Cost: one UUID column (~16 bytes) per row. Benefit: structural safety. |
| Composite FKs | "Why not just application validation?" | Application bugs happen. A composite FK makes it structurally impossible to create cross-tenant references, regardless of code quality. The schema enforces what the code promises. |
| Single role per user per agency | "What if someone is both admin and client in the same agency?" | `UNIQUE(user_id, agency_id)` prevents it. The assignment defines three roles without requiring dual-role within one agency. If needed, remove the unique constraint and add `UNIQUE(user_id, agency_id, role)`. |
| JWT includes `agency_id` | "Why not a header-based tenant selector?" | Baking tenant into the token provides cryptographic integrity. A header is spoofable unless validated per-request, which is equivalent work without the guarantee. |
| Per-request membership check | "Isn't that slow?" | One indexed query per request. Catches deactivation immediately. Acceptable for a take-home. Production could add short-lived caching (seconds, not minutes). |
| Assignee FK to `users.id` not `project_memberships.id` | "Why not FK to membership for automatic unassignment?" | FK to membership auto-cascades but makes the API less natural (must resolve user → membership for assignment). Explicit transaction is 3 SQL statements and more debuggable. I can discuss the FK-to-membership alternative as a valid schema-first option. |
| `visibility` as VARCHAR + CHECK, not PostgreSQL ENUM | "Why not a proper ENUM type?" | PostgreSQL ENUMs cannot be altered inside a transaction (`ALTER TYPE ... ADD VALUE`). VARCHAR + CHECK is functionally identical at query time and easier to migrate. |
| All visibility defaults to `internal` | "Even comments?" | Especially comments. Accidentally hiding a comment from a client is recoverable. Accidentally exposing internal agency discussion is a security/privacy failure. Safe-by-default. |
| Invitation token hashing (SHA-256) | "Is that necessary for a take-home?" | Implementation cost is minimal (3 lines of code). A database leak of invitation tokens would allow anyone to accept pending invitations and gain access. Hashing prevents this. It's a small investment for a meaningful security improvement. |
| Soft-delete users + ON DELETE RESTRICT | "Why not just CASCADE?" | Time entries and comments are historical records. Destroying them on user deletion violates audit requirements. RESTRICT forces explicit handling. Soft-delete preserves referential integrity while removing access. |
| `client_memberships UNIQUE(user_id, agency_id)` | "What if a contact works with multiple clients?" | The assignment says clients see "their own projects." One client per user per agency is simpler, avoids "which client am I acting as?" complexity, and matches the assignment scope. If multi-client is needed later, remove the constraint. |
