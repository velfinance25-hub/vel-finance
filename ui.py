import streamlit as st
import requests
from datetime import date
from datetime import datetime
import json
import os
import uuid

def is_online():
    try:
        requests.get("http://127.0.0.1:8000", timeout=2)
        return True
    except:
        return False

LOCAL_FILE = "offline_transactions.json"

if not os.path.exists(LOCAL_FILE):
    with open(LOCAL_FILE, "w") as f:
        json.dump([], f)

# Page config for mobile
st.set_page_config(page_title="VEL Finance", layout="centered")

# Sidebar navigation (keep minimal)
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

    res = requests.get("http://127.0.0.1:8000/transactions/daily-summary")

    if res.status_code == 200:
        data = res.json()

        st.success(f"💰 Collected: ₹{data['total_collected']}")
        st.error(f"💸 Expense: ₹{data['total_expense']}")
        st.info(f"🧾 Net: ₹{data['net_amount']}")

        # Expense breakdown
        st.markdown("### 🧾 Expense Details")

        res_exp = requests.get("http://127.0.0.1:8000/expenses/today")

        if res_exp.status_code == 200:
            exp_data = res_exp.json()

            if len(exp_data["expenses"]) == 0:
                st.write("No expenses today")
            else:
                for e in exp_data["expenses"]:
                    st.write(f"₹{e['amount']} → {e['note']}")
        else:
            st.error("Error loading expenses")

    else:
        st.error("❌ Failed to load summary")

    # Not paid today
    st.markdown("### ⚠️ Not Paid Today")

    res = requests.get("http://127.0.0.1:8000/customers/not-paid-today")

    if res.status_code == 200:
        data = res.json()

        if len(data) == 0:
            st.success("All paid ✅")
        else:
            for c in data:
                st.write(f"{c['customer_id']} - {c['name']}")
    else:
        st.error("Error")

    # Gap tracking
    st.markdown("### 🚨 Not Paid for 3+ Days")

    res = requests.get("http://127.0.0.1:8000/customers/payment-gaps")

    if res.status_code == 200:
        gap_data = res.json()

        if len(gap_data) == 0:
            st.success("All regular ✅")
        else:
            for c in gap_data:
                if c["last_paid"] == "Never":
                    st.error(f"{c['customer_id']} - {c['name']} ❗ Never Paid")
                else:
                    st.warning(
                        f"{c['customer_id']} - {c['name']} | {c['gap_days']} days gap"
                    )
    else:
        st.error("Error")

    # SYNCCCCCCCCCCCC

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
                if not entry.get("is_synced", False):  # only unsynced

                    try:
                        res = requests.post(
                            "http://127.0.0.1:8000/transactions/add",
                            json=entry,
                            timeout=5
                        )

                        if res.status_code == 200:
                            entry["is_synced"] = True  # mark synced

                    except:
                        st.error("⚠️ Connection error. Check internet")
                        break

                updated_data.append(entry)

            # Save updated file
            with open(LOCAL_FILE, "w") as f:
                json.dump(updated_data, f)

            st.success("✅ Sync completed")

# ================= ADD PAYMENT =================
if page == "Add Payment":
    st.markdown("## 💸 Collection Entry")

    with st.form("payment_form", clear_on_submit=True):

        customer_id = st.number_input(
            "Customer ID",
            step=1,
            min_value=1,
            value=None,
            placeholder="Enter ID"
        )

        amount_paid = st.number_input(
            "Amount",
            step=10,
            min_value=1,
            value=None,
            placeholder="Enter amount"
        )

        submitted = st.form_submit_button("✅ ADD PAYMENT", use_container_width=True)

        if submitted:

            if not customer_id or not amount_paid:
                st.warning("Enter valid data")
            else:
                new_entry = {
                    "id": str(uuid.uuid4()),   # NEW
                    "customer_id": int(customer_id),
                    "amount_paid": int(amount_paid),
                    "payment_date": str(date.today()),
                    "is_synced": False         # NEW
                }

                with open(LOCAL_FILE, "r") as f:
                    data = json.load(f)

                data.append(new_entry)

                with open(LOCAL_FILE, "w") as f:
                    json.dump(data, f)

                st.success(f"📥 Saved Offline → ID {customer_id} ₹{amount_paid}")


