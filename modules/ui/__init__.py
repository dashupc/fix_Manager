"""
UI 模块，包含各个标签页的 Mixin 类
"""
from modules.ui.job_tab import JobTabMixin
from modules.ui.retail_tab import RetailTabMixin
from modules.ui.finance_tab import FinanceTabMixin
from modules.ui.client_tab import ClientTabMixin

__all__ = ['JobTabMixin', 'RetailTabMixin', 'FinanceTabMixin', 'ClientTabMixin']
