"""
财务统计标签页相关逻辑
"""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from dateutil.relativedelta import relativedelta

from modules.ui_helpers import make_treeview_sortable


class FinanceTabMixin:
    """财务统计标签页的 Mixin 类，需要混入到主 App 类中使用"""

    def setup_finance_tab(self):
        summary_frame = ttk.LabelFrame(self.finance_tab, text="总览与筛选")
        summary_frame.pack(fill="x", padx=10, pady=10)

        filter_frame = ttk.Frame(summary_frame)
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="起始日期 (YYYY-MM-DD):").pack(side="left", padx=5)
        self.start_date_entry = tk.Entry(filter_frame, width=15)
        self.start_date_entry.pack(side="left", padx=5)
        self.start_date_entry.insert(0, (datetime.now() - relativedelta(months=1)).strftime('%Y-%m-01'))

        tk.Label(filter_frame, text="结束日期:").pack(side="left", padx=5)
        self.end_date_entry = tk.Entry(filter_frame, width=15)
        self.end_date_entry.pack(side="left", padx=5)
        self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(filter_frame, text="当月", command=lambda: self.set_finance_date_range('month')).pack(side="left", padx=5)
        ttk.Button(filter_frame, text="当日", command=lambda: self.set_finance_date_range('day')).pack(side="left", padx=5)

        ttk.Button(filter_frame, text="筛选统计", command=self.refresh_finance_report).pack(side="left", padx=15)

        stats_frame = ttk.Frame(summary_frame)
        stats_frame.pack(fill="x", pady=5)

        self.income_label = tk.Label(stats_frame, text="总收入: ¥ 0.00", font=('Arial', 12, 'bold'))
        self.income_label.pack(side="left", padx=10, pady=5)
        self.expense_label = tk.Label(stats_frame, text="总支出: ¥ 0.00", font=('Arial', 12, 'bold'))
        self.expense_label.pack(side="left", padx=10, pady=5)
        self.profit_label = tk.Label(stats_frame, text="净利润: ¥ 0.00", font=('Arial', 12, 'bold'), fg='green')
        self.profit_label.pack(side="left", padx=10, pady=5)

        ttk.Button(stats_frame, text="添加手动支出", command=self.add_manual_expense).pack(side="right", padx=10)
        ttk.Button(stats_frame, text="💵 欠款查询", command=self.show_debt_report).pack(side="right", padx=10)
        ttk.Button(stats_frame, text="添加手动收入", command=self.add_manual_income).pack(side="right", padx=10)

        finance_frame = ttk.Frame(self.finance_tab)
        finance_frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ('job_id', 'client_name', 'device_info', 'amount', 'description', 'date')
        column_names = {
            'job_id': '工单ID',
            'client_name': '客户姓名',
            'device_info': '设备信息',
            'amount': '金额(¥)',
            'description': '描述/类型',
            'date': '日期'
        }
        self.finance_tree = ttk.Treeview(finance_frame, columns=columns, show='headings')

        for col in columns:
            self.finance_tree.heading(col, text=column_names[col])
            self.finance_tree.column(col, width=120)

        self.finance_tree.column('job_id', width=60, anchor='center')
        self.finance_tree.column('client_name', width=120)
        self.finance_tree.column('device_info', width=150)
        self.finance_tree.column('amount', width=100, anchor='e')
        self.finance_tree.column('description', width=300)
        self.finance_tree.column('date', width=100)

        self.finance_tree.pack(fill="both", expand=True)
        make_treeview_sortable(self.finance_tree, numeric_columns={'job_id', 'amount'})
        self.finance_tree.bind('<Double-1>', self.handle_finance_double_click)

        self.finance_tree.tag_configure('income', background='#E6F9E6')
        self.finance_tree.tag_configure('expense', background='#FFF0F0')
        self.finance_tree.tag_configure('debt', background='#FFCCCC', foreground='red')

        self.refresh_finance_report()

    def set_finance_date_range(self, period):
        """设置财务统计的日期筛选范围（当月或当日）"""
        now = datetime.now()

        if period == 'day':
            start_date = now.strftime('%Y-%m-%d')
            end_date = now.strftime('%Y-%m-%d')
        elif period == 'month':
            start_date = now.strftime('%Y-%m-01')
            end_date = now.strftime('%Y-%m-%d')
        else:
            return

        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, start_date)

        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, end_date)

        self.refresh_finance_report()

    def handle_finance_double_click(self, event):
        """双击财务统计列表：工单记录打开工单详情，零售记录打开零售单窗口。"""
        selected_item = self.finance_tree.focus()
        if not selected_item:
            return

        record_data = self.finance_tree.item(selected_item, 'values')

        entry_id = record_data[0]
        if not entry_id:
            return

        if str(entry_id).startswith('R'):
            try:
                retail_id = int(str(entry_id)[1:])
                self.open_retail_order_window(retail_id)
            except ValueError:
                messagebox.showerror("错误", f"无法解析零售订单编号: {entry_id}")
            return

        if not str(entry_id).isdigit():
            messagebox.showinfo("提示", "该记录没有关联有效的工单/零售单 ID。")
            return

        job_id = int(entry_id)

        try:
            class FinanceMockEvent:
                def __init__(self, widget):
                    self.widget = widget

            class FinanceMockTreeview:
                def __init__(self, job_id_val):
                    self._job_id = job_id_val

                def focus(self):
                    return 'finance_job_item'

                def item(self, item_id, option):
                    if option == 'values':
                        return (self._job_id, '')

            mock_tree = FinanceMockTreeview(job_id)
            self.show_job_detail_window(FinanceMockEvent(mock_tree))

        except Exception as exc:
            messagebox.showerror("错误", f"无法加载工单详情 (ID: {job_id})。错误: {exc}")

    def show_debt_report(self):
        """显示所有状态为'完成'且付款方式为'欠款'的工单列表"""

        debt_win = tk.Toplevel(self)
        debt_win.title("欠款工单查询")
        self._set_window_icon(debt_win)
        self.center_window_manual(debt_win, 800, 500)

        query = '''
            SELECT 
                j.id, c.name, c.phone, j.device_info, j.final_price, j.payment_notes, j.created_at
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            WHERE j.status = '完成' AND j.payment_method = '欠款' AND j.final_price > 0
            ORDER BY j.created_at ASC
        '''
        debt_jobs = self.db.fetch_all(query)

        tk.Label(debt_win, text=f"当前未结清欠款工单数量: {len(debt_jobs)} 份",
                 font=('Arial', 12, 'bold'), fg='red', pady=10).pack()

        if not debt_jobs:
            tk.Label(debt_win, text="恭喜！当前没有未结清的欠款工单。", fg='green').pack(pady=20)
            return

        debt_tree_frame = ttk.Frame(debt_win)
        debt_tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ('id', 'client', 'phone', 'device', 'amount', 'notes', 'date')
        column_names = {
            'id': '工单ID',
            'client': '客户姓名',
            'phone': '联系电话',
            'device': '设备信息',
            'amount': '欠款金额(¥)',
            'notes': '备注',
            'date': '完成日期'
        }
        debt_tree = ttk.Treeview(debt_tree_frame, columns=columns, show='headings')

        for col in columns:
            debt_tree.heading(col, text=column_names[col])
            debt_tree.column(col, width=100)

        debt_tree.column('amount', width=90)
        debt_tree.column('notes', width=200)

        total_debt = 0.0
        for job in debt_jobs:
            job_id, name, phone, device, price, notes, date = job
            total_debt += price
            debt_tree.insert('', 'end', values=(job_id, name, phone, device, f'¥ {price:.2f}', notes, date))

        debt_tree.pack(fill="both", expand=True)
        make_treeview_sortable(debt_tree, numeric_columns={'id', 'amount'})

        tk.Label(debt_win, text=f"总欠款金额合计: ¥ {total_debt:.2f}",
                 font=('Arial', 14, 'bold'), fg='red', pady=10).pack()

        tk.Label(debt_win, text="提示: 欠款结清请在'工单管理'中修改该工单的付款方式。", fg='blue').pack()

    def add_manual_expense(self):
        expense_win = tk.Toplevel(self)
        expense_win.title("添加手动支出")
        self._set_window_icon(expense_win)

        self.center_window_manual(expense_win, 350, 250)

        main_frame = ttk.Frame(expense_win, padding="15")
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="支出项目描述:").pack(pady=5, anchor="w")
        self.expense_desc_entry = tk.Entry(main_frame)
        self.expense_desc_entry.pack(fill="x", padx=5)

        tk.Label(main_frame, text="金额 (¥):").pack(pady=5, anchor="w")
        self.expense_amount_entry = tk.Entry(main_frame)
        self.expense_amount_entry.pack(fill="x", padx=5)

        tk.Label(main_frame, text=f"记录日期: {datetime.now().strftime('%Y-%m-%d')}", fg='gray').pack(pady=5, anchor="w")

        ttk.Button(main_frame, text="保存支出",
                   command=lambda: self.save_manual_expense(expense_win)).pack(fill="x", pady=15, padx=5)

    def save_manual_expense(self, window):
        description = self.expense_desc_entry.get().strip()
        amount_str = self.expense_amount_entry.get().strip()
        current_date = datetime.now().strftime('%Y-%m-%d')

        if not description or not amount_str:
            messagebox.showwarning("输入错误", "支出项目和金额不能为空！")
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                messagebox.showwarning("输入错误", "金额必须大于零。")
                return
        except ValueError:
            messagebox.showwarning("输入错误", "金额必须是有效数字。")
            return

        if self.db.execute_query(
            '''
            INSERT INTO financial_records (record_type, amount, description, date)
            VALUES ('Expense', ?, ?, ?)
            ''',
            (amount, description, current_date)
        ) is not None:
            messagebox.showinfo("成功", f"手动支出 '{description}' (¥{amount:.2f}) 已记录！")
            self.refresh_finance_report()
            window.destroy()
        else:
            messagebox.showerror("失败", "保存支出失败。")

    def add_manual_income(self):
        income_win = tk.Toplevel(self)
        income_win.title("添加手动收入")
        self._set_window_icon(income_win)
        self.center_window_manual(income_win, 350, 250)

        main_frame = ttk.Frame(income_win, padding="15")
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="收入项目描述:").pack(pady=5, anchor="w")
        self.income_desc_entry = tk.Entry(main_frame)
        self.income_desc_entry.pack(fill="x", padx=5)

        tk.Label(main_frame, text="金额 (¥):").pack(pady=5, anchor="w")
        self.income_amount_entry = tk.Entry(main_frame)
        self.income_amount_entry.pack(fill="x", padx=5)

        tk.Label(main_frame, text=f"记录日期: {datetime.now().strftime('%Y-%m-%d')}", fg='gray').pack(pady=5, anchor="w")

        ttk.Button(
            main_frame,
            text="保存收入",
            command=lambda: self.save_manual_income(income_win)
        ).pack(fill="x", pady=15, padx=5)

    def save_manual_income(self, window):
        description = self.income_desc_entry.get().strip()
        amount_str = self.income_amount_entry.get().strip()
        current_date = datetime.now().strftime('%Y-%m-%d')

        if not description or not amount_str:
            messagebox.showwarning("输入错误", "收入项目和金额不能为空！")
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                messagebox.showwarning("输入错误", "金额必须大于零。")
                return
        except ValueError:
            messagebox.showwarning("输入错误", "金额必须是有效数字。")
            return

        if self.db.execute_query(
            '''
            INSERT INTO financial_records (record_type, amount, description, date)
            VALUES ('Income', ?, ?, ?)
            ''',
            (amount, description, current_date)
        ) is not None:
            messagebox.showinfo("成功", f"手动收入 '{description}' (¥{amount:.2f}) 已记录！")
            self.refresh_finance_report()
            window.destroy()
        else:
            messagebox.showerror("失败", "保存收入失败。")

    def refresh_finance_report(self):
        """刷新财务统计报告"""
        start_date_str = self.start_date_entry.get()
        end_date_str = self.end_date_entry.get()

        try:
            datetime.strptime(start_date_str, '%Y-%m-%d')
            datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("日期错误", "日期格式不正确，请使用 YYYY-MM-DD 格式。")
            return

        for item in self.finance_tree.get_children():
            self.finance_tree.delete(item)

        date_filter_clause_fr = "WHERE date BETWEEN ? AND ?"
        date_filter_clause_jo = "WHERE strftime('%Y-%m-%d', created_at) BETWEEN ? AND ?"
        date_params = (start_date_str, end_date_str)

        # 1. 查询所有财务记录
        records = self.db.fetch_all(
            f"SELECT id, record_type, amount, job_id, description, date FROM financial_records {date_filter_clause_fr} ORDER BY date DESC",
            date_params
        )

        # 2. 准备工单信息缓存
        all_job_ids = [r[3] for r in records if r[3] is not None]
        unique_job_ids = list(set(all_job_ids))
        job_info_cache = {}

        if unique_job_ids:
            job_id_placeholders = ','.join(['?'] * len(unique_job_ids))
            job_details_query = f'''
                SELECT 
                    j.id, c.name, j.device_info
                FROM job_orders j
                JOIN clients c ON j.client_id = c.id
                WHERE j.id IN ({job_id_placeholders})
            '''
            details = self.db.fetch_all(job_details_query, unique_job_ids)
            for j_id, c_name, d_info in details:
                job_info_cache[j_id] = (c_name, d_info)

        # 3. 插入正常的财务记录 (收入/支出)
        for record in records:
            record_id, record_type, amount, job_id, description, date = record

            tag = 'income' if record_type == 'Income' else 'expense'
            display_amount = amount

            client_name = ''
            device_info = ''
            display_job_id = str(job_id) if job_id else ''

            if record_type == 'Income':
                if job_id and job_id in job_info_cache:
                    client_name, device_info = job_info_cache[job_id]
                    description = f'[收入] {description}'
                elif job_id:
                    description = f'[收入] 工单 #{job_id} (信息缺失)'

            elif record_type == 'Expense':
                display_amount = -amount
                if job_id is None:
                    description = f'[支出] {description}'
                    display_job_id = ''

            self.finance_tree.insert(
                '',
                'end',
                values=(display_job_id, client_name, device_info, f'{display_amount:.2f}', description, date),
                tags=(tag,)
            )

        # 4. 零售订单收入
        retail_query = '''
            SELECT id, customer_unit, total_amount, created_at, payment_method
            FROM retail_orders
            WHERE strftime('%Y-%m-%d', created_at) BETWEEN ? AND ?
            ORDER BY created_at DESC
        '''
        retail_orders = self.db.fetch_all(retail_query, date_params)
        for order_id, customer, total_amount, created_at, payment_method in retail_orders:
            fmt_amount = float(total_amount or 0)
            desc = f"[零售]{customer or '散客'}"
            tags = ('income',)
            if payment_method == '欠款':
                tags = ('debt',)
                desc += " (欠款)"
            self.finance_tree.insert(
                '',
                'end',
                values=(f'R{order_id}', customer or '', '', f'{fmt_amount:.2f}', desc, created_at or ''),
                tags=tags
            )

        # 5. 显示欠款工单
        debt_jobs_query = f'''
            SELECT 
                j.id, c.name, j.device_info, j.final_price, j.payment_notes, strftime('%Y-%m-%d', j.created_at)
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            WHERE j.status = '完成' 
            AND j.payment_method = '欠款' 
            AND j.final_price > 0 
            AND strftime('%Y-%m-%d', j.created_at) BETWEEN ? AND ?
            ORDER BY j.created_at DESC
        '''

        debt_jobs = self.db.fetch_all(debt_jobs_query, date_params)

        for job_id, client_name, device_info, amount, notes, date in debt_jobs:
            description = f'[欠款] 客户: {client_name} (备注: {notes or "无"})'
            self.finance_tree.insert(
                '',
                'end',
                values=(str(job_id), client_name, device_info, f'{amount:.2f}', description, date),
                tags=('debt',)
            )

        # 5.5. 显示所有已完成且已付款的工单
        completed_jobs_query = f'''
            SELECT 
                j.id, c.name, j.device_info, j.final_price, j.payment_method, j.payment_notes, strftime('%Y-%m-%d', j.created_at)
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            WHERE j.status = '完成' 
            AND j.payment_method != '欠款'
            AND j.final_price > 0 
            AND strftime('%Y-%m-%d', j.created_at) BETWEEN ? AND ?
            AND j.id NOT IN (
                SELECT DISTINCT job_id FROM financial_records WHERE job_id IS NOT NULL
            )
            ORDER BY j.created_at DESC
        '''

        completed_jobs = self.db.fetch_all(completed_jobs_query, date_params)

        for job_id, client_name, device_info, amount, payment_method, payment_notes, date in completed_jobs:
            payment_info = f'付款方式: {payment_method}'
            if payment_notes:
                payment_info += f' (备注: {payment_notes})'
            description = f'[工单收入] {payment_info}'

            self.finance_tree.insert(
                '',
                'end',
                values=(str(job_id), client_name, device_info, f'{amount:.2f}', description, date),
                tags=('income',)
            )

        # 6. 统计总览计算
        total_income_res = self.db.fetch_one(
            f"SELECT SUM(amount) FROM financial_records {date_filter_clause_fr} AND record_type='Income'",
            date_params
        )
        income_from_records = total_income_res[0] or 0.0

        completed_jobs_income_res = self.db.fetch_one(
            f'''
            SELECT SUM(j.final_price)
            FROM job_orders j
            WHERE j.status = '完成' 
            AND j.payment_method != '欠款'
            AND j.final_price > 0 
            AND strftime('%Y-%m-%d', j.created_at) BETWEEN ? AND ?
            AND j.id NOT IN (
                SELECT DISTINCT job_id FROM financial_records WHERE job_id IS NOT NULL
            )
            ''',
            date_params
        )
        income_from_jobs = completed_jobs_income_res[0] or 0.0

        retail_income_res = self.db.fetch_one(
            '''
            SELECT SUM(total_amount)
            FROM retail_orders
            WHERE strftime('%Y-%m-%d', created_at) BETWEEN ? AND ?
            ''',
            date_params
        )
        income_from_retail = retail_income_res[0] or 0.0

        income = income_from_records + income_from_jobs + income_from_retail

        manual_expense_res = self.db.fetch_one(
            f"SELECT SUM(amount) FROM financial_records {date_filter_clause_fr} AND record_type='Expense'",
            date_params
        )
        manual_expense = manual_expense_res[0] or 0.0

        job_cost_res = self.db.fetch_one(
            f'''
            SELECT SUM(cost) + SUM(other_cost) + SUM(COALESCE(part_cost, 0)) 
            FROM job_orders 
            {date_filter_clause_jo} AND status='完成'
            ''',
            date_params
        )
        job_cost = job_cost_res[0] or 0.0

        retail_cost_res = self.db.fetch_one(
            '''
            SELECT SUM(total_cost)
            FROM retail_orders
            WHERE strftime('%Y-%m-%d', created_at) BETWEEN ? AND ?
            ''',
            date_params
        )
        retail_cost = retail_cost_res[0] or 0.0

        expense = manual_expense + job_cost + retail_cost
        profit = income - expense

        self.income_label.config(text=f"总收入 ({start_date_str} 至 {end_date_str}): ¥ {income:.2f}")
        self.expense_label.config(text=f"总支出 : ¥ {expense:.2f}")
        self.profit_label.config(text=f"净利润: ¥ {profit:.2f}", fg='green' if profit >= 0 else 'red')

