from fastapi import APIRouter
from app.db import supabase
from app.schemas import CustomerCreate

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/add")
def add_customer(data: CustomerCreate):
    customer = data.dict()

    res = supabase.table("customers").insert(customer).execute()
    return res.data


@router.get("/")
def get_customers():
    res = supabase.table("customers").select("*").execute()
    return res.data

from datetime import date

@router.get("/not-paid-today")
def get_not_paid_today():

    today = date.today().isoformat()

    # 1. Get all customers
    customers_res = supabase.table("customers").select("*").execute()
    customers = customers_res.data

    # 2. Get today's transactions
    txn_res = supabase.table("transactions") \
        .select("customer_id") \
        .eq("payment_date", today) \
        .execute()

    paid_customer_ids = {t["customer_id"] for t in txn_res.data}

    # 3. Find customers not paid today
    not_paid = [
        c for c in customers
        if c["customer_id"] not in paid_customer_ids
    ]

    return not_paid

@router.get("/payment-gaps")
def get_payment_gaps():

    from datetime import date

    today = date.today()

    # 1. Get all customers
    customers_res = supabase.table("customers").select("*").execute()
    customers = customers_res.data

    result = []

    for c in customers:
        cid = c["customer_id"]

        # 2. Get latest transaction
        txn_res = supabase.table("transactions") \
            .select("payment_date") \
            .eq("customer_id", cid) \
            .order("payment_date", desc=True) \
            .limit(1) \
            .execute()

        if txn_res.data:
            last_paid_str = txn_res.data[0]["payment_date"]

            # Handle date safely
            if isinstance(last_paid_str, str):
                last_paid = date.fromisoformat(last_paid_str)
            else:
                last_paid = last_paid_str

            gap_days = (today - last_paid).days

            # Show only if gap > 1
            if gap_days >= 3:
                result.append({
                    "customer_id": cid,
                    "name": c["name"],
                    "last_paid": str(last_paid),
                    "gap_days": gap_days
                })

        else:
            # Never paid
            result.append({
                "customer_id": cid,
                "name": c["name"],
                "last_paid": "Never",
                "gap_days": -1,
                "status": "Never Paid"
            })

    return result