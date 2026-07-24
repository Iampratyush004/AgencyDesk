# AgencyDesk Testing Strategy

AgencyDesk includes 69 backend tests covering authentication, multi-tenancy, authorization, visibility, database integrity, concurrency, and lifecycle edge cases.

## Test Suite Summary

| Area | Tests |
| --- | ---: |
| Authentication & Multi-Agency Login | 14 |
| Comments | 4 |
| Authentication Dependencies & Revalidation | 9 |
| Files & Approvals | 5 |
| Invitations | 4 |
| Projects, Memberships & Dashboard | 21 |
| Tasks | 9 |
| Time Entries | 3 |
| Total | 69 |

## 1. Authentication and Multi-Agency Identity

The authentication suite verifies:

- Valid single-agency login
- Invalid email/password rejection
- Inactive user rejection
- Users with zero active memberships
- Multi-agency login requiring agency selection
- Only the user's own agencies appearing during selection
- Explicit agency selection and token issuance
- Foreign-agency selection rejection
- Inactive agency membership rejection
- Client users with and without required client membership
- Password behavior at and beyond the 72-byte boundary
- Multibyte UTF-8 password byte-limit behavior

## 2. Runtime Authentication Revalidation

Authentication is not trusted solely because a JWT was valid when originally issued.

Tests cover:

- Valid JWT context resolution
- Malformed JWT rejection
- Expired JWT rejection
- User deactivation after token issuance
- Agency-membership deactivation after token issuance
- Role changes after token issuance, using the current database role
- Client-membership removal after token issuance
- Allowed role dependencies
- Disallowed role dependencies

These tests verify that important authorization state is revalidated against current database state.

## 3. Project and Tenant Authorization

Project tests cover:

- Agency-admin access inside the same agency
- Cross-agency admin access protection
- Agency-member project access
- Client-user project access
- Project listing
- Project creation
- Unauthorized project creation
- Project updates
- Project memberships
- Deactivated project memberships

The backend is responsible for tenant and project authorization rather than relying on frontend filtering.

## 4. Project-Member Removal Edge Case

Removing an agency member from a project is explicitly tested.

Coverage includes:

- Access after project-member removal
- Tasks assigned to the removed member
- Existing time-entry history
- Atomic rollback when the operation fails

Task unassignment and membership removal are handled transactionally so the system does not retain invalid task assignments.

Historical time-entry data is preserved rather than deleting previously recorded work.

## 5. Client Visibility and Dashboard Isolation

Dashboard tests cover:

- Client-user dashboard behavior
- Cross-client dashboard access
- Cross-tenant dashboard access
- Staff dashboard aggregation
- Staff projects with zero logged time
- Unassigned agency-member dashboard access

For staff, dashboard task counts include the data authorized for agency staff.

For clients, dashboard task aggregation is restricted to client-visible tasks by the backend.

Staff responses can contain project time totals, while the client dashboard response omits the time field.

## 6. Task Authorization

Task tests cover:

- Task authorization
- Task search
- Task creation
- Task assignment
- Task updates
- Visibility invariants
- Authentication revalidation
- Project-membership correction
- Schema-level security

Internal content protection is enforced by backend authorization and query logic rather than frontend filtering.

## 7. Comments

Comment tests cover:

- Comment listing
- Comment creation
- Authentication revalidation
- Schema-level security

Comment access follows backend task authorization and visibility rules.

## 8. Files and Client Approval

File tests cover:

- File listing
- File upload
- Upload cleanup
- Authenticated file download
- Client file approvals

Agency staff can upload authorized files, while clients can access client-visible files and perform the client approval workflow.

Internal files remain protected by backend authorization.

## 9. Time Tracking

Time-entry tests cover:

- Time-entry listing
- Time-entry creation
- Structural preservation of historical entries

Historical time entries are preserved when project membership changes.

## 10. Invitation Safety and Concurrency

Invitation tests cover:

- Invitation sending and resending
- Idempotent invitation acceptance
- Concurrent invitation operations
- Invitation validation

These tests verify that invitation operations remain consistent when requests are repeated or occur concurrently.

## 11. Schema-Level Security

Schema-level security tests exist for projects, tasks, and comments.

These tests complement application-level authorization by validating database-level tenant relationship constraints.

Composite tenant relationships include agency context, reducing the possibility of associating resources belonging to different agencies.

## 12. Security Principles Covered

Across the suite, the main security and correctness properties being tested are:

- Tenant isolation between agencies
- Project-level authorization
- Client-to-client isolation
- Internal versus client-visible content isolation
- Role-based access control
- Multi-agency identity selection
- Runtime authorization revalidation
- Database-level tenant integrity
- Safe membership removal
- Historical data preservation
- Invitation idempotency and concurrency safety

The frontend is not treated as a security boundary. Authorization, tenant isolation, membership checks, client association, and visibility restrictions are enforced by the backend.

## Running the Test Suite

Tests must run against the isolated agencydesk_test PostgreSQL database.

From the backend directory:

    DATABASE_URL="postgresql+asyncpg://YOUR_POSTGRES_USER@localhost:5432/agencydesk_test" pytest -q

Validated result:

    69 passed

The test configuration contains a safety guard that refuses to run the suite against the normal development database.
