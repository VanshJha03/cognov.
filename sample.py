import requests
import json

# ============================================================
#  PASTE YOUR CREDENTIALS HERE
# ============================================================
API_KEY  = "YOUR_10_CHAR_KEY"      # Developer API key from cogno.vercel.app
BASE_URL = "https://cogno.vercel.app/request"
# ============================================================


def post(endpoint, body=None, params=None):
    url = f"{BASE_URL}{endpoint}"
    r = requests.post(url, json=body, params=params)
    r.raise_for_status()
    return r.json()

def get(endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def pretty(label, data):
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    print(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────
# STEP 1: Register a user (business on your inventory platform)
# ─────────────────────────────────────────────────────────────
print("\n[1] Registering a new user...")
reg = post("/register_user", params={"api_key": API_KEY})
pretty("Register user response", reg)

USER_ID = reg["user_id"]
print(f"\n  ✓ User ID: {USER_ID}")


# ─────────────────────────────────────────────────────────────
# STEP 2: Initialize inventory & opening balances
# ─────────────────────────────────────────────────────────────
print("\n[2] Initializing inventory and opening balances...")
init = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action": "initialize",
        "inventory": ["Laptop", "Mouse", "Keyboard"],
        "qty":       [20,       50,      30       ],
        "unit_cost": [500,      15,      25       ],
        "asset":     ["Cash"],
        "value":     [10000   ],
        "liability": [],
        "values":    []
    }
})
pretty("Initialize response", init)


# ─────────────────────────────────────────────────────────────
# STEP 3: Purchase stock (cash)
# ─────────────────────────────────────────────────────────────
print("\n[3] Purchasing 10 Monitors at $200 each (cash)...")
purchase = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action":    "purchase",
        "item":      "Monitor",
        "qty":       10,
        "unit_cost": 200
    }
})
pretty("Purchase response", purchase)


# ─────────────────────────────────────────────────────────────
# STEP 4: Purchase on credit
# ─────────────────────────────────────────────────────────────
print("\n[4] Purchasing 5 Laptops on credit from 'Dell Corp'...")
credit_purchase = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action":    "purchase_on_credit",
        "item":      "Laptop",
        "qty":       5,
        "unit_cost": 500,
        "creditor":  "Dell Corp"
    }
})
pretty("Credit purchase response", credit_purchase)


# ─────────────────────────────────────────────────────────────
# STEP 5: Sell items (cash)
# ─────────────────────────────────────────────────────────────
print("\n[5] Selling 3 Laptops at $950 each (cash)...")
sale = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action":        "sales",
        "item":          "Laptop",
        "qty":           3,
        "selling_price": 950
    }
})
pretty("Sales response", sale)


# ─────────────────────────────────────────────────────────────
# STEP 6: Sell on credit
# ─────────────────────────────────────────────────────────────
print("\n[6] Selling 5 Monitors on credit to 'RetailMart'...")
credit_sale = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action":        "sales_on_credit",
        "item":          "Monitor",
        "qty":           5,
        "selling_price": 320,
        "debtor":        "RetailMart"
    }
})
pretty("Credit sale response", credit_sale)


# ─────────────────────────────────────────────────────────────
# STEP 7: Sales return
# ─────────────────────────────────────────────────────────────
print("\n[7] RetailMart returns 1 Monitor...")
sales_return = post("/transaction", body={
    "api_key": API_KEY,
    "user_id": USER_ID,
    "transaction": {
        "action":        "sales_return",
        "item":          "Monitor",
        "qty":           1,
        "selling_price": 320
    }
})
pretty("Sales return response", sales_return)


# ─────────────────────────────────────────────────────────────
# STEP 8: Fetch Journal
# ─────────────────────────────────────────────────────────────
print("\n[8] Fetching full journal ledger...")
journal = get(f"/fetch/{USER_ID}/journal", params={"api_key": API_KEY})
pretty("Journal", journal)


# ─────────────────────────────────────────────────────────────
# STEP 9: Fetch Trial Balance
# ─────────────────────────────────────────────────────────────
print("\n[9] Fetching trial balance...")
trial = get(f"/fetch/{USER_ID}/trialbalance", params={"api_key": API_KEY})
pretty("Trial Balance", trial)


# ─────────────────────────────────────────────────────────────
# STEP 10: Fetch Balance Sheet
# ─────────────────────────────────────────────────────────────
print("\n[10] Fetching balance sheet...")
bs = get(f"/fetch/{USER_ID}/balancesheet", params={"api_key": API_KEY})
pretty("Balance Sheet", bs)

print(f"\n{'='*50}")
print(f"  Done! All 10 steps completed for User: {USER_ID}")
print(f"{'='*50}\n")
