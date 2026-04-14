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
        r = requests.get(f"{API_BASE}/papers", headers=auth_headers(), timeout=10)
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
for p in papers:
    t = p.get("title", "Untitled")
    if t not in options:
        options[t] = str(p.get("paper_id") or p.get("_id") or p.get("id", ""))
chosen = st.selectbox("Select a paper to check", list(options.keys()))

if st.button("🔎 Run Plagiarism Check", use_container_width=True, type="primary"):
    paper_id = options[chosen]
    with st.spinner("Scanning for plagiarism… this may take a moment."):
        try:
            r = requests.post(
                f"{API_BASE}/papers/{paper_id}/plagiarism",
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
    overall = data.get("overall_score", 0)

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
    chunks = data.get("flagged_chunks", [])
    if chunks:
        st.divider()
        st.subheader(f"Flagged Passages ({len(chunks)})")
        for i, chunk in enumerate(chunks, 1):
            with st.expander(
                f"Chunk {i} — Score: {chunk.get('score', 0):.0%}  |  Source: {chunk.get('source', 'Unknown')}"
            ):
                st.markdown(
                    f"**Source:** [{chunk.get('source', '—')}]({chunk.get('source_url', '#')})"
                )
                st.metric("Match Score", f"{chunk.get('score', 0):.0%}")
                st.markdown("**Flagged text:**")
                text = chunk.get("text", "")
                st.markdown(
                    f"<div style='background:#2d1c1c;padding:0.75rem;border-radius:6px;"
                    f"border-left:3px solid #fc8181;color:#fed7d7;font-size:0.9rem'>{text}</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.info("No specific passages flagged.")


