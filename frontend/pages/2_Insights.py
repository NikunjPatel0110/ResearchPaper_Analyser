import streamlit as st
import requests
import altair as alt
import pandas as pd

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="Insights — Paper IQ", page_icon="🔍", layout="wide")

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


st.title("🔍 Paper Insights")

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
    st.info("No documents are processed yet. Upload a paper and wait a moment.")
    st.stop()

# Title selection
titles = list(options.keys())
chosen_title = st.selectbox("Select a Research Paper", titles)
paper_id = options[chosen_title]

if st.button("Load Insights", use_container_width=False, type="primary"):
    with st.spinner("Fetching analysis..."):
        try:
            r = requests.get(
                f"{API_BASE}/papers/{paper_id}/insights", headers=auth_headers(), timeout=15
            )
            result = r.json()
            if not result.get("success"):
                st.error(f"Error: {result.get('error')}")
                st.stop()
            paper = result.get("data", {})
        except Exception:
            st.error("Failed to load paper.")
            st.stop()

    st.subheader("Summary")
    st.write(paper.get("summary") or "*No summary.*")
    st.divider()

    # Keywords bar chart
    kws = paper.get("keywords", [])
    kw_scores = paper.get("keyword_scores", {})
    if kws:
        st.subheader("Top Keywords")
        if isinstance(kws[0], dict):
            kdf = pd.DataFrame(kws).sort_values("score", ascending=False)
            kdf.rename(columns={"word": "keyword"}, inplace=True)
        else:
            kdf = pd.DataFrame(
                [(k, kw_scores.get(k, 1.0)) for k in kws], columns=["keyword", "score"]
            ).sort_values("score", ascending=False)
        chart = (
            alt.Chart(kdf)
            .mark_bar(color="#4299e1")
            .encode(
                x=alt.X("score:Q", title="Score"),
                y=alt.Y("keyword:N", sort="-x", title=""),
                tooltip=["keyword", "score"],
            )
            .properties(height=min(400, len(kdf) * 28 + 40))
        )
        st.altair_chart(chart, use_container_width=True)

    # Entities table + donut
    entities = paper.get("entities", [])
    if entities:
        st.subheader("Named Entities")
        edf = pd.DataFrame(entities)
        col1, col2 = st.columns([2, 1])
        with col1:
            if "label" in edf.columns:
                for label, group in edf.groupby("label"):
                    with st.expander(f"{label} ({len(group)})"):
                        st.write(", ".join(group["text"].tolist()))
            else:
                st.dataframe(edf)
        with col2:
            if "label" in edf.columns:
                counts = edf["label"].value_counts().reset_index()
                counts.columns = ["label", "count"]
                donut = (
                    alt.Chart(counts)
                    .mark_arc(innerRadius=50)
                    .encode(
                        theta="count:Q",
                        color=alt.Color("label:N", legend=alt.Legend(title="Type")),
                        tooltip=["label", "count"],
                    )
                    .properties(height=250)
                )
                st.altair_chart(donut, use_container_width=True)

    # Similar papers
    similar = paper.get("similar_papers", [])
    if similar:
        st.subheader("Similar Papers")
        for sp in similar[:5]:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                
                title = sp.get("title", "Untitled")
                url = sp.get("url", "")
                
                if url:
                    # If it's an internal link (relative path), prepend the base origin and append token
                    if url.startswith("/"):
                        # Deriving base origin from API_BASE (assuming http://domain:port/api/v1)
                        # We'll just use the host part of API_BASE
                        import urllib.parse
                        parsed_base = urllib.parse.urlparse(API_BASE)
                        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
                        full_url = f"{base_origin}{url}?token={st.session_state.token}"
                    else:
                        full_url = url
                    
                    c1.markdown(f"**[{title}]({full_url})**")
                else:
                    c1.markdown(f"**{title}**")
                
                c1.caption(sp.get("source", "Internal"))
                c2.metric("Similarity", f"{sp.get('score', 0):.0%}")


