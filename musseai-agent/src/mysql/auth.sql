-- 创建用户（如果不存在）
CREATE USER IF NOT EXISTS 'asset_agent'@'localhost' IDENTIFIED BY 'asset_agent_123456';

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS crypto_positions;

-- 授予用户对数据库的所有权限
GRANT ALL PRIVILEGES ON crypto_positions.* TO 'asset_agent'@'localhost';

-- 如果需要从任何主机连接（不仅仅是localhost）
CREATE USER IF NOT EXISTS 'asset_agent'@'%' IDENTIFIED BY 'asset_agent_123456';
GRANT ALL PRIVILEGES ON crypto_positions.* TO 'asset_agent'@'%';

-- 刷新权限
FLUSH PRIVILEGES;
