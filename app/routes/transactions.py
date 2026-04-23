from fastapi import APIRouter
from app.db import supabase
from app.schemas import TransactionCreate
from datetime import date

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/add")
def add_transaction(data: TransactionCreate):
    transaction = data.dict()

    res = supabase.table("transactions").insert(transaction).execute()
    return res.data


@router.get("/customer/{customer_id}")
def get_customer_balance(customer_id: int):

    from datetime import date

    # 1. Get customer
    customer_res = supabase.table("customers") \
        .select("*") \
        .eq("customer_id", customer_id) \
        .execute()

    if not customer_res.data:
        return {"error": "Customer not found"}

    customer = customer_res.data[0]

    # 2. Get transactions
    txn_res = supabase.table("transactions") \
        .select("*") \
        .eq("customer_id", customer_id) \
        .execute()

    transactions = txn_res.data

    # 3. Total paid (SAFE)
    total_paid = sum(t.get("amount_paid", 0) or 0 for t in transactions)

    # 4. Balance
    balance = (customer.get("net_given") or 0) - total_paid

    # 5. Overdue calculation
    today = date.today()

    due_date_raw = customer.get("due_date")

    if due_date_raw:
        try:
            if isinstance(due_date_raw, str):
                due_date = date.fromisoformat(due_date_raw)
            else:
                due_date = due_date_raw
        except:
            due_date = None
    else:
        due_date = None

    if due_date and today > due_date:
        overdue_days = (today - due_date).days
        status = "OVERDUE"
    else:
        overdue_days = 0
        status = "ON TIME"

    return {
        "customer_id": customer_id,
        "name": customer.get("name"),
        "phone": customer.get("phone"),
        "address": customer.get("address"),
        "interest": customer.get("interest"),
        "loan_amount": customer.get("net_given"),
        "loan_date": customer.get("loan_date"),
        "due_date": customer.get("due_date"),
        "total_paid": total_paid,
        "balance": balance,
        "status": status,
        "overdue_days": overdue_days,
        "transactions": transactions
    }

@router.get("/daily-summary")
def get_daily_summary():
    from datetime import date

    today = date.today().isoformat()

    try:
        # 1. Get today's transactions
        t_res = supabase.table("transactions") \
            .select("*") \
            .eq("payment_date", today) \
            .execute()

        transactions = t_res.data if t_res.data else []

        total_collected = sum(
            t.get("amount_paid", 0) for t in transactions
        )

        # 2. Get today's expenses
        e_res = supabase.table("expenses") \
            .select("*") \
            .eq("date", today) \
            .execute()

        expenses = e_res.data if e_res.data else []

        total_expense = sum(
            e.get("amount", 0) for e in expenses
        )

        # 3. Calculate net
        net_amount = total_collected - total_expense

        # ✅ 4. Total Outstanding (Money with customers)
        cust_res = supabase.table("customers").select("*").execute()
        customers = cust_res.data if cust_res.data else []

        total_outstanding = 0

        for c in customers:
            txn_res = supabase.table("transactions") \
                .select("*") \
                .eq("customer_id", c["customer_id"]) \
                .execute()

            txns = txn_res.data if txn_res.data else []

            paid = sum(t.get("amount_paid", 0) for t in txns)
            balance = c.get("net_given", 0) - paid

            total_outstanding += balance

        # ✅ FINAL RETURN (ALL VALUES)
        return {
            "date": today,
            "total_collected": total_collected,
            "total_expense": total_expense,
            "net_amount": net_amount,
            "total_outstanding": total_outstanding
        }

    except Exception as e:
        return {
            "error": str(e)
        }
    
@router.get("/summary-by-date/{selected_date}")
def summary_by_date(selected_date: str):
    try:
        # Transactions
        t_res = supabase.table("transactions") \
            .select("*") \
            .eq("payment_date", selected_date) \
            .execute()

        transactions = t_res.data or []
        total_collection = sum(t.get("amount_paid", 0) for t in transactions)

        # Expenses
        e_res = supabase.table("expenses") \
            .select("*") \
            .eq("date", selected_date) \
            .execute()

        expenses = e_res.data or []
        total_expense = sum(e.get("amount", 0) for e in expenses)

        return {
            "date": selected_date,
            "collection": total_collection,
            "expense": total_expense,
            "net": total_collection - total_expense,
            "transactions": transactions,
            "expenses": expenses
        }

    except Exception as e:
        return {"error": str(e)}