# AgencyDesk — Design Notes

## Tenant Isolation

AgencyDesk uses a shared-database, shared-schema multi-tenant model where every tenant-owned record carries an `agency_id`. The active agency is derived from the authenticated JWT and revalidated against the user's active agency membership on each request; tenant IDs supplied by clients are never trusted for authorization.

Isolation is also enforced at the database level. Tenant relationships use composite foreign keys such as `(project_id, agency_id)` and `(task_id, agency_id)`, backed by corresponding composite unique constraints. This prevents records from being associated across agencies even if application code contains a bug. API queries additionally scope tenant-owned data by the authenticated `agency_id`, providing application-level defense in depth. Unauthorized and cross-tenant resource lookups return 404 rather than revealing that another tenant's resource exists.

## Client Visibility

Tasks, comments, and files have an explicit `visibility` field with a safe default of `internal`. Client users are restricted to their associated client through `client_memberships`, and backend queries for client users explicitly filter content to `visibility = 'client'`.

Visibility is enforced on every relevant access path rather than relying on frontend filtering. Clients cannot create or modify tasks, cannot log time, and cannot upload files. Client comments are forced to client-visible server-side even if a malicious request submits `internal`. Client-visible comments or files also cannot be attached to an internal task, preventing child content from accidentally exposing an internal resource.

## Identity Across Multiple Agencies

A user has one global identity in the `users` table, keyed independently of any agency. Roles and tenant access belong to `agency_memberships`, not to the user itself. This allows the same email address to participate in multiple agencies with a different role in each.

If a user belongs to more than one active agency, login does not arbitrarily choose a tenant. The API returns the available agency memberships and requires the user to select one. A new JWT is then issued containing that agency context and role. The seeded `alex@agencydesk.demo` account demonstrates this by acting as an `agency_member` in Northstar Creative and an `agency_admin` in PixelForge Studio while retaining one global user identity.

## Edge Case: Safe Project-Member Removal

The edge case I focused on is removing an agency member from a project while tasks are still assigned to them. Leaving those assignments intact would create stale authorization and ownership state.

Member removal therefore performs task unassignment and project-membership deletion atomically in one database transaction. Tasks assigned to the removed member are set to unassigned before the membership is deleted. If any part of the operation fails, the transaction rolls back instead of leaving partially updated state. This behavior is covered by the backend test suite along with tenant isolation, client visibility, invitation races, and authorization rules.
