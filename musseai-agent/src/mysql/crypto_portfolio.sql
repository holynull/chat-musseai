-- =============================================
-- 加密货币投资组合管理系统数据库
-- =============================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS crypto_portfolio
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE crypto_portfolio;

-- =============================================
-- 1. 资产来源表
-- =============================================
DROP TABLE IF EXISTS portfolio_sources;
CREATE TABLE portfolio_sources (
    source_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL COMMENT '用户标识',
    source_type ENUM('WALLET', 'EXCHANGE', 'DEFI') NOT NULL COMMENT '来源类型',
    source_name VARCHAR(100) NOT NULL COMMENT '来源名称',
    source_config JSON NOT NULL COMMENT '配置信息（地址、交易所信息等）',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_sync_at TIMESTAMP NULL COMMENT '最后同步时间',
    
    INDEX idx_user_type (user_id, source_type),
    INDEX idx_user_active (user_id, is_active),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='用户资产来源表';

-- =============================================
-- 2. 资产定义表
-- =============================================
DROP TABLE IF EXISTS assets;
CREATE TABLE assets (
    asset_id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL COMMENT '资产符号',
    name VARCHAR(100) NOT NULL COMMENT '资产名称',
    chain VARCHAR(20) NOT NULL DEFAULT 'GENERAL' COMMENT '所属链',
    contract_address VARCHAR(100) NULL COMMENT '合约地址',
    decimals INT DEFAULT 18 COMMENT '精度',
    logo_url VARCHAR(255) NULL COMMENT 'Logo图片URL',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    UNIQUE KEY unique_asset (symbol, chain),
    INDEX idx_symbol (symbol),
    INDEX idx_chain (chain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='资产定义表';

-- =============================================
-- 3. 持仓表
-- =============================================
DROP TABLE IF EXISTS positions;
CREATE TABLE positions (
    position_id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '来源ID',
    asset_id INT NOT NULL COMMENT '资产ID',
    quantity DECIMAL(30,18) NOT NULL DEFAULT 0 COMMENT '持仓数量',
    avg_cost DECIMAL(20,8) NULL COMMENT '平均成本',
    last_price DECIMAL(20,8) NULL COMMENT '最新价格',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    FOREIGN KEY (source_id) REFERENCES portfolio_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    UNIQUE KEY unique_position (source_id, asset_id),
    INDEX idx_source (source_id),
    INDEX idx_asset (asset_id),
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='持仓表';

-- =============================================
-- 4. 交易记录表
-- =============================================
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    source_id INT NOT NULL COMMENT '来源ID',
    transaction_type ENUM('BUY', 'SELL', 'DEPOSIT', 'WITHDRAW', 'TRANSFER') NOT NULL COMMENT '交易类型',
    asset_id INT NOT NULL COMMENT '资产ID',
    quantity DECIMAL(30,18) NOT NULL COMMENT '交易数量',
    price DECIMAL(20,8) NULL COMMENT '交易价格',
    fee DECIMAL(20,8) DEFAULT 0 COMMENT '手续费',
    fee_asset_id INT NULL COMMENT '手续费资产ID',
    external_tx_id VARCHAR(200) NULL COMMENT '外部交易ID',
    transaction_time TIMESTAMP NOT NULL COMMENT '交易时间',
    notes TEXT NULL COMMENT '备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    
    FOREIGN KEY (source_id) REFERENCES portfolio_sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    FOREIGN KEY (fee_asset_id) REFERENCES assets(asset_id) ON DELETE RESTRICT,
    INDEX idx_source_time (source_id, transaction_time),
    INDEX idx_asset (asset_id),
    INDEX idx_type_time (transaction_type, transaction_time),
    INDEX idx_external (external_tx_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='交易记录表';

-- =============================================
-- 5. 价格快照表
-- =============================================
DROP TABLE IF EXISTS price_snapshots;
CREATE TABLE price_snapshots (
    snapshot_id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT NOT NULL COMMENT '资产ID',
    price DECIMAL(20,8) NOT NULL COMMENT '价格',
    timestamp TIMESTAMP NOT NULL COMMENT '时间戳',
    
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE,
    UNIQUE KEY unique_asset_time (asset_id, timestamp),
    INDEX idx_asset_time (asset_id, timestamp DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='价格快照表';

-- =============================================
-- 插入初始数据
-- =============================================

-- 插入常见资产
INSERT INTO assets (symbol, name, chain, decimals) VALUES
-- 主流币
('BTC', 'Bitcoin', 'BTC', 8),
('ETH', 'Ethereum', 'ETH', 18),
('BNB', 'Binance Coin', 'BSC', 18),
('SOL', 'Solana', 'SOL', 9),

-- 稳定币（多链）
('USDT', 'Tether', 'ETH', 6),
('USDT', 'Tether', 'BSC', 18),
('USDT', 'Tether', 'TRX', 6),
('USDC', 'USD Coin', 'ETH', 6),
('USDC', 'USD Coin', 'BSC', 18),
('BUSD', 'Binance USD', 'BSC', 18),
('DAI', 'Dai Stablecoin', 'ETH', 18),

-- DeFi代币
('UNI', 'Uniswap', 'ETH', 18),
('AAVE', 'Aave', 'ETH', 18),
('SUSHI', 'SushiSwap', 'ETH', 18),
('CAKE', 'PancakeSwap', 'BSC', 18),

-- 其他主流代币
('MATIC', 'Polygon', 'POLYGON', 18),
('AVAX', 'Avalanche', 'AVAX', 18),
('DOT', 'Polkadot', 'DOT', 10),
('ADA', 'Cardano', 'ADA', 6),
('LINK', 'Chainlink', 'ETH', 18),
('XRP', 'Ripple', 'XRP', 6);

-- =============================================
-- 创建视图（可选）
-- =============================================

-- 用户投资组合汇总视图
CREATE OR REPLACE VIEW v_user_portfolio_summary AS
SELECT 
    ps.user_id,
    a.symbol,
    a.name,
    a.chain,
    SUM(p.quantity) as total_quantity,
    AVG(p.avg_cost) as avg_cost,
    MAX(p.last_price) as last_price,
    SUM(p.quantity * p.last_price) as current_value,
    SUM(p.quantity * p.avg_cost) as total_cost,
    COUNT(DISTINCT ps.source_id) as source_count,
    MAX(p.updated_at) as last_updated
FROM portfolio_sources ps
JOIN positions p ON ps.source_id = p.source_id
JOIN assets a ON p.asset_id = a.asset_id
WHERE ps.is_active = TRUE AND p.quantity > 0
GROUP BY ps.user_id, a.asset_id;

-- 用户交易历史视图
CREATE OR REPLACE VIEW v_user_transactions AS
SELECT 
    ps.user_id,
    ps.source_name,
    ps.source_type,
    t.transaction_id,
    t.transaction_type,
    a.symbol,
    a.name,
    t.quantity,
    t.price,
    t.fee,
    fa.symbol as fee_symbol,
    t.transaction_time,
    t.notes
FROM portfolio_sources ps
JOIN transactions t ON ps.source_id = t.source_id
JOIN assets a ON t.asset_id = a.asset_id
LEFT JOIN assets fa ON t.fee_asset_id = fa.asset_id
ORDER BY t.transaction_time DESC;

-- =============================================
-- 创建存储过程（可选）
-- =============================================

-- 更新持仓的存储过程
DELIMITER //
CREATE PROCEDURE sp_update_position(
    IN p_source_id INT,
    IN p_asset_id INT,
    IN p_quantity DECIMAL(30,18),
    IN p_avg_cost DECIMAL(20,8),
    IN p_transaction_type VARCHAR(20)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- 更新或插入持仓
    INSERT INTO positions (source_id, asset_id, quantity, avg_cost)
    VALUES (p_source_id, p_asset_id, p_quantity, p_avg_cost)
    ON DUPLICATE KEY UPDATE
        quantity = VALUES(quantity),
        avg_cost = VALUES(avg_cost),
        updated_at = CURRENT_TIMESTAMP;
    
    -- 记录交易
    INSERT INTO transactions (
        source_id, transaction_type, asset_id, 
        quantity, price, transaction_time
    )
    VALUES (
        p_source_id, p_transaction_type, p_asset_id,
        p_quantity, p_avg_cost, CURRENT_TIMESTAMP
    );
    
    COMMIT;
END//
DELIMITER ;

-- =============================================
-- 授权（根据需要调整）
-- =============================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON crypto_portfolio.* TO 'app_user'@'%';
-- FLUSH PRIVILEGES;

-- =============================================
-- 查看创建的表
-- =============================================
SHOW TABLES;

-- 查看表结构
-- DESCRIBE portfolio_sources;
-- DESCRIBE assets;
-- DESCRIBE positions;
-- DESCRIBE transactions;
-- DESCRIBE price_snapshots;
