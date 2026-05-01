# import streamlit as st
# import requests

# API_BASE = "http://127.0.0.1:5000/api/v1"

# st.set_page_config(page_title="Upload — Paper IQ", page_icon="📤", layout="wide")

# if not st.session_state.get("token"):
#     st.warning("Please sign in first.")
#     st.stop()


# def auth_headers():
#     return {"Authorization": f"Bearer {st.session_state.token}"}


# st.title("📤 Upload Paper")
# st.markdown("Upload a research paper in **PDF**, **TXT**, or **DOCX** format.")

# uploaded = st.file_uploader(
#     "Choose a file",
#     type=["pdf", "txt", "docx"],
#     help="Max file size depends on your server configuration.",
# )

# if uploaded:
#     col1, col2 = st.columns([1, 3])
#     with col1:
#         st.metric("File name", uploaded.name)
#         st.metric("Size", f"{uploaded.size / 1024:.1f} KB")
#     with col2:
#         if st.button("🚀 Upload & Analyse", use_container_width=True):
#             with st.spinner("Uploading… (analysis runs in the background)"):
#                 files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
#                 try:
#                     resp = requests.post(
#                         f"{API_BASE}/papers/upload",
#                         files=files,
#                         headers=auth_headers(),
#                         timeout=60,
#                     )

#                     # Accept 200/201 (sync) and 202 (async background processing)
#                     if resp.status_code not in (200, 201, 202):
#                         try:
#                             err_msg = resp.json().get("error", "The server encountered an error.")
#                             st.error(f"Upload Blocked (Error {resp.status_code}): {err_msg}")
#                         except:
#                             st.error(f"Backend Error {resp.status_code}: Something broke on the server.")
                        
#                         if resp.status_code != 409: # Show debug info for non-duplicate errors
#                             st.code(resp.text[:500])
#                         st.stop()

#                     data = resp.json()

#                 except requests.exceptions.ConnectionError as e:
#                     st.error(f"Connection dropped! Is the backend running? Details: {str(e)}")
#                     st.stop()
#                 except ValueError:
#                     st.error("Backend returned an invalid response (not JSON).")
#                     st.code(resp.text[:500])
#                     st.stop()

#             if data.get("success"):
#                 paper  = data["data"]
#                 status = paper.get("status", "ready")

#                 if status == "processing":
#                     st.success("✅ Paper uploaded! Analysis is running in the background.")
#                     st.info(
#                         "⏳ Large PDFs take 1–2 minutes to process. "
#                         "Go to the **Insights** page and select this paper once it shows as *ready*."
#                     )
#                     st.metric("Paper ID", str(paper.get("_id", "—"))[:16] + "…")
#                 else:
#                     st.success("✅ Paper uploaded and analysed successfully!")
#                     st.divider()

#                     m1, m2 = st.columns(2)
#                     m1.metric("Word Count", paper.get("word_count", "—"))
#                     m2.metric("Paper ID", str(paper.get("_id", "—"))[:16] + "…")

#                     st.subheader("Summary")
#                     st.write(paper.get("summary", "*No summary available.*"))

#                     with st.expander("Top Keywords"):
#                         kws = paper.get("keywords", [])
#                         if kws:
#                             kw_strings = [k.get("word") if isinstance(k, dict) else k for k in kws]
#                             st.write(", ".join(kw_strings))
#                         else:
#                             st.write("None extracted.")
#             else:
#                 st.error(data.get("error", "Upload failed."))

# ============================================


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

# --- PAYMENT VERIFICATION BLOCK ---
# This sits at the top so if they refresh after paying, they can still verify
# if "current_payment_id" in st.session_state:
#     st.info("Payment initiated! After completing the transaction in the new tab, click the button below.")
#     if st.button("✅ I have completed the payment"):
#         with st.spinner("Verifying with Razorpay..."):
#             verify_resp = requests.post(
#                 f"{API_BASE}/payments/verify-payment", 
#                 json={"payment_link_id": st.session_state.current_payment_id},
#                 headers=auth_headers()
#             )
            
#             if verify_resp.status_code == 200 and verify_resp.json().get("success"):
#                 st.success("🎉 Payment verified! Your account is now Premium.")
#                 del st.session_state.current_payment_id # Clear the ID
#                 st.rerun() # Refresh the page to unlock uploads
#             else:
#                 st.error("We couldn't verify your payment. Did you complete the transaction?")
#     st.divider()
# # ----------------------------------

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
            with st.spinner("Uploading… (analysis runs in the background)"):
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                try:
                    resp = requests.post(
                        f"{API_BASE}/papers/upload",
                        files=files,
                        headers=auth_headers(),
                        timeout=60,
                    )

                    # Accept 200/201 (sync) and 202 (async background processing)
                    if resp.status_code not in (200, 201, 202):
                        
                        # --- 1. THE PAYWALL INTERCEPTOR ---
                        if resp.status_code == 402:
                            st.error("🛑 Upload limit reached! You have used all your free uploads.")
                            st.page_link("pages/8_Billing.py", label="🌟 Click here to Upgrade to Premium", icon="💳")
                            st.stop()
                        # ----------------------------------
                        
                        # --- 2. STANDARD ERROR HANDLING ---
                        else:
                            try:
                                err_data = resp.json()
                                err_msg = err_data.get("error", "The server encountered an error.")
                                st.error(f"Upload Blocked (Error {resp.status_code}): {err_msg}")
                            except Exception: # Catch specific errors, NOT st.stop()
                                st.error(f"Backend Error {resp.status_code}: Something broke on the server.")
                            
                            # Only show raw JSON for unexpected errors (not 409 duplicates)
                            if resp.status_code != 409: 
                                st.code(resp.text[:500])
                            st.stop()

                    data = resp.json()

                except requests.exceptions.ConnectionError as e:
                    st.error(f"Connection dropped! Is the backend running? Details: {str(e)}")
                    st.stop()
                except ValueError:
                    st.error("Backend returned an invalid response (not JSON).")
                    st.code(resp.text[:500])
                    st.stop()

            if data.get("success"):
                paper  = data["data"]
                status = paper.get("status", "ready")

                if status == "processing":
                    st.success("✅ Paper uploaded! Analysis is running in the background.")
                    st.info(
                        "⏳ Large PDFs take 1–2 minutes to process. "
                        "Go to the **Insights** page and select this paper once it shows as *ready*."
                    )
                    st.metric("Paper ID", str(paper.get("_id", "—"))[:16] + "…")
                else:
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