import os
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from supabase import create_client, Client

# ---------- Supabase Setup ----------
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", "https://sznqtrlrjfyxkzaplxsn.supabase.co"),
    os.getenv("SUPABASE_KEY", "")
)

# ---------- FastAPI App ----------
app = FastAPI(title="CognoV Accounting API", version="1.0")

# Rewrite path to strip /request prefix if present (Vercel rewrite support)
@app.middleware("http")
async def strip_request_prefix(request: Request, call_next):
    path = request.scope.get("path", "")
    if path.startswith("/request"):
        request.scope["path"] = path[len("/request"):]
    return await call_next(request)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cognov-3a24.vercel.app",
        "https://cogno.vercel.app",
        "https://cognov.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Rate Limiting ----------
rate_limit_storage = defaultdict(list)  # user_id -> list of timestamps
RATE_LIMIT = 100  # requests per minute
RATE_WINDOW = 60  # seconds

def check_rate_limit(user_id: str):
    now = datetime.utcnow().timestamp()
    # clean old entries
    rate_limit_storage[user_id] = [ts for ts in rate_limit_storage[user_id] if now - ts < RATE_WINDOW]
    if len(rate_limit_storage[user_id]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: max {RATE_LIMIT} requests per minute")
    rate_limit_storage[user_id].append(now)

# ---------- Helper Functions ----------
def generate_api_key() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))

def generate_user_id() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))

def validate_api_key(api_key: str) -> bool:
    # Check owners table
    owner = supabase.table("owners").select("api_key").eq("api_key", api_key).execute()
    if owner.data:
        return True
    # Also could check users table if we generate per-user keys
    user = supabase.table("users").select("api_key").eq("api_key", api_key).execute()
    return bool(user.data)

def get_owner_from_api_key(api_key: str) -> Optional[str]:
    owner = supabase.table("owners").select("entity").eq("api_key", api_key).execute()
    if owner.data:
        return owner.data[0]["entity"]
    return None

def update_trial_balance(user_id: str, account: str, is_debit: bool, amount: Decimal):
    existing = supabase.table("trial_balance").select("*")\
        .eq("user_id", user_id).eq("account_name", account).execute()
    if existing.data:
        rec = existing.data[0]
        if is_debit:
            new_debit = Decimal(rec["debit_balance"]) + amount
            supabase.table("trial_balance").update({"debit_balance": float(new_debit)})\
                .eq("user_id", user_id).eq("account_name", account).execute()
        else:
            new_credit = Decimal(rec["credit_balance"]) + amount
            supabase.table("trial_balance").update({"credit_balance": float(new_credit)})\
                .eq("user_id", user_id).eq("account_name", account).execute()
    else:
        supabase.table("trial_balance").insert({
            "user_id": user_id,
            "account_name": account,
            "debit_balance": float(amount) if is_debit else 0,
            "credit_balance": float(amount) if not is_debit else 0
        }).execute()

def add_journal_entry(user_id: str, action: str, debit_account: str, credit_account: str, amount: Decimal, description: str = ""):
    supabase.table("journal").insert({
        "user_id": user_id,
        "action": action,
        "debit_account": debit_account,
        "credit_account": credit_account,
        "amount": float(amount),
        "description": description
    }).execute()
    update_trial_balance(user_id, debit_account, True, amount)
    update_trial_balance(user_id, credit_account, False, amount)

