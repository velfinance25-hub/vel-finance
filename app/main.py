from fastapi import FastAPI
from app.routes import customers, transactions, expenses   # ✅ add this
from app.db import supabase

app = FastAPI()

app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(expenses.router)          # ✅ add this

@app.get("/")
def root():
    return {"message": "VEL Finance Running"}

@app.get("/health")
def health():
    try:
        supabase.table("customers").select("customer_id").limit(1).execute()
    except:
        pass
    return {"status": "ok"}