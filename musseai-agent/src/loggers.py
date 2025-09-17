import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
env_file_path = project_root / ".env.musseai_agent"

# Load .env file with verbose output for debugging
env_loaded = load_dotenv(env_file_path, verbose=True)

if not env_loaded:
    print(f"Warning: Could not load .env file from {env_file_path}")
    # Try to find .env file in alternative locations
    alternative_paths = [
        Path(__file__).parent / ".env",  # src directory
        Path.cwd() / ".env",  # current working directory
    ]
    
    for alt_path in alternative_paths:
        if alt_path.exists():
            print(f"Found alternative .env file at: {alt_path}")
            load_dotenv(alt_path, verbose=True)
            break
    else:
        print("No .env file found in any expected location")

# 默认日志级别
DEFAULT_LOG_LEVEL = logging.INFO

# 默认日志格式
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 默认日志文件大小（10MB）
DEFAULT_MAX_BYTES = 10 * 1024 * 1024

# 默认保留的日志文件数量
DEFAULT_BACKUP_COUNT = 5


def setup_logger(name=None):
    """
    设置并返回一个已配置的logger实例
    
    Args:
        name (str, optional): Logger名称，如果为None则返回根logger
        
    Returns:
        logging.Logger: 配置好的logger实例
    """
    # 获取logger实例
    logger = logging.getLogger(name)
    
    # 如果logger已经被配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level_str = os.environ.get("MUSSEAI_LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), DEFAULT_LOG_LEVEL)
    logger.setLevel(log_level)
    
    # 创建格式化器
    log_format = os.environ.get("MUSSEAI_LOG_FORMAT", DEFAULT_LOG_FORMAT)
    formatter = logging.Formatter(log_format)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件路径，添加文件处理器
    log_file = os.environ.get("MUSSEAI_LOG_FILE")
    if log_file:
        # 确保日志目录存在
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取文件处理器配置
        max_bytes = int(os.environ.get("MUSSEAI_LOG_MAX_BYTES", DEFAULT_MAX_BYTES))
        backup_count = int(os.environ.get("MUSSEAI_LOG_BACKUP_COUNT", DEFAULT_BACKUP_COUNT))
        
        # 创建文件处理器（使用RotatingFileHandler进行日志轮转）
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# 导出全局logger实例
logger = setup_logger("musseai")
