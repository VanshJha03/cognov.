import os
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator, Extra
from supabase import acreate_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

# ---------- Supabase Lazy Setup ----------
_supabase_client: Optional[AsyncClient] = None

async def get_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment")
        _supabase_client = await acreate_client(url, key)
    return _supabase_client

# ---------- FastAPI App ----------
app = FastAPI(title="CognoV Accounting API", version="1.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cogno.vercel.app",
        "https://cognov.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
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
    now = datetime.now(timezone.utc).timestamp()
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

async def validate_api_key(api_key: str) -> bool:
    try:
        client = await get_supabase()
        owner = await client.table("owners").select("api_key").eq("api_key", api_key).execute()
        if owner.data:
            return True
        user = await client.table("users").select("api_key").eq("api_key", api_key).execute()
        return bool(user.data)
    except Exception:
        return False

async def get_owner_from_api_key(api_key: str) -> Optional[str]:
    try:
        client = await get_supabase()
        owner = await client.table("owners").select("entity").eq("api_key", api_key).execute()
        if owner.data:
            return owner.data[0]["entity"]
    except Exception:
        pass
    return None

async def update_trial_balance(user_id: str, account: str, is_debit: bool, amount: Decimal):
    try:
        client = await get_supabase()
        existing = await client.table("trial_balance").select("*")\
            .eq("user_id", user_id).eq("account_name", account).execute()
        if existing.data:
            rec = existing.data[0]
            if is_debit:
                new_debit = Decimal(rec["debit_balance"]) + amount
                await client.table("trial_balance").update({"debit_balance": float(new_debit)})\
                    .eq("user_id", user_id).eq("account_name", account).execute()
            else:
                new_credit = Decimal(rec["credit_balance"]) + amount
                await client.table("trial_balance").update({"credit_balance": float(new_credit)})\
                    .eq("user_id", user_id).eq("account_name", account).execute()
        else:
            await client.table("trial_balance").insert({
                "user_id": user_id,
                "account_name": account,
                "debit_balance": float(amount) if is_debit else 0,
                "credit_balance": float(amount) if not is_debit else 0
            }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error in update_trial_balance: {str(e)}")

async def add_journal_entry(user_id: str, action: str, debit_account: str, credit_account: str,
                      amount: Decimal, description: str = ""):
    try:
        client = await get_supabase()
        await client.table("journal").insert({
            "user_id": user_id,
            "action": action,
            "debit_account": debit_account,
            "credit_account": credit_account,
            "amount": float(amount),
            "description": description,
            "date": datetime.now(timezone.utc).isoformat()
        }).execute()
        await update_trial_balance(user_id, debit_account, True, amount)
        await update_trial_balance(user_id, credit_account, False, amount)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error in add_journal_entry: {str(e)}")

async def log_transaction(user_id: str, action: str):
    try:
        client = await get_supabase()
        await client.table("transactions_log").insert({
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).execute()

        user_resp = await client.table("users").select("transaction_count").eq("user_id", user_id).execute()
        if user_resp.data:
            new_count = user_resp.data[0]["transaction_count"] + 1
            await client.table("users").update({"transaction_count": new_count}).eq("user_id", user_id).execute()
        else:
            await client.table("users").insert({
                "user_id": user_id,
                "api_key": "unknown",
                "transaction_count": 1
            }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error in log_transaction: {str(e)}")

async def refresh_balance_sheet(user_id: str):
    try:
        client = await get_supabase()
        tb = await client.table("trial_balance").select("*").eq("user_id", user_id).execute()
        assets, liabilities, equity = {}, {}, {}
        for row in tb.data:
            account = row["account_name"]
            debit = Decimal(row["debit_balance"])
            credit = Decimal(row["credit_balance"])
            balance = debit - credit
            if account.startswith(("Cash", "Inventory", "Asset", "Car", "Table", "Chair", "Receivable")):
                assets[account] = float(balance)
            elif account.startswith(("Loan", "Payable", "Liability")):
                liabilities[account] = float(-balance) if balance < 0 else float(balance)
            else:
                equity[account] = float(balance)
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
        await client.table("balance_sheet").upsert({
            "user_id": user_id,
            "data": bs_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return bs_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error in refresh_balance_sheet: {str(e)}")

async def update_inventory(user_id: str, item: str, qty_change: Decimal, new_unit_cost: Optional[Decimal] = None):
    try:
        client = await get_supabase()
        existing = await client.table("inventory").select("*").eq("user_id", user_id).eq("item_name", item).execute()
        if existing.data:
            current_qty = Decimal(existing.data[0]["quantity"])
            new_qty = current_qty + qty_change
            if new_qty < 0:
                raise HTTPException(status_code=400, detail=f"Insufficient inventory for {item}")
            cost_to_use = new_unit_cost if new_unit_cost is not None else Decimal(existing.data[0]["unit_cost"])
            await client.table("inventory").update({
                "quantity": float(new_qty),
                "unit_cost": float(cost_to_use)
            }).eq("user_id", user_id).eq("item_name", item).execute()
        else:
            if qty_change <= 0:
                raise HTTPException(status_code=400, detail=f"Cannot add negative quantity for new item {item}")
            await client.table("inventory").insert({
                "user_id": user_id,
                "item_name": item,
                "quantity": float(qty_change),
                "unit_cost": float(new_unit_cost) if new_unit_cost else 0
            }).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error in update_inventory: {str(e)}")

# ---------- Pydantic Schemas ----------
class InitializeAction(BaseModel):
    action: str = "initialize"
    inventory: List[str] = Field(default_factory=list)
    qty: List[float] = Field(default_factory=list)
    unit_cost: List[float] = Field(default_factory=list)
    asset: List[str] = Field(default_factory=list)
    value: List[float] = Field(default_factory=list)
    liability: List[str] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)

    @validator('qty', 'unit_cost', 'value', 'values', each_item=True)
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Negative values not allowed")
        return v

    class Config:
        extra = "ignore"

class PurchaseAction(BaseModel):
    action: str = "purchase"
    item: str
    qty: float
    unit_cost: float

    class Config:
        extra = "ignore"

class PurchaseReturnAction(BaseModel):
    action: str = "purchase_return"
    item: str
    qty: float
    unit_cost: float

    class Config:
        extra = "ignore"

class SalesAction(BaseModel):
    action: str = "sales"
    item: str
    qty: float
    selling_price: float

    class Config:
        extra = "ignore"

class SalesReturnAction(BaseModel):
    action: str = "sales_return"
    item: str
    qty: float
    selling_price: float

    class Config:
        extra = "ignore"

class PurchaseOnCreditAction(BaseModel):
    action: str = "purchase_on_credit"
    item: str
    qty: float
    unit_cost: float
    creditor: str = "Accounts Payable"

    class Config:
        extra = "ignore"

class SalesOnCreditAction(BaseModel):
    action: str = "sales_on_credit"
    item: str
    qty: float
    selling_price: float
    debtor: str = "Accounts Receivable"

    class Config:
        extra = "ignore"

class WriteOffAction(BaseModel):
    action: str = "write_off"
    account_to_debit: str
    account_to_credit: str
    amount: float
    description: str = ""

    class Config:
        extra = "ignore"

class AdjustAction(BaseModel):
    action: str = "adjust"
    debit_account: str
    credit_account: str
    amount: float
    description: str = ""

    class Config:
        extra = "ignore"

class RegisterUserAction(BaseModel):
    action: str = "Register"

    class Config:
        extra = "ignore"

class TransactionRequest(BaseModel):
    api_key: str
    user_id: Optional[str] = None
    transaction: Dict[str, Any]

# ---------- API Endpoints ----------
@app.post("/admin/generate_owner_api_key")
async def generate_owner_api_key(entity: str, master_secret: str):
    if master_secret != os.getenv("MASTER_SECRET", "change_me"):
        raise HTTPException(status_code=403, detail="Invalid master secret")
    api_key = generate_api_key()
    try:
        client = await get_supabase()
        await client.table("owners").upsert({"entity": entity, "api_key": api_key}).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return {"api_key": api_key}

@app.post("/register_user")
async def register_user(api_key: str):
    if not await validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    user_id = generate_user_id()
    try:
        client = await get_supabase()
        await client.table("users").insert({
            "user_id": user_id,
            "api_key": api_key,
            "transaction_count": 0
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return {"user_id": user_id, "api_key": api_key}

@app.post("/transaction")
async def process_transaction(req: TransactionRequest):
    if not await validate_api_key(req.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if req.transaction.get("action") == "Register":
        return await register_user(req.api_key)

    if not req.user_id:
        raise HTTPException(status_code=400, detail="user_id required for this action")

    client = await get_supabase()
    user_check = await client.table("users").select("user_id").eq("user_id", req.user_id).eq("api_key", req.api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not associated with this API key")

    check_rate_limit(req.user_id)

    action = req.transaction.get("action")
    if action is None:
        raise HTTPException(status_code=400, detail="Missing action in transaction")

    try:
        if action == "initialize":
            data = InitializeAction(**req.transaction)
            result = await handle_initialize(req.user_id, data)
        elif action == "purchase":
            data = PurchaseAction(**req.transaction)
            result = await handle_purchase(req.user_id, data, credit=False)
        elif action == "purchase_return":
            data = PurchaseReturnAction(**req.transaction)
            result = await handle_purchase_return(req.user_id, data)
        elif action == "sales":
            data = SalesAction(**req.transaction)
            result = await handle_sales(req.user_id, data, credit=False)
        elif action == "sales_return":
            data = SalesReturnAction(**req.transaction)
            result = await handle_sales_return(req.user_id, data)
        elif action == "purchase_on_credit":
            data = PurchaseOnCreditAction(**req.transaction)
            result = await handle_purchase(req.user_id, data, credit=True)
        elif action == "sales_on_credit":
            data = SalesOnCreditAction(**req.transaction)
            result = await handle_sales(req.user_id, data, credit=True)
        elif action == "write_off":
            data = WriteOffAction(**req.transaction)
            result = await handle_write_off(req.user_id, data)
        elif action == "adjust":
            data = AdjustAction(**req.transaction)
            result = await handle_adjust(req.user_id, data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

        await log_transaction(req.user_id, action)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

# ---------- Business Logic Handlers ----------
async def handle_initialize(user_id: str, data: InitializeAction):
    # Validate that all paired lists have the same length
    if len(data.inventory) != len(data.qty) or len(data.inventory) != len(data.unit_cost):
        raise HTTPException(status_code=422, detail="inventory, qty, unit_cost must have same length")
    if len(data.asset) != len(data.value):
        raise HTTPException(status_code=422, detail="asset and value must have same length")
    if len(data.liability) != len(data.values):
        raise HTTPException(status_code=422, detail="liability and values must have same length")

    total_inv_value = Decimal(0)
    for item, qty, cost in zip(data.inventory, data.qty, data.unit_cost):
        qty_dec = Decimal(qty)
        cost_dec = Decimal(cost)
        await update_inventory(user_id, item, qty_dec, cost_dec)
        inv_value = qty_dec * cost_dec
        total_inv_value += inv_value
        await add_journal_entry(user_id, "initialize", "Inventory", "Owner's Equity", inv_value, f"Initial inventory: {item}")

    for asset_name, val in zip(data.asset, data.value):
        val_dec = Decimal(val)
        await add_journal_entry(user_id, "initialize", asset_name, "Owner's Equity", val_dec, f"Initial asset: {asset_name}")

    for liab_name, val in zip(data.liability, data.values):
        val_dec = Decimal(val)
        await add_journal_entry(user_id, "initialize", "Owner's Equity", liab_name, val_dec, f"Initial liability: {liab_name}")

    await refresh_balance_sheet(user_id)
    return {"status": "initialized"}

async def handle_purchase(user_id: str, data: Union[PurchaseAction, PurchaseOnCreditAction], credit: bool):
    amount = Decimal(data.qty) * Decimal(data.unit_cost)
    await update_inventory(user_id, data.item, Decimal(data.qty), Decimal(data.unit_cost))
    if not credit:
        await add_journal_entry(user_id, "purchase", "Inventory", "Cash", amount, f"Purchase {data.qty} {data.item}")
        debit = "Inventory"
        credit_acct = "Cash"
    else:
        await add_journal_entry(user_id, "purchase_on_credit", "Inventory", data.creditor, amount,
                          f"Credit purchase {data.qty} {data.item}")
        debit = "Inventory"
        credit_acct = data.creditor
    await refresh_balance_sheet(user_id)
    return {"debit": debit, "credit": credit_acct, "amount": float(amount)}

async def handle_purchase_return(user_id: str, data: PurchaseReturnAction):
    amount = Decimal(data.qty) * Decimal(data.unit_cost)
    await update_inventory(user_id, data.item, -Decimal(data.qty))
    await add_journal_entry(user_id, "purchase_return", "Cash", "Inventory", amount, f"Return {data.qty} {data.item}")
    await refresh_balance_sheet(user_id)
    return {"debit": "Cash", "credit": "Inventory", "amount": float(amount)}

async def handle_sales(user_id: str, data: Union[SalesAction, SalesOnCreditAction], credit: bool):
    client = await get_supabase()
    inv = await client.table("inventory").select("unit_cost").eq("user_id", user_id).eq("item_name", data.item).execute()
    if not inv.data:
        raise HTTPException(status_code=400, detail=f"Item {data.item} not found in inventory")
    unit_cost = Decimal(inv.data[0]["unit_cost"])
    cogs_amount = Decimal(data.qty) * unit_cost
    revenue_amount = Decimal(data.qty) * Decimal(data.selling_price)
    await update_inventory(user_id, data.item, -Decimal(data.qty))

    if not credit:
        await add_journal_entry(user_id, "sales", "Cash", "Sales Revenue", revenue_amount, f"Sale of {data.qty} {data.item}")
        await add_journal_entry(user_id, "sales_cogs", "COGS", "Inventory", cogs_amount, f"COGS for {data.qty} {data.item}")
        debit_acct = "Cash"
        credit_acct = "Sales Revenue"
    else:
        await add_journal_entry(user_id, "sales_on_credit", data.debtor, "Sales Revenue", revenue_amount,
                          f"Credit sale {data.qty} {data.item}")
        await add_journal_entry(user_id, "sales_cogs", "COGS", "Inventory", cogs_amount, f"COGS for {data.qty} {data.item}")
        debit_acct = data.debtor
        credit_acct = "Sales Revenue"

    await refresh_balance_sheet(user_id)
    return {"debit": debit_acct, "credit": credit_acct, "revenue": float(revenue_amount), "cogs": float(cogs_amount)}

async def handle_sales_return(user_id: str, data: SalesReturnAction):
    client = await get_supabase()
    inv = await client.table("inventory").select("unit_cost").eq("user_id", user_id).eq("item_name", data.item).execute()
    if not inv.data:
        raise HTTPException(status_code=400, detail=f"Item {data.item} not found")
    unit_cost = Decimal(inv.data[0]["unit_cost"])
    cogs_return = Decimal(data.qty) * unit_cost
    revenue_return = Decimal(data.qty) * Decimal(data.selling_price)
    await update_inventory(user_id, data.item, Decimal(data.qty))
    await add_journal_entry(user_id, "sales_return", "Sales Returns", "Cash", revenue_return, f"Return {data.qty} {data.item}")
    await add_journal_entry(user_id, "sales_return_cogs", "Inventory", "COGS", cogs_return, "Reverse COGS for return")
    await refresh_balance_sheet(user_id)
    return {"debit": "Sales Returns", "credit": "Cash", "amount": float(revenue_return)}

async def handle_write_off(user_id: str, data: WriteOffAction):
    amount = Decimal(data.amount)
    await add_journal_entry(user_id, "write_off", data.account_to_debit, data.account_to_credit, amount, data.description)
    await refresh_balance_sheet(user_id)
    return {"debit": data.account_to_debit, "credit": data.account_to_credit, "amount": float(amount)}

async def handle_adjust(user_id: str, data: AdjustAction):
    amount = Decimal(data.amount)
    await add_journal_entry(user_id, "adjust", data.debit_account, data.credit_account, amount, data.description)
    await refresh_balance_sheet(user_id)
    return {"debit": data.debit_account, "credit": data.credit_account, "amount": float(amount)}

# ---------- Owner & Fetch Endpoints ----------
@app.get("/owner/users")
async def get_owner_users(api_key: str):
    if not await validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        client = await get_supabase()
        users = await client.table("users").select("user_id, created_at, transaction_count").eq("api_key", api_key).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    result = []
    for u in users.data:
        user_id = u["user_id"]
        day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        try:
            count_24h = await client.table("transactions_log").select("id", count="exact")\
                .eq("user_id", user_id).gte("timestamp", day_ago).execute()
            count = count_24h.count
        except Exception:
            count = 0
        result.append({
            "user_id": user_id,
            "created_at": u["created_at"],
            "transaction_count_all_time": u.get("transaction_count", 0),
            "transaction_count_last_24h": count
        })

    total_txn = sum(r["transaction_count_all_time"] for r in result)
    total_cost = total_txn / 1000
    return {
        "users": result,
        "total_transactions": total_txn,
        "total_cost_usd": round(total_cost, 2)
    }

@app.get("/fetch/{user_id}/{report_type}")
async def fetch_report(user_id: str, report_type: str, api_key: str):
    if not await validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    client = await get_supabase()
    user_check = await client.table("users").select("user_id").eq("user_id", user_id).eq("api_key", api_key).execute()
    if not user_check.data:
        raise HTTPException(status_code=403, detail="User not accessible")

    rt = report_type.lower()
    try:
        if rt == "trialbalance":
            tb = await client.table("trial_balance").select("*").eq("user_id", user_id).execute()
            return {"trial_balance": tb.data}
        elif rt == "journal":
            journal = await client.table("journal").select("*").eq("user_id", user_id).order("date").execute()
            return {"journal": journal.data}
        elif rt == "balancesheet":
            bs = await client.table("balance_sheet").select("data").eq("user_id", user_id).execute()
            if not bs.data:
                await refresh_balance_sheet(user_id)
                bs = await client.table("balance_sheet").select("data").eq("user_id", user_id).execute()
            return {"balance_sheet": bs.data[0]["data"] if bs.data else {}}
        else:
            raise HTTPException(status_code=400, detail="Report type must be trialbalance, journal, or balancesheet")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ---------- Cloudflare Pyodide Entrypoint ----------
from workers import WorkerEntrypoint
import asgi

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # Dynamically inject worker env variables into os.environ for runtime libraries that expect them
        for key in ["SUPABASE_URL", "SUPABASE_KEY", "MASTER_SECRET"]:
            val = getattr(self.env, key, None)
            if val is not None:
                os.environ[key] = str(val)
        return await asgi.fetch(app, request.js_object, self.env)