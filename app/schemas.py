from pydantic import BaseModel

class CustomerCreate(BaseModel):
    customer_id: int
    name: str
    phone: str
    address: str
    interest: int
    net_given: int
    loan_date: str
    due_date: str

class TransactionCreate(BaseModel):
    customer_id: int
    amount_paid: int   # ✅ FIXED
    payment_date: str

class ExpenseCreate(BaseModel):
    amount: int
    note: str
    date: str