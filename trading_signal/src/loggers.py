"""
独立的日志配置模块
用于替代对外部 musseai-agent 模块的依赖
"""
import logging
import os
from pathlib import Path

# 默认日志级别
DEFAULT_LOG_LEVEL = logging.INFO

def setup_trading_signal_logger(
    name: str = "trading_signal", 
    log_file: str = "logs/trading_signal.log"
) -> logging.Logger:
    """
    设置交易信号专用的日志器
    
    Args:
        name: 日志器名称
        log_file: 日志文件路径
        
    Returns:
        配置好的日志器实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    # 获取日志级别
    log_level_str = os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), DEFAULT_LOG_LEVEL)
    logger.setLevel(log_level)
    
    # 创建日志目录
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建格式器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
