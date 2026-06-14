CREATE TABLE owners (
    entity TEXT PRIMARY KEY,
    api_key TEXT UNIQUE NOT NULL
);

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    api_key TEXT NOT NULL REFERENCES owners(api_key) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    transaction_count INTEGER DEFAULT 0
);

CREATE TABLE journal (
    id SERIAL PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    date TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,
    debit_account TEXT NOT NULL,
    credit_account TEXT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    description TEXT
);

CREATE TABLE trial_balance (
    user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    debit_balance DECIMAL(15,2) DEFAULT 0,
    credit_balance DECIMAL(15,2) DEFAULT 0,
    PRIMARY KEY (user_id, account_name)
);

CREATE TABLE inventory (
    user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    quantity DECIMAL(15,2) NOT NULL,
    unit_cost DECIMAL(15,2) NOT NULL,
    PRIMARY KEY (user_id, item_name)
);

CREATE TABLE balance_sheet (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transactions_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);