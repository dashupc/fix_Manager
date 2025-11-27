"""
工单管理标签页相关逻辑
"""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

from modules.ui_helpers import make_treeview_sortable
from modules.config_helpers import (
    load_fault_types, save_fault_types,
    load_parts, save_parts,
    load_part_sources, save_part_sources,
    load_units, save_units,
    load_departments, save_departments,
    load_device_categories, save_device_categories,
    get_client_names
)


class JobTabMixin:
    """工单管理标签页的 Mixin 类，需要混入到主 App 类中使用"""

    def setup_job_tab(self):
        top_frame = ttk.Frame(self.job_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        # 左侧按钮
        left_buttons = ttk.Frame(top_frame)
        left_buttons.pack(side="left")
        ttk.Button(left_buttons, text="✚ 新增工单", command=self.add_new_job_window).pack(side="left", padx=5)

        # 搜索框
        search_frame = ttk.Frame(top_frame)
        search_frame.pack(side="left", padx=20, fill="x", expand=True)

        tk.Label(search_frame, text="搜索:").pack(side="left", padx=5)
        self.job_search_entry = tk.Entry(search_frame, width=30)
        self.job_search_entry.pack(side="left", padx=5)
        self.job_search_entry.bind('<Return>', lambda e: self.search_jobs())

        ttk.Button(search_frame, text="🔍 搜索", command=self.search_jobs).pack(side="left", padx=5)
        ttk.Button(search_frame, text="当日", command=self.filter_today_jobs).pack(side="left", padx=5)
        ttk.Button(search_frame, text="清除", command=self.clear_job_search).pack(side="left", padx=5)

        # 右侧按钮
        ttk.Button(top_frame, text="📥 导出全部工单 (CSV)", command=self.export_jobs_to_csv).pack(side="right", padx=5)

        job_frame = ttk.Frame(self.job_tab)
        job_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        columns = ('id', 'client_name', 'phone', 'serial_number', 'device', 'fault_desc', 'status', 'quote', 'created_at')
        column_names = {
            'id': 'ID',
            'client_name': '客户姓名',
            'phone': '联系电话',
            'serial_number': '序列号',
            'device': '品牌型号',
            'fault_desc': '故障描述',
            'status': '状态',
            'quote': '报价',
            'created_at': '创建日期'
        }
        self.job_tree = ttk.Treeview(job_frame, columns=columns, show='headings')

        for col in columns:
            self.job_tree.heading(col, text=column_names[col])
            self.job_tree.column(col, width=100)

        self.job_tree.column('id', width=40)
        self.job_tree.column('serial_number', width=100)
        self.job_tree.column('device', width=150)
        self.job_tree.column('fault_desc', width=200)
        self.job_tree.column('status', width=50, anchor='center')
        self.job_tree.column('quote', width=50, anchor='center')

        # 配置标签颜色：非完成状态=红色
        self.job_tree.tag_configure('other', background='#FFF0F0', foreground='red')

        self.job_tree.pack(fill="both", expand=True)
        make_treeview_sortable(self.job_tree, numeric_columns={'id', 'quote'})

        self.job_tree.bind('<Double-1>', self.show_job_detail_window)

        self.refresh_job_list()

    def export_jobs_to_csv(self):
        """将所有工单及其详细信息导出为 CSV 文件"""

        query = '''
            SELECT 
                j.id, c.name, c.phone, j.serial_number, j.device_info, j.fault_desc, 
                j.repair_details, j.status, j.initial_quote, j.final_price, j.cost, j.other_cost, 
                (j.final_price - j.cost - j.other_cost) AS net_profit, 
                j.payment_method, j.payment_notes, 
                j.created_at
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            ORDER BY j.id DESC
        '''
        jobs = self.db.fetch_all(query)

        if not jobs:
            messagebox.showinfo("导出失败", "当前数据库中没有工单记录可以导出。")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"Job_Orders_Export_{timestamp}.csv"

        export_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_filename,
            title="选择工单导出保存位置",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )

        if not export_path:
            messagebox.showinfo("导出取消", "工单导出操作已取消。")
            return

        headers = [
            '工单ID', '客户姓名', '联系电话', '序列号', '设备信息', '故障描述',
            '维修详情', '状态', '初步报价(¥)', '最终实收(¥)', '内部成本(¥)', '其他成本(¥)',
            '净利润(¥)', '付款方式', '付款备注', '创建日期'
        ]

        try:
            with open(export_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                csv_writer = csv.writer(csvfile)

                csv_writer.writerow(headers)

                for job in jobs:
                    row = [str(item) if item is not None else '' for item in job]
                    csv_writer.writerow(row)

            messagebox.showinfo("导出成功", f"所有工单数据已成功导出到:\n{export_path}")

        except Exception as e:
            messagebox.showerror("导出失败", f"导出过程中发生错误: {e}")

    def show_job_detail_window(self, event):
        """显示工单详细信息，并允许修改维修详情 (双击事件)"""

        selected_item = event.widget.focus()
        if not selected_item:
            return

        job_data = event.widget.item(selected_item, 'values')
        job_id = job_data[0]

        query = '''
            SELECT 
                j.id, c.name, c.phone, c.unit, c.department, j.serial_number,
                j.device_info, j.device_category, j.fault_type, j.fault_desc, j.repair_details, j.status, 
                j.initial_quote, j.final_price, j.cost, j.other_cost, 
                j.payment_method, j.payment_notes, j.replaced_parts, 
                j.part_source, j.part_cost, j.invoice_amount, j.invoice_date, j.is_urgent, j.created_at
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            WHERE j.id = ?
        '''
        details = self.db.fetch_one(query, (job_id,))
        if not details:
            messagebox.showerror("错误", f"无法找到工单 ID: {job_id} 的详细信息。")
            return

        (job_id, client_name, client_phone, client_unit, client_department, serial_number,
         device_info, device_category, fault_type, fault_desc, repair_details, status,
         initial_quote, final_price, cost, other_cost,
         payment_method, payment_notes, replaced_parts,
         part_source, part_cost, invoice_amount, invoice_date, is_urgent, created_at) = details

        replaced_parts = replaced_parts or ''
        part_source = part_source or ''
        part_cost = part_cost or 0.0
        invoice_amount = invoice_amount or 0.0
        invoice_date = invoice_date or ''
        is_urgent = is_urgent or 0

        net_profit = final_price - cost - other_cost - part_cost

        detail_win = tk.Toplevel(self)
        detail_win.title(f"工单详情 #{job_id} - {client_name}")
        self._set_window_icon(detail_win)

        self.center_window_manual(detail_win, 600, 650)

        main_frame = ttk.Frame(detail_win, padding="5")
        main_frame.pack(fill="both", expand=True)

        details_frame = ttk.LabelFrame(main_frame, text="工单与客户信息")
        details_frame.pack(fill="x", pady=5)
        details_frame.columnconfigure(1, weight=1)
        details_frame.columnconfigure(3, weight=1)

        r = 0
        # 第一行：工单 ID
        tk.Label(details_frame, text="工单 ID:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        job_id_frame = tk.Frame(details_frame)
        job_id_frame.grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(job_id_frame, text=str(job_id) if job_id else '', anchor="w", wraplength=200).pack(side="left")
        if is_urgent:
            tk.Label(job_id_frame, text="紧急", anchor="w", font=('Arial', 10, 'bold'), fg='red').pack(side="left", padx=(10, 0))
        r += 1

        # 第二行：联系人/电话 和 单位/部门
        tk.Label(details_frame, text="联系人/电话:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        contact_parts = [p for p in [client_name, client_phone] if p]
        contact_info = '/'.join(contact_parts) if contact_parts else ''
        tk.Label(details_frame, text=contact_info, anchor="w", wraplength=200).grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text="单位/部门:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=2, sticky="w")
        unit_dept_parts = [p for p in [client_unit, client_department] if p]
        unit_dept_info = '/'.join(unit_dept_parts) if unit_dept_parts else ''
        tk.Label(details_frame, text=unit_dept_info, anchor="w", wraplength=200).grid(row=r, column=3, padx=5, pady=2, sticky="w")
        r += 1

        # 第三行：设备类别/品牌型号
        tk.Label(details_frame, text="类别/品牌型号:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        device_parts = [p for p in [device_category, device_info] if p]
        device_info_text = '/'.join(device_parts) if device_parts else ''
        tk.Label(details_frame, text=device_info_text, anchor="w", wraplength=200).grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text="序列号:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(serial_number) if serial_number else '', anchor="w", wraplength=200).grid(row=r, column=3, padx=5, pady=2, sticky="w")
        r += 1

        # 第四行：故障类型 和 工单状态
        tk.Label(details_frame, text="故障类型:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(fault_type) if fault_type else '', anchor="w", wraplength=200).grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text="工单状态:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=2, sticky="w")
        status_var = tk.StringVar(value=status)
        statuses = ['待检测', '检测中', '报价中', '维修中', '完成', '取消']
        status_menu = ttk.Combobox(details_frame, textvariable=status_var, values=statuses, state="readonly", width=18)
        status_menu.grid(row=r, column=3, padx=5, pady=2, sticky="ew")

        desc_frame = ttk.LabelFrame(main_frame, text="故障描述")
        desc_frame.pack(fill="x", pady=5)

        edit_fault_desc = tk.Text(desc_frame, height=3, wrap=tk.WORD, font=('Arial', 10))
        edit_fault_desc.pack(fill="x", padx=5, pady=3)
        edit_fault_desc.insert(tk.END, fault_desc if fault_desc else "")

        repair_frame = ttk.LabelFrame(main_frame, text="维修详情")
        repair_frame.pack(fill="x", pady=5)

        edit_repair_details = tk.Text(repair_frame, height=4, wrap=tk.WORD, font=('Arial', 10))
        edit_repair_details.insert(tk.END, repair_details if repair_details else "")
        edit_repair_details.pack(fill="x", padx=5, pady=3)

        # 配件信息
        parts_frame = ttk.LabelFrame(main_frame, text="配件信息")
        parts_frame.pack(fill="x", pady=5)
        parts_frame.columnconfigure(1, weight=1)
        parts_frame.columnconfigure(3, weight=1)

        r = 0
        tk.Label(parts_frame, text="更换配件:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        parts_list = load_parts(self.db)
        replaced_parts_var = tk.StringVar(value=replaced_parts)
        replaced_parts_combo = ttk.Combobox(parts_frame, textvariable=replaced_parts_var, values=parts_list, state="normal", width=18)
        replaced_parts_combo.grid(row=r, column=1, padx=5, pady=3, sticky="ew")

        tk.Label(parts_frame, text="配件来源:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        sources_list = load_part_sources(self.db)
        part_source_var = tk.StringVar(value=part_source)
        part_source_combo = ttk.Combobox(parts_frame, textvariable=part_source_var, values=sources_list, state="normal", width=18)
        part_source_combo.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1

        edit_frame = ttk.LabelFrame(main_frame, text="财务信息")
        edit_frame.pack(fill="x", pady=5)
        edit_frame.columnconfigure(1, weight=1)
        edit_frame.columnconfigure(3, weight=1)

        r = 0
        # 第一列
        tk.Label(edit_frame, text="实收金额", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        final_price_entry = tk.Entry(edit_frame)
        final_price_entry.insert(0, str(final_price))
        final_price_entry.grid(row=r, column=1, padx=5, pady=3, sticky="ew")

        # 第二列
        tk.Label(edit_frame, text="付款方式", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        payment_method_var = tk.StringVar(value=payment_method)
        payment_methods = ['待定', '现金', '微信', '支付宝', '收款码', '欠款']
        payment_method_menu = ttk.Combobox(edit_frame, textvariable=payment_method_var, values=payment_methods, state="readonly", width=18)
        payment_method_menu.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1

        # 第一列
        tk.Label(edit_frame, text="配件成本", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        part_cost_entry = tk.Entry(edit_frame)
        part_cost_entry.insert(0, str(part_cost))
        part_cost_entry.grid(row=r, column=1, padx=5, pady=3, sticky="ew")

        # 第二列
        tk.Label(edit_frame, text="付款备注", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        payment_notes_entry = tk.Entry(edit_frame)
        payment_notes_entry.insert(0, payment_notes or '')
        payment_notes_entry.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1

        # 第一列
        tk.Label(edit_frame, text="内部成本", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        cost_entry = tk.Entry(edit_frame)
        cost_entry.insert(0, str(cost))
        cost_entry.grid(row=r, column=1, padx=5, pady=3, sticky="ew")

        # 第二列
        tk.Label(edit_frame, text="其他成本", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        other_cost_entry = tk.Entry(edit_frame)
        other_cost_entry.insert(0, str(other_cost))
        other_cost_entry.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1

        # 第一列
        tk.Label(edit_frame, text="开票金额", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        invoice_amount_entry = tk.Entry(edit_frame)
        invoice_amount_entry.insert(0, str(invoice_amount or 0))
        invoice_amount_entry.grid(row=r, column=1, padx=5, pady=3, sticky="ew")

        # 第二列
        tk.Label(edit_frame, text="开票日期", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        invoice_date_entry = tk.Entry(edit_frame)
        invoice_date_entry.insert(0, invoice_date or '')
        invoice_date_entry.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1

        financial_frame = ttk.LabelFrame(main_frame, text="财务摘要")
        financial_frame.pack(fill="x", pady=5)

        total_cost = cost + other_cost + part_cost
        summary_text = f"最终实收: ¥ {final_price:.2f}  |  总成本: ¥ {total_cost:.2f}  |  净利润: ¥ {net_profit:.2f}"
        summary_label = tk.Label(financial_frame, text=summary_text, font=('Arial', 10, 'bold'), anchor="w")
        summary_label.pack(fill="x", padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=5)
        button_frame.columnconfigure(0, weight=1)

        ttk.Button(button_frame, text="保存所有更改",
                   command=lambda: self._save_all_job_info_from_window(
                       job_id, edit_fault_desc, edit_repair_details, status_var, final_price_entry,
                       payment_method_var, payment_notes_entry, cost_entry,
                       other_cost_entry, replaced_parts_var, part_source_var,
                       part_cost_entry, invoice_amount_entry, invoice_date_entry,
                       replaced_parts_combo, part_source_combo, detail_win
                   )).grid(row=0, column=0, padx=5)

    def _save_all_job_info_from_window(self, job_id, edit_fault_desc_widget, edit_repair_details_widget, status_var,
                                       final_price_entry, payment_method_var, payment_notes_entry,
                                       cost_entry, other_cost_entry, replaced_parts_var, part_source_var,
                                       part_cost_entry, invoice_amount_entry, invoice_date_entry,
                                       replaced_parts_combo, part_source_combo, window):
        """从详情窗口同时保存故障描述、维修详情、配件信息和更新工单状态及财务信息"""
        try:
            fault_desc = edit_fault_desc_widget.get("1.0", tk.END).strip()
            repair_details = edit_repair_details_widget.get("1.0", tk.END).strip()

            status = status_var.get()
            final_price = float(final_price_entry.get() or 0)
            payment_method = payment_method_var.get()
            payment_notes = payment_notes_entry.get().strip()
            cost = float(cost_entry.get() or 0)
            other_cost = float(other_cost_entry.get() or 0)

            # 获取配件信息
            replaced_parts = replaced_parts_var.get().strip()
            part_source = part_source_var.get().strip()
            part_cost = float(part_cost_entry.get() or 0)

            # 获取开票信息
            invoice_amount = float(invoice_amount_entry.get() or 0)
            invoice_date = invoice_date_entry.get().strip()

            # 如果配件不在列表中，添加到列表
            if replaced_parts:
                current_parts = load_parts(self.db)
                if replaced_parts not in current_parts:
                    current_parts.append(replaced_parts)
                    save_parts(self.db, current_parts)
                    replaced_parts_combo['values'] = current_parts

            # 如果配件来源不在列表中，添加到列表
            if part_source:
                current_sources = load_part_sources(self.db)
                if part_source not in current_sources:
                    current_sources.append(part_source)
                    save_part_sources(self.db, current_sources)
                    part_source_combo['values'] = current_sources

            update_query = '''
                UPDATE job_orders 
                SET fault_desc=?, repair_details=?, status=?, final_price=?, payment_method=?, 
                    payment_notes=?, cost=?, other_cost=?, replaced_parts=?, part_source=?, part_cost=?,
                    invoice_amount=?, invoice_date=?
                WHERE id=?
            '''
            if self.db.execute_query(update_query, (fault_desc, repair_details, status, final_price,
                                                     payment_method, payment_notes, cost,
                                                     other_cost, replaced_parts, part_source, part_cost,
                                                     invoice_amount, invoice_date, job_id)) is not None:
                messagebox.showinfo("成功", f"工单 #{job_id} 的所有信息已保存！")
                window.destroy()
                self.refresh_job_list()
            else:
                messagebox.showerror("失败", "保存工单信息失败。")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字（最终实收、内部成本、其他成本、配件成本、开票金额）。")

    def add_new_job_window(self):
        new_job_win = tk.Toplevel(self)
        new_job_win.title("新增工单")
        self._set_window_icon(new_job_win)

        self.center_window_manual(new_job_win, 500, 600)

        main_frame = ttk.Frame(new_job_win, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 获取现有客户名称列表
        client_names = get_client_names(self.db)

        client_frame = ttk.LabelFrame(main_frame, text="客户信息")
        client_frame.pack(fill="x", pady=10)

        # 第一行：联系人和电话
        tk.Label(client_frame, text="联系人:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.new_client_name = ttk.Combobox(client_frame, width=18, values=client_names)
        self.new_client_name.config(state='normal')
        self.new_client_name.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(client_frame, text="电话:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.new_client_phone = tk.Entry(client_frame, width=18)
        self.new_client_phone.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        # 第二行：单位和部门
        tk.Label(client_frame, text="单位:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        units_list = load_units(self.db)
        self.new_client_unit = ttk.Combobox(client_frame, width=18, values=units_list, state="normal")
        self.new_client_unit.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(client_frame, text="部门:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        departments_list = load_departments(self.db)
        self.new_client_department = ttk.Combobox(client_frame, width=18, values=departments_list, state="normal")
        self.new_client_department.grid(row=1, column=3, padx=5, pady=5, sticky="ew")

        # 配置列权重，让输入框可以扩展
        client_frame.columnconfigure(1, weight=1)
        client_frame.columnconfigure(3, weight=1)

        device_frame = ttk.LabelFrame(main_frame, text="设备信息")
        device_frame.pack(fill="x", pady=10)

        # 第一行：设备类别和品牌型号
        tk.Label(device_frame, text="设备类别:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        categories_list = load_device_categories(self.db)
        self.new_device_category = ttk.Combobox(device_frame, width=18, values=categories_list, state="normal")
        self.new_device_category.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(device_frame, text="品牌型号:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.new_device_info = tk.Entry(device_frame, width=18)
        self.new_device_info.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        tk.Label(device_frame, text="序列号:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.new_serial_number = tk.Entry(device_frame)
        self.new_serial_number.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # 配置列权重，让输入框可以扩展
        device_frame.columnconfigure(1, weight=1)
        device_frame.columnconfigure(3, weight=1)

        tk.Label(device_frame, text="故障类型:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        types = load_fault_types(self.db)
        self.new_recovery_type = ttk.Combobox(device_frame, values=types, state="normal")
        self.new_recovery_type.set('其他')
        self.new_recovery_type.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # 紧急勾选框
        self.new_is_urgent = tk.BooleanVar(value=False)
        urgent_checkbox = tk.Checkbutton(device_frame, text="紧急", variable=self.new_is_urgent)
        urgent_checkbox.grid(row=2, column=2, padx=5, pady=5, sticky="w")

        tk.Label(device_frame, text="故障描述:").grid(row=3, column=0, padx=5, pady=5, sticky="nw")
        self.new_fault_desc = tk.Text(device_frame, height=5, width=40)
        self.new_fault_desc.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        tk.Label(device_frame, text="初步报价(¥):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.new_initial_quote = tk.Entry(device_frame)
        self.new_initial_quote.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.new_initial_quote.insert(0, "0.00")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=20)

        ttk.Button(button_frame, text="保存工单",
                   command=lambda: self.save_new_job(new_job_win)).pack(side="left", expand=True, padx=5)
        ttk.Button(button_frame, text="取消", command=new_job_win.destroy).pack(side="right", expand=True, padx=5)

    def save_new_job(self, window):
        """保存新的工单"""
        client_name = self.new_client_name.get().strip()
        client_phone = self.new_client_phone.get().strip()
        client_unit = self.new_client_unit.get().strip()
        client_department = self.new_client_department.get().strip()
        serial_number = self.new_serial_number.get().strip()

        device_category = self.new_device_category.get().strip()
        device_info = self.new_device_info.get().strip()
        initial_quote = self.new_initial_quote.get().strip()
        fault_desc = self.new_fault_desc.get("1.0", tk.END).strip()
        is_urgent = 1 if self.new_is_urgent.get() else 0

        # 获取故障类型，如果不在列表中则添加
        recovery_type = self.new_recovery_type.get().strip()
        if recovery_type:
            current_types = load_fault_types(self.db)
            if recovery_type not in current_types:
                current_types.append(recovery_type)
                save_fault_types(self.db, current_types)
                self.new_recovery_type['values'] = current_types

        # 如果单位不在列表中，添加到列表
        if client_unit:
            current_units = load_units(self.db)
            if client_unit not in current_units:
                current_units.append(client_unit)
                save_units(self.db, current_units)
                self.new_client_unit['values'] = current_units

        # 如果部门不在列表中，添加到列表
        if client_department:
            current_departments = load_departments(self.db)
            if client_department not in current_departments:
                current_departments.append(client_department)
                save_departments(self.db, current_departments)
                self.new_client_department['values'] = current_departments

        # 如果设备类别不在列表中，添加到列表
        if device_category:
            current_categories = load_device_categories(self.db)
            if device_category not in current_categories:
                current_categories.append(device_category)
                save_device_categories(self.db, current_categories)
                self.new_device_category['values'] = current_categories

        if not client_name or not device_info or not fault_desc:
            messagebox.showwarning("输入错误", "客户姓名、设备信息和故障描述为必填项！")
            return

        try:
            quote = float(initial_quote)
        except ValueError:
            messagebox.showwarning("输入错误", "初步报价必须是有效的数字！")
            return

        client_id = None

        # 1. 尝试通过电话查找现有客户
        if client_phone:
            client_data = self.db.fetch_one("SELECT id FROM clients WHERE phone = ?", (client_phone,))
            if client_data:
                client_id = client_data[0]
                self.db.execute_query(
                    "UPDATE clients SET name = ?, unit = ?, department = ? WHERE id = ?",
                    (client_name, client_unit or '', client_department or '', client_id)
                )

        # 2. 如果电话未匹配，尝试通过姓名查找现有客户
        if client_id is None:
            client_data = self.db.fetch_one("SELECT id, phone FROM clients WHERE name = ?", (client_name,))
            if client_data:
                client_id, existing_phone = client_data
                if client_phone and client_phone != existing_phone:
                    self.db.execute_query(
                        "UPDATE clients SET phone = ?, unit = ?, department = ? WHERE id = ?",
                        (client_phone, client_unit or '', client_department or '', client_id)
                    )
                elif client_unit or client_department:
                    self.db.execute_query(
                        "UPDATE clients SET unit = ?, department = ? WHERE id = ?",
                        (client_unit or '', client_department or '', client_id)
                    )

        # 3. 如果以上都没有匹配到，则创建新客户
        if client_id is None:
            client_id = self.db.execute_query(
                "INSERT INTO clients (name, phone, unit, department) VALUES (?, ?, ?, ?)",
                (client_name, client_phone or '', client_unit or '', client_department or '')
            )

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        job_id = self.db.execute_query(
            '''
            INSERT INTO job_orders 
            (client_id, serial_number, device_info, device_category, fault_desc, fault_type, status, initial_quote, final_price, 
             created_at, cost, other_cost, repair_details, payment_method, payment_notes, is_urgent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, '', '待定', '', ?)
            ''',
            (client_id, serial_number or '', device_info, device_category or '', fault_desc, recovery_type or '其他', '待检测', quote, quote,
             current_time, is_urgent)
        )

        if job_id:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ 新工单 #{job_id} 已创建！初步报价 (¥{quote:.2f}) 已自动填充至最终实收。")
            self.refresh_job_list()
            self.refresh_client_list()
            window.destroy()
        else:
            messagebox.showerror("失败", "工单创建失败，请检查数据库连接。")

    def refresh_job_list(self, search_keyword=None, filter_today=False):
        """刷新工单列表，支持搜索过滤和当天筛选"""
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)

        # 构建查询语句
        if filter_today:
            today = datetime.now().strftime('%Y-%m-%d')
            query = '''
                SELECT 
                    j.id, c.name, c.phone, j.serial_number, j.device_info, j.fault_desc, j.status, j.initial_quote, j.created_at
                FROM job_orders j
                JOIN clients c ON j.client_id = c.id
                WHERE strftime('%Y-%m-%d', j.created_at) = ?
                ORDER BY j.created_at DESC
            '''
            jobs = self.db.fetch_all(query, (today,))
        elif search_keyword and search_keyword.strip():
            search_pattern = f'%{search_keyword.strip()}%'
            query = '''
                SELECT 
                    j.id, c.name, c.phone, j.serial_number, j.device_info, j.fault_desc, j.status, j.initial_quote, j.created_at
                FROM job_orders j
                JOIN clients c ON j.client_id = c.id
                WHERE 
                    CAST(j.id AS TEXT) LIKE ? OR
                    c.name LIKE ? OR
                    c.phone LIKE ? OR
                    j.serial_number LIKE ? OR
                    j.device_info LIKE ?
                ORDER BY j.created_at DESC
            '''
            params = (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern)
            jobs = self.db.fetch_all(query, params)
        else:
            query = '''
                SELECT 
                    j.id, c.name, c.phone, j.serial_number, j.device_info, j.fault_desc, j.status, j.initial_quote, j.created_at
                FROM job_orders j
                JOIN clients c ON j.client_id = c.id
                ORDER BY j.created_at DESC
            '''
            jobs = self.db.fetch_all(query)

        for job in jobs:
            status = job[6] if len(job) > 6 else ''
            if status != '完成':
                self.job_tree.insert('', 'end', values=job, tags=('other',))
            else:
                self.job_tree.insert('', 'end', values=job)

    def search_jobs(self):
        """执行工单搜索"""
        search_keyword = self.job_search_entry.get()
        self.refresh_job_list(search_keyword)

    def filter_today_jobs(self):
        """筛选当天的工单"""
        self.job_search_entry.delete(0, tk.END)
        self.refresh_job_list(filter_today=True)

    def clear_job_search(self):
        """清除搜索并显示所有工单"""
        self.job_search_entry.delete(0, tk.END)
        self.refresh_job_list()

