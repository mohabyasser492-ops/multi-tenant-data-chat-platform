import asyncio

from sqlalchemy import select

from app.config import settings
from core.security import hash_password
from db.session import AsyncSessionFactory, engine
from models.role import Role, UserRole
from models.tenant import Tenant
from models.user import User


async def get_or_create_tenant() -> Tenant:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.code == settings.initial_tenant_code)
        )
        tenant = result.scalar_one_or_none()

        if tenant is not None:
            print(f"Tenant already exists: {tenant.code}")
            return tenant

        tenant = Tenant(
            name=settings.initial_tenant_name,
            code=settings.initial_tenant_code,
            status="active",
            settings={},
        )

        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        print(f"Tenant created: {tenant.code}")
        return tenant


async def get_or_create_admin_role(tenant: Tenant) -> Role:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Role).where(
                Role.tenant_id == tenant.id,
                Role.name == "Tenant Administrator",
            )
        )
        role = result.scalar_one_or_none()

        if role is not None:
            print(f"Role already exists: {role.name}")
            return role

        role = Role(
            tenant_id=tenant.id,
            name="Tenant Administrator",
            description=("Full administrative access within the active tenant."),
        )

        session.add(role)
        await session.commit()
        await session.refresh(role)

        print(f"Role created: {role.name}")
        return role


async def get_or_create_admin(
    tenant: Tenant,
) -> tuple[User, bool]:
    normalized_email = settings.initial_admin_email.lower().strip()

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == normalized_email,
            )
        )
        user = result.scalar_one_or_none()

        if user is not None:
            print(f"Administrator already exists: {user.email}")
            return user, False

        user = User(
            tenant_id=tenant.id,
            email=normalized_email,
            full_name=settings.initial_admin_full_name,
            password_hash=hash_password(settings.initial_admin_password),
            status="active",
            is_tenant_admin=True,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        print(f"Administrator created: {user.email}")
        return user, True


async def assign_admin_role(
    user: User,
    role: Role,
) -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        )
        assignment = result.scalar_one_or_none()

        if assignment is not None:
            print("Administrator role is already assigned.")
            return

        session.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
            )
        )
        await session.commit()

        print("Administrator role assigned.")


async def create_initial_administrator() -> None:
    print("Creating initial tenant administrator...")

    tenant = await get_or_create_tenant()
    role = await get_or_create_admin_role(tenant)
    user, created = await get_or_create_admin(tenant)

    await assign_admin_role(user, role)

    print()
    print("Bootstrap completed successfully.")
    print(f"Tenant: {tenant.name} ({tenant.code})")
    print(f"Administrator: {user.email}")
    print(f"New administrator created: {created}")


async def main() -> None:
    try:
        await create_initial_administrator()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
