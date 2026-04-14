import streamlit as st
import requests
import pandas as pd

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Admin — Paper IQ", page_icon="🛡️", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in first.")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("🛡️ Access denied. Admin only.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


st.title("🛡️ Admin Panel")

# ── Generate Invite Code ──────────────────────────────────────────────────────
st.subheader("Generate Invite Code")
with st.form("gen_invite"):
    note = st.text_input("Note (optional)", placeholder="e.g. For PhD student cohort")
    submitted = st.form_submit_button("Generate", use_container_width=True)
    if submitted:
        try:
            r = requests.post(
                f"{API_BASE}/auth/invite",
                json={"note": note},
                headers=auth_headers(),
                timeout=10,
            )
            data = r.json()
        except Exception:
            st.error("Failed to generate invite code.")
            data = {}
        if data.get("success"):
            code = data["data"].get("invite_code", "—")
            st.success(f"✅ Invite code: **`{code}`**")
        elif data:
            st.error(data.get("error", "Failed."))

st.divider()

# ── Users Table ───────────────────────────────────────────────────────────────
st.subheader("All Users")
try:
    r = requests.get(f"{API_BASE}/auth/users", headers=auth_headers(), timeout=10)
    users_data = r.json()
except Exception:
    users_data = {"success": False}

if users_data.get("success"):
    users = users_data["data"]
    if users:
        udf = pd.DataFrame(users)
        display_cols = [c for c in ["name", "email", "role", "created_at"] if c in udf.columns]
        st.dataframe(udf[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No users yet.")
else:
    st.warning("Could not load users.")

st.divider()

# ── Invite Codes Table ────────────────────────────────────────────────────────
st.subheader("All Invite Codes")
try:
    r = requests.get(f"{API_BASE}/auth/invites", headers=auth_headers(), timeout=10)
    invites_data = r.json()
except Exception:
    invites_data = {"success": False}

if invites_data.get("success"):
    invites = invites_data["data"]
    if invites:
        idf = pd.DataFrame(invites)
        display_cols = [c for c in ["code", "used", "used_by", "note", "created_at"] if c in idf.columns]
        st.dataframe(idf[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No invite codes generated yet.")
else:
    st.warning("Could not load invite codes.")


