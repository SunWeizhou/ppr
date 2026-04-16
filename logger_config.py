"""
统一日志配置模块

为 arXiv 推荐系统提供标准化的日志功能：
- 控制台输出：INFO 及以上级别，带颜色
- 文件输出：DEBUG 及以上级别，按日期分割
- 第三方库日志降级：减少噪音

使用方法:
    from logger_config import get_logger
    logger = get_logger(__name__)
    logger.info("正常信息")
    logger.warning("警告信息")
    logger.error("错误信息")
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""

    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        # 添加颜色
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{self.BOLD}{record.levelname:8}{self.RESET}"
        return super().format(record)


class RecommenderLogger:
    """
    推荐系统日志管理器

    单例模式，确保全局只有一个日志配置
    """

    _instance: Optional['RecommenderLogger'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        log_dir: str = "logs",
        console_level: str = "INFO",
        file_level: str = "DEBUG",
        app_name: str = "arxiv_recommender"
    ):
        """
        初始化日志系统

        Args:
            log_dir: 日志文件目录
            console_level: 控制台最低日志级别
            file_level: 文件最低日志级别
            app_name: 应用名称（用于日志文件名）
        """
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.app_name = app_name
        self.console_level = getattr(logging, console_level.upper())
        self.file_level = getattr(logging, file_level.upper())

        self._setup()
        self._initialized = True

    def _setup(self):
        """配置日志系统"""
        # 创建日志目录
        self.log_dir.mkdir(exist_ok=True)

        # 获取根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 设置最低级别

        # 清除已有的处理器（避免重复）
        root_logger.handlers.clear()

        # 添加控制台处理器
        console_handler = self._create_console_handler()
        root_logger.addHandler(console_handler)

        # 添加文件处理器
        file_handler = self._create_file_handler()
        root_logger.addHandler(file_handler)

        # 降级第三方库日志
        self._quiet_third_party_loggers()

    def _create_console_handler(self) -> logging.Handler:
        """创建控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.console_level)

        # 使用带颜色的格式化器
        formatter = ColoredFormatter(
            '%(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)

        return handler

    def _create_file_handler(self) -> logging.Handler:
        """创建文件处理器（按日期分割）"""
        log_file = self.log_dir / f"{self.app_name}_{datetime.now():%Y%m%d}.log"

        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(self.file_level)

        # 文件使用详细格式
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        return handler

    def _quiet_third_party_loggers(self):
        """降低第三方库的日志级别"""
        noisy_loggers = [
            'urllib3',
            'requests',
            'sentence_transformers',
            'transformers',
            'torch',
            'werkzeug',
            'flask',
        ]

        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        return logging.getLogger(name)


# 全局实例
_logger_manager: Optional[RecommenderLogger] = None


def setup_logging(
    log_dir: str = "logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    app_name: str = "arxiv_recommender"
) -> RecommenderLogger:
    """
    初始化全局日志系统

    应该在程序入口处调用一次。

    Args:
        log_dir: 日志文件目录
        console_level: 控制台日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        file_level: 文件日志级别
        app_name: 应用名称

    Returns:
        日志管理器实例
    """
    global _logger_manager
    _logger_manager = RecommenderLogger(
        log_dir=log_dir,
        console_level=console_level,
        file_level=file_level,
        app_name=app_name
    )
    return _logger_manager


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器

    如果尚未初始化，会使用默认配置自动初始化。

    Args:
        name: 日志器名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例

    Example:
        >>> from logger_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Hello, world!")
    """
    global _logger_manager

    if _logger_manager is None:
        # 使用默认配置初始化
        _logger_manager = setup_logging()

    return _logger_manager.get_logger(name)


# 预定义的日志级别常量，方便使用
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


# 便捷函数
def log_info(message: str, *args, **kwargs):
    """快速记录 INFO 级别日志"""
    get_logger('arxiv_recommender').info(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs):
    """快速记录 WARNING 级别日志"""
    get_logger('arxiv_recommender').warning(message, *args, **kwargs)


def log_error(message: str, *args, **kwargs):
    """快速记录 ERROR 级别日志"""
    get_logger('arxiv_recommender').error(message, *args, **kwargs)


def log_debug(message: str, *args, **kwargs):
    """快速记录 DEBUG 级别日志"""
    get_logger('arxiv_recommender').debug(message, *args, **kwargs)


# 测试代码
if __name__ == "__main__":
    # 初始化日志系统
    setup_logging(console_level="DEBUG")

    logger = get_logger(__name__)

    print("\n=== 日志系统测试 ===\n")

    logger.debug("这是一条 DEBUG 消息 - 用于详细调试信息")
    logger.info("这是一条 INFO 消息 - 正常运行状态")
    logger.warning("这是一条 WARNING 消息 - 可恢复的问题")
    logger.error("这是一条 ERROR 消息 - 需要关注的错误")
    logger.critical("这是一条 CRITICAL 消息 - 严重错误")

    print(f"\n日志文件已保存到: logs/arxiv_recommender_{datetime.now():%Y%m%d}.log\n")
