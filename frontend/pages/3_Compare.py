import streamlit as st
import requests

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Compare — Paper IQ", page_icon="⚖️", layout="wide")

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


st.title("⚖️ Compare Papers")

papers = fetch_papers()
if len(papers) < 2:
    st.info("You need at least 2 papers to compare. Upload more first.")
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
    st.info("No papers processed yet. Upload more and wait for them to be ready.")
    st.stop()

titles = list(options.keys())

col1, col2 = st.columns(2)
with col1:
    title_a = st.selectbox("Paper A", titles, index=0, key="pa")
with col2:
    remaining = [t for t in titles if t != title_a]
    if not remaining:
        st.warning("You need at least 2 papers for comparison.")
        st.stop()
    title_b = st.selectbox("Paper B", remaining, index=0, key="pb")

if st.button("⚖️ Compare", use_container_width=True, type="primary"):
    id_a = options[title_a]
    id_b = options[title_b]
    with st.spinner("Comparing papers…"):
        try:
            r = requests.post(
                f"{API_BASE}/papers/compare",
                json={"paper_id_1": id_a, "paper_id_2": id_b},
                headers=auth_headers(),
                timeout=30,
            )
            result = r.json()
        except Exception:
            st.error("Failed to compare papers.")
            st.stop()

    if not result.get("success"):
        st.error(result.get("error", "Comparison failed."))
        st.stop()

    data = result["data"]
    score = data.get("similarity_score", 0)

    st.divider()
    st.metric(
        "Overall Similarity",
        f"{score:.1%}",
        delta=None,
        help="Cosine similarity of sentence embeddings",
    )

    # Progress bar coloured by severity
    color = "green" if score < 0.5 else ("orange" if score < 0.8 else "red")
    st.progress(score)

    st.divider()
    # Keyword Venn — side-by-side lists
    kw_a = set(data.get("keywords_a", []))
    kw_b = set(data.get("keywords_b", []))
    shared = kw_a & kw_b
    only_a = kw_a - kw_b
    only_b = kw_b - kw_a

    st.subheader("Keyword Overlap")
    ca, cm, cb = st.columns([2, 1.5, 2])
    with ca:
        st.markdown(f"**{title_a}** only")
        for kw in sorted(only_a):
            st.markdown(f"- {kw}")
    with cm:
        st.markdown("**Shared**")
        for kw in sorted(shared):
            st.markdown(f"- 🔵 **{kw}**")
    with cb:
        st.markdown(f"**{title_b}** only")
        for kw in sorted(only_b):
            st.markdown(f"- {kw}")

    st.divider()
    st.subheader("Summaries")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"**{title_a}**")
        st.write(data.get("summary_a", "*No summary.*"))
    with s2:
        st.markdown(f"**{title_b}**")
        st.write(data.get("summary_b", "*No summary.*"))


