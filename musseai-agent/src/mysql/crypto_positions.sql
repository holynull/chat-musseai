-- 创建数据库
CREATE DATABASE IF NOT EXISTS crypto_positions DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE crypto_positions;

-- 创建钱包地址表
CREATE TABLE wallet_addresses (
    wallet_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) NOT NULL,
    address VARCHAR(100) NOT NULL COMMENT '钱包地址',
    chain_type VARCHAR(20) NOT NULL COMMENT '链类型，如 ETH, BSC 等',
    address_label VARCHAR(50) COMMENT '地址标签（可选）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_address_chain (address, chain_type),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='钱包地址表';

-- 创建资产类型表
CREATE TABLE crypto_assets (
    asset_id INT PRIMARY KEY AUTO_INCREMENT,
    asset_symbol VARCHAR(20) NOT NULL COMMENT '如 BTC, ETH 等',
    asset_name VARCHAR(50) NOT NULL,
    chain_type VARCHAR(20) NOT NULL COMMENT '所属链',
    contract_address VARCHAR(100) COMMENT '代币合约地址（主币为null）',
    decimals INT DEFAULT 18 COMMENT '精度位数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TINYINT DEFAULT 1 COMMENT '1:active, 0:inactive',
    INDEX idx_symbol (asset_symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='加密资产信息表';

-- 创建仓位信息表
CREATE TABLE wallet_positions (
    position_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    wallet_id BIGINT NOT NULL,
    asset_id INT NOT NULL,
    quantity DECIMAL(65,18) NOT NULL COMMENT '数量（使用更大精度）',
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_sync_time TIMESTAMP NULL COMMENT '最后同步时间',
    FOREIGN KEY (wallet_id) REFERENCES wallet_addresses(wallet_id),
    FOREIGN KEY (asset_id) REFERENCES crypto_assets(asset_id),
    UNIQUE INDEX idx_wallet_asset (wallet_id, asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='钱包仓位信息表';

-- 创建仓位历史记录表
CREATE TABLE position_history (
    history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    wallet_id BIGINT NOT NULL,
    asset_id INT NOT NULL,
    quantity DECIMAL(65,18) NOT NULL,
    change_amount DECIMAL(65,18) NOT NULL COMMENT '变化数量（正数增加，负数减少）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_id VARCHAR(50) COMMENT '记录操作的agent标识',
    conversation_id VARCHAR(100) COMMENT '对话ID',
    FOREIGN KEY (wallet_id) REFERENCES wallet_addresses(wallet_id),
    FOREIGN KEY (asset_id) REFERENCES crypto_assets(asset_id),
    INDEX idx_wallet_time (wallet_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓位历史记录表';

-- 创建Agent操作日志表
CREATE TABLE agent_logs (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    conversation_id VARCHAR(100),
    action_type VARCHAR(20),
    request_content TEXT,
    response_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TINYINT COMMENT '1:success, 0:failed',
    error_message TEXT,
    INDEX idx_user_conv (user_id, conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent操作日志表';

-- 插入一些示例数据
-- 插入常见主链信息
INSERT INTO crypto_assets (asset_symbol, asset_name, chain_type, decimals) VALUES
('ETH', 'Ethereum', 'ETH', 18),
('BNB', 'Binance Coin', 'BSC', 18),
('BTC', 'Bitcoin', 'BTC', 8),
('MATIC', 'Polygon', 'POLYGON', 18),
('TRX', 'TRON', 'TRON', 6);

-- 插入一些常见代币
INSERT INTO crypto_assets (asset_symbol, asset_name, chain_type, contract_address, decimals) VALUES
('USDT', 'Tether USD', 'ETH', '0xdac17f958d2ee523a2206206994597c13d831ec7', 6),
('USDC', 'USD Coin', 'ETH', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 6),
('BUSD', 'Binance USD', 'BSC', '0xe9e7cea3dedca5984780bafc599bd69add087d56', 18),
('USDT', 'Tether USD', 'BSC', '0x55d398326f99059ff775485246999027b3197955', 18),
('USDT', 'Tether USD', 'TRON', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 6);

-- 添加触发器：更新仓位时自动记录历史
DELIMITER //
CREATE TRIGGER trg_position_history
AFTER UPDATE ON wallet_positions
FOR EACH ROW
BEGIN
    IF NEW.quantity != OLD.quantity THEN
        INSERT INTO position_history (
            wallet_id,
            asset_id,
            quantity,
            change_amount
        ) VALUES (
            NEW.wallet_id,
            NEW.asset_id,
            NEW.quantity,
            NEW.quantity - OLD.quantity
        );
    END IF;
END//
DELIMITER ;

-- 创建视图：用户总资产视图
CREATE VIEW user_total_positions AS
SELECT 
    u.user_id,
    u.username,
    wa.address,
    wa.chain_type,
    ca.asset_symbol,
    wp.quantity,
    wp.last_updated_at
FROM users u
JOIN wallet_addresses wa ON u.user_id = wa.user_id
JOIN wallet_positions wp ON wa.wallet_id = wp.wallet_id
JOIN crypto_assets ca ON wp.asset_id = ca.asset_id
WHERE u.status = 1;
