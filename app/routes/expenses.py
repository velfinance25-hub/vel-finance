from fastapi import APIRouter
from app.db import supabase
from app.schemas import ExpenseCreate

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("/add")
def add_expense(data: ExpenseCreate):
    expense = data.dict()

    res = supabase.table("expenses").insert(expense).execute()
    return res.data


@router.get("/today")
def get_today_expense():

    from datetime import date

    today = date.today().isoformat()

    res = supabase.table("expenses") \
        .select("*") \
        .eq("date", today) \
        .execute()

    expenses = res.data

    total_expense = sum(e["amount"] for e in expenses)

    return {
        "date": today,
        "total_expense": total_expense,
        "expenses": expenses
    }