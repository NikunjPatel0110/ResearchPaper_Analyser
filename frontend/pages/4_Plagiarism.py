import streamlit as st
import requests

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Plagiarism — Paper IQ", page_icon="🚨", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in first.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def fetch_papers():
    try:
        r = requests.get(f"{API_BASE}/papers/", headers=auth_headers(), timeout=10)
        data = r.json()
        return data["data"] if data.get("success") else []
    except Exception:
        return []


st.title("🚨 Plagiarism Check")

papers = fetch_papers()
if not papers:
    st.info("No papers found. Upload one first.")
    st.stop()

options = {}
if isinstance(papers, list):
    for p in papers:
        if isinstance(p, dict):
            t = p.get("title", "Untitled")
            if t not in options:
                options[t] = str(p.get("paper_id") or p.get("_id") or p.get("id", ""))
        else:
            st.error(f"Backend returned unexpected data format: {p}")
else:
    st.error("Could not fetch papers. Check if the Flask backend is running.")

if not options:
    st.info("No processed papers found. Upload a paper first.")
    st.stop()

# Title selection
titles = list(options.keys())
chosen_title = st.selectbox("Select a Research Paper to Scan", titles)
paper_id = options[chosen_title]

# Optional Threshold setting
threshold = st.slider("Similarity Threshold (%)", min_value=10, max_value=95, value=40, step=5) / 100.0

if st.button("🔎 Run Plagiarism Check", use_container_width=True, type="primary"):
    with st.spinner("Scanning for plagiarism… this may take a moment."):
        try:
            r = requests.post(
                f"{API_BASE}/papers/plagiarism-check",
                json={"paper_id": paper_id, "threshold": threshold},
                headers=auth_headers(),
                timeout=60,
            )
            result = r.json()
        except Exception:
            st.error("Failed to run check.")
            st.stop()

    if not result.get("success"):
        st.error(result.get("error", "Check failed."))
        st.stop()

    data = result["data"]
    overall = data.get("overall_similarity", 0)

    st.divider()
    # Overall score
    col_score, col_status = st.columns([1, 2])
    with col_score:
        color = "🟢" if overall < 0.2 else ("🟡" if overall < 0.5 else "🔴")
        st.metric("Plagiarism Score", f"{overall:.1%}", delta=None)
    with col_status:
        if overall < 0.2:
            st.success("✅ Low plagiarism risk.")
        elif overall < 0.5:
            st.warning("⚠️ Moderate plagiarism risk. Review flagged sections.")
        else:
            st.error("🚨 High plagiarism risk. Multiple matches detected.")

    st.progress(min(overall, 1.0))

    # Flagged chunks
    chunks = data.get("matches", [])
    if chunks:
        st.divider()
        st.subheader(f"Flagged Passages ({len(chunks)})")
        for i, chunk in enumerate(chunks, 1):
            with st.expander(
                f"Chunk {i} — Score: {chunk.get('similarity', 0):.0%}  |  Source: {chunk.get('matched_paper_title', 'Unknown')}"
            ):
                st.markdown(
                    f"**Source:** {chunk.get('matched_paper_title', '—')}"
                )
                st.metric("Match Score", f"{chunk.get('similarity', 0):.0%}")
                st.markdown("**Flagged text:**")
                text = chunk.get("chunk_text", "")
                st.markdown(
                    f"<div style='background:#2d1c1c;padding:0.75rem;border-radius:6px;"
                    f"border-left:3px solid #fc8181;color:#fed7d7;font-size:0.9rem'>{text}</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.info("No specific passages flagged.")


