"""Database engine and session management."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


async def get_db():
    """Dependency that yields a database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables and default data."""
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_legacy_migrations(conn)

    from app.core.security import get_or_create_admin
    from app.models import Setting

    async with async_session_maker() as session:
        await get_or_create_admin(session)

        result = await session.execute(select(Setting).limit(1))
        if result.scalar_one_or_none() is None:
            cfg = get_settings()
            session.add(Setting(key="contact_email", value=cfg.contact_email))
            session.add(Setting(key="email", value=cfg.contact_email))
            session.add(Setting(key="intro_text", value=""))
            session.add(Setting(key="instagram", value=""))
            session.add(Setting(key="tiktok", value=""))
            await session.commit()


async def _run_legacy_migrations(conn):
    """Run migration SQL for legacy schema compatibility."""
    migrations = [
        ("ALTER TABLE events ADD COLUMN date_end DATETIME", "date_end"),
        (
            "ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES product_categories(id)",
            "category_id",
        ),
        ("ALTER TABLE products ADD COLUMN available BOOLEAN DEFAULT 1", "available"),
        ("ALTER TABLE products ADD COLUMN display BOOLEAN DEFAULT 1", "display"),
        ("ALTER TABLE events ADD COLUMN display BOOLEAN DEFAULT 1", "events.display"),
        ("ALTER TABLE products ADD COLUMN stripe_product_id VARCHAR(255)", "stripe_product_id"),
        ("ALTER TABLE products ADD COLUMN stripe_price_id VARCHAR(255)", "stripe_price_id"),
        ("ALTER TABLE products ADD COLUMN stock_quantity INTEGER", "stock_quantity"),
        ("ALTER TABLE orders ADD COLUMN customer_first_name VARCHAR(120)", "orders.first_name"),
        ("ALTER TABLE orders ADD COLUMN customer_last_name VARCHAR(120)", "orders.last_name"),
        ("ALTER TABLE orders ADD COLUMN shipping_address VARCHAR(500)", "orders.address"),
        ("ALTER TABLE orders ADD COLUMN shipping_postal_code VARCHAR(20)", "orders.postal"),
        ("ALTER TABLE orders ADD COLUMN shipping_city VARCHAR(120)", "orders.city"),
        ("ALTER TABLE orders ADD COLUMN shipping_country VARCHAR(80)", "orders.country"),
        ("ALTER TABLE orders ADD COLUMN subtotal FLOAT DEFAULT 0", "orders.subtotal"),
        ("ALTER TABLE orders ADD COLUMN shipping_fee FLOAT DEFAULT 0", "orders.shipping_fee"),
    ]
    for sql, _ in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass

    try:
        await conn.execute(
            text("ALTER TABLE events ADD COLUMN event_type_id INTEGER REFERENCES event_types(id)")
        )
    except Exception:
        pass

    try:
        result = await conn.execute(
            text(
                "SELECT id, event_type FROM events WHERE event_type_id IS NULL AND event_type IS NOT NULL"
            )
        )
        for eid, type_name in result.fetchall():
            if type_name:
                await conn.execute(
                    text("INSERT OR IGNORE INTO event_types (name) VALUES (:n)"),
                    {"n": str(type_name).strip()},
                )
                r = await conn.execute(
                    text("SELECT id FROM event_types WHERE name = :n"),
                    {"n": str(type_name).strip()},
                )
                row = r.fetchone()
                if row:
                    await conn.execute(
                        text("UPDATE events SET event_type_id = :tid WHERE id = :eid"),
                        {"tid": row[0], "eid": eid},
                    )
    except Exception:
        pass
