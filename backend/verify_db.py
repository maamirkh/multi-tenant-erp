from sqlalchemy import create_engine, text

from core.config.settings import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
            """)
    )

    print("\n===== TABLES =====\n")

    for row in result:
        print(row[0])
