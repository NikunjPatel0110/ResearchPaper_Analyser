#!/usr/bin/env python3
"""
CLI script to create the first admin user.
Usage: python scripts/create_admin.py
"""
import sys
import os
import getpass

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import Config  # noqa: E402 — must come after sys.path tweak
from backend.models.db import get_db  # noqa: E402
from backend.services.auth_service import create_admin_user  # noqa: E402


def main():
    print("=" * 50)
    print("  Paper IQ — Create Admin User")
    print("=" * 50)

    # Ensure DB is reachable
    try:
        get_db()
    except Exception as exc:
        print(f"[ERROR] Could not connect to MongoDB: {exc}")
        sys.exit(1)

    name = input("Full name: ").strip()
    if not name:
        print("[ERROR] Name cannot be empty.")
        sys.exit(1)

    email = input("Email: ").strip().lower()
    if not email or "@" not in email:
        print("[ERROR] Invalid email.")
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("[ERROR] Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("[ERROR] Passwords do not match.")
        sys.exit(1)

    print("\nCreating admin user…")
    success, message = create_admin_user(name=name, email=email, password=password)

    if success:
        print(f"\n✅ Admin user created successfully!")
        print(f"   Name:  {name}")
        print(f"   Email: {email}")
        print(f"   Role:  admin")
    else:
        print(f"\n❌ Failed: {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()