# AgencyDesk — Agent Engineering Instructions

## Project

AgencyDesk is a multi-tenant client and project management platform for agencies.

One deployment serves multiple agencies. Data belonging to one agency must never be accessible by another agency.

This repository is being built as a take-home engineering assignment. Prioritize correctness, maintainability, clear architecture, security, and demonstrable functionality over unnecessary complexity.

## Required Stack

Frontend:
- React
- JavaScript/TypeScript only where appropriate
- Modern functional components and hooks
- Vite unless assignment requirements dictate otherwise

Backend:
- Python
- REST API
- Use a lightweight, production-appropriate Python web framework

Database:
- PostgreSQL
- Use migrations
- Do not substitute SQLite for PostgreSQL in the final implementation

## Repository Structure

Prefer a monorepo structure:

AgencyDesk/
  frontend/
  backend/
  README.md
  .gitignore
  .env.example

Keep frontend and backend responsibilities clearly separated.

## Multi-Tenancy — Critical Requirement

AgencyDesk is multi-tenant.

Every tenant-owned entity must be scoped to an agency/tenant.

Never implement database queries that can accidentally return another agency's records.

Tenant isolation must be enforced by the backend, not merely by frontend filtering.

Do not trust tenant IDs supplied arbitrarily by the client.

Authorization and tenant ownership checks must happen server-side.

When creating database models, relationships, API endpoints, services, or queries, explicitly consider tenant isolation.

## Backend Architecture

Keep backend code modular.

Prefer separation between:
- API/routes
- database models
- schemas/validation
- business/service logic
- authentication/authorization
- database configuration

Avoid putting all backend logic into a single file.

Use environment variables for configuration and secrets.

Never hardcode credentials.

## Frontend Architecture

Use reusable components.

Keep:
- pages
- components
- API/client logic
- authentication state
- shared utilities

reasonably separated.

Do not over-engineer global state management unless the application actually requires it.

The UI should be responsive, professional, and appropriate for a SaaS dashboard.

## Database

Use PostgreSQL-compatible models and migrations.

Use proper:
- primary keys
- foreign keys
- uniqueness constraints
- indexes where justified
- timestamps

Design relationships deliberately.

Do not create duplicate or redundant tenant relationships without justification.

## Security

Never expose secrets to the frontend.

Never commit `.env` files.

Validate incoming API data.

Authentication is not sufficient by itself: authorization and tenant ownership must also be checked.

Do not weaken tenant isolation for implementation convenience.

## Code Quality

Write readable, maintainable code.

Prefer simple implementations over unnecessary abstractions.

Avoid:
- giant files
- duplicated business logic
- dead code
- placeholder implementations presented as complete
- unnecessary dependencies

Add comments only where they explain non-obvious decisions.

## Agent Working Rules

Before implementing a substantial feature:

1. Inspect the existing repository.
2. Understand the current architecture.
3. Identify how the change affects tenant isolation.
4. Make the smallest coherent implementation.
5. Run relevant validation/tests after changes.

Do not rewrite unrelated working code.

Do not change the required technology stack without explicit user approval.

Do not install major dependencies solely for convenience without explaining why they are needed.

Do not delete files, reset Git history, force push, or perform destructive Git operations.

Do not modify files outside this repository.

## Terminal / Environment

The project uses a local Python virtual environment at:

`.venv/`

Do not commit this directory.

When Python commands are required, prefer the project's virtual environment.

Do not modify system Python or global shell configuration.

Do not install Python packages globally.

Node dependencies must remain project-local.

## Git

Make changes in logical units.

Do not automatically commit changes unless explicitly requested.

Never push to a remote repository unless explicitly requested.

## Testing

Important backend behavior should be testable.

Tenant isolation should receive explicit tests.

When fixing a bug, prefer adding a regression test when practical.

Before claiming a feature is complete, run the relevant tests/build/lint checks and report failures accurately.

## Implementation Discipline

Do not attempt to build the entire assignment in one uncontrolled pass.

Implement the system incrementally.

When requirements are ambiguous, preserve the simplest architecture that satisfies the assignment rather than inventing unnecessary product requirements.

Never claim something works unless it has actually been implemented and, where practical, verified.