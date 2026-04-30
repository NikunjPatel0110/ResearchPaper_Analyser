"""
7_Billing.py — Subscription plans, quota status, and Razorpay checkout.
"""
import streamlit as st
import requests

API = "http://localhost:5000/api/v1"

st.set_page_config(page_title="Billing — Paper IQ", page_icon="💳")

if "token" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state.token}"}


def get_quota():
    r = requests.get(f"{API}/payments/quota", headers=headers, timeout=10)
    return r.json().get("data", {}) if r.ok else {}


def get_plans():
    r = requests.get(f"{API}/payments/plans", timeout=10)
    return r.json().get("data", []) if r.ok else []


def get_history():
    r = requests.get(f"{API}/payments/history", headers=headers, timeout=10)
    return r.json().get("data", []) if r.ok else []


def create_order(plan):
    r = requests.post(f"{API}/payments/create-order", json={"plan": plan}, headers=headers, timeout=15)
    return r.json() if r.ok else None


st.title("💳 Billing & Subscription")

quota = get_quota()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current Plan",  quota.get("plan_label", "Free"))
with col2:
    st.metric("Uploads Used",  f"{quota.get('upload_count', 0)} / {quota.get('upload_limit', 10)}")
with col3:
    st.metric("Remaining",     quota.get("remaining", 0))

used  = quota.get("upload_count", 0)
limit = quota.get("upload_limit", 10)
pct   = min(used / max(limit, 1), 1.0)
st.progress(pct, text=f"{used}/{limit} uploads used")

if quota.get("plan_expires"):
    st.caption(f"Expires: {quota['plan_expires'][:10]}")

if not quota.get("can_upload"):
    st.error("You have reached your upload limit. Upgrade below to continue.")

st.divider()
st.subheader("Choose a Plan")

plans = get_plans()
if not plans:
    st.warning("Could not load plans. Is the backend running?")
else:
    cols = st.columns(len(plans))
    for col, plan in zip(cols, plans):
        with col:
            is_current = quota.get("plan") == plan["plan"]
            border = "2px solid #6C63FF" if is_current else "1px solid #ddd"
            st.markdown(
                f"""<div style="border:{border};border-radius:12px;padding:16px;
                    text-align:center;margin-bottom:8px">
                  <h3 style="margin:0">{plan['label']}</h3>
                  <p style="font-size:26px;font-weight:700;margin:8px 0">&#8377;{plan['price_inr']}</p>
                  <p style="color:#888;margin:0;font-size:13px">{plan['period']}</p>
                  <p style="font-size:13px;margin:8px 0"><b>{plan['upload_limit']:,}</b> uploads</p>
                </div>""",
                unsafe_allow_html=True
            )
            for feat in plan.get("features", []):
                st.markdown(f"✓ {feat}")

            if is_current:
                st.success("Active")
            else:
                if st.button(f"Get {plan['label']}", key=f"btn_{plan['plan']}", use_container_width=True):
                    st.session_state["selected_plan"] = plan["plan"]
                    st.session_state["show_checkout"]  = True
                    st.rerun()

st.divider()

# Checkout widget
if st.session_state.get("show_checkout") and st.session_state.get("selected_plan"):
    selected = st.session_state["selected_plan"]
    plan_obj = next((p for p in plans if p["plan"] == selected), None)

    if plan_obj:
        st.subheader(f"Checkout — {plan_obj['label']}")

        with st.spinner("Preparing order..."):
            resp = create_order(selected)

        if not resp or not resp.get("success"):
            st.error(resp.get("error", "Failed to create order") if resp else "Backend error")
        else:
            od = resp["data"]
            token = st.session_state.token

            html = f"""<!DOCTYPE html><html><head>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
</head><body>
<div id="msg" style="font-family:sans-serif;padding:6px;min-height:30px"></div>
<button id="paybtn" onclick="pay()"
  style="background:#6C63FF;color:#fff;border:none;padding:12px 0;
         font-size:15px;border-radius:8px;cursor:pointer;width:100%">
  Pay &#8377;{od['amount'] // 100} with Razorpay
</button>
<script>
function pay() {{
  var rzp = new Razorpay({{
    key: "{od['key_id']}",
    amount: {od['amount']},
    currency: "{od['currency']}",
    name: "Paper IQ",
    description: "{plan_obj['label']} Plan",
    order_id: "{od['order_id']}",
    theme: {{color: "#6C63FF"}},
    handler: function(r) {{
      document.getElementById("msg").innerHTML =
        "<span style='color:#0f9960'>Payment received. Activating plan...</span>";
      fetch("http://localhost:5000/api/v1/payments/verify", {{
        method: "POST",
        headers: {{"Content-Type":"application/json","Authorization":"Bearer {token}"}},
        body: JSON.stringify({{
          razorpay_order_id:   r.razorpay_order_id,
          razorpay_payment_id: r.razorpay_payment_id,
          razorpay_signature:  r.razorpay_signature,
          plan: "{selected}"
        }})
      }})
      .then(x => x.json())
      .then(d => {{
        if(d.success) {{
          document.getElementById("msg").innerHTML =
            "<span style='color:#0f9960;font-size:17px'>Plan activated! Please refresh the page.</span>";
          document.getElementById("paybtn").style.display = "none";
        }} else {{
          document.getElementById("msg").innerHTML =
            "<span style='color:red'>Verification failed: " + (d.error||"error") + "</span>";
        }}
      }})
      .catch(e => {{
        document.getElementById("msg").innerHTML =
          "<span style='color:red'>Network error: " + e + "</span>";
      }});
    }},
    modal: {{ondismiss: function(){{
      document.getElementById("msg").innerHTML =
        "<span style='color:orange'>Payment cancelled.</span>";
    }}}}
  }});
  rzp.on("payment.failed", function(r) {{
    document.getElementById("msg").innerHTML =
      "<span style='color:red'>Failed: " + r.error.description + "</span>";
  }});
  rzp.open();
}}
</script></body></html>"""

            st.components.v1.html(html, height=110)

        if st.button("Cancel"):
            st.session_state.pop("show_checkout", None)
            st.session_state.pop("selected_plan", None)
            st.rerun()

st.divider()
st.subheader("Payment History")
history = get_history()
if not history:
    st.info("No payments yet.")
else:
    import pandas as pd
    df = pd.DataFrame(history)
    if "amount" in df.columns:
        df["amount"] = df["amount"].apply(lambda x: f"₹{x//100}" if isinstance(x, int) else x)
    if "created_at" in df.columns:
        df["created_at"] = df["created_at"].apply(lambda x: x[:10] if x else "")
    cols = [c for c in ["created_at","plan","amount","status","payment_id"] if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)