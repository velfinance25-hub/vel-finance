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

        txn_res = supabase.table("transactions").select("*").execute()
        all_txns = txn_res.data or []

        paid_map = {}
        for t in all_txns:
            cid = t.get("customer_id")
            paid_map[cid] = paid_map.get(cid, 0) + (t.get("amount_paid", 0) or 0)

        total_outstanding = 0
        for c in customers:
            paid = paid_map.get(c["customer_id"], 0)
            balance = (c.get("net_given") or 0) - paid
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
    

@router.get("/weekly-summary")
def weekly_summary():
    try:
        from datetime import datetime, timedelta

        result = []

        for i in range(6, -1, -1):
            day = (datetime.today() - timedelta(days=i)).date().isoformat()

            # collection
            t = supabase.table("transactions") \
                .select("amount_paid") \
                .eq("payment_date", day) \
                .execute()

            total_collection = sum(x["amount_paid"] for x in (t.data or []))

            # expense
            e = supabase.table("expenses") \
                .select("amount") \
                .eq("date", day) \
                .execute()

            total_expense = sum(x["amount"] for x in (e.data or []))

            result.append({
                "date": day,
                "collection": total_collection,
                "expense": total_expense,
                "net": total_collection - total_expense
            })

        return result

    except Exception as e:
        return {"error": str(e)}
    

def get_not_paid_logic():
    from datetime import date

    today = date.today().isoformat()

    customers = supabase.table("customers").select("*").execute().data or []

    txns = supabase.table("transactions") \
        .select("customer_id") \
        .eq("payment_date", today) \
        .execute().data or []

    paid_today = set(t["customer_id"] for t in txns)

    not_paid = []

    for c in customers:
        if c["customer_id"] not in paid_today:
            not_paid.append({
                "customer_id": c["customer_id"],
                "name": c["name"]
            })

    return not_paid

def get_gaps_logic():
    from datetime import date

    today = date.today()

    customers = supabase.table("customers").select("*").execute().data or []

    all_txns = supabase.table("transactions").select("*").execute().data or []

    txn_map = {}
    for t in all_txns:
        cid = t["customer_id"]
        txn_map.setdefault(cid, []).append(t)

    gaps = []

    for c in customers:
        transactions = txn_map.get(c["customer_id"], [])

        if not transactions:
            gaps.append({
                "customer_id": c["customer_id"],
                "name": c["name"],
                "last_paid": "Never"
            })
            continue

        last_payment = max(
            date.fromisoformat(t["payment_date"]) for t in transactions
        )

        gap_days = (today - last_payment).days

        if gap_days > 1:
            gaps.append({
                "customer_id": c["customer_id"],
                "name": c["name"],
                "gap_days": gap_days,
                "last_paid": str(last_payment)
            })

    return gaps
@router.get("/dashboard")
def get_dashboard():
    try:
        summary = get_daily_summary()
        not_paid = get_not_paid_logic()
        gaps = get_gaps_logic()

        return {
            "summary": summary,
            "not_paid": not_paid,
            "gaps": gaps
        }

    except Exception as e:
        return {"error": str(e)}



