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
        r = requests.get(f"{API_BASE}/papers", headers=auth_headers(), timeout=10)
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
for p in papers:
    t = p.get("title", "Untitled")
    if t not in options:
        options[t] = str(p.get("paper_id") or p.get("_id") or p.get("id", ""))
chosen_title = st.selectbox("Select a paper", list(options.keys()))
paper_id = options[chosen_title]

if st.button("Load Insights", use_container_width=False):
    with st.spinner("Fetching…"):
        try:
            r = requests.get(
                f"{API_BASE}/papers/{paper_id}", headers=auth_headers(), timeout=15
            )
            paper = r.json().get("data", {})
            if isinstance(paper, list):
                paper = paper[0] if paper else {}
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
                c1.markdown(f"**{sp.get('title', 'Untitled')}**")
                c1.caption(sp.get("source", "Internal"))
                c2.metric("Similarity", f"{sp.get('score', 0):.0%}")


