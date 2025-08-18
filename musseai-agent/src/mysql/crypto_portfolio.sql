-- =============================================
-- Crypto Portfolio Management System Database
-- =============================================

-- Create database
CREATE DATABASE IF NOT EXISTS crypto_portfolio
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE crypto_portfolio;

-- =============================================
-- 1. Portfolio Sources Table
-- =============================================
DROP TABLE IF EXISTS portfolio_sources;
CREATE TABLE portfolio_sources (
    source_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL COMMENT 'User identifier',
    source_type ENUM('WALLET', 'EXCHANGE', 'DEFI') NOT NULL COMMENT 'Source type',
    source_name VARCHAR(100) NOT NULL COMMENT 'Source name',
    source_config JSON NOT NULL COMMENT 'Configuration info (address, exchange info, etc.)',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    last_sync_at TIMESTAMP NULL COMMENT 'Last sync time',
    
    INDEX idx_user_type (user_id, source_type),
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='User portfolio sources table';

-- =============================================
-- 2. Assets Definition Table
-- =============================================
DROP TABLE IF EXISTS assets;
CREATE TABLE assets (
    asset_id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL COMMENT 'Asset symbol',
    name VARCHAR(100) NOT NULL COMMENT 'Asset name',
    chain VARCHAR(20) NOT NULL DEFAULT 'GENERAL' COMMENT 'Blockchain',
    contract_address VARCHAR(100) NULL COMMENT 'Contract address',
    decimals INT DEFAULT 18 COMMENT 'Decimal precision',
    logo_url VARCHAR(255) NULL COMMENT 'Logo image URL',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    
    UNIQUE KEY unique_asset (symbol, chain),
    INDEX idx_symbol (symbol),
    INDEX idx_chain (chain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Assets definition table';

-- =============================================
-- 3. Positions Table
-- =============================================
DROP TABLE IF EXISTS positions;
CREATE TABLE positions (
    position_id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT 'Source ID',
    asset_id INT NOT NULL COMMENT 'Asset ID',
    quantity DECIMAL(30,18) NOT NULL DEFAULT 0 COMMENT 'Position quantity',
    avg_cost DECIMAL(20,8) NULL COMMENT 'Average cost',
    last_price DECIMAL(20,8) NULL COMMENT 'Last price',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    
    FOREIGN KEY (source_id) REFERENCES portfolio_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    UNIQUE KEY unique_position (source_id, asset_id),
    INDEX idx_source (source_id),
    INDEX idx_asset (asset_id),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Positions table';

-- =============================================
-- 4. Transactions Table
-- =============================================
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT 'Source ID',
    transaction_type ENUM('BUY', 'SELL', 'DEPOSIT', 'WITHDRAW', 'TRANSFER') NOT NULL COMMENT 'Transaction type',
    asset_id INT NOT NULL COMMENT 'Asset ID',
    quantity DECIMAL(30,18) NOT NULL COMMENT 'Transaction quantity',
    price DECIMAL(20,8) NULL COMMENT 'Transaction price',
    fee DECIMAL(20,8) DEFAULT 0 COMMENT 'Transaction fee',
    fee_asset_id INT NULL COMMENT 'Fee asset ID',
    external_tx_id VARCHAR(200) NULL COMMENT 'External transaction ID',
    transaction_time TIMESTAMP NOT NULL COMMENT 'Transaction time',
    notes TEXT NULL COMMENT 'Notes',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    
    FOREIGN KEY (source_id) REFERENCES portfolio_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    FOREIGN KEY (fee_asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    INDEX idx_source_time (source_id, transaction_time),
    INDEX idx_asset (asset_id),
    INDEX idx_type_time (transaction_type, transaction_time),
    INDEX idx_external (external_tx_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Transactions table';

-- =============================================
-- 5. Price Snapshots Table
-- =============================================
DROP TABLE IF EXISTS price_snapshots;
CREATE TABLE price_snapshots (
    snapshot_id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT NOT NULL COMMENT 'Asset ID',
    price DECIMAL(20,8) NOT NULL COMMENT 'Price',
    timestamp TIMESTAMP NOT NULL COMMENT 'Timestamp',
    
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE,
    UNIQUE KEY unique_asset_time (asset_id, timestamp),
    INDEX idx_asset_time (asset_id, timestamp DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Price snapshots table';

-- =============================================
-- 6. Portfolio Alerts Table (NEW)
-- =============================================
DROP TABLE IF EXISTS portfolio_alerts;
CREATE TABLE portfolio_alerts (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL COMMENT 'User identifier',
    alert_type ENUM('PRICE', 'PORTFOLIO_VALUE', 'RISK', 'PERFORMANCE', 'REBALANCING', 'VOLUME', 'VOLATILITY') NOT NULL COMMENT 'Alert type',
    alert_name VARCHAR(200) NOT NULL COMMENT 'User-defined alert name',
    conditions JSON NOT NULL COMMENT 'Alert conditions',
    notification_methods JSON NOT NULL COMMENT 'Notification methods',
    status ENUM('ACTIVE', 'TRIGGERED', 'INACTIVE', 'EXPIRED') DEFAULT 'ACTIVE' COMMENT 'Alert status',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
    last_checked_at TIMESTAMP NULL COMMENT 'Last check time',
    last_triggered_at TIMESTAMP NULL COMMENT 'Last trigger time',
    trigger_count INT DEFAULT 0 COMMENT 'Total trigger count',
    
    INDEX idx_user_type (user_id, alert_type),
    INDEX idx_user_status (user_id, status),
    INDEX idx_status_check (status, last_checked_at),
    INDEX idx_user_active (user_id, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Portfolio alerts configuration table';

ALTER TABLE portfolio_alerts ADD COLUMN expiry_date TIMESTAMP NULL COMMENT 'Alert expiry date';

-- =============================================
-- 7. Alert History Table (NEW)
-- =============================================
DROP TABLE IF EXISTS alert_history;
CREATE TABLE alert_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    alert_id INT NOT NULL COMMENT 'Alert ID',
    triggered_at TIMESTAMP NOT NULL COMMENT 'Trigger time',
    trigger_value JSON NOT NULL COMMENT 'Values that triggered the alert',
    message TEXT NOT NULL COMMENT 'Alert message',
    notification_sent BOOLEAN DEFAULT FALSE COMMENT 'Whether notification was sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    
    FOREIGN KEY (alert_id) REFERENCES portfolio_alerts(alert_id) ON DELETE CASCADE,
    INDEX idx_alert_time (alert_id, triggered_at DESC),
    INDEX idx_triggered_time (triggered_at DESC),
    INDEX idx_notification (notification_sent, triggered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Alert trigger history table';

-- =============================================
-- Insert Initial Data
-- =============================================

-- Insert common assets
INSERT INTO assets (symbol, name, chain, decimals) VALUES
-- Major cryptocurrencies
('BTC', 'Bitcoin', 'BTC', 8),
('ETH', 'Ethereum', 'ETH', 18),
('BNB', 'Binance Coin', 'BSC', 18),
('SOL', 'Solana', 'SOL', 9),

-- Stablecoins (multi-chain)
('USDT', 'Tether', 'ETH', 6),
('USDT', 'Tether', 'BSC', 18),
('USDT', 'Tether', 'TRX', 6),
('USDC', 'USD Coin', 'ETH', 6),
('USDC', 'USD Coin', 'BSC', 18),
('BUSD', 'Binance USD', 'BSC', 18),
('DAI', 'Dai Stablecoin', 'ETH', 18),

-- DeFi tokens
('UNI', 'Uniswap', 'ETH', 18),
('AAVE', 'Aave', 'ETH', 18),
-- DeFi tokens
('UNI', 'Uniswap', 'ETH', 18),
('AAVE', 'Aave', 'ETH', 18),
('SUSHI', 'SushiSwap', 'ETH', 18),
('CAKE', 'PancakeSwap', 'BSC', 18),

-- Other major tokens
('MATIC', 'Polygon', 'POLYGON', 18),
('AVAX', 'Avalanche', 'AVAX', 18),
('DOT', 'Polkadot', 'DOT', 10),
('ADA', 'Cardano', 'ADA', 6),
('LINK', 'Chainlink', 'ETH', 18),
('XRP', 'Ripple', 'XRP', 6);