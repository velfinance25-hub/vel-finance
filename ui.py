import streamlit as st
import requests
from datetime import date
import time
from concurrent.futures import ThreadPoolExecutor

# ✅ MUST BE FIRST STREAMLIT CALL
st.set_page_config(page_title="VEL Finance", layout="wide")

# 🎨 UI STYLE
st.markdown("""
<style>
.block-container {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
}
.stButton>button {
    width: 100%;
    border-radius: 10px;
    height: 45px;
    font-weight: bold;
}
.stTextInput>div>div>input {
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)


API_BASE = "https://vel-finance-api.onrender.com"



# 🔥 WARMUP
def warmup():
    try:
        requests.get(f"{API_BASE}/health", timeout=5)
    except:
        pass

warmup()



# ================= HELPERS =================

@st.cache_data(ttl=30)
def fetch_with_retry(url):
    for _ in range(3):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(2)
    return None

@st.cache_data(ttl=10)
def load_dashboard():
    return {
        "summary": fetch_with_retry(f"{API_BASE}/transactions/daily-summary"),
        "expenses": fetch_with_retry(f"{API_BASE}/expenses/today"),
        "not_paid": fetch_with_retry(f"{API_BASE}/customers/not-paid-today"),
        "gaps": fetch_with_retry(f"{API_BASE}/customers/payment-gaps")
    }

if "customers" not in st.session_state:
    st.session_state["customers"] = fetch_with_retry(f"{API_BASE}/customers/")


def is_online():
    try:
        requests.get(f"{API_BASE}/health", timeout=3)
        return True
    except:
        return False
    
# ================= SIDEBAR =================
page = st.sidebar.selectbox("Menu", [
    "Dashboard",
    "View Customer",
    "Add Customer",
    "Add Payment",
    "History"   # 👈 ADD THIS
])

st.title("💰 VEL Finance")

if "msg" in st.session_state:
    st.success(st.session_state["msg"])
    del st.session_state["msg"]

if is_online():
    st.success("🟢 Online Mode")
else:
    st.error("🔴 No Internet / Server Down")

# ================= DASHBOARD =================
if page == "Dashboard":
    st.markdown("## 📊 Today Summary")

    with st.spinner("Loading data..."):
        data_all = load_dashboard()

    data = data_all["summary"]
    exp = data_all["expenses"]
    np = data_all["not_paid"]
    gaps = data_all["gaps"]

        

    if data:
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("💰 Collected", f"₹{data['total_collected']}")
        col2.metric("💸 Expense", f"₹{data['total_expense']}")
        col3.metric("📊 Net", f"₹{data['net_amount']}")
        col4.metric("🏦 Outstanding", f"₹{data.get('total_outstanding', 0)}")
    else:
        st.info("Loading data, please wait...")

    # Expense
    st.markdown("### 🧾 Expense Details")

    if exp and len(exp["expenses"]) > 0:
        for e in exp["expenses"]:
            st.write(f"₹{e['amount']} → {e['note']}")
    else:
        st.info("No expenses today")

    # Not paid
    st.markdown("### ⚠️ Not Paid Today")

    if np:
        for c in np:
            st.warning(f"{c['customer_id']} - {c['name']}")
    else:
        st.success("All paid ✅")

    # Gaps
    st.markdown("### 🚨 Payment Gaps")

    if gaps:
        for c in gaps:
            if c["last_paid"] == "Never":
                st.error(f"{c['customer_id']} - {c['name']} ❗ Never Paid")
            else:
                st.warning(f"{c['customer_id']} - {c['name']} | {c['gap_days']} days gap")
    else:
        st.success("All regular ✅")


# ================= ADD PAYMENT =================
if page == "Add Payment":
    
    st.markdown("## 💸 Collection Entry")

    with st.form("payment_form", clear_on_submit=True):

        customers = st.session_state.get("customers", [])

        options = {f"{c['customer_id']} - {c['name']}": c["customer_id"] for c in customers} if customers else {}

        if options:
            selected = st.selectbox("Select Customer", list(options.keys()))
            customer_id = options[selected]
        else:
            st.warning("No customers available or server issue")
            st.stop()
        amount_paid = st.number_input("Amount", step=10, min_value=0, value=None, placeholder="Enter amount")

        submitted = st.form_submit_button("✅ ADD PAYMENT", use_container_width=True)

        if submitted:
            if amount_paid <= 0:
                st.warning("Enter valid amount")
                st.stop()

            try:
                with st.spinner("Processing..."):
                    res = requests.post(
                        f"{API_BASE}/transactions/add",
                        json={
                            "customer_id": int(customer_id),
                            "amount_paid": int(amount_paid),
                            "payment_date": str(date.today())
                        },
                        timeout=5
                    )

                if res.status_code == 200:
                    st.success("Payment added successfully")
# update locally (instant UI update)
                    if "customers" in st.session_state:
                        st.session_state["customers"] = fetch_with_retry(f"{API_BASE}/customers/")
                else:
                    st.error("❌ Failed to add payment")

            except Exception as e:
                if "timeout" in str(e).lower():
                    st.warning("⚠️ Server slow, but payment may be saved")
                else:
                    st.error("❌ No internet / server issue")


# ================= ADD EXPENSE =================
if page == "Add Expense":

    st.markdown("## 💸 Add Expense")

    amount = st.number_input("Amount", step=10, min_value=0, value=None, placeholder="Enter amount")
    note = st.text_input("Note", placeholder="Enter expense note")

    if st.button("➕ ADD EXPENSE", use_container_width=True):

        if amount <= 0 or not note.strip():
            st.error("Enter valid amount")
            st.stop()

        try:
            with st.spinner("Processing..."):
                res = requests.post(
                    f"{API_BASE}/expenses/add",
                    json={
                        "amount": int(amount),
                        "note": note,
                        "date": str(date.today())
                    },
                    timeout=5
                )

            if res.status_code == 200:
                st.success(f"Expense added ₹{amount}")
            else:
                st.error("❌ Failed to add expense")

        except Exception as e:
            if "timeout" in str(e).lower():
                st.warning("⚠️ Server slow, but expense may be saved")
            else:
                st.error("❌ Connection error")


# ================= VIEW CUSTOMER =================
if page == "View Customer":
  
    st.markdown("## 🔍 Customer Details")

    customers = st.session_state.get("customers", [])

    if not customers:
        st.error("Failed to load customers")
        st.stop()

    search = st.text_input("Search Customer") or ""

    filtered = [
        c for c in customers
        if search.lower() in c["name"].lower()
    ]

    options = {
        f"{c['customer_id']} - {c['name']}": c["customer_id"]
        for c in filtered
    }

    if options:
        selected = st.selectbox("Select Customer", list(options.keys()))
        cid = options[selected]
    else:
        st.warning("⚠️ No customers found")
        st.stop()

    # ✅ MUST BE HERE (NOT inside else)
    data = fetch_with_retry(f"{API_BASE}/transactions/customer/{cid}")

    if data:
        st.write(f"👤 {data['name']} | Balance: ₹{data['balance']}")
        st.write(f"📞 {data['phone']}")
        if st.button("🗑️ Delete Customer"):
            st.session_state["confirm_delete"] = True

        if st.session_state.get("confirm_delete"):
            st.warning("Are you sure you want to delete this customer?")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Yes, Delete"):
                    try:
                        res = requests.delete(f"{API_BASE}/customers/delete/{cid}")
                        data = res.json()

                        if res.status_code == 200 and "message" in data:
                            st.success("Customer deleted successfully")
                            st.session_state["confirm_delete"] = False
                            st.session_state["customers"] = fetch_with_retry(f"{API_BASE}/customers/")
                        else:
                            st.error(data.get("error", "Delete failed"))

                    except Exception as e:
                        st.error(f"Error: {e}")

            with col2:
                if st.button("❌ Cancel"):
                    st.session_state["confirm_delete"] = False

        st.markdown("### 💸 Quick Payment")

        amount = st.number_input("Amount", step=10, min_value=0, value=None, placeholder="Enter amount")

        if "payment_done" not in st.session_state:
            st.session_state.payment_done = False

        if st.button("Pay Now", disabled=st.session_state.payment_done):

            if not amount or amount <= 0:
                st.error("Enter valid amount")
                st.stop()

            st.session_state.payment_done = True

            try:
                with st.spinner("Processing..."):
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
                    st.session_state.payment_done = False
                    st.session_state["customers"] = fetch_with_retry(f"{API_BASE}/customers/")
                else:
                    st.session_state.payment_done = False
                    st.error("Failed")

            except Exception as e:
                st.session_state.payment_done = False
                st.error(f"Error: {e}")

        st.markdown("### 💵 Transactions")
        transactions = data.get("transactions") or data.get("data") or []

        if not transactions:
            st.info("No transactions found")
        else:
            for t in transactions:
                st.write(f"₹{t.get('amount_paid', 0)} → {t.get('payment_date', '-')}")
    else:
        st.error("Error loading data")


# ================= ADD CUSTOMER =================
if page == "Add Customer":
    
    st.markdown("## ➕ Add Customer")   

    with st.form("customer_form", clear_on_submit=True):

        customer_id = st.text_input("Customer ID")
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        interest = st.number_input("Interest", min_value=0, step=1)
        net_given = st.number_input("Loan Amount", min_value=0, value=None, placeholder="Enter amount")

        loan_date = st.date_input("Loan Date")
        due_date = st.date_input("Due Date")

        submitted = st.form_submit_button("✅ ADD CUSTOMER")

        if submitted:

            if not all([customer_id, name, phone, address]):
                st.error("Fill all fields")
                st.stop()

            if net_given is None or net_given <= 0:
                st.error("Enter valid loan amount")
                st.stop()
                
            try:
                with st.spinner("Processing..."):
                    res = requests.post(
                        f"{API_BASE}/customers/add",
                        json={
                            "customer_id": int(customer_id),
                            "name": name,
                            "phone": phone,
                            "address": address,
                            "interest": int(interest) if interest else 0,
                            "net_given": int(net_given),
                            "loan_date": str(loan_date),
                            "due_date": str(due_date)
                        },
                        timeout=5
                    )

                if res.status_code == 200:
                    st.session_state["customers"] = fetch_with_retry(f"{API_BASE}/customers/")
                    st.success(f"Customer {name} added")
                else:
                    st.error(res.text)

            except Exception as e:
                if "timeout" in str(e).lower():
                    st.warning("⚠️ Server slow, but data may be saved")
                else:
                    st.error("❌ Connection error")


# ================= HISTORY =================
if page == "History":

    st.markdown("## 📅 Date-wise Summary")

    selected_date = st.date_input("Select Date")

    # Convert to string (IMPORTANT)
    selected_date_str = str(selected_date)

    data = fetch_with_retry(
        f"{API_BASE}/transactions/summary-by-date/{selected_date_str}"
    )

    if not data or "error" in data:
        st.error("Failed to load summary")
        st.stop()

    # 🔹 Top Summary
    col1, col2, col3 = st.columns(3)

    col1.metric("💰 Collection", f"₹{data['collection']}")
    col2.metric("💸 Expense", f"₹{data['expense']}")
    col3.metric("📊 Net", f"₹{data['net']}")

    st.divider()

    # 🔹 Transactions
    st.markdown("### 💵 Transactions")

    if not data["transactions"]:
        st.info("No transactions for this date")
    else:
        for t in data["transactions"]:
            st.write(f"₹{t.get('amount_paid', 0)} → {t.get('payment_date', '-')}")

    st.divider()

    # 🔹 Expenses
    st.markdown("### 🧾 Expenses")

    if not data["expenses"]:
        st.info("No expenses for this date")
    else:
        for e in data["expenses"]:
            st.write(f"₹{e.get('amount', 0)} → {e.get('note', '-')}")