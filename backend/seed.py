import asyncio
import os
from datetime import date, timedelta
from sqlalchemy import select
from app.database import async_session_maker
from app.config import settings
from app.core.security import get_password_hash

from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.comment import Comment
from app.models.time_entry import TimeEntry
from app.models.file import File, FileApproval
from app.models.enums import (
    RoleEnum, ProjectStatusEnum, TaskStatusEnum,
    TaskPriorityEnum, VisibilityEnum, FileApprovalStatusEnum
)

async def seed():
    # 1. Safety Guard
    if settings.DATABASE_URL.endswith("agencydesk_test"):
        print("Safety Guard: Cannot run seed against the test database.")
        return

    print(f"Targeting database: {settings.DATABASE_URL.split('@')[-1]}")

    async with async_session_maker() as session:
        # Check if already seeded
        result = await session.execute(
            select(Agency).where(Agency.slug == "northstar-creative")
        )
        if result.scalar_one_or_none() is not None:
            print("AgencyDesk demo data appears to be already seeded. Exiting successfully.")
            return

        try:
            # Hash password
            password_hash = get_password_hash("Password123!")

            # --- AGENCIES ---
            northstar = Agency(name="Northstar Creative", slug="northstar-creative")
            pixelforge = Agency(name="PixelForge Studio", slug="pixelforge-studio")
            session.add_all([northstar, pixelforge])
            await session.flush()

            # --- USERS ---
            maya = User(email="admin@northstar.demo", full_name="Maya Chen", password_hash=password_hash)
            alex = User(email="alex@agencydesk.demo", full_name="Alex Morgan", password_hash=password_hash)
            olivia = User(email="client@acme.demo", full_name="Olivia Carter", password_hash=password_hash)
            jordan = User(email="member@pixelforge.demo", full_name="Jordan Lee", password_hash=password_hash)
            ethan = User(email="client@orbit.demo", full_name="Ethan Brooks", password_hash=password_hash)
            session.add_all([maya, alex, olivia, jordan, ethan])
            await session.flush()

            # --- AGENCY MEMBERSHIPS ---
            session.add_all([
                AgencyMembership(user_id=maya.id, agency_id=northstar.id, role=RoleEnum.agency_admin.value),
                AgencyMembership(user_id=alex.id, agency_id=northstar.id, role=RoleEnum.agency_member.value),
                AgencyMembership(user_id=olivia.id, agency_id=northstar.id, role=RoleEnum.client_user.value),
                AgencyMembership(user_id=alex.id, agency_id=pixelforge.id, role=RoleEnum.agency_admin.value),
                AgencyMembership(user_id=jordan.id, agency_id=pixelforge.id, role=RoleEnum.agency_member.value),
                AgencyMembership(user_id=ethan.id, agency_id=pixelforge.id, role=RoleEnum.client_user.value),
            ])
            await session.flush()

            # --- CLIENTS ---
            acme = Client(agency_id=northstar.id, name="Acme Retail")
            bluebird = Client(agency_id=northstar.id, name="Bluebird Health")
            orbit = Client(agency_id=pixelforge.id, name="Orbit Labs")
            session.add_all([acme, bluebird, orbit])
            await session.flush()

            # --- CLIENT MEMBERSHIPS ---
            session.add_all([
                ClientMembership(user_id=olivia.id, agency_id=northstar.id, client_id=acme.id),
                ClientMembership(user_id=ethan.id, agency_id=pixelforge.id, client_id=orbit.id),
            ])
            await session.flush()

            # --- PROJECTS ---
            acme_web = Project(
                agency_id=northstar.id, client_id=acme.id,
                name="Acme Website Redesign",
                description="Redesign and launch Acme Retail's customer-facing website.",
                status=ProjectStatusEnum.active.value
            )
            holiday = Project(
                agency_id=northstar.id, client_id=acme.id,
                name="Holiday Campaign",
                description="Creative campaign for Acme Retail's holiday launch.",
                status=ProjectStatusEnum.active.value
            )
            patient_portal = Project(
                agency_id=northstar.id, client_id=bluebird.id,
                name="Patient Portal Launch",
                description="Launch campaign and digital assets for the new patient portal.",
                status=ProjectStatusEnum.active.value
            )
            orbit_launch = Project(
                agency_id=pixelforge.id, client_id=orbit.id,
                name="Orbit Product Launch",
                description="Product launch campaign for Orbit Labs.",
                status=ProjectStatusEnum.active.value
            )
            session.add_all([acme_web, holiday, patient_portal, orbit_launch])
            await session.flush()

            # --- PROJECT MEMBERSHIPS ---
            session.add_all([
                ProjectMembership(user_id=alex.id, agency_id=northstar.id, project_id=acme_web.id),
                ProjectMembership(user_id=alex.id, agency_id=northstar.id, project_id=holiday.id),
                ProjectMembership(user_id=jordan.id, agency_id=pixelforge.id, project_id=orbit_launch.id),
            ])
            await session.flush()

            # --- TASKS ---
            # Acme Website Redesign
            t_home_wire = Task(
                agency_id=northstar.id, project_id=acme_web.id, assignee_id=alex.id,
                title="Homepage wireframes", description="Prepare the first client-facing homepage wireframe.",
                status=TaskStatusEnum.done.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.client.value
            )
            t_home_design = Task(
                agency_id=northstar.id, project_id=acme_web.id, assignee_id=alex.id,
                title="Finalize homepage design", description="Prepare the polished homepage design for client review.",
                status=TaskStatusEnum.review.value, priority=TaskPriorityEnum.urgent.value, visibility=VisibilityEnum.client.value
            )
            t_mobile = Task(
                agency_id=northstar.id, project_id=acme_web.id, assignee_id=alex.id,
                title="Mobile responsive pass", description="Verify responsive behavior across target breakpoints.",
                status=TaskStatusEnum.in_progress.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.client.value
            )
            t_pricing = Task(
                agency_id=northstar.id, project_id=acme_web.id, assignee_id=alex.id,
                title="Internal pricing discussion", description="Review scope implications before discussing additional work with the client.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.internal.value
            )
            t_qa = Task(
                agency_id=northstar.id, project_id=acme_web.id, assignee_id=alex.id,
                title="QA launch checklist", description="Complete the pre-launch quality assurance checklist.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.internal.value
            )

            # Holiday Campaign
            t_hol_copy = Task(
                agency_id=northstar.id, project_id=holiday.id, assignee_id=alex.id,
                title="Draft ad copy", description="Initial draft for social media ad copy.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.client.value
            )
            t_hol_assets = Task(
                agency_id=northstar.id, project_id=holiday.id, assignee_id=alex.id,
                title="Design creative assets", description="Hero images and banners.",
                status=TaskStatusEnum.in_progress.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.client.value
            )
            t_hol_strategy = Task(
                agency_id=northstar.id, project_id=holiday.id, assignee_id=alex.id,
                title="Review media spend strategy", description="Internal sync on budget allocation.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.internal.value
            )

            # Patient Portal Launch (unassigned tasks)
            t_portal_1 = Task(
                agency_id=northstar.id, project_id=patient_portal.id,
                title="Welcome email template", description="Design template for welcome email.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.client.value
            )
            t_portal_2 = Task(
                agency_id=northstar.id, project_id=patient_portal.id,
                title="Compliance check", description="Internal HIPAA compliance review.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.internal.value
            )

            # Orbit Product Launch (PixelForge)
            t_orbit_1 = Task(
                agency_id=pixelforge.id, project_id=orbit_launch.id, assignee_id=jordan.id,
                title="Press release draft", description="Draft PR announcement.",
                status=TaskStatusEnum.done.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.client.value
            )
            t_orbit_2 = Task(
                agency_id=pixelforge.id, project_id=orbit_launch.id, assignee_id=jordan.id,
                title="Landing page structure", description="Wireframe the landing page.",
                status=TaskStatusEnum.review.value, priority=TaskPriorityEnum.medium.value, visibility=VisibilityEnum.client.value
            )
            t_orbit_3 = Task(
                agency_id=pixelforge.id, project_id=orbit_launch.id, assignee_id=jordan.id,
                title="Update target personas", description="Internal target audience update.",
                status=TaskStatusEnum.in_progress.value, priority=TaskPriorityEnum.low.value, visibility=VisibilityEnum.internal.value
            )
            t_orbit_4 = Task(
                agency_id=pixelforge.id, project_id=orbit_launch.id, assignee_id=jordan.id,
                title="Client onboarding packet", description="Prepare the onboarding presentation.",
                status=TaskStatusEnum.todo.value, priority=TaskPriorityEnum.high.value, visibility=VisibilityEnum.client.value
            )

            session.add_all([
                t_home_wire, t_home_design, t_mobile, t_pricing, t_qa,
                t_hol_copy, t_hol_assets, t_hol_strategy,
                t_portal_1, t_portal_2,
                t_orbit_1, t_orbit_2, t_orbit_3, t_orbit_4
            ])
            await session.flush()

            # --- COMMENTS ---
            session.add_all([
                Comment(
                    agency_id=northstar.id, task_id=t_home_design.id, author_id=alex.id,
                    content="Need final design lead review before presenting this direction.",
                    visibility=VisibilityEnum.internal.value
                ),
                Comment(
                    agency_id=northstar.id, task_id=t_home_design.id, author_id=alex.id,
                    content="Updated the hero section based on the latest feedback.",
                    visibility=VisibilityEnum.client.value
                ),
                Comment(
                    agency_id=northstar.id, task_id=t_home_design.id, author_id=olivia.id,
                    content="The updated hero looks good. Please keep the CTA above the fold.",
                    visibility=VisibilityEnum.client.value
                ),
                Comment(
                    agency_id=northstar.id, task_id=t_hol_assets.id, author_id=alex.id,
                    content="Drafting the assets now.",
                    visibility=VisibilityEnum.client.value
                ),
                Comment(
                    agency_id=pixelforge.id, task_id=t_orbit_2.id, author_id=jordan.id,
                    content="I think we should use a simpler structure.",
                    visibility=VisibilityEnum.internal.value
                )
            ])
            await session.flush()

            # --- TIME ENTRIES ---
            today = date.today()
            session.add_all([
                TimeEntry(agency_id=northstar.id, project_id=acme_web.id, task_id=t_home_wire.id, user_id=alex.id, duration_minutes=120, date=today - timedelta(days=2), note="Initial wireframes and content hierarchy"),
                TimeEntry(agency_id=northstar.id, project_id=acme_web.id, task_id=t_home_design.id, user_id=alex.id, duration_minutes=180, date=today - timedelta(days=1), note="Homepage visual design iteration"),
                TimeEntry(agency_id=northstar.id, project_id=acme_web.id, task_id=t_mobile.id, user_id=alex.id, duration_minutes=90, date=today, note="Responsive layout implementation"),
                TimeEntry(agency_id=northstar.id, project_id=acme_web.id, task_id=t_pricing.id, user_id=alex.id, duration_minutes=30, date=today, note="Scope review"),
                TimeEntry(agency_id=pixelforge.id, project_id=orbit_launch.id, task_id=t_orbit_1.id, user_id=jordan.id, duration_minutes=60, date=today, note="PR draft outline")
            ])
            await session.flush()

            # --- FILES ---
            upload_dir = settings.FILE_STORAGE_ROOT
            os.makedirs(upload_dir, exist_ok=True)

            f1_path = os.path.join(upload_dir, "homepage-v2.txt")
            with open(f1_path, "w") as f:
                f.write("AgencyDesk demo file: Acme homepage design v2")

            f2_path = os.path.join(upload_dir, "internal-design-notes.txt")
            with open(f2_path, "w") as f:
                f.write("AgencyDesk internal demo file: design review notes")

            f3_path = os.path.join(upload_dir, "orbit-pr.txt")
            with open(f3_path, "w") as f:
                f.write("Orbit Product Launch PR Draft")

            f1 = File(
                agency_id=northstar.id, task_id=t_home_design.id, uploaded_by_id=alex.id,
                filename="homepage-v2.txt", storage_path=f1_path, mime_type="text/plain",
                file_size_bytes=os.path.getsize(f1_path), visibility=VisibilityEnum.client.value
            )
            f2 = File(
                agency_id=northstar.id, task_id=t_home_design.id, uploaded_by_id=alex.id,
                filename="internal-design-notes.txt", storage_path=f2_path, mime_type="text/plain",
                file_size_bytes=os.path.getsize(f2_path), visibility=VisibilityEnum.internal.value
            )
            f3 = File(
                agency_id=pixelforge.id, task_id=t_orbit_3.id, uploaded_by_id=jordan.id,
                filename="orbit-pr.txt", storage_path=f3_path, mime_type="text/plain",
                file_size_bytes=os.path.getsize(f3_path), visibility=VisibilityEnum.internal.value
            )
            session.add_all([f1, f2, f3])
            await session.flush()

            # --- FILE APPROVAL ---
            appr1 = FileApproval(
                agency_id=northstar.id, file_id=f1.id, reviewer_id=olivia.id,
                status=FileApprovalStatusEnum.approved.value, note="Approved for implementation."
            )
            session.add(appr1)

            # Commit all
            await session.commit()

            print("\nAgencyDesk demo data seeded successfully.")
            print("\nAgencies:")
            print("- Northstar Creative")
            print("- PixelForge Studio")

            print("\nDemo logins:")
            print("- admin@northstar.demo / Password123!")
            print("- alex@agencydesk.demo / Password123!")
            print("- client@acme.demo / Password123!")
            print("- member@pixelforge.demo / Password123!")
            print("- client@orbit.demo / Password123!")

            print("\nMulti-agency demo:")
            print("- alex@agencydesk.demo")
            print("  Northstar Creative -> agency_member")
            print("  PixelForge Studio -> agency_admin")

            # Record counts
            result = await session.execute(select(User))
            print(f"\nRecord counts:")
            print(f"users: {len(result.scalars().all())}")

            for model_cls, name in [
                (Agency, "agencies"),
                (AgencyMembership, "agency_memberships"),
                (Client, "clients"),
                (ClientMembership, "client_memberships"),
                (Project, "projects"),
                (ProjectMembership, "project_memberships"),
                (Task, "tasks"),
                (Comment, "comments"),
                (TimeEntry, "time_entries"),
                (File, "files"),
                (FileApproval, "file_approvals"),
            ]:
                result = await session.execute(select(model_cls))
                print(f"{name}: {len(result.scalars().all())}")

        except Exception as e:
            await session.rollback()
            print(f"Seeding failed: {e}")
            raise e

if __name__ == "__main__":
    asyncio.run(seed())
