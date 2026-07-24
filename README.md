# AgencyDesk

AgencyDesk is a multi-tenant client and project management platform built for agency-client workflows. One deployment supports multiple isolated agencies, with role-based access for agency administrators, agency members, and client users.

This project was built for the Sapyon take-home assignment using React, Python/FastAPI, and PostgreSQL, with an emphasis on tenant isolation, authorization correctness, schema design, and explicit handling of access-control edge cases.

## Features

- Multi-tenant agency isolation
- Multi-agency user identities and agency selection at login
- Role-based access control: `agency_admin`, `agency_member`, and `client_user`
- Project and task boards
- Internal and client-visible tasks
- Task creation and editing for agency staff
- Task comments with visibility controls
- Time tracking against tasks
- Per-project task counts and hours reporting
- File upload and authenticated download
- Client file approval / needs-changes workflow
- Invitation handling
- Safe project-member removal
- Seed data covering multiple agencies and roles
- Automated authorization and tenant-isolation tests

## Tech Stack

### Frontend

- React 19
- Vite
- React Router
- JavaScript
- jwt-decode

### Backend

- Python
- FastAPI
- SQLAlchemy 2 async ORM
- PostgreSQL
- asyncpg
- Alembic
- Pydantic
- PyJWT

### Testing

- pytest
- pytest-asyncio
- HTTPX

## Prerequisites

Before running AgencyDesk locally, make sure you have:

- Python 3
- PostgreSQL
- Node.js
- npm

PostgreSQL must be running before starting the backend.

## Quick Start

The project is designed to be set up locally in under 10 minutes.

### 1. Clone the repository

```bash
git clone <repository-url>
cd AgencyDesk
```

### 2. Create the PostgreSQL databases

Create the development database:

```bash
createdb agencydesk
```

Create the isolated test database:

```bash
createdb agencydesk_test
```

If either database already exists, skip the corresponding command.

### 3. Set up the backend

From the repository root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Create the local backend environment file:

```bash
cp backend/.env.example backend/.env
```

Update `backend/.env` with your local PostgreSQL username and a secure development secret.

Example:

```env
DATABASE_URL=postgresql+asyncpg://YOUR_POSTGRES_USER@localhost:5432/agencydesk
SECRET_KEY=replace-with-a-long-random-development-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4. Run database migrations

Move into the backend directory and apply the Alembic migrations:

```bash
cd backend
alembic upgrade head
```

### 5. Seed demo data

While still inside `backend/`, run:

```bash
python seed.py
```

The seed script creates two agencies, multiple user roles, projects, internal and client-visible tasks, comments, time entries, files, approvals, and a user who belongs to two agencies.

### 6. Start the backend

From `backend/`, run:

```bash
uvicorn app.main:app --reload
```

The API will run on `http://localhost:8000`.

You can verify it using the health endpoint:

```text
GET /health
```

### 7. Start the frontend

Open a second terminal from the repository root:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The Vite development server normally runs on `http://localhost:5173`.

During development, Vite proxies `/api` requests to the FastAPI backend running on port `8000`.

## Demo Accounts

All seeded demo accounts use the password:

```text
Password123!
```

| Email | Agency | Role |
| --- | --- | --- |
| `admin@northstar.demo` | Northstar Creative | `agency_admin` |
| `alex@agencydesk.demo` | Northstar Creative | `agency_member` |
| `alex@agencydesk.demo` | PixelForge Studio | `agency_admin` |
| `client@acme.demo` | Northstar Creative | `client_user` |
| `member@pixelforge.demo` | PixelForge Studio | `agency_member` |
| `client@orbit.demo` | PixelForge Studio | `client_user` |

The `alex@agencydesk.demo` account demonstrates the multi-agency identity model. Alex has one global user identity but belongs to two agencies with different roles. After entering the credentials, the login flow asks which agency context to use before authentication is completed.

## Running Backend Tests

The test suite uses a dedicated `agencydesk_test` database and includes a safety guard to prevent tests from accidentally running against the development database.

From `backend/`, run:

```bash
DATABASE_URL="postgresql+asyncpg://YOUR_POSTGRES_USER@localhost:5432/agencydesk_test" pytest -q
```

Current validated result:

```text
69 passed
```

The test suite covers tenant isolation, client visibility, role-based access, multi-agency authentication, invitation handling, member removal, tasks, comments, files, time entries, and project dashboard authorization.

## Frontend Validation

From `frontend/`, run:

```bash
npm run build
npm run lint
```

The production build completes successfully. The current lint result contains warnings only and no errors.

## Architecture and Security

AgencyDesk uses a shared-database, shared-schema multi-tenant architecture. Tenant-owned records carry an `agency_id`, and backend authorization derives the active tenant from the authenticated JWT and revalidates the user's agency membership.

Tenant isolation is enforced at multiple layers:

- API queries are scoped to the authenticated agency.
- Composite foreign keys include `agency_id` across tenant-owned relationships.
- Agency members can access only projects to which they are assigned.
- Client users are restricted to their own client and client-visible content.
- Internal tasks, comments, and files are filtered server-side and are never exposed based on frontend filtering.
- Unauthorized and cross-tenant resource lookups return `404` to avoid leaking resource existence.

User identity is global while roles are tenant-specific through `agency_memberships`, allowing the same user to belong to multiple agencies with different roles.

For the detailed schema and access-control decisions, see `DESIGN.md`.

## Testing Documentation

For a detailed breakdown of the testing strategy, authorization scenarios, tenant-isolation cases, and edge cases covered by the backend suite, see `TESTING.md`.

The exact inventory of all 69 backend tests is available in `TEST_INVENTORY.txt`.
