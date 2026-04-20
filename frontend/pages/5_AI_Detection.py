import streamlit as st
import requests

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(page_title="AI Detection — Paper IQ", page_icon="🤖", layout="wide")

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


st.title("🤖 AI Content Detection")
st.markdown("Estimate the probability that a paper was generated (fully or partially) by an AI language model.")

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
chosen_title = st.selectbox("Select a Research Paper to Analyse", titles)
paper_id = options[chosen_title]

if st.button("🧠 Detect AI Content", use_container_width=True, type="primary"):
    with st.spinner("Analysing writing patterns…"):
        try:
            r = requests.post(
                f"{API_BASE}/papers/ai-detection",
                json={"paper_id": paper_id},
                headers=auth_headers(),
                timeout=60,
            )
            result = r.json()
        except Exception:
            st.error("Failed to run detection.")
            st.stop()

    if not result.get("success"):
        st.error(result.get("error", "Detection failed."))
        st.stop()

    data = result["data"]
    # API returns ai_probability as 0-100 (percent); convert to 0-1 fraction for display
    prob = max(0.0, min(1.0, data.get("ai_probability", 0) / 100.0))
    confidence = data.get("confidence", "low").lower()
    explanation = data.get("explanation", "")

    st.divider()

    # Color-coded metric
    if prob < 0.3:
        badge_color = "#2f855a"
        badge_bg = "#1c2d1c"
        verdict = "Likely Human-Written"
        icon = "✅"
    elif prob < 0.7:
        badge_color = "#c05621"
        badge_bg = "#2d1e0f"
        verdict = "Possibly AI-Assisted"
        icon = "⚠️"
    else:
        badge_color = "#c53030"
        badge_bg = "#2d1c1c"
        verdict = "Likely AI-Generated"
        icon = "🚨"

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(f"{icon} AI Probability", f"{prob:.1%}")
        st.progress(prob)
        # Confidence badge
        conf_colors = {"low": "#718096", "medium": "#c05621", "high": "#c53030"}
        st.markdown(
            f"<span style='background:{conf_colors.get(confidence, '#718096')};"
            f"color:white;padding:0.2rem 0.6rem;border-radius:12px;font-size:0.8rem'>"
            f"Confidence: {confidence.upper()}</span>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div style='background:{badge_bg};border-left:4px solid {badge_color};"
            f"padding:1rem 1.25rem;border-radius:6px'>"
            f"<div style='font-size:1.1rem;font-weight:600;color:{badge_color}'>{verdict}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if explanation:
            st.markdown("**Analysis**")
            st.write(explanation)


