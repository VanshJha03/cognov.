import os
import secrets
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union, Annotated, Literal
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, status, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, root_validator
from supabase import create_client, Client
from postgrest.exceptions import APIError

# ---------- Supabase Setup (Hardcoded as requested) ----------
SUPABASE_URL = "https://sznqtrlrjfyxkzaplxsn.supabase.co"
SUPABASE_KEY = "sb_secret_mgdl5W5C0s8dMy_DMxaUCg_IzyEh_EZ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- FastAPI App ----------
app = FastAPI(title="CognoV Accounting API", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Helper Functions ----------
def call_rpc(func_name: str, params: dict):
    """Wrapper to call Supabase RPCs and handle Postgres errors cleanly."""
    try:
        return supabase.rpc(func_name, params).execute()
    except APIError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def get_current_api_key(authorization: str = Header(None)):
    """Extracts API key from the Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid format. Use 'Bearer <api_key>'")
    return parts[1]

def validate_api_key(api_key: str) -> bool:
    owner = supabase.table("owners").select("api_key").eq("api_key", api_key).execute()
    if owner.data: return True
    user = supabase.table("users").select("api_key").eq("api_key", api_key).execute()
    return bool(user.data)

def generate_user_id() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))

# ---------- Rate Limiting ----------
rate_limit_storage = defaultdict(list)
RATE_LIMIT = 100
RATE_WINDOW = 60

def check_rate_limit(user_id: str):
    now = datetime.utcnow().timestamp()
    rate_limit_storage[user_id] = [ts for ts in rate_limit_storage[user_id] if now - ts < RATE_WINDOW]
    if len(rate_limit_storage[user_id]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    rate_limit_storage[user_id].append(now)
    if not rate_limit_storage[user_id]:
        del rate_limit_storage[user_id]

# ---------- Accounting Logic ----------
ACCOUNT_TYPES = {
    "Cash": "Asset", "Bank": "Asset", "Inventory": "Asset", "Accounts Receivable": "Asset",
    "Accumulated Depreciation": "Contra-Asset", "Accounts Payable": "Liability", 
    "Loan from Bank": "Liability", "Owner's Equity": "Equity", "Retained Earnings": "Equity",
    "Sales Revenue": "Revenue", "Service Revenue": "Revenue", "Sales Returns": "Contra-Revenue",
    "COGS": "Expense", "Rent Expense": "Expense", "Salaries Expense": "Expense",
}

def get_account_type(account_name: str) -> str:
    if account_name in ACCOUNT_TYPES: return ACCOUNT_TYPES[account_name]
    if "Receivable" in account_name or "Debtor" in account_name: return "Asset"
    if "Payable" in account_name or "Creditor" in account_name: return "Liability"
    if any(k in account_name for k in ["Cash", "Bank", "Inventory", "Asset"]): return "Asset"
    if any(k in account_name for k in ["Loan", "Payable", "Liability"]): return "Liability"
    if any(k in account_name for k in ["Revenue", "Income"]): return "Revenue"
    if any(k in account_name for k in ["Expense", "Cost", "Loss"]): return "Expense"
    return "Equity"

def calculate_balance_sheet(tb_data: List[Dict]) -> Dict:
    """Calculates a clean Balance Sheet handling contra-entries correctly."""
    assets, liabilities, equity = {}, {}, {}
    total_revenue, total_expenses = Decimal('0'), Decimal('0')
    
    for row in tb_data:
        account = row["account_name"]
        debit = Decimal(str(row["debit_balance"]))
        credit = Decimal(str(row["credit_balance"]))
        acc_type = get_account_type(account)
        
        if acc_type == "Revenue":
            total_revenue += (credit - debit) # Handles sales returns (debits)
        elif acc_type == "Expense":
            total_expenses += (debit - credit)
        elif acc_type in ["Asset", "Contra-Asset"]:
            assets[account] = debit - credit
        elif acc_type == "Liability":
            liabilities[account] = credit - debit
        elif acc_type == "Equity":
            equity[account] = credit - debit
            
    net_income = total_revenue - total_expenses
    if "Retained Earnings" in equity:
        equity["Retained Earnings"] += net_income
    else:
        equity["Current Period Earnings"] = net_income
        
    return {
        "assets": {k: float(v) for k, v in assets.items()},
        "liabilities": {k: float(v) for k, v in liabilities.items()},
        "equity": {k: float(v) for k, v in equity.items()},
        "total_assets": float(sum(assets.values())),
        "total_liabilities": float(sum(liabilities.values())),
        "total_equity": float(sum(equity.values())),
        "net_income": float(net_income)
    }

# ---------- Pydantic Schemas ----------
class InitializeAction(BaseModel):
    action: Literal["initialize"] = "initialize"
    cash_account: str = "Cash"
    inventory: List[str]
    qty: List[Decimal]
    unit_cost: List[Decimal]
    asset: List[str]
    value: List[Decimal]
    liability: List[str]
    values: List[Decimal]

    @root_validator
    def check_list_lengths(cls, values):
        if not (len(values.get('inventory', [])) == len(values.get('qty', [])) == len(values.get('unit_cost', []))):
            raise ValueError('Inventory, qty, and unit_cost must have the same length')
        if len(values.get('asset', [])) != len(values.get('value', [])):
            raise ValueError('Asset and value must have the same length')
        if len(values.get('liability', [])) != len(values.get('values', [])):
            raise ValueError('Liability and values must have the same length')
        return values

class PurchaseAction(BaseModel):
    action: Literal["purchase"] = "purchase"
    item: str
    qty: Decimal
    unit_cost: Decimal

class PurchaseReturnAction(BaseModel):
    action: Literal["purchase_return"] = "purchase_return"
    item: str
    qty: Decimal
    unit_cost: Decimal
    is_credit_return: bool = False
    creditor_account: str = "Accounts Payable"

class SalesAction(BaseModel):
    action: Literal["sales"] = "sales"
    item: str
    qty: Decimal
    selling_price: Decimal

class PurchaseOnCreditAction(BaseModel):
    action: Literal["purchase_on_credit"] = "purchase_on_credit"
    item: str
    qty: Decimal
    unit_cost: Decimal
    creditor: str = "Accounts Payable"

class SalesOnCreditAction(BaseModel):
    action: Literal["sales_on_credit"] = "sales_on_credit"
    item: str
    qty: Decimal
    selling_price: Decimal
    debtor: str = "Accounts Receivable"

class AdjustAction(BaseModel):
    action: Literal["adjust"] = "adjust"
    debit_account: str
    credit_account: str
    amount: Decimal
    description: str = ""

ActionUnion = Annotated[
    Union[InitializeAction, PurchaseAction, PurchaseReturnAction, SalesAction, 
          PurchaseOnCreditAction, SalesOnCreditAction, AdjustAction],
    Field(discriminator='action')
]

class TransactionRequest(BaseModel):
    user_id: Optional[str] = None
    transaction: ActionUnion

# ---------- API Endpoints ----------
@app.post("/register_user")
def register_user(api_key: str = Depends(get_current_api_key)):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = generate_user_id()
    supabase.table("users").insert({
        "user_id": user_id, "api_key": api_key, "transaction_count": 0
    }).execute()
    return {"user_id": user_id, "api_key": api_key}

@app.post("/transaction")
def process_transaction(req: TransactionRequest, api_key: str = Depends(get_current_api_key)):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    user_check = supabase.table("users").select("user_id").eq("user_id", req.user_id).eq("api_key", api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not associated with this API key")
    
    check_rate_limit(req.user_id)
    
    action_model = req.transaction
    action_type = action_model.action
    
    try:
        if action_type == "initialize": result = handle_initialize(req.user_id, action_model)
        elif action_type == "purchase": result = handle_purchase(req.user_id, action_model, credit=False)
        elif action_type == "purchase_return": result = handle_purchase_return(req.user_id, action_model)
        elif action_type == "sales": result = handle_sales(req.user_id, action_model, credit=False)
        elif action_type == "purchase_on_credit": result = handle_purchase(req.user_id, action_model, credit=True)
        elif action_type == "sales_on_credit": result = handle_sales(req.user_id, action_model, credit=True)
        elif action_type == "adjust": result = handle_adjust(req.user_id, action_model)
        else: raise HTTPException(status_code=400, detail=f"Unknown action: {action_type}")
        
        # Update transaction count atomically
        call_rpc('increment_transaction_count', {"p_user_id": req.user_id})
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

# ---------- Business Logic Handlers ----------
def handle_initialize(user_id: str, data: InitializeAction):
    for item, qty, cost in zip(data.inventory, data.qty, data.unit_cost):
        inv_value = qty * cost
        call_rpc('update_inventory_wac', {"p_user_id": user_id, "p_item": item, "p_qty_change": str(qty), "p_new_unit_cost": str(cost)})
        call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "initialize", "p_debit_account": "Inventory", "p_credit_account": "Owner's Equity", "p_amount": str(inv_value), "p_description": f"Initial inventory: {item}"})
    
    for asset_name, val in zip(data.asset, data.value):
        call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "initialize", "p_debit_account": asset_name, "p_credit_account": "Owner's Equity", "p_amount": str(val), "p_description": f"Initial asset: {asset_name}"})
    
    for liab_name, val in zip(data.liability, data.values):
        call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "initialize", "p_debit_account": data.cash_account, "p_credit_account": liab_name, "p_amount": str(val), "p_description": f"Initial liability: {liab_name}"})
        
    return {"status": "initialized"}

def handle_purchase(user_id: str, data: Union[PurchaseAction, PurchaseOnCreditAction], credit: bool):
    amount = data.qty * data.unit_cost
    call_rpc('update_inventory_wac', {"p_user_id": user_id, "p_item": data.item, "p_qty_change": str(data.qty), "p_new_unit_cost": str(data.unit_cost)})
    
    credit_account = data.creditor if credit else "Cash"
    call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": data.action, "p_debit_account": "Inventory", "p_credit_account": credit_account, "p_amount": str(amount), "p_description": f"Purchase {data.qty} {data.item}"})
    return {"status": "success", "amount": float(amount)}

def handle_purchase_return(user_id: str, data: PurchaseReturnAction):
    amount = data.qty * data.unit_cost
    call_rpc('update_inventory_wac', {"p_user_id": user_id, "p_item": data.item, "p_qty_change": str(-data.qty), "p_new_unit_cost": "0"})
    
    credit_account = data.creditor_account if data.is_credit_return else "Cash"
    call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "purchase_return", "p_debit_account": credit_account, "p_credit_account": "Inventory", "p_amount": str(amount), "p_description": f"Return {data.qty} {data.item}"})
    return {"status": "success", "amount": float(amount)}

def handle_sales(user_id: str, data: Union[SalesAction, SalesOnCreditAction], credit: bool):
    inv = supabase.table("inventory").select("unit_cost").eq("user_id", user_id).eq("item_name", data.item).execute()
    if not inv.data: raise HTTPException(status_code=400, detail=f"Item {data.item} not found")
        
    unit_cost = Decimal(str(inv.data[0]["unit_cost"]))
    cogs_amount = data.qty * unit_cost
    revenue_amount = data.qty * data.selling_price
    
    call_rpc('update_inventory_wac', {"p_user_id": user_id, "p_item": data.item, "p_qty_change": str(-data.qty), "p_new_unit_cost": "0"})
    
    debit_account = data.debtor if credit else "Cash"
    call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": data.action, "p_debit_account": debit_account, "p_credit_account": "Sales Revenue", "p_amount": str(revenue_amount), "p_description": f"Sale of {data.qty} {data.item}"})
    call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "sales_cogs", "p_debit_account": "COGS", "p_credit_account": "Inventory", "p_amount": str(cogs_amount), "p_description": f"COGS for {data.qty} {data.item}"})
    
    return {"status": "success", "revenue": float(revenue_amount), "cogs": float(cogs_amount)}

def handle_adjust(user_id: str, data: AdjustAction):
    call_rpc('record_journal_entry', {"p_user_id": user_id, "p_action": "adjust", "p_debit_account": data.debit_account, "p_credit_account": data.credit_account, "p_amount": str(data.amount), "p_description": data.description})
    return {"status": "success", "amount": float(data.amount)}

# ---------- Fetch Endpoints ----------
@app.get("/fetch/{user_id}/{report_type}")
def fetch_report(user_id: str, report_type: str, api_key: str = Depends(get_current_api_key)):
    if not validate_api_key(api_key): raise HTTPException(status_code=401, detail="Invalid API key")
    user_check = supabase.table("users").select("user_id").eq("user_id", user_id).eq("api_key", api_key).execute()
    if not user_check.data: raise HTTPException(status_code=403, detail="User not accessible")
    
    rt = report_type.lower()
    if rt == "trialbalance":
        tb = supabase.table("trial_balance").select("*").eq("user_id", user_id).execute()
        return {"trial_balance": tb.data}
    elif rt == "journal":
        journal = supabase.table("journal").select("*").eq("user_id", user_id).order("id").execute()
        return {"journal": journal.data}
    elif rt == "balancesheet":
        tb = supabase.table("trial_balance").select("*").eq("user_id", user_id).execute()
        return {"balance_sheet": calculate_balance_sheet(tb.data)}
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")