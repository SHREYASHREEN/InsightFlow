"""Create the database, demo users and fictional sample data.
Run from the project folder:   python scripts/seed_data.py          (add --reset to wipe sample data first)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from insightflow import db, seed  # noqa: E402


def main():
    conn = db.connect()
    db.init_db(conn)
    if "--reset" in sys.argv:
        seed.reset_demo(conn)
        print("Existing sample data removed.")
    seed.seed_users(conn)
    created = seed.seed_sample_data(conn)
    print("Sample data created." if created else "Sample data already present - nothing changed.")
    print("Demo logins: admin / Admin@12345, analyst / Analyst@12345, viewer / Viewer@12345")
    print("Change these passwords before using the app with any real information.")
    conn.close()


if __name__ == "__main__":
    main()
