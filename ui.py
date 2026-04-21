import streamlit as st
import requests
from datetime import date
from datetime import datetime
import json
import os
import uuid
import time

# ================= RETRY FUNCTION =================
def fetch_with_retry(url):
    for i in range(3):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                return res.json()
        except:
            time.sleep(2)
    return None

# ================= ONLINE CHECK =================
def is_online():
    try:
        requests.get("https://vel-finance-api.onrender.com", timeout=2)
        return True
    except:
        return False

LOCAL_FILE = "offline_transactions.json"

if not os.path.exists(LOCAL_FILE):
    with open(LOCAL_FILE, "w") as f:
        json.dump([], f)

# ================= UI =================
st.set_page_config(page_title="VEL Finance", layout="centered")

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

    # ✅ FIXED SUMMARY
    data = fetch_with_retry("https://vel-finance-api.onrender.com/transactions/daily-summary")

    if data:
        st.success(f"💰 Collected: ₹{data['total_collected']}")
        st.error(f"💸 Expense: ₹{data['total_expense']}")
        st.info(f"🧾 Net: ₹{data['net_amount']}")
    else:
        st.warning("⚠️ Backend waking up...")

    # ✅ FIXED EXPENSE
    st.markdown("### 🧾 Expense Details")

    exp_data = fetch_with_retry("https://vel-finance-api.onrender.com/expenses/today")

    if exp_data:
        if len(exp_data["expenses"]) == 0:
            st.write("No expenses today")
        else:
            for e in exp_data["expenses"]:
                st.write(f"₹{e['amount']} → {e['note']}")
    else:
        st.warning("Expense data not available")

    # ✅ FIXED NOT PAID
    st.markdown("### ⚠️ Not Paid Today")

    not_paid = fetch_with_retry("https://vel-finance-api.onrender.com/customers/not-paid-today")

    if not_paid is not None:
        if len(not_paid) == 0:
            st.success("All paid ✅")
        else:
            for c in not_paid:
                st.write(f"{c['customer_id']} - {c['name']}")
    else:
        st.warning("Data not available")

    # ✅ FIXED GAPS
    st.markdown("### 🚨 Not Paid for 3+ Days")

    gap_data = fetch_with_retry("https://vel-finance-api.onrender.com/customers/payment-gaps")

    if gap_data is not None:
        if len(gap_data) == 0:
            st.success("All regular ✅")
        else:
            for c in gap_data:
                if c["last_paid"] == "Never":
                    st.error(f"{c['customer_id']} - {c['name']} ❗ Never Paid")
                else:
                    st.warning(f"{c['customer_id']} - {c['name']} | {c['gap_days']} days gap")
    else:
        st.warning("Data not available")

    # ================= SYNC =================
    st.markdown("## 🔄 Sync Offline Data")

    with open(LOCAL_FILE, "r") as f:
        offline_data = json.load(f)

    st.write(f"Pending Offline Entries: {len(offline_data)}")

    if not is_online():
        st.warning("⚠️ No internet. Cannot sync")
    else:
        if st.button("🚀 SYNC NOW"):

            if len(offline_data) == 0:
                st.info("No offline data to sync")
            else:
                updated_data = []

                for entry in offline_data:
                    if not entry.get("is_synced", False):

                        try:
                            res = requests.post(
                                "https://vel-finance-api.onrender.com/transactions/add",
                                json=entry,
                                timeout=5
                            )

                            if res.status_code == 200:
                                entry["is_synced"] = True

                        except:
                            st.error("⚠️ Connection error")
                            break

                    updated_data.append(entry)

                with open(LOCAL_FILE, "w") as f:
                    json.dump(updated_data, f)

                st.success("✅ Sync completed")
                st.rerun()

