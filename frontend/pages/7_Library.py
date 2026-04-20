import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Manage Library — Paper IQ", page_icon="📚", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in first.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def fetch_papers():
    try:
        r = requests.get(f"{API_BASE}/papers/", headers=auth_headers(), timeout=10)
        data = r.json()
        if data.get("success"):
            return data["data"]
        return []
    except Exception as e:
        st.error(f"Error connecting to backend: {str(e)}")
        return []


def delete_paper(paper_id):
    try:
        r = requests.delete(f"{API_BASE}/papers/{paper_id}", headers=auth_headers(), timeout=10)
        data = r.json()
        return data.get("success"), data.get("error")
    except Exception as e:
        return False, str(e)


st.title("📚 Manage Library")
st.markdown("View and manage your uploaded research papers. Analysis status and deletion options are available below.")

papers = fetch_papers()

if not papers:
    st.info("Your library is empty. Go to the **Upload** page to add your first research paper!")
    if st.button("📤 Go to Upload"):
        st.switch_page("pages/1_Upload.py")
    st.stop()

# Table header
cols = st.columns([3, 1.5, 1.5, 1.5, 1])
cols[0].write("**Paper Title**")
cols[1].write("**Status**")
cols[2].write("**Word Count**")
cols[3].write("**Date Added**")
cols[4].write("**Action**")

st.divider()

for paper in papers:
    with st.container():
        c1, c2, c3, c4, c5 = st.columns([3, 1.5, 1.5, 1.5, 1])
        
        paper_id = paper.get("paper_id") or paper.get("_id")
        title = paper.get("title", "Untitled")
        status = paper.get("status", "unknown").capitalize()
        word_count = paper.get("word_count", 0)
        
        # Format date
        try:
            date_str = paper.get("created_at", "")
            if date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                display_date = dt.strftime("%Y-%m-%d")
            else:
                display_date = "—"
        except:
            display_date = "—"

        c1.write(f"**{title}**")
        
        # Status Badge
        if status == "Ready":
            c2.success(f"✅ {status}")
        elif status == "Processing":
            c2.info(f"⏳ {status}")
        elif status == "Error":
            c2.error(f"❌ {status}")
        else:
            c2.write(status)
            
        c3.write(f"{word_count:,}")
        c4.write(display_date)
        
        # Delete with confirmation popover
        with c5:
            with st.popover("🗑️", help="Delete paper"):
                st.warning("Are you sure? This will permanently delete the file and all analysis data.")
                if st.button("Confirm Delete", key=f"del_{paper_id}", type="primary", use_container_width=True):
                    success, err = delete_paper(paper_id)
                    if success:
                        st.success("Deleted!")
                        st.rerun()
                    else:
                        st.error(f"Failed: {err}")

    st.divider()

st.caption(f"Showing {len(papers)} papers in your library.")
