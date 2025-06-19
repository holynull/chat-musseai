-- 改进版crypto_positions_schema.sql：数据库结构定义
-- 作者：Assistant
-- 版本：2.0

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS crypto_positions DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE crypto_positions;

-- --------------------------------
-- 新增表：资产来源类型表
-- --------------------------------
CREATE TABLE IF NOT EXISTS asset_source_types (
    source_type_id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(50) NOT NULL COMMENT '资产来源类型，如 WALLET, EXCHANGE, DeFi 等',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TINYINT DEFAULT 1 COMMENT '1:active, 0:inactive',
    UNIQUE INDEX idx_type_name (type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资产来源类型表';

-- --------------------------------
-- 新增表：资产来源表
-- --------------------------------
CREATE TABLE IF NOT EXISTS asset_sources (
    source_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) NOT NULL,
    source_type_id INT NOT NULL,
    source_name VARCHAR(100) NOT NULL COMMENT '资产来源名称/标识',
    source_details JSON COMMENT '存储特定来源类型的详细信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_time TIMESTAMP NULL COMMENT '最后同步时间',
    FOREIGN KEY (source_type_id) REFERENCES asset_source_types(source_type_id),
    UNIQUE INDEX idx_user_source (user_id, source_type_id, source_name),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资产来源表';

-- --------------------------------
-- 新增表：支持的交易所表
-- --------------------------------
CREATE TABLE IF NOT EXISTS supported_exchanges (
    exchange_id INT PRIMARY KEY AUTO_INCREMENT,
    exchange_name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    api_base_url VARCHAR(200) NOT NULL,
    logo_url VARCHAR(200),
    supported_features JSON COMMENT '支持的功能，如 spot_trading, margin, futures 等',
    status TINYINT DEFAULT 1 COMMENT '1:active, 0:inactive',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_exchange_name (exchange_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支持的交易所表';

-- --------------------------------
-- 新增表：交易所API凭证表
-- --------------------------------
CREATE TABLE IF NOT EXISTS exchange_api_credentials (
    credential_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) NOT NULL,
    exchange_name VARCHAR(50) NOT NULL COMMENT '交易所名称，如 Binance, Coinbase 等',
    api_key VARCHAR(200) NOT NULL COMMENT 'API Key',
    api_secret VARCHAR(500) NOT NULL COMMENT '加密存储的API Secret',
    api_passphrase VARCHAR(200) COMMENT '部分交易所需要的API密码',
    description VARCHAR(200) COMMENT '用户描述',
    is_active TINYINT DEFAULT 1 COMMENT '是否激活',
    permissions JSON COMMENT '该API的权限信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,
    UNIQUE INDEX idx_user_exchange_key (user_id, exchange_name, api_key),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易所API凭证表';

-- --------------------------------
-- 保留并扩展：资产类型表
-- --------------------------------
CREATE TABLE IF NOT EXISTS crypto_assets (
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

-- --------------------------------
-- 新增表：资产仓位表
-- --------------------------------
CREATE TABLE IF NOT EXISTS asset_positions (
    position_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_id BIGINT NOT NULL,
    asset_id INT NOT NULL,
    quantity DECIMAL(65,18) NOT NULL COMMENT '数量',
    cost_basis DECIMAL(20,8) DEFAULT NULL COMMENT '成本基础（可选）',
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_sync_time TIMESTAMP NULL COMMENT '最后同步时间',
    additional_data JSON COMMENT '额外特定资产信息',
    FOREIGN KEY (source_id) REFERENCES asset_sources(source_id),
    FOREIGN KEY (asset_id) REFERENCES crypto_assets(asset_id),
    UNIQUE INDEX idx_source_asset (source_id, asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资产仓位信息表';

-- --------------------------------
-- 新增表：仓位历史记录表（增强版）
-- --------------------------------
CREATE TABLE IF NOT EXISTS position_history_new (
    history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_id BIGINT NOT NULL,
    asset_id INT NOT NULL,
    quantity DECIMAL(65,18) NOT NULL,
    change_amount DECIMAL(65,18) NOT NULL COMMENT '变化数量',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_id VARCHAR(50) COMMENT '记录操作的agent标识',
    conversation_id VARCHAR(100) COMMENT '对话ID',
    sync_type VARCHAR(30) COMMENT '同步类型，如 MANUAL, API, BLOCKCHAIN',
    operation_type VARCHAR(30) COMMENT '操作类型，如 DEPOSIT, WITHDRAW, TRADE',
    operation_details JSON COMMENT '操作详情',
    FOREIGN KEY (source_id) REFERENCES asset_sources(source_id),
    FOREIGN KEY (asset_id) REFERENCES crypto_assets(asset_id),
    INDEX idx_source_time (source_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓位历史记录表（新版）';

-- --------------------------------
-- 新增表：资产交易记录表
-- --------------------------------
CREATE TABLE IF NOT EXISTS asset_transactions (
    transaction_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(100) NOT NULL,
    source_id BIGINT NOT NULL,
    transaction_type VARCHAR(30) NOT NULL COMMENT '交易类型，如 BUY, SELL, DEPOSIT, WITHDRAW',
    base_asset_id INT NOT NULL COMMENT '基础资产ID',
    quote_asset_id INT COMMENT '计价资产ID（如适用）',
    base_amount DECIMAL(65,18) NOT NULL COMMENT '基础资产数量',
    quote_amount DECIMAL(65,18) COMMENT '计价资产数量（如适用）',
    fee_asset_id INT COMMENT '手续费资产ID',
    fee_amount DECIMAL(65,18) COMMENT '手续费数量',
    price DECIMAL(65,18) COMMENT '成交价格',
    transaction_time TIMESTAMP NOT NULL COMMENT '交易时间',
    external_id VARCHAR(200) COMMENT '外部系统的交易ID',
    status VARCHAR(20) NOT NULL DEFAULT 'COMPLETED' COMMENT '交易状态',
    additional_info JSON COMMENT '额外信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES asset_sources(source_id),
    FOREIGN KEY (base_asset_id) REFERENCES crypto_assets(asset_id),
    FOREIGN KEY (quote_asset_id) REFERENCES crypto_assets(asset_id),
    FOREIGN KEY (fee_asset_id) REFERENCES crypto_assets(asset_id),
    INDEX idx_user_time (user_id, transaction_time),
    INDEX idx_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资产交易记录表';

-- --------------------------------
-- 触发器：资产仓位更新历史记录
-- --------------------------------
DELIMITER //
CREATE TRIGGER trg_position_history_new
AFTER UPDATE ON asset_positions
FOR EACH ROW
BEGIN
    IF NEW.quantity != OLD.quantity THEN
        INSERT INTO position_history_new (
            source_id,
            asset_id,
            quantity,
            change_amount,
            sync_type,
            operation_type
        ) VALUES (
            NEW.source_id,
            NEW.asset_id,
            NEW.quantity,
            NEW.quantity - OLD.quantity,
            'SYSTEM',
            CASE 
                WHEN NEW.quantity > OLD.quantity THEN 'DEPOSIT'
                ELSE 'WITHDRAW'
            END
        );
    END IF;
END //
DELIMITER ;

-- --------------------------------
-- 视图：用户总资产视图
-- --------------------------------
CREATE OR REPLACE VIEW user_total_positions AS
SELECT 
    ast.user_id,
    ast.source_name,
    ast_type.type_name as source_type,
    ca.asset_symbol,
    ca.asset_name,
    ca.chain_type,
    ap.quantity,
    ap.cost_basis,
    ap.last_updated_at,
    JSON_MERGE(ast.source_details, ap.additional_data) as details
FROM asset_sources ast
JOIN asset_source_types ast_type ON ast.source_type_id = ast_type.source_type_id
JOIN asset_positions ap ON ast.source_id = ap.source_id
JOIN crypto_assets ca ON ap.asset_id = ca.asset_id
WHERE ast_type.status = 1;

-- --------------------------------
-- 视图：交易所资产视图
-- --------------------------------
CREATE OR REPLACE VIEW exchange_positions AS
SELECT 
    ast.user_id,
    se.exchange_name,
    se.display_name as exchange_display_name,
    ast.source_name as account_name,
    ca.asset_symbol,
    ca.asset_name,
    ap.quantity,
    ap.cost_basis,
    ap.last_updated_at
FROM asset_sources ast
JOIN asset_source_types ast_type ON ast.source_type_id = ast_type.source_type_id
JOIN asset_positions ap ON ast.source_id = ap.source_id
JOIN crypto_assets ca ON ap.asset_id = ca.asset_id
JOIN supported_exchanges se ON JSON_EXTRACT(ast.source_details, '$.exchange') = se.exchange_name
WHERE ast_type.type_name = 'EXCHANGE'
AND se.status = 1;