# ================= ADD EXPENSE =================
if page == "Add Expense":
    st.markdown("## 💸 Add Expense")

    amount = st.number_input("Amount", step=10)
    note = st.text_input("Note")

    if st.button("➕ ADD EXPENSE", use_container_width=True):

        if amount == 0 or note == "":
            st.warning("Enter valid data")
        else:
            res = requests.post(
                "http://127.0.0.1:8000/expenses/add",
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

    res = requests.get("http://127.0.0.1:8000/customers/")

    if res.status_code != 200:
        st.error("Error")
        st.stop()

    customers = res.json()

    options = {
        f"{c['customer_id']} - {c['name']}": c["customer_id"]
        for c in customers
    }

    selected = st.selectbox("Select Customer", list(options.keys()))

    if selected:
        cid = options[selected]

        res = requests.get(
            f"http://127.0.0.1:8000/transactions/customer/{cid}"
        )

        if res.status_code == 200:
            data = res.json()

            # 🔹 Basic Info
            st.markdown("### 👤 Basic Info")
            st.write(f"🆔 ID: {data['customer_id']}")
            st.write(f"👤 Name: {data['name']}")
            st.write(f"📞 Phone: {data['phone']}")
            st.write(f"🏠 Address: {data['address']}")

            # 🔹 Loan Info
            st.markdown("### 💰 Loan Info")
            st.write(f"Loan Amount: ₹{data['loan_amount']}")
            st.write(f"Interest: {data['interest']}")
            loan_date = datetime.strptime(data["loan_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
            due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
            st.write(f"Loan Date: {loan_date}")
            st.write(f"Due Date: {due_date}")

            # 🔹 Status
            st.markdown("### 📊 Status")
            st.success(f"Balance: ₹{data['balance']}")
            st.write(f"Status: {data['status']}")
            st.write(f"Overdue Days: {data['overdue_days']}")
            st.write(f"Total Paid: ₹{data['total_paid']}")

            # 🔹 Transactions
            st.markdown("### 💵 Transactions")

            if len(data["transactions"]) == 0:
                st.write("No transactions yet")
            else:
                for t in data["transactions"]:
                    payment_date = datetime.strptime(t["payment_date"], "%Y-%m-%d").strftime("%d-%m-%Y")
                    st.write(f"₹{t['amount_paid']} → {payment_date}")


# ================= ADD CUSTOMER =================
if page == "Add Customer":
    st.markdown("## ➕ Add Customer")

    with st.form("customer_form", clear_on_submit=True):

        customer_id = st.number_input(
            "Customer ID",
            step=1,
            min_value=1,
            value=None,
            placeholder="Enter ID"
        )

        name = st.text_input("Name", placeholder="Enter name")
        phone = st.text_input("Phone", placeholder="Enter phone")
        address = st.text_input("Address", placeholder="Enter address")

        interest = st.number_input(
            "Interest",
            step=1,
            min_value=1,
            value=None,
            placeholder="Enter interest"
        )

        net_given = st.number_input(
            "Loan Amount",
            step=100,
            min_value=1,
            value=None,
            placeholder="Enter amount"
        )

        loan_date_input = st.date_input("Loan Date")
        due_date_input = st.date_input("Due Date")

        submitted = st.form_submit_button("✅ ADD CUSTOMER", use_container_width=True)

        if submitted:

            if not customer_id or not name or not net_given:
                st.warning("Enter required fields")
            else:
                try:
                    loan_date = loan_date_input.strftime("%Y-%m-%d")
                    due_date = due_date_input.strftime("%Y-%m-%d")
                except:
                    st.error("❌ Invalid date format. Use DD-MM-YYYY")
                    st.stop()

                res = requests.post(
                    "http://127.0.0.1:8000/customers/add",
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