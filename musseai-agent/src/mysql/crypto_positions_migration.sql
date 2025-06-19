-- 改进版crypto_positions_migration.sql：数据迁移和初始化数据
-- 作者：Assistant
-- 版本：2.0

USE crypto_positions;

-- --------------------------------
-- 初始化资产来源类型
-- --------------------------------
INSERT INTO asset_source_types (type_name, description) VALUES
('WALLET', '区块链钱包地址'),
('EXCHANGE', '中心化交易所账户'),
('DEFI', 'DeFi协议中的仓位');

-- --------------------------------
-- 初始化支持的交易所
-- --------------------------------
INSERT INTO supported_exchanges (exchange_name, display_name, api_base_url, supported_features) VALUES
('Binance', 'Binance', 'https://api.binance.com', '{"spot": true, "margin": true, "futures": true}'),
('Coinbase', 'Coinbase', 'https://api.coinbase.com', '{"spot": true}'),
('OKX', 'OKX', 'https://www.okx.com', '{"spot": true, "margin": true, "futures": true}'),
('Huobi', 'Huobi Global', 'https://api.huobi.pro', '{"spot": true, "margin": true, "futures": true}'),
('Kraken', 'Kraken', 'https://api.kraken.com', '{"spot": true, "margin": true, "futures": true}'),
('Bybit', 'Bybit', 'https://api.bybit.com', '{"spot": true, "futures": true}'),
('Gate.io', 'Gate.io', 'https://api.gateio.ws', '{"spot": true, "margin": true, "futures": true}'),
('KuCoin', 'KuCoin', 'https://api.kucoin.com', '{"spot": true, "margin": true, "futures": true}');

-- --------------------------------
-- 数据迁移存储过程
-- --------------------------------
DELIMITER //
CREATE PROCEDURE migrate_wallet_data()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_wallet_id BIGINT;
    DECLARE v_user_id VARCHAR(100);
    DECLARE v_address VARCHAR(100);
    DECLARE v_chain_type VARCHAR(20);
    DECLARE v_address_label VARCHAR(50);
    DECLARE v_created_at TIMESTAMP;
    DECLARE v_source_id BIGINT;
    
    -- 声明游标
    DECLARE wallet_cursor CURSOR FOR 
        SELECT wallet_id, user_id, address, chain_type, address_label, created_at
        FROM wallet_addresses;
    
    -- 声明异常处理
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    
    -- 确保钱包类型存在
    SET @wallet_type_id = (SELECT source_type_id FROM asset_source_types WHERE type_name = 'WALLET');
    
    IF @wallet_type_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'WALLET source type not found in asset_source_types table';
    END IF;
    
    -- 开始事务
    START TRANSACTION;
    
    -- 创建临时映射表
    DROP TEMPORARY TABLE IF EXISTS wallet_to_source_mapping;
    CREATE TEMPORARY TABLE wallet_to_source_mapping (
        wallet_id BIGINT,
        source_id BIGINT
    );
    
    -- 打开游标
    OPEN wallet_cursor;
    
    -- 开始循环
    wallet_loop: LOOP
        FETCH wallet_cursor INTO v_wallet_id, v_user_id, v_address, v_chain_type, v_address_label, v_created_at;
        
        IF done THEN
            LEAVE wallet_loop;
        END IF;
        
        -- 插入到资产来源表
        INSERT INTO asset_sources (
            user_id, 
            source_type_id, 
            source_name, 
            source_details,
            created_at
        ) VALUES (
            v_user_id,
            @wallet_type_id,
            CONCAT(v_address, '_', v_chain_type),
            JSON_OBJECT(
			'address', v_address, 
            'chain_type', v_chain_type, 
            'address_label', v_address_label
            ),
            v_created_at
        );
        
        -- 获取新插入的source_id
        SET v_source_id = LAST_INSERT_ID();
        
        -- 添加到映射表
        INSERT INTO wallet_to_source_mapping (wallet_id, source_id)
        VALUES (v_wallet_id, v_source_id);
        
    END LOOP;
    
    -- 关闭游标
    CLOSE wallet_cursor;
    
    -- 迁移仓位数据
    INSERT INTO asset_positions (
        source_id, 
        asset_id, 
        quantity, 
        last_updated_at, 
        last_sync_time
    )
    SELECT 
        m.source_id,
        wp.asset_id,
        wp.quantity,
        wp.last_updated_at,
        wp.last_sync_time
    FROM wallet_positions wp
    JOIN wallet_to_source_mapping m ON wp.wallet_id = m.wallet_id;
    
    -- 迁移历史记录
    INSERT INTO position_history_new (
        source_id, 
        asset_id, 
        quantity, 
        change_amount, 
        created_at, 
        agent_id, 
        conversation_id,
        sync_type,
        operation_type
    )
    SELECT 
        m.source_id,
        ph.asset_id,
        ph.quantity,
        ph.change_amount,
        ph.created_at,
        ph.agent_id,
        ph.conversation_id,
        'MANUAL',
        CASE 
            WHEN ph.change_amount > 0 THEN 'DEPOSIT'
            ELSE 'WITHDRAW'
        END
    FROM position_history ph
    JOIN wallet_to_source_mapping m ON ph.wallet_id = m.wallet_id;
    
    -- 清理临时表
    DROP TEMPORARY TABLE wallet_to_source_mapping;
    
    -- 提交事务
    COMMIT;
    
END //
DELIMITER ;

-- --------------------------------
-- 常见加密资产初始化数据
-- --------------------------------
INSERT INTO crypto_assets (asset_symbol, asset_name, chain_type, contract_address, decimals) VALUES
-- 主网币
('BTC', 'Bitcoin', 'BTC', NULL, 8),
('ETH', 'Ethereum', 'ETH', NULL, 18),
('BNB', 'Binance Coin', 'BSC', NULL, 18),
('SOL', 'Solana', 'SOLANA', NULL, 9),
('MATIC', 'Polygon', 'POLYGON', NULL, 18),
('TRX', 'TRON', 'TRON', NULL, 6),
('AVAX', 'Avalanche', 'AVALANCHE', NULL, 18),
('ARB', 'Arbitrum', 'ARBITRUM', '0x912CE59144191C1204E64559FE8253a0e49E6548', 18),
('OP', 'Optimism', 'OPTIMISM', '0x4200000000000000000000000000000000000042', 18),

-- ERC20代币
('USDT', 'Tether USD', 'ETH', '0xdac17f958d2ee523a2206206994597c13d831ec7', 6),
('USDC', 'USD Coin', 'ETH', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 6),
('DAI', 'Dai Stablecoin', 'ETH', '0x6b175474e89094c44da98b954eedeac495271d0f', 18),
('LINK', 'Chainlink', 'ETH', '0x514910771af9ca656af840dff83e8264ecf986ca', 18),
('UNI', 'Uniswap', 'ETH', '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', 18),
('AAVE', 'Aave', 'ETH', '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9', 18),

-- BSC代币
('USDT', 'Tether USD', 'BSC', '0x55d398326f99059ff775485246999027b3197955', 18),
('USDC', 'USD Coin', 'BSC', '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d', 18),
('CAKE', 'PancakeSwap', 'BSC', '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82', 18),

-- Polygon代币
('USDT', 'Tether USD', 'POLYGON', '0xc2132d05d31c914a87c6611c10748aeb04b58e8f', 6),
('USDC', 'USD Coin', 'POLYGON', '0x2791bca1f2de4661ed88a30c99a7a9449aa84174', 6),

-- Solana代币
('USDT', 'Tether USD', 'SOLANA', 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', 6),
('USDC', 'USD Coin', 'SOLANA', 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 6),

-- TRON代币
('USDT', 'Tether USD', 'TRON', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 6),
('USDD', 'USDD', 'TRON', 'TPQuDh4En44sR27p5dLcwovkf7yBAD6Yrx', 18),

-- Avalanche代币
('USDT', 'Tether USD', 'AVALANCHE', '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 6),
('USDC', 'USD Coin', 'AVALANCHE', '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e', 6);

-- --------------------------------
-- 使用说明
-- --------------------------------
/*
执行顺序：
1. 首先执行 crypto_positions_schema.sql 创建表结构
2. 然后执行本文件 crypto_positions_migration.sql 进行数据初始化
3. 如果需要迁移现有钱包数据，执行：
   CALL migrate_wallet_data();

数据验证：
1. 检查资产来源类型：
   SELECT * FROM asset_source_types;

2. 检查支持的交易所：
   SELECT * FROM supported_exchanges;

3. 检查加密资产列表：
   SELECT * FROM crypto_assets;

4. 如果进行了数据迁移，检查迁移结果：
   SELECT * FROM asset_sources;
   SELECT * FROM asset_positions;
   SELECT * FROM position_history_new;

5. 查看用户总资产：
   SELECT * FROM user_total_positions;

6. 查看交易所资产：
   SELECT * FROM exchange_positions;
*/

