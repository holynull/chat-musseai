-- =============================================
-- 向 assets 表插入数据
-- 基于 crypto_portfolio.sql 的表结构
-- =============================================

USE crypto_portfolio;

-- 插入资产数据，避免重复
INSERT IGNORE INTO assets (symbol, name, chain, contract_address, decimals, logo_url) VALUES

-- 主流区块链原生币
('BTC', 'Bitcoin', 'BTC', NULL, 8, NULL),
('ETH', 'Ethereum', 'ETH', NULL, 18, NULL),
('SOL', 'Solana', 'SOL', NULL, 9, NULL),
('TRX', 'TRON', 'TRX', NULL, 6, NULL),
('BNB', 'Binance Coin', 'BSC', NULL, 18, NULL),
('BCH', 'Bitcoin Cash', 'BCH', NULL, 8, NULL),
('LTC', 'Litecoin', 'LTC', NULL, 8, NULL),
('XRP', 'Ripple', 'XRP', NULL, 6, NULL),
('DOGE', 'Dogecoin', 'DOGE', NULL, 8, NULL),
('AVAX', 'Avalanche', 'AVAX', NULL, 18, NULL),
('MATIC', 'Polygon', 'POLYGON', NULL, 18, NULL),
('APT', 'Aptos', 'APT', NULL, 8, NULL),
('TON', 'TON', 'TON', NULL, 9, NULL),
('OP', 'Optimism', 'OPTIMISM', '0x4200000000000000000000000000000000000042', 18, NULL),
('ARB', 'Arbitrum', 'ARBITRUM', '0x912CE59144191C1204E64559FE8253a0e49E6548', 18, NULL),
('SUI', 'Sui', 'SUI', '0x2::sui::SUI', 9, NULL),