def log_transaction(user_id: str, action: str):
    supabase.table("transactions_log").insert({
        "user_id": user_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()
    # increment user transaction count
    user_resp = supabase.table("users").select("transaction_count").eq("user_id", user_id).execute()
    if user_resp.data:
        new_count = user_resp.data[0]["transaction_count"] + 1
        supabase.table("users").update({"transaction_count": new_count}).eq("user_id", user_id).execute()
    else:
        supabase.table("users").update({"transaction_count": 1}).eq("user_id", user_id).execute()

def refresh_balance_sheet(user_id: str):
    tb = supabase.table("trial_balance").select("*").eq("user_id", user_id).execute()
    assets, liabilities, equity = {}, {}, {}
    total_revenue = Decimal(0)
    total_expense = Decimal(0)
    
    for row in tb.data:
        account = row["account_name"]
        debit = Decimal(row["debit_balance"])
        credit = Decimal(row["credit_balance"])
        
        # Classify accounts and apply debit/credit rules
        if account.startswith(("Cash", "Inventory", "Asset", "Car", "Table", "Chair", "Receivable", "Equipment", "Property", "Vehicle")):
            assets[account] = float(debit - credit)
        elif account.startswith(("Loan", "Payable", "Liability")):
            liabilities[account] = float(credit - debit)
        elif account.startswith(("Sales Revenue", "Revenue", "Income", "Gain")):
            total_revenue += (credit - debit)
        elif account.startswith(("COGS", "Sales Returns", "Expense", "Loss", "Write-Off", "Depreciation")):
            total_expense += (debit - credit)
        else:
            equity[account] = float(credit - debit)
            
    net_income = float(total_revenue - total_expense)
    if net_income != 0:
        equity["Retained Earnings (Net Income)"] = net_income
        
    total_assets = sum(assets.values())
    total_liab_eq = sum(liabilities.values()) + sum(equity.values())
    
    if abs(total_assets - total_liab_eq) > 0.01:
        diff = total_assets - total_liab_eq
        equity["Balancing_Equity"] = equity.get("Balancing_Equity", 0) + float(diff)
        
    bs_data = {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities_equity": sum(liabilities.values()) + sum(equity.values())
    }
    supabase.table("balance_sheet").upsert({
        "user_id": user_id,
        "data": bs_data,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()
    return bs_data

def update_inventory(user_id: str, item: str, qty_change: Decimal, new_unit_cost: Optional[Decimal] = None):
    existing = supabase.table("inventory").select("*").eq("user_id", user_id).eq("item_name", item).execute()
    if existing.data:
        current_qty = Decimal(existing.data[0]["quantity"])
        new_qty = current_qty + qty_change
        if new_qty < 0:
            raise HTTPException(status_code=400, detail=f"Insufficient inventory for {item}")
        cost_to_use = new_unit_cost if new_unit_cost is not None else Decimal(existing.data[0]["unit_cost"])
        supabase.table("inventory").update({
            "quantity": float(new_qty),
            "unit_cost": float(cost_to_use)
        }).eq("user_id", user_id).eq("item_name", item).execute()
    else:
        if qty_change <= 0:
            raise HTTPException(status_code=400, detail=f"Cannot add negative quantity for new item {item}")
        supabase.table("inventory").insert({
            "user_id": user_id,
            "item_name": item,
            "quantity": float(qty_change),
            "unit_cost": float(new_unit_cost) if new_unit_cost else 0
        }).execute()

# ---------- Pydantic Schemas ----------
class InitializeAction(BaseModel):
    action: str = "initialize"
    inventory: List[str]
    qty: List[float]
    unit_cost: List[float]
    asset: List[str]
    value: List[float]
    liability: List[str]
    values: List[float]

    @validator('qty', 'unit_cost', 'value', 'values', each_item=True)
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Negative values not allowed")
        return v

class PurchaseAction(BaseModel):
    action: str = "purchase"
    item: str
    qty: float
    unit_cost: float

class PurchaseReturnAction(BaseModel):
    action: str = "purchase_return"
    item: str
    qty: float
    unit_cost: float
    creditor: Optional[str] = None

class SalesAction(BaseModel):
    action: str = "sales"
    item: str
    qty: float
    selling_price: float
    unit_cost: Optional[float] = None

class SalesReturnAction(BaseModel):
    action: str = "sales_return"
    item: str
    qty: float
    selling_price: float
    unit_cost: Optional[float] = None
    debtor: Optional[str] = None

class PurchaseOnCreditAction(BaseModel):
    action: str = "purchase_on_credit"
    item: str
    qty: float
    unit_cost: float
    creditor: str = "Accounts Payable"

class SalesOnCreditAction(BaseModel):
    action: str = "sales_on_credit"
    item: str
    qty: float
    selling_price: float
    debtor: str = "Accounts Receivable"
    unit_cost: Optional[float] = None

class WriteOffAction(BaseModel):
    action: str = "write_off"
    account_to_debit: str
    account_to_credit: str
    amount: float
    description: str = ""

class AdjustAction(BaseModel):
    action: str = "adjust"
    debit_account: str
    credit_account: str
    amount: float
    description: str = ""

class RegisterUserAction(BaseModel):
    action: str = "Register"

class RegisterAssetRequest(BaseModel):
    api_key: str
    user_id: str
    asset_name: str
    asset_type: str
    purchase_cost: float
    funding_source: str = "Cash"

class AdjustAssetRequest(BaseModel):
    api_key: str
    user_id: str
    asset_id: str
    new_value: float
    description: str = ""

class TransactionRequest(BaseModel):
    api_key: str
    user_id: Optional[str] = None
    transaction: Dict[str, Any]

# ---------- API Endpoints ----------
@app.post("/register")
def register_owner(entity: str, owner_name: str = ""):
    """Open signup endpoint. Any inventory app can register to get an API key."""
    # Check if this entity already has a key (prevent duplicates)
    existing = supabase.table("owners").select("api_key").eq("entity", entity).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail=f"Entity '{entity}' is already registered. Use your existing API key.")
    api_key = generate_api_key()
    supabase.table("owners").insert({
        "entity": entity,
        "owner_name": owner_name,
        "api_key": api_key
    }).execute()
    return {"api_key": api_key, "entity": entity, "owner_name": owner_name}

@app.post("/register_user")
def register_user(api_key: str):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = generate_user_id()
    # Also generate a user-specific API key (optional, but we'll keep it simple: user uses same owner key)
    # For per‑user keys, uncomment below:
    # user_api_key = generate_api_key()
    supabase.table("users").insert({
        "user_id": user_id,
        "api_key": api_key,   # using owner key
        "transaction_count": 0
    }).execute()
    return {"user_id": user_id, "api_key": api_key}   # in real case, return user_api_key

@app.post("/transaction")
def process_transaction(req: TransactionRequest):
    # Validate API key
    if not validate_api_key(req.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Special case: register user via transaction
    if req.transaction.get("action") == "Register":
        return register_user(req.api_key)
    
    # All other actions require user_id
    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id required for this action")
    
    # Verify that user belongs to this API key (owner key)
    user_check = supabase.table("users").select("user_id").eq("user_id", req.user_id).eq("api_key", req.api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not associated with this API key")
    
    # Rate limit by user_id
    check_rate_limit(req.user_id)
    
    action = req.transaction.get("action")
    if action is None:
        raise HTTPException(status_code=400, detail="Missing action in transaction")
    
    try:
        if action == "initialize":
            data = InitializeAction(**req.transaction)
            result = handle_initialize(req.user_id, data)
        elif action == "purchase":
            data = PurchaseAction(**req.transaction)
            result = handle_purchase(req.user_id, data, credit=False)
        elif action == "purchase_return":
            data = PurchaseReturnAction(**req.transaction)
            result = handle_purchase_return(req.user_id, data)
        elif action == "sales":
            data = SalesAction(**req.transaction)
            result = handle_sales(req.user_id, data, credit=False)
        elif action == "sales_return":
            data = SalesReturnAction(**req.transaction)
            result = handle_sales_return(req.user_id, data)
        elif action == "purchase_on_credit":
            data = PurchaseOnCreditAction(**req.transaction)
            result = handle_purchase(req.user_id, data, credit=True)
        elif action == "sales_on_credit":
            data = SalesOnCreditAction(**req.transaction)
            result = handle_sales(req.user_id, data, credit=True)
        elif action == "write_off":
            data = WriteOffAction(**req.transaction)
            result = handle_write_off(req.user_id, data)
        elif action == "adjust":
            data = AdjustAction(**req.transaction)
            result = handle_adjust(req.user_id, data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        
        # Log transaction for billing & rate limit (only for non‑Register actions)
        log_transaction(req.user_id, action)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

# ---------- Business Logic Handlers ----------
def handle_initialize(user_id: str, data: InitializeAction):
    total_inv_value = Decimal(0)
    for item, qty, cost in zip(data.inventory, data.qty, data.unit_cost):
        qty_dec = Decimal(qty)
        cost_dec = Decimal(cost)
        update_inventory(user_id, item, qty_dec, cost_dec)
        inv_value = qty_dec * cost_dec
        total_inv_value += inv_value
        add_journal_entry(user_id, "initialize", "Inventory", "Owner's Equity", inv_value, f"Initial inventory: {item}")
    
    for asset_name, val in zip(data.asset, data.value):
        val_dec = Decimal(val)
        add_journal_entry(user_id, "initialize", asset_name, "Owner's Equity", val_dec, f"Initial asset: {asset_name}")
    
    for liab_name, val in zip(data.liability, data.values):
        val_dec = Decimal(val)
        add_journal_entry(user_id, "initialize", "Owner's Equity", liab_name, val_dec, f"Initial liability: {liab_name}")
    
    refresh_balance_sheet(user_id)
    return {"status": "initialized"}

def handle_purchase(user_id: str, data: Union[PurchaseAction, PurchaseOnCreditAction], credit: bool):
    amount = Decimal(data.qty) * Decimal(data.unit_cost)
    update_inventory(user_id, data.item, Decimal(data.qty), Decimal(data.unit_cost))
    if not credit:
        add_journal_entry(user_id, "purchase", "Inventory", "Cash", amount, f"Purchase {data.qty} {data.item}")
        debit = "Inventory"
        credit_acct = "Cash"
    else:
        add_journal_entry(user_id, "purchase_on_credit", "Inventory", data.creditor, amount, f"Credit purchase {data.qty} {data.item}")
        debit = "Inventory"
        credit_acct = data.creditor
    refresh_balance_sheet(user_id)
    return {"debit": debit, "credit": credit_acct, "amount": float(amount)}

def handle_purchase_return(user_id: str, data: PurchaseReturnAction):
    amount = Decimal(data.qty) * Decimal(data.unit_cost)
    update_inventory(user_id, data.item, -Decimal(data.qty))
    debit_acct = data.creditor if data.creditor else "Cash"
    add_journal_entry(user_id, "purchase_return", debit_acct, "Inventory", amount, f"Return {data.qty} {data.item}")
    refresh_balance_sheet(user_id)
    return {"debit": debit_acct, "credit": "Inventory", "amount": float(amount)}

def handle_sales(user_id: str, data: Union[SalesAction, SalesOnCreditAction], credit: bool):
    if data.unit_cost is not None:
        unit_cost = Decimal(data.unit_cost)
    else:
        inv = supabase.table("inventory").select("unit_cost").eq("user_id", user_id).eq("item_name", data.item).execute()
        if not inv.data:
            raise HTTPException(status_code=400, detail=f"Item {data.item} not found in inventory")
        unit_cost = Decimal(inv.data[0]["unit_cost"])
    cogs_amount = Decimal(data.qty) * unit_cost
    revenue_amount = Decimal(data.qty) * Decimal(data.selling_price)
    update_inventory(user_id, data.item, -Decimal(data.qty))
    
    if not credit:
        add_journal_entry(user_id, "sales", "Cash", "Sales Revenue", revenue_amount, f"Sale of {data.qty} {data.item}")
        add_journal_entry(user_id, "sales_cogs", "COGS", "Inventory", cogs_amount, f"COGS for {data.qty} {data.item}")
        debit_acct = "Cash"
        credit_acct = "Sales Revenue"
    else:
        add_journal_entry(user_id, "sales_on_credit", data.debtor, "Sales Revenue", revenue_amount, f"Credit sale {data.qty} {data.item}")
        add_journal_entry(user_id, "sales_cogs", "COGS", "Inventory", cogs_amount, f"COGS for {data.qty} {data.item}")
        debit_acct = data.debtor
        credit_acct = "Sales Revenue"
    
    refresh_balance_sheet(user_id)
    return {"debit": debit_acct, "credit": credit_acct, "revenue": float(revenue_amount), "cogs": float(cogs_amount)}

def handle_sales_return(user_id: str, data: SalesReturnAction):
    if data.unit_cost is not None:
        unit_cost = Decimal(data.unit_cost)
    else:
        inv = supabase.table("inventory").select("unit_cost").eq("user_id", user_id).eq("item_name", data.item).execute()
        if not inv.data:
            raise HTTPException(status_code=400, detail=f"Item {data.item} not found")
        unit_cost = Decimal(inv.data[0]["unit_cost"])
    cogs_return = Decimal(data.qty) * unit_cost
    revenue_return = Decimal(data.qty) * Decimal(data.selling_price)
    update_inventory(user_id, data.item, Decimal(data.qty))
    credit_acct = data.debtor if data.debtor else "Cash"
    add_journal_entry(user_id, "sales_return", "Sales Returns", credit_acct, revenue_return, f"Return {data.qty} {data.item}")
    add_journal_entry(user_id, "sales_return_cogs", "Inventory", "COGS", cogs_return, "Reverse COGS for return")
    refresh_balance_sheet(user_id)
    return {"debit": "Sales Returns", "credit": credit_acct, "amount": float(revenue_return)}

def handle_write_off(user_id: str, data: WriteOffAction):
    amount = Decimal(data.amount)
    add_journal_entry(user_id, "write_off", data.account_to_debit, data.account_to_credit, amount, data.description)
    refresh_balance_sheet(user_id)
    return {"debit": data.account_to_debit, "credit": data.account_to_credit, "amount": float(amount)}

def handle_adjust(user_id: str, data: AdjustAction):
    amount = Decimal(data.amount)
    add_journal_entry(user_id, "adjust", data.debit_account, data.credit_account, amount, data.description)
    refresh_balance_sheet(user_id)
    return {"debit": data.debit_account, "credit": data.credit_account, "amount": float(amount)}

# ---------- Owner & Fetch Endpoints ----------
@app.get("/owner/users")
def get_owner_users(api_key: str):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    users = supabase.table("users").select("user_id, created_at, transaction_count").eq("api_key", api_key).execute()
    result = []
    for u in users.data:
        user_id = u["user_id"]
        day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        count_24h = supabase.table("transactions_log").select("id", count="exact")\
            .eq("user_id", user_id).gte("timestamp", day_ago).execute()
        result.append({
            "user_id": user_id,
            "created_at": u["created_at"],
            "transaction_count_all_time": u.get("transaction_count", 0),
            "transaction_count_last_24h": count_24h.count
        })
    total_txn = sum(r["transaction_count_all_time"] for r in result)
    total_cost = total_txn / 1000
    return {
        "users": result,
        "total_transactions": total_txn,
        "total_cost_usd": round(total_cost, 2)
    }

@app.get("/fetch/{user_id}/{report_type}")
def fetch_report(user_id: str, report_type: str, api_key: str):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Verify user belongs to this api_key
    user_check = supabase.table("users").select("user_id").eq("user_id", user_id).eq("api_key", api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not accessible")
    
    rt = report_type.lower()
    if rt == "trialbalance":
        tb = supabase.table("trial_balance").select("*").eq("user_id", user_id).execute()
        return {"trial_balance": tb.data}
    elif rt == "journal":
        journal = supabase.table("journal").select("*").eq("user_id", user_id).order("date").execute()
        return {"journal": journal.data}
    elif rt == "balancesheet":
        bs = supabase.table("balance_sheet").select("data").eq("user_id", user_id).execute()
        if not bs.data:
            refresh_balance_sheet(user_id)
            bs = supabase.table("balance_sheet").select("data").eq("user_id", user_id).execute()
        return {"balance_sheet": bs.data[0]["data"] if bs.data else {}}
    elif rt in ("incomestatement", "pnl", "profitandloss"):
        tb = supabase.table("trial_balance").select("*").eq("user_id", user_id).execute()
        revenue_items = {}
        expense_items = {}
        total_rev = Decimal(0)
        total_exp = Decimal(0)
        for row in tb.data:
            acct = row["account_name"]
            debit = Decimal(row["debit_balance"])
            credit = Decimal(row["credit_balance"])
            if acct.startswith(("Sales Revenue", "Revenue", "Income", "Gain")):
                val = float(credit - debit)
                revenue_items[acct] = val
                total_rev += Decimal(str(val))
            elif acct.startswith(("COGS", "Sales Returns", "Expense", "Loss", "Write-Off", "Depreciation")):
                val = float(debit - credit)
                expense_items[acct] = val
                total_exp += Decimal(str(val))
        net_income = float(total_rev - total_exp)
        return {
            "revenue": revenue_items,
            "expenses": expense_items,
            "total_revenue": float(total_rev),
            "total_expenses": float(total_exp),
            "net_income": net_income
        }
    else:
        raise HTTPException(status_code=400, detail="Report type must be trialbalance, journal, balancesheet, or pnl")

@app.post("/assets/register")
def register_asset(req: RegisterAssetRequest):
    if not validate_api_key(req.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_check = supabase.table("users").select("user_id").eq("user_id", req.user_id).eq("api_key", req.api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not associated with this API key")
    
    asset_data = {
        "user_id": req.user_id,
        "asset_name": req.asset_name,
        "asset_type": req.asset_type,
        "purchase_cost": req.purchase_cost,
        "current_value": req.purchase_cost
    }
    res = supabase.table("assets").insert(asset_data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to register asset")
    
    # Create journal entry debiting Asset account, crediting funding source
    asset_account_name = f"Asset: {req.asset_name}"
    add_journal_entry(
        req.user_id,
        "asset_purchase",
        asset_account_name,
        req.funding_source,
        Decimal(str(req.purchase_cost)),
        f"Acquisition of asset {req.asset_name} ({req.asset_type})"
    )
    refresh_balance_sheet(req.user_id)
    return res.data[0]

@app.post("/assets/adjust")
def adjust_asset(req: AdjustAssetRequest):
    if not validate_api_key(req.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Fetch existing asset
    asset_res = supabase.table("assets").select("*").eq("id", req.asset_id).eq("user_id", req.user_id).execute()
    if not asset_res.data:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset = asset_res.data[0]
    old_value = Decimal(str(asset["current_value"]))
    new_val_dec = Decimal(str(req.new_value))
    diff = new_val_dec - old_value
    
    if diff == 0:
        return {"status": "no change", "current_value": float(old_value)}
    
    # Update current value
    supabase.table("assets").update({"current_value": float(new_val_dec)}).eq("id", req.asset_id).execute()
    
    asset_account_name = f"Asset: {asset['asset_name']}"
    if diff > 0:
        # Asset appreciated/value adjusted upwards
        add_journal_entry(
            req.user_id,
            "asset_adjustment",
            asset_account_name,
            "Gain on Asset Revaluation",
            diff,
            req.description or f"Upward value adjustment of {asset['asset_name']}"
        )
    else:
        # Asset value adjusted downwards
        add_journal_entry(
            req.user_id,
            "asset_adjustment",
            "Loss on Asset Revaluation",
            asset_account_name,
            abs(diff),
            req.description or f"Downward value adjustment of {asset['asset_name']}"
        )
        
    refresh_balance_sheet(req.user_id)
    return {"status": "adjusted", "previous_value": float(old_value), "new_value": float(new_val_dec), "adjustment": float(diff)}

@app.get("/assets/{user_id}")
def list_assets(user_id: str, api_key: str):
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_check = supabase.table("users").select("user_id").eq("user_id", user_id).eq("api_key", api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not accessible")
    
    res = supabase.table("assets").select("*").eq("user_id", user_id).execute()
    return {"assets": res.data}
