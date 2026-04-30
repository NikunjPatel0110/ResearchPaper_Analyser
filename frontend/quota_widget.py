"""
quota_widget.py
Reusable quota bar + upgrade CTA for use in any Streamlit page.
Import and call: show_quota_bar(headers)
"""
import streamlit as st
import requests

API = "http://localhost:5000/api/v1"


def get_quota(headers):
    try:
        r = requests.get(f"{API}/payments/quota", headers=headers, timeout=5)
        if r.ok:
            return r.json().get("data", {})
    except Exception:
        pass
    return {}


def show_quota_bar(headers, show_upgrade_btn=True):
    """
    Renders a compact quota progress bar.
    Returns True if user CAN upload, False if blocked.
    """
    quota = get_quota(headers)
    if not quota:
        return True  # Can't check — let backend enforce

    used      = quota.get("upload_count", 0)
    limit     = quota.get("upload_limit", 10)
    remaining = quota.get("remaining", 0)
    plan      = quota.get("plan_label", "Free")
    can       = quota.get("can_upload", True)

    pct = min(used / max(limit, 1), 1.0)
    col1, col2 = st.columns([3, 1])

    with col1:
        st.progress(pct, text=f"{plan} · {used}/{limit} uploads used · {remaining} remaining")

    with col2:
        if not can and show_upgrade_btn:
            if st.button("Upgrade", type="primary", use_container_width=True):
                st.switch_page("pages/7_Billing.py")

    if not can:
        st.warning(
            f"You've used all {limit} uploads on your **{plan}** plan. "
            "Go to **Billing** to upgrade and unlock more uploads."
        )

    return can