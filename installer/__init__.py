"""
arXiv 论文推荐系统 - 安装配置向导

为统计学和机器学习研究者提供一键配置功能。
"""

from .templates import RESEARCH_TEMPLATES, get_all_fields, get_subfields
from .cli_wizard import SetupWizard, run_setup
from .zotero_extractor import ZoteroExtractor

__all__ = [
    'RESEARCH_TEMPLATES',
    'get_all_fields',
    'get_subfields',
    'SetupWizard',
    'run_setup',
    'ZoteroExtractor',
]

__version__ = '1.0.0'