-- 以太坊代币
('USDT', 'Tether', 'ETH', '0xdac17f958d2ee523a2206206994597c13d831ec7', 6, NULL),
('USDC', 'USD Coin', 'ETH', '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 6, NULL),
('DAI', 'Dai Stablecoin', 'ETH', '0x6B175474E89094C44Da98b954EedeAC495271d0F', 18, NULL),
('WBTC', 'Wrapped Bitcoin', 'ETH', '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 8, NULL),
('WETH', 'Wrapped Ether', 'ETH', '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', 18, NULL),
('LINK', 'Chainlink', 'ETH', '0x514910771af9ca656af840dff83e8264ecf986ca', 18, NULL),
('UNI', 'Uniswap', 'ETH', '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 18, NULL),
('AAVE', 'Aave', 'ETH', '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9', 18, NULL),
('SHIB', 'Shiba Inu', 'ETH', '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce', 18, NULL),
('PEPE', 'Pepe', 'ETH', '0x6982508145454Ce325dDbE47a25d4ec3d2311933', 18, NULL),
('MANA', 'Decentraland', 'ETH', '0x0f5d2fb29fb7d3cfee444a200298f468908cc942', 18, NULL),
('ENS', 'Ethereum Name Service', 'ETH', '0xc18360217d8f7ab5e7c516566761ea12ce7f9d72', 18, NULL),
('APE', 'ApeCoin', 'ETH', '0x4d224452801aced8b2f0aebe155379bb5d594381', 18, NULL),
('QNT', 'Quant', 'ETH', '0x4a220e6096b25eadb88358cb44068a3248254675', 18, NULL),
('1INCH', '1inch', 'ETH', '0x111111111117dc0aa78b770fa6a738034120c302', 18, NULL),
('GRT', 'The Graph', 'ETH', '0xc944E90C64B2c07662A292be6244BDf05Cda44a7', 18, NULL),
('BAT', 'Basic Attention Token', 'ETH', '0x0d8775f648430679a709e98d2b0cb6250d2887ef', 18, NULL),
('COMP', 'Compound', 'ETH', '0xc00e94cb662c3520282e6f5717214004a7f26888', 18, NULL),
('YFI', 'yearn.finance', 'ETH', '0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e', 18, NULL),
('SUSHI', 'SushiSwap', 'ETH', '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2', 18, NULL),
('IMX', 'Immutable X', 'ETH', '0xf57e7e7c23978c3caec3c3548e3d615c346e79ff', 18, NULL),
('NEXO', 'Nexo', 'ETH', '0xb62132e35a6c13ee1ee0f84dc5d40bad8d815206', 18, NULL),

-- BSC 代币
('USDT', 'Tether', 'BSC', '0x55d398326f99059ff775485246999027b3197955', 18, NULL),
('USDC', 'USD Coin', 'BSC', '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d', 18, NULL),
('BUSD', 'Binance USD', 'BSC', '0xe9e7cea3dedca5984780bafc599bd69add087d56', 18, NULL),
('DAI', 'Dai Stablecoin', 'BSC', '0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3', 18, NULL),
('BTCB', 'Bitcoin BEP20', 'BSC', '0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c', 18, NULL),
('ETH', 'Ethereum', 'BSC', '0x2170ed0880ac9a755fd29b2688956bd959f933f8', 18, NULL),
('CAKE', 'PancakeSwap', 'BSC', '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82', 18, NULL),
('WBNB', 'Wrapped BNB', 'BSC', '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 18, NULL),
('UNI', 'Uniswap', 'BSC', '0xbf5140a22578168fd562dccf235e5d43a02ce9b1', 18, NULL),
('LINK', 'Chainlink', 'BSC', '0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd', 18, NULL),
('DOT', 'Polkadot', 'BSC', '0x7083609fce4d1d8dc0c979aab8c869ea2c873402', 18, NULL),
('AVAX', 'Avalanche', 'BSC', '0x1ce0c2827e2ef14d5c4f29a091d735a204794041', 18, NULL),

-- Polygon 代币
('USDT', 'Tether', 'POLYGON', '0xc2132d05d31c914a87c6611c10748aeb04b58e8f', 6, NULL),
('USDC', 'USD Coin', 'POLYGON', '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359', 6, NULL),
('DAI', 'Dai Stablecoin', 'POLYGON', '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063', 18, NULL),
('WETH', 'Wrapped Ether', 'POLYGON', '0x7ceb23fd6bc0add59e62ac25578270cff1b9f619', 18, NULL),

-- TRON 代币
('USDT', 'Tether', 'TRX', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 6, NULL),
('USDD', 'USDD', 'TRX', 'TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn', 18, NULL),
('JST', 'JUST', 'TRX', 'TCFLL5dx5ZJdKnWuesXxi1VPwjLVmWZZy9', 18, NULL),
('WIN', 'WINkLink', 'TRX', 'TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7', 6, NULL),
('SUN', 'SUN', 'TRX', 'TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S', 18, NULL),
('BTT', 'BitTorrent', 'TRX', 'TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4', 18, NULL),

-- Solana 代币
('USDC', 'USD Coin', 'SOL', 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 6, NULL),
('USDT', 'Tether', 'SOL', 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', 6, NULL),

-- Avalanche 代币
('USDC', 'USD Coin', 'AVAX', '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E', 6, NULL),
('USDT', 'Tether', 'AVAX', '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7', 6, NULL),
('DAI', 'Dai Stablecoin', 'AVAX', '0xd586e7f844cea2f87f50152665bcbc2c279d8d70', 18, NULL),
('JOE', 'JOE', 'AVAX', '0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd', 18, NULL),
('PNG', 'Pangolin', 'AVAX', '0x60781c2586d68229fde47564546784ab3faca982', 18, NULL),
('QI', 'BENQI', 'AVAX', '0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5', 18, NULL),
('GMX', 'GMX', 'AVAX', '0x62edc0692BD897D2295872a9FFCac5425011c661', 18, NULL),

-- Arbitrum 代币
('USDT', 'Tether', 'ARBITRUM', '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9', 6, NULL),
('USDC', 'USD Coin', 'ARBITRUM', '0xaf88d065e77c8cC2239327C5EDb3A432268e5831', 6, NULL),
('WETH', 'Wrapped Ether', 'ARBITRUM', '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1', 18, NULL),
('WBTC', 'Wrapped Bitcoin', 'ARBITRUM', '0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f', 8, NULL),
('GMX', 'GMX', 'ARBITRUM', '0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a', 18, NULL),
('PENDLE', 'PENDLE', 'ARBITRUM', '0x0c880f6761F1af8d9Aa9C466984b80DAb9a8c9e8', 18, NULL),

-- Optimism 代币
('USDT', 'Tether', 'OPTIMISM', '0x94b008aA00579c1307B0EF2c499aD98a8ce58e58', 6, NULL),
('USDC', 'USD Coin', 'OPTIMISM', '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', 6, NULL),
 ('WETH', 'Wrapped Ether', 'OPTIMISM', '0x4200000000000000000000000000000000000006', 18, NULL),

-- BASE 网络代币 
('ETH', 'Ethereum', 'BASE', NULL, 18, NULL),
 ('USDC', 'USD Coin', 'BASE', '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', 6, NULL), 
 ('DEGEN', 'DEGEN', 'BASE', '0x4ed4e862860bed51a9570b96d89af5e1b0efefed', 18, NULL),

-- TON 网络代币 
('USDT', 'Tether', 'TON', 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs', 6, NULL),

-- 其他主流代币（原生链） 
('ADA', 'Cardano', 'ADA', NULL, 6, NULL), ('DOT', 'Polkadot', 'DOT', NULL, 10, NULL);

-- 查询插入结果 
SELECT chain, COUNT(*) as asset_count FROM assets GROUP BY chain ORDER BY asset_count DESC;

-- 查看总资产数 
SELECT COUNT(*) as total_assets FROM assets;
