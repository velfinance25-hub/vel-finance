import streamlit as st
import requests
from datetime import date
import time

st.set_page_config(page_title="VEL Finance", layout="wide")

# ================= STYLE =================
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
}
.stButton>button {
    width: 100%;
    border-radius: 10px;
    height: 45px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

API_BASE = "https://vel-finance-api.onrender.com"

# ================= HELPERS =================
def fetch_with_retry(url):
    for _ in range(3):
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(1)
    return None


def is_online():
    try:
        requests.get(API_BASE, timeout=3)
        return True
    except:
        return False


# ================= SIDEBAR =================
page = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Add Payment", "Add Expense", "View Customer", "Add Customer"]
)

st.markdown("<h1 style='text-align:center;'>💰 VEL Finance</h1>", unsafe_allow_html=True)

# ================= STATUS =================
if is_online():
    st.success("🟢 Online Mode")
else:
    st.error("🔴 Server not reachable")

# ================= DASHBOARD =================
if page == "Dashboard":
    st.markdown("## 📊 Today Summary")

    data = fetch_with_retry(f"{API_BASE}/transactions/daily-summary")

    if data:
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("💰 Collected", f"₹{data['total_collected']}")
        col2.metric("💸 Expense", f"₹{data['total_expense']}")
        col3.metric("📊 Net", f"₹{data['net_amount']}")
        col4.metric("🏦 Outstanding", f"₹{data.get('total_outstanding', 0)}")
    else:
        st.warning("⚠️ Backend waking up...")

# ================= ADD PAYMENT =================
if page == "Add Payment":
    st.markdown("## 💸 Collection Entry")

    customers = fetch_with_retry(f"{API_BASE}/customers/")

    if not customers:
        st.error("Failed to load customers")
        st.stop()

    options = {
        f"{c['customer_id']} - {c['name']}": c["customer_id"]
        for c in customers
    }

    selected = st.selectbox("Select Customer", list(options.keys()))
    customer_id = options[selected]

    amount_paid = st.number_input("Amount", min_value=1, step=10)

    if st.button("✅ ADD PAYMENT", use_container_width=True):

        if amount_paid <= 0:
            st.warning("Enter valid amount")
            st.stop()

        try:
            with st.spinner("Processing payment..."):
                res = requests.post(
                    f"{API_BASE}/transactions/add",
                    json={
                        "customer_id": customer_id,
                        "amount_paid": int(amount_paid),
                        "payment_date": str(date.today())
                    },
                    timeout=10
                )

            if res.status_code == 200:
                st.success("✅ Payment added successfully")
                st.toast("Saved ✔")
                st.rerun()
            else:
                st.error("❌ Failed to add payment")

        except:
            st.error("❌ Server not reachable")


# ================= ADD EXPENSE =================
if page == "Add Expense":
    st.markdown("## 💸 Add Expense")

    amount = st.number_input("Amount", min_value=1, step=10)
    note = st.text_input("Note")

    if st.button("➕ ADD EXPENSE", use_container_width=True):

        if amount <= 0 or not note:
            st.error("Enter valid data")
            st.stop()

        try:
            with st.spinner("Adding expense..."):
                res = requests.post(
                    f"{API_BASE}/expenses/add",
                    json={
                        "amount": int(amount),
                        "note": note,
                        "date": str(date.today())
                    },
                    timeout=10
                )

            if res.status_code == 200:
                st.success(f"✅ Expense added ₹{amount}")
                st.toast("Expense saved ✔")
                st.rerun()
            else:
                st.error("❌ Failed to add expense")

        except:
            st.error("❌ Connection error")


# ================= VIEW CUSTOMER =================
if page == "View Customer":
    st.markdown("## 🔍 Customer Details")

    customers = fetch_with_retry(f"{API_BASE}/customers/")

    if not customers:
        st.error("Failed to load customers")
        st.stop()

    search = st.text_input("Search Customer")

    filtered = [
        c for c in customers
        if search.lower() in c["name"].lower()
    ]

    options = {
        f"{c['customer_id']} - {c['name']}": c["customer_id"]
        for c in filtered
    }

    selected = st.selectbox("Select Customer", list(options.keys()))

    if selected:
        cid = options[selected]

        data = fetch_with_retry(f"{API_BASE}/transactions/customer/{cid}")

        if data:
            st.write(f"👤 {data['name']} | Balance: ₹{data['balance']}")
            st.write(f"📞 {data['phone']}")

            st.markdown("### 💸 Quick Payment")

            amount = st.number_input("Pay Amount", min_value=1, step=10)

            if st.button("Pay Now"):
                try:
                    res = requests.post(
                        f"{API_BASE}/transactions/add",
                        json={
                            "customer_id": cid,
                            "amount_paid": int(amount),
                            "payment_date": str(date.today())
                        }
                    )

                    if res.status_code == 200:
                        st.success("Payment added")
                        st.rerun()
                    else:
                        st.error("Failed")

                except:
                    st.error("Error")

            st.markdown("### 💵 Transactions")

            for t in data["transactions"]:
                st.write(f"₹{t['amount_paid']} → {t['payment_date']}")
        else:
            st.error("Error loading data")


# ================= ADD CUSTOMER =================
if page == "Add Customer":
    st.markdown("## ➕ Add Customer")

    with st.form("customer_form", clear_on_submit=True):

        customer_id = st.number_input("Customer ID", min_value=1)
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        interest = st.number_input("Interest %", min_value=0)
        net_given = st.number_input("Loan Amount", min_value=1)

        loan_date = st.date_input("Loan Date")
        due_date = st.date_input("Due Date")

        submitted = st.form_submit_button("✅ ADD CUSTOMER")

        if submitted:

            if not name or not phone or not address:
                st.error("Fill all fields")
                st.stop()

            try:
                res = requests.post(
                    f"{API_BASE}/customers/add",
                    json={
                        "customer_id": int(customer_id),
                        "name": name,
                        "phone": phone,
                        "address": address,
                        "interest": int(interest),
                        "net_given": int(net_given),
                        "loan_date": str(loan_date),
                        "due_date": str(due_date)
                    },
                    timeout=10
                )

                if res.status_code == 200:
                    st.success(f"✅ Customer {name} added")
                    st.rerun()
                else:
                    st.error("❌ API error")

            except:
                st.error("❌ Connection error")