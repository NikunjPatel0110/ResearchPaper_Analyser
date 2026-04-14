import streamlit as st
import requests

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Upload — Paper IQ", page_icon="📤", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in first.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


st.title("📤 Upload Paper")
st.markdown("Upload a research paper in **PDF**, **TXT**, or **DOCX** format.")

uploaded = st.file_uploader(
    "Choose a file",
    type=["pdf", "txt", "docx"],
    help="Max file size depends on your server configuration.",
)

if uploaded:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("File name", uploaded.name)
        st.metric("Size", f"{uploaded.size / 1024:.1f} KB")
    with col2:
        if st.button("🚀 Upload & Analyse", use_container_width=True):
            with st.spinner("Uploading and analysing…"):
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                try:
                    resp = requests.post(
                        f"{API_BASE}/papers/upload",
                        files=files,
                        headers=auth_headers(),
                        timeout=60,
                    )
                    data = resp.json()
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the backend.")
                    st.stop()

            if data.get("success"):
                paper = data["data"]
                st.success("✅ Paper uploaded and analysed successfully!")
                st.divider()

                m1, m2 = st.columns(2)
                m1.metric("Word Count", paper.get("word_count", "—"))
                m2.metric("Paper ID", str(paper.get("_id", "—"))[:16] + "…")

                st.subheader("Summary")
                st.write(paper.get("summary", "*No summary available.*"))

                with st.expander("Top Keywords"):
                    kws = paper.get("keywords", [])
                    if kws:
                        kw_strings = [k.get("word") if isinstance(k, dict) else k for k in kws]
                        st.write(", ".join(kw_strings))
                    else:
                        st.write("None extracted.")
            else:
                st.error(data.get("error", "Upload failed."))