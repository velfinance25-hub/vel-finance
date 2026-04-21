import streamlit as st
import requests
from datetime import date, datetime
import json
import os
import uuid
import time

API_BASE = "https://vel-finance-api.onrender.com"
LOCAL_FILE = "offline_transactions.json"

# ================= INIT =================
if not os.path.exists(LOCAL_FILE):
    with open(LOCAL_FILE, "w") as f:
        json.dump([], f)

st.set_page_config(page_title="VEL Finance", layout="centered")

# ================= HELPERS =================
def fetch_with_retry(url):
    for _ in range(3):
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(2)
    return None


def is_online():
    try:
        requests.get(API_BASE, timeout=3)
        return True
    except:
        return False


def load_offline():
    with open(LOCAL_FILE, "r") as f:
        return json.load(f)


def save_offline(data):
    with open(LOCAL_FILE, "w") as f:
        json.dump(data, f)

# ================= SIDEBAR =================
page = st.sidebar.selectbox(
    "Menu",
    ["Dashboard", "Add Payment", "Add Expense", "View Customer", "Add Customer"]
)

st.title("💰 VEL Finance")

if is_online():
    st.success("🟢 Online Mode")
else:
    st.error("🔴 Offline Mode")

# ================= DASHBOARD =================
if page == "Dashboard":
    st.markdown("## 📊 Today Summary")

    data = fetch_with_retry(f"{API_BASE}/transactions/daily-summary")

    if data:
        st.success(f"💰 Collected: ₹{data['total_collected']}")
        st.error(f"💸 Expense: ₹{data['total_expense']}")
        st.info(f"🧾 Net: ₹{data['net_amount']}")
    else:
        st.warning("⚠️ Backend waking up...")

    # Expense
    st.markdown("### 🧾 Expense Details")
    exp = fetch_with_retry(f"{API_BASE}/expenses/today")

    if exp and len(exp["expenses"]) > 0:
        for e in exp["expenses"]:
            st.write(f"₹{e['amount']} → {e['note']}")
    else:
        st.info("No expenses today")

    # Not paid
    st.markdown("### ⚠️ Not Paid Today")
    np = fetch_with_retry(f"{API_BASE}/customers/not-paid-today")

    if np:
        for c in np:
            st.warning(f"{c['customer_id']} - {c['name']}")
    else:
        st.success("All paid ✅")

    # Gaps
    st.markdown("### 🚨 Payment Gaps")
    gaps = fetch_with_retry(f"{API_BASE}/customers/payment-gaps")

    if gaps:
        for c in gaps:
            if c["last_paid"] == "Never":
                st.error(f"{c['customer_id']} - {c['name']} ❗ Never Paid")
            else:
                st.warning(f"{c['customer_id']} - {c['name']} | {c['gap_days']} days gap")
    else:
        st.success("All regular ✅")

    # ================= SYNC =================
    st.markdown("## 🔄 Sync Offline Data")

    offline_data = load_offline()
    st.write(f"Pending Offline Entries: {len(offline_data)}")

    if st.button("🚀 SYNC NOW"):

        if not is_online():
            st.error("No internet")
        elif len(offline_data) == 0:
            st.info("Nothing to sync")
        else:
            success = 0

            for entry in offline_data:
                try:
                    res = requests.post(
                        f"{API_BASE}/transactions/add",
                        json=entry,
                        timeout=10
                    )
                    if res.status_code == 200:
                        success += 1
                except:
                    st.error("Sync failed")
                    break

            if success == len(offline_data):
                save_offline([])
                st.success("✅ Sync completed")
                st.rerun()

# ================= ADD PAYMENT =================
if page == "Add Payment":
    st.markdown("## 💸 Collection Entry")

    with st.form("payment_form", clear_on_submit=True):

        customer_id = st.number_input("Customer ID", min_value=1, step=1, value=None)
        amount_paid = st.number_input("Amount", min_value=1, step=10, value=None)

        submitted = st.form_submit_button("✅ ADD PAYMENT", use_container_width=True)

        if submitted:

            if not customer_id or not amount_paid:
                st.error("Enter valid values")
                st.stop()

            entry = {
                "id": str(uuid.uuid4()),
                "customer_id": int(customer_id),
                "amount_paid": int(amount_paid),
                "payment_date": str(date.today()),
                "is_synced": False
            }

            if is_online():
                try:
                    res = requests.post(
                        f"{API_BASE}/transactions/add",
                        json=entry,
                        timeout=10
                    )

                    if res.status_code == 200:
                        st.success("✅ Payment added online")
                        st.stop()

                except:
                    pass

            # fallback
            data = load_offline()
            data.append(entry)
            save_offline(data)

            st.warning("Saved offline")

# ================= ADD EXPENSE =================
if page == "Add Expense":
    st.markdown("## 💸 Add Expense")

    amount = st.number_input("Amount", min_value=1, step=10, value=None)
    note = st.text_input("Note")

    if st.button("➕ ADD EXPENSE", use_container_width=True):

        if not amount or note.strip() == "":
            st.error("Enter valid data")
            st.stop()

        try:
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
                st.rerun()
            else:
                st.error("API Error")

        except:
            st.error("Connection error")

# ================= VIEW CUSTOMER =================
if page == "View Customer":
    st.markdown("## 🔍 Customer Details")

    customers = fetch_with_retry(f"{API_BASE}/customers/")

    if not customers:
        st.error("Failed to load customers")
        st.stop()

    options = {f"{c['customer_id']} - {c['name']}": c["customer_id"] for c in customers}

    selected = st.selectbox("Select Customer", list(options.keys()))

    if selected:
        cid = options[selected]

        data = fetch_with_retry(f"{API_BASE}/transactions/customer/{cid}")

        if data:
            st.write(f"👤 {data['name']} | ₹{data['balance']}")
            st.write(f"📞 {data['phone']}")

            st.markdown("### 💵 Transactions")
            for t in data["transactions"]:
                st.write(f"₹{t['amount_paid']} → {t['payment_date']}")
        else:
            st.error("Error loading data")

# ================= ADD CUSTOMER =================
if page == "Add Customer":
    st.markdown("## ➕ Add Customer")

    with st.form("customer_form", clear_on_submit=True):

        customer_id = st.number_input("Customer ID", min_value=1, value=None)
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        interest = st.number_input("Interest", min_value=1, value=None)
        net_given = st.number_input("Loan Amount", min_value=1, value=None)

        loan_date = st.date_input("Loan Date")
        due_date = st.date_input("Due Date")

        submitted = st.form_submit_button("✅ ADD CUSTOMER")

        if submitted:

            if not all([customer_id, name, phone, address, interest, net_given]):
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
                else:
                    st.error("API error")

            except:
                st.error("Connection error")