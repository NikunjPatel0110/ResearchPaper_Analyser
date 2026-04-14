#!/usr/bin/env python3
"""
Seed script: creates 1 admin user + 3 invite codes and prints them.
Usage: python scripts/seed_demo.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.db import get_db  # noqa: E402
from backend.services.auth_service import create_admin_user, create_invite  # noqa: E402

ADMIN = {
    "name": "Demo Admin",
    "email": "admin@paperiq.local",
    "password": "Admin1234!",
}


def main():
    print("=" * 50)
    print("  Paper IQ — Seed Demo Data")
    print("=" * 50)

    try:
        get_db()
    except Exception as exc:
        print(f"[ERROR] Cannot connect to MongoDB: {exc}")
        sys.exit(1)

    # Create admin
    print(f"\n→ Creating admin: {ADMIN['email']}")
    success, message = create_admin_user(**ADMIN)
    if success:
        print("  ✅ Admin created.")
    else:
        if "already registered" in message.lower():
            print("  ℹ️  Admin already exists, skipping.")
        else:
            print(f"  ❌ {message}")

    # Get admin user_id for invite creation
    from backend.models.db import users, invites as invites_col
    admin_doc = users().find_one({"email": ADMIN["email"].lower()})
    if not admin_doc:
        print("\n❌ Could not find admin user to generate invites.")
        sys.exit(1)
    admin_id = str(admin_doc["_id"])

    # Generate invite codes
    print("\n→ Generating 3 invite codes…\n")
    codes = []
    notes = ["Beta tester 1", "Beta tester 2", "Beta tester 3"]
    for note in notes:
        res, _ = create_invite(admin_user_id=admin_id, note=note)
        if res.get("success"):
            code = res["data"]["invite_code"]
            codes.append(code)
            print(f"  🎫  {code}  ({note})")
        else:
            print(f"  ❌  Failed to generate code: {res.get('error')}")

    print("\n" + "=" * 50)
    print("  Seed complete!")
    print(f"\n  Admin email:    {ADMIN['email']}")
    print(f"  Admin password: {ADMIN['password']}")
    print("\n  Invite codes:")
    for c in codes:
        print(f"    • {c}")
    print("=" * 50)


if __name__ == "__main__":
    main()