-- ============================================================
-- Charging Platform - MySQL Schema
-- All tables managed by SQLAlchemy; this file is for reference
-- and manual MySQL setup if needed.
-- ============================================================

USE charging_platform;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) DEFAULT '',
    avatar_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME,
    INDEX idx_email (email),
    INDEX idx_phone (phone)
);

-- Wallets
CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    balance FLOAT DEFAULT 0.0,
    points INTEGER DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'MYR',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    plate_number VARCHAR(20),
    brand VARCHAR(100),
    model VARCHAR(100),
    year INTEGER,
    battery_capacity_kwh FLOAT,
    connector_type VARCHAR(50),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Chargers
CREATE TABLE IF NOT EXISTS chargers (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charge_point_id VARCHAR(255) UNIQUE NOT NULL,
    vendor VARCHAR(255),
    model VARCHAR(255),
    firmware_version VARCHAR(255),
    status VARCHAR(50) DEFAULT 'offline',
    availability VARCHAR(50) DEFAULT 'unknown',
    last_heartbeat DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    number_of_connectors INTEGER DEFAULT 1,
    heartbeat_interval INTEGER DEFAULT 7200,
    meter_value_sample_interval INTEGER DEFAULT 10,
    transaction_message_attempts INTEGER DEFAULT 3,
    transaction_message_retry_interval INTEGER DEFAULT 120,
    INDEX idx_charge_point_id (charge_point_id)
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'MYR',
    payment_method VARCHAR(255),
    payment_status VARCHAR(50) DEFAULT 'pending',
    payment_gateway VARCHAR(255),
    gateway_transaction_id VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    INDEX idx_user_id (user_id)
);

-- Charging Sessions
CREATE TABLE IF NOT EXISTS charging_sessions (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charger_id INTEGER,
    transaction_id INTEGER UNIQUE NOT NULL,
    start_time DATETIME NOT NULL,
    stop_time DATETIME,
    energy_consumed FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'active',
    user_id VARCHAR(255),
    payment_id INTEGER,
    FOREIGN KEY (charger_id) REFERENCES chargers(id),
    FOREIGN KEY (payment_id) REFERENCES payments(id),
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_charger_id (charger_id)
);

-- Wallet Transactions
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    wallet_id INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    amount FLOAT NOT NULL,
    balance_before FLOAT NOT NULL,
    balance_after FLOAT NOT NULL,
    points_amount INTEGER DEFAULT 0,
    points_before INTEGER DEFAULT 0,
    points_after INTEGER DEFAULT 0,
    session_id INTEGER,
    payment_method VARCHAR(50),
    payment_gateway VARCHAR(50),
    gateway_reference VARCHAR(255),
    status VARCHAR(50) DEFAULT 'completed',
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (wallet_id) REFERENCES wallets(id),
    FOREIGN KEY (session_id) REFERENCES charging_sessions(id)
);

-- Pricing
CREATE TABLE IF NOT EXISTS pricing (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charger_id INTEGER,
    price_per_kwh FLOAT NOT NULL DEFAULT 0.50,
    price_per_minute FLOAT DEFAULT 0.0,
    minimum_charge FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (charger_id) REFERENCES chargers(id)
);

-- Meter Values
CREATE TABLE IF NOT EXISTS meter_values (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charger_id INTEGER,
    transaction_id INTEGER,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    voltage FLOAT,
    current FLOAT,
    power FLOAT,
    total_kwh FLOAT,
    FOREIGN KEY (charger_id) REFERENCES chargers(id),
    INDEX idx_charger_id (charger_id),
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_timestamp (timestamp)
);

-- Faults
CREATE TABLE IF NOT EXISTS faults (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charger_id INTEGER,
    fault_type VARCHAR(255) NOT NULL,
    message TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cleared BOOLEAN DEFAULT FALSE,
    cleared_at DATETIME,
    FOREIGN KEY (charger_id) REFERENCES chargers(id),
    INDEX idx_charger_id (charger_id),
    INDEX idx_cleared (cleared)
);

-- Maintenance Records
CREATE TABLE IF NOT EXISTS maintenance_records (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    charger_id INTEGER NOT NULL,
    maintenance_type VARCHAR(50) NOT NULL,
    issue_description TEXT,
    work_performed TEXT NOT NULL,
    parts_replaced TEXT,
    cost FLOAT,
    technician_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'completed',
    date_reported DATETIME DEFAULT CURRENT_TIMESTAMP,
    date_scheduled DATETIME,
    date_completed DATETIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (charger_id) REFERENCES chargers(id)
);
