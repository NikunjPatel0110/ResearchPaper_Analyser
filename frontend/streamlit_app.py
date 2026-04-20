import streamlit as st
import requests

API_BASE = "http://127.0.0.1:5000/api/v1"

st.set_page_config(
    page_title="Paper IQ",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

for key, default in [("token", None), ("role", None), ("user_name", ""), ("show_register", False)]:
    if key not in st.session_state:
        st.session_state[key] = default


def hide_sidebar():
    st.markdown("""
        <style>
            [data-testid="collapsedControl"] {display: none;}
            [data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)


def do_login(email, password):
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"email": email, "password": password}, timeout=60)
        data = resp.json()
        if data.get("success"):
            st.session_state.token = data["data"]["access_token"]
            st.session_state.role = data["data"].get("role", "user")
            st.session_state.user_name = data["data"].get("name", email)
            return None
        return data.get("error", "Login failed.")
    except requests.exceptions.ConnectionError:
        return "Cannot reach the backend — is Flask running on port 5000?"


def do_register(name, email, password, invite_code):
    try:
        resp = requests.post(
            f"{API_BASE}/auth/register",
            json={"name": name, "email": email, "password": password, "invite_code": invite_code},
            timeout=10,
        )
        data = resp.json()
        if data.get("success"):
            return None
        return data.get("error", "Registration failed.")
    except requests.exceptions.ConnectionError:
        return "Cannot reach the backend — is Flask running on port 5000?"


def login_page():
    hide_sidebar()
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("## 📄 Paper IQ")
        st.markdown("*Research Navigator*")
        st.divider()

        if not st.session_state.show_register:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        with st.spinner("Signing in…"):
                            err = do_login(email, password)
                        if err:
                            st.error(err)
                        else:
                            st.success("Welcome back!")
                            st.rerun()
            if st.button("Don't have an account? Register with invite code →", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
        else:
            with st.form("register_form"):
                st.markdown("#### Create Account")
                name = st.text_input("Full Name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password", help="Minimum 8 characters")
                invite_code = st.text_input("Invite Code", placeholder="INV-XXXXXXXX")
                submitted = st.form_submit_button("Create Account", use_container_width=True)
                if submitted:
                    if not all([name, email, password, invite_code]):
                        st.error("Please fill in all fields.")
                    elif len(password) < 8:
                        st.error("Password must be at least 8 characters.")
                    else:
                        with st.spinner("Creating account…"):
                            err = do_register(name, email, password, invite_code)
                        if err:
                            st.error(err)
                        else:
                            st.success("✅ Account created! Please sign in.")
                            st.session_state.show_register = False
                            st.rerun()
            if st.button("← Back to Sign In"):
                st.session_state.show_register = False
                st.rerun()


def main_app():
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user_name}")
        st.caption(f"Role: `{st.session_state.role}`")
        st.divider()
        st.page_link("streamlit_app.py", label="🏠 Home", icon="🏠")
        st.page_link("pages/1_Upload.py", label="Upload Paper", icon="📤")
        st.page_link("pages/7_Library.py", label="Manage Library", icon="📚")
        st.page_link("pages/2_Insights.py", label="Insights", icon="🔍")
        st.page_link("pages/3_Compare.py", label="Compare Papers", icon="⚖️")
        st.page_link("pages/4_Plagiarism.py", label="Plagiarism Check", icon="🚨")
        st.page_link("pages/5_AI_Detection.py", label="AI Detection", icon="🤖")
        if st.session_state.role == "admin":
            st.page_link("pages/6_Admin.py", label="Admin Panel", icon="🛡️")
        st.divider()
        if st.button("Sign Out", use_container_width=True):
            for k in ["token", "role", "user_name"]:
                st.session_state[k] = None if k != "user_name" else ""
            st.rerun()

    st.title("📄 Paper IQ — Research Navigator")
    st.markdown("""
        Welcome to **Paper IQ**. Use the sidebar to navigate:

        | Page | Description |
        |---|---|
        | 📤 **Upload** | Upload PDF, TXT, or DOCX research papers |
        | 📚 **Library** | Manage library, check status, and delete papers |
        | 🔍 **Insights** | Keywords, entities, summaries, similar papers |
        | ⚖️ **Compare** | Side-by-side similarity analysis |
        | 🚨 **Plagiarism** | Detect copied content with source links |
        | 🤖 **AI Detection** | Estimate AI-generated content probability |
    """)


if st.session_state.token is None:
    login_page()
else:
    main_app()

# import streamlit as st
# import requests

# API_BASE = "http://127.0.0.1:5000/api/v1"

# st.set_page_config(
#     page_title="Paper IQ",
#     page_icon="📄",
#     layout="wide",
#     initial_sidebar_state="collapsed",
# )

# # --- SESSION STATE ---
# for key, default in [("token", None), ("role", None), ("user_name", ""), ("show_register", False)]:
#     if key not in st.session_state:
#         st.session_state[key] = default


# # --- GLOBAL CSS (🔥 BIG UI UPGRADE) ---
# st.markdown("""
# <style>
# /* Background */
# body {
#     background-color: #0f172a;
# }

# /* Center card (login) */
# .auth-card {
#     padding: 30px;
#     border-radius: 15px;
#     background: #1e293b;
#     border: 1px solid #334155;
# }

# /* Feature cards */
# .card {
#     padding: 20px;
#     border-radius: 15px;
#     background: #1e293b;
#     border: 1px solid #334155;
#     transition: 0.3s;
# }
# .card:hover {
#     transform: scale(1.03);
#     border: 1px solid #2563eb;
# }

# /* Titles */
# .title {
#     font-size: 42px;
#     font-weight: 700;
# }
# .subtitle {
#     color: #94a3b8;
#     margin-bottom: 25px;
# }

# /* Buttons */
# .stButton>button {
#     border-radius: 10px;
#     background-color: #2563eb;
#     color: white;
#     border: none;
# }
# .stButton>button:hover {
#     background-color: #1d4ed8;
# }
# </style>
# """, unsafe_allow_html=True)


# # --- API FUNCTIONS ---
# def do_login(email, password):
#     try:
#         resp = requests.post(f"{API_BASE}/auth/login", json={"email": email, "password": password}, timeout=60)
#         data = resp.json()
#         if data.get("success"):
#             st.session_state.token = data["data"]["access_token"]
#             st.session_state.role = data["data"].get("role", "user")
#             st.session_state.user_name = data["data"].get("name", email)
#             return None
#         return data.get("error", "Login failed.")
#     except:
#         return "Backend not running."


# def do_register(name, email, password, invite_code):
#     try:
#         resp = requests.post(
#             f"{API_BASE}/auth/register",
#             json={"name": name, "email": email, "password": password, "invite_code": invite_code},
#             timeout=10,
#         )
#         data = resp.json()
#         if data.get("success"):
#             return None
#         return data.get("error", "Registration failed.")
#     except:
#         return "Backend not running."


# # --- LOGIN PAGE (🔥 Redesigned) ---
# def login_page():
#     st.markdown("<br><br>", unsafe_allow_html=True)

#     col1, col2, col3 = st.columns([1, 1.2, 1])

#     with col2:
#         st.markdown('<div class="auth-card">', unsafe_allow_html=True)

#         st.markdown('<div class="title">📄 Paper IQ</div>', unsafe_allow_html=True)
#         st.markdown('<div class="subtitle">Research Navigator</div>', unsafe_allow_html=True)

#         if not st.session_state.show_register:
#             with st.form("login_form"):
#                 email = st.text_input("Email")
#                 password = st.text_input("Password", type="password")
#                 submitted = st.form_submit_button("Sign In", use_container_width=True)

#                 if submitted:
#                     err = do_login(email, password)
#                     if err:
#                         st.error(err)
#                     else:
#                         st.success("Welcome back!")
#                         st.rerun()

#             if st.button("Create account →", use_container_width=True):
#                 st.session_state.show_register = True
#                 st.rerun()

#         else:
#             with st.form("register_form"):
#                 name = st.text_input("Full Name")
#                 email = st.text_input("Email")
#                 password = st.text_input("Password", type="password")
#                 invite_code = st.text_input("Invite Code")

#                 submitted = st.form_submit_button("Create Account", use_container_width=True)

#                 if submitted:
#                     err = do_register(name, email, password, invite_code)
#                     if err:
#                         st.error(err)
#                     else:
#                         st.success("Account created!")
#                         st.session_state.show_register = False
#                         st.rerun()

#             if st.button("← Back to login"):
#                 st.session_state.show_register = False
#                 st.rerun()

#         st.markdown("</div>", unsafe_allow_html=True)


# # --- MAIN APP (🔥 Redesigned Dashboard) ---
# def main_app():
#     # Sidebar
#     with st.sidebar:
#         st.markdown(f"### 👤 {st.session_state.user_name}")
#         st.caption(f"Role: `{st.session_state.role}`")
#         st.divider()

#         st.page_link("streamlit_app.py", label="🏠 Home")
#         st.page_link("pages/1_Upload.py", label="📄 Upload")
#         st.page_link("pages/2_Insights.py", label="📊 Insights")
#         st.page_link("pages/3_Compare.py", label="⚖️ Compare")
#         st.page_link("pages/4_Plagiarism.py", label="🚨 Plagiarism")
#         st.page_link("pages/5_AI_Detection.py", label="🤖 AI Detection")

#         if st.session_state.role == "admin":
#             st.page_link("pages/6_Admin.py", label="🛡️ Admin")

#         st.divider()
#         if st.button("Sign Out", use_container_width=True):
#             for k in ["token", "role", "user_name"]:
#                 st.session_state[k] = None if k != "user_name" else ""
#             st.rerun()

#     # HERO SECTION
#     st.markdown('<div class="title">📄 Paper IQ</div>', unsafe_allow_html=True)
#     st.markdown('<div class="subtitle">Analyze research papers in seconds</div>', unsafe_allow_html=True)

#     col1, col2 = st.columns(2)
#     with col1:
#         st.button("📤 Upload Paper")
#     with col2:
#         st.button("🚀 Run Analysis")

#     st.markdown("---")

#     # FEATURE CARDS
#     col1, col2, col3 = st.columns(3)

#     with col1:
#         st.markdown('<div class="card"><h3>📄 Upload</h3><p>Upload research papers</p></div>', unsafe_allow_html=True)

#     with col2:
#         st.markdown('<div class="card"><h3>📊 Insights</h3><p>Summaries & keywords</p></div>', unsafe_allow_html=True)

#     with col3:
#         st.markdown('<div class="card"><h3>⚖️ Compare</h3><p>Compare multiple papers</p></div>', unsafe_allow_html=True)

#     st.markdown("")

#     col4, col5 = st.columns(2)

#     with col4:
#         st.markdown('<div class="card"><h3>🚨 Plagiarism</h3><p>Detect copied content</p></div>', unsafe_allow_html=True)

#     with col5:
#         st.markdown('<div class="card"><h3>🤖 AI Detection</h3><p>Detect AI-generated text</p></div>', unsafe_allow_html=True)

#     st.markdown("---")

#     # STATS
#     col1, col2, col3 = st.columns(3)
#     col1.metric("📄 Papers", "24")
#     col2.metric("📊 Reports", "12")
#     col3.metric("🤖 AI Checks", "8")


# # --- ROUTING ---
# if st.session_state.token is None:
#     login_page()
# else:
#     main_app()