# ================= ADD PAYMENT =================
if page == "Add Payment":
    st.markdown("## 💸 Collection Entry")

    with st.form("payment_form", clear_on_submit=True):

        customer_id = st.number_input("Customer ID", step=1, min_value=1)
        amount_paid = st.number_input("Amount", step=10, min_value=1)

        submitted = st.form_submit_button("✅ ADD PAYMENT", use_container_width=True)

        if submitted:

            new_entry = {
                "id": str(uuid.uuid4()),
                "customer_id": int(customer_id),
                "amount_paid": int(amount_paid),
                "payment_date": str(date.today()),
                "is_synced": False
            }

            if is_online():
                try:
                    res = requests.post(
                        "https://vel-finance-api.onrender.com/transactions/add",
                        json=new_entry,
                        timeout=5
                    )

                    if res.status_code == 200:
                        st.success("✅ Payment added online")
                        st.stop()  # ✅ FIX

                    else:
                        st.warning("⚠️ API failed, saving offline")

                except:
                    st.warning("⚠️ Backend not responding, saving offline")

            # ✅ ONLY runs if failed
            with open(LOCAL_FILE, "r") as f:
                data = json.load(f)

            data.append(new_entry)

            with open(LOCAL_FILE, "w") as f:
                json.dump(data, f)

            st.success("📥 Saved Offline")

# ================= ADD EXPENSE =================
if page == "Add Expense":
    st.markdown("## 💸 Add Expense")

    amount = st.number_input("Amount", step=10)
    note = st.text_input("Note")

    if st.button("➕ ADD EXPENSE", use_container_width=True):

        res = requests.post(
            "https://vel-finance-api.onrender.com/expenses/add",
            json={
                "amount": int(amount),
                "note": note,
                "date": str(date.today())
            }
        )

        if res.status_code == 200:
            st.success(f"Added ₹{amount}")
            st.rerun()
        else:
            st.error("Error")

# ================= VIEW CUSTOMER =================
if page == "View Customer":
    st.markdown("## 🔍 Customer Details")

    customers = fetch_with_retry("https://vel-finance-api.onrender.com/customers/")

    if not customers:
        st.error("Error")
        st.stop()

    options = {
        f"{c['customer_id']} - {c['name']}": c["customer_id"]
        for c in customers
    }

    selected = st.selectbox("Select Customer", list(options.keys()))

    if selected:
        cid = options[selected]

        data = fetch_with_retry(
            f"https://vel-finance-api.onrender.com/transactions/customer/{cid}"
        )

        if data:
            st.markdown("### 👤 Basic Info")
            st.write(f"🆔 ID: {data['customer_id']}")
            st.write(f"👤 Name: {data['name']}")
            st.write(f"📞 Phone: {data['phone']}")
            st.write(f"🏠 Address: {data['address']}")

            st.markdown("### 💰 Loan Info")
            st.write(f"Loan Amount: ₹{data['loan_amount']}")
            st.write(f"Interest: {data['interest']}")

            loan_date = datetime.strptime(data["loan_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
            due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%d-%m-%Y")

            st.write(f"Loan Date: {loan_date}")
            st.write(f"Due Date: {due_date}")

            st.markdown("### 📊 Status")
            st.success(f"Balance: ₹{data['balance']}")
            st.write(f"Status: {data['status']}")
            st.write(f"Overdue Days: {data['overdue_days']}")
            st.write(f"Total Paid: ₹{data['total_paid']}")

            st.markdown("### 💵 Transactions")

            if len(data["transactions"]) == 0:
                st.write("No transactions yet")
            else:
                for t in data["transactions"]:
                    payment_date = datetime.strptime(t["payment_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
                    st.write(f"₹{t['amount_paid']} → {payment_date}")
        else:
            st.error("Error loading customer")

# ================= ADD CUSTOMER =================
if page == "Add Customer":
    st.markdown("## ➕ Add Customer")

    with st.form("customer_form", clear_on_submit=True):

        customer_id = st.number_input("Customer ID", step=1, min_value=1)
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        address = st.text_input("Address")
        interest = st.number_input("Interest", step=1, min_value=1)
        net_given = st.number_input("Loan Amount", step=100, min_value=1)

        loan_date_input = st.date_input("Loan Date")
        due_date_input = st.date_input("Due Date")

        submitted = st.form_submit_button("✅ ADD CUSTOMER", use_container_width=True)

        if submitted:
            loan_date = loan_date_input.strftime("%Y-%m-%d")
            due_date = due_date_input.strftime("%Y-%m-%d")

            res = requests.post(
                "https://vel-finance-api.onrender.com/customers/add",
                json={
                    "customer_id": int(customer_id),
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "interest": int(interest),
                    "net_given": int(net_given),
                    "loan_date": loan_date,
                    "due_date": due_date
                }
            )

            if res.status_code == 200:
                st.success(f"✅ Customer {name} added")
                st.balloons()
            else:
                st.error("❌ Error adding customer")