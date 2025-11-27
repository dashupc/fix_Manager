"""
零售开单标签页相关逻辑
"""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from modules.ui_helpers import make_treeview_sortable
from modules.config_helpers import (
    load_parts, load_retail_units, ensure_config_value, get_client_names
)


class RetailTabMixin:
    """零售开单标签页的 Mixin 类，需要混入到主 App 类中使用"""

    def setup_retail_tab(self):
        """零售开单主界面：顶部按钮 + 列表 + 双击编辑"""
        top_frame = ttk.Frame(self.retail_tab)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="✚ 新增零售单", command=lambda: self.open_retail_order_window()).pack(side="left", padx=5)
        ttk.Button(top_frame, text="刷新列表", command=self.refresh_retail_orders).pack(side="left", padx=5)

        order_frame = ttk.Frame(self.retail_tab)
        order_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ('id', 'customer', 'total_amount', 'total_cost', 'profit', 'payment_method', 'created_at')
        column_names = {
            'id': 'ID',
            'customer': '客户单位',
            'total_amount': '总价',
            'total_cost': '总成本',
            'profit': '利润',
            'payment_method': '付款方式',
            'created_at': '创建时间'
        }
        self.retail_orders_tree = ttk.Treeview(order_frame, columns=columns, show='headings')

        for col in columns:
            self.retail_orders_tree.heading(col, text=column_names[col])
            width = 110 if col not in ('id', 'payment_method') else (60 if col == 'id' else 80)
            self.retail_orders_tree.column(col, width=width, anchor='center')

        self.retail_orders_tree.pack(fill="both", expand=True)
        self.retail_orders_tree.tag_configure('debt', background='#FFECEC', foreground='red')
        make_treeview_sortable(self.retail_orders_tree, numeric_columns={'id', 'total_amount', 'total_cost', 'profit'})
        self.retail_orders_tree.bind('<Double-1>', self.on_retail_order_double_click)

        self.refresh_retail_orders()

    def refresh_retail_orders(self):
        """加载零售订单列表"""
        for item in self.retail_orders_tree.get_children():
            self.retail_orders_tree.delete(item)

        orders = self.db.fetch_all(
            '''
            SELECT id, COALESCE(customer_unit, ''), total_amount, total_cost, profit, payment_method, created_at
            FROM retail_orders
            ORDER BY id DESC
            '''
        )
        for order in orders:
            order_id, customer, total_amount, total_cost, profit, payment_method, created_at = order
            payment_method = payment_method or '待定'
            tags = ()
            if payment_method == '欠款':
                tags = ('debt',)
            self.retail_orders_tree.insert(
                '',
                'end',
                values=(
                    order_id,
                    customer or '散客',
                    f"{total_amount or 0:.2f}",
                    f"{total_cost or 0:.2f}",
                    f"{profit or 0:.2f}",
                    payment_method,
                    created_at or ''
                ),
                tags=tags
            )

    def on_retail_order_double_click(self, event):
        """双击打开编辑窗口"""
        selected = self.retail_orders_tree.focus()
        if not selected:
            return
        values = self.retail_orders_tree.item(selected, 'values')
        if not values:
            return
        order_id = int(values[0])
        self.open_retail_order_window(order_id)

    def open_retail_order_window(self, order_id=None):
        """打开新增/编辑零售订单窗口"""
        is_edit = order_id is not None
        window = tk.Toplevel(self)
        window.title("编辑零售单" if is_edit else "新增零售单")
        self._set_window_icon(window)
        self.center_window_manual(window, 820, 600)

        main_frame = ttk.Frame(window, padding="10")
        main_frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))

        client_names = get_client_names(self.db)
        ttk.Label(top_frame, text="客户单位:", font=('Arial', 10)).pack(side="left", padx=5)
        customer_entry = ttk.Combobox(top_frame, values=client_names, width=30)
        customer_entry.pack(side="left", padx=5)
        customer_entry.set('')

        ttk.Label(top_frame, text="订单备注:", font=('Arial', 10)).pack(side="left", padx=5)
        order_note_entry = ttk.Entry(top_frame, width=30)
        order_note_entry.pack(side="left", padx=5)

        ttk.Label(top_frame, text="付款方式:", font=('Arial', 10)).pack(side="left", padx=5)
        payment_methods = ['待定', '现金', '微信', '支付宝', '收款码', '欠款']
        payment_method_combo = ttk.Combobox(top_frame, values=payment_methods, state="readonly", width=10)
        payment_method_combo.set(payment_methods[0])
        payment_method_combo.pack(side="left", padx=5)

        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill="both", expand=True, pady=10)

        columns = ('product_name', 'unit', 'quantity', 'unit_price', 'amount', 'source', 'cost', 'notes')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)

        headers = {
            'product_name': '货物名称',
            'unit': '单位',
            'quantity': '数量',
            'unit_price': '单价',
            'amount': '金额',
            'source': '货物来源',
            'cost': '成本',
            'notes': '备注'
        }
        widths = {
            'product_name': 140,
            'unit': 60,
            'quantity': 70,
            'unit_price': 80,
            'amount': 80,
            'source': 110,
            'cost': 80,
            'notes': 150
        }

        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor='center')

        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        make_treeview_sortable(tree, numeric_columns={'quantity', 'unit_price', 'amount', 'cost'})

        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill="x", pady=10)

        ttk.Label(summary_frame, text="总价:", font=('Arial', 11, 'bold')).pack(side="left", padx=10)
        total_label = ttk.Label(summary_frame, text="0.00", font=('Arial', 11))
        total_label.pack(side="left", padx=5)

        ttk.Label(summary_frame, text="利润:", font=('Arial', 11, 'bold')).pack(side="left", padx=10)
        profit_label = ttk.Label(summary_frame, text="0.00", font=('Arial', 11))
        profit_label.pack(side="left", padx=5)

        product_values = load_parts(self.db)
        unit_values = load_retail_units(self.db)
        source_rows = self.db.fetch_all("SELECT DISTINCT config_value FROM config_data WHERE config_type='part_source'")
        source_values = [row[0] for row in source_rows] if source_rows else ['自购', '客户提供', '其他']
        if '' not in product_values:
            product_values.insert(0, '')
        if '' not in unit_values:
            unit_values.insert(0, '')
        if '' not in source_values:
            source_values.insert(0, '')

        inline_editor = {'widget': None}
        NEW_ROW_SENTINEL = object()

        def get_adjacent_cell(current_item, current_key, forward=True):
            try:
                idx = columns.index(current_key)
            except ValueError:
                return current_item, columns[0]

            if forward:
                if idx < len(columns) - 1:
                    return current_item, columns[idx + 1]
                next_item = tree.next(current_item)
                if not next_item:
                    return NEW_ROW_SENTINEL, columns[0]
                return next_item, columns[0]
            else:
                if idx > 0:
                    return current_item, columns[idx - 1]
                prev_item = tree.prev(current_item)
                if not prev_item:
                    siblings = tree.get_children()
                    if not siblings:
                        return None, None
                    prev_item = siblings[-1]
                return prev_item, columns[-1]

        def destroy_inline_editor():
            widget = inline_editor.get('widget')
            if widget and widget.winfo_exists():
                widget.destroy()
            inline_editor['widget'] = None

        def update_totals():
            total_amount = 0.0
            total_cost = 0.0
            for item in tree.get_children():
                values = tree.item(item, 'values')
                total_amount += float(values[4]) if values[4] else 0.0
                total_cost += float(values[6]) if values[6] else 0.0
            profit = total_amount - total_cost
            total_label.config(text=f"{total_amount:.2f}")
            profit_label.config(text=f"{profit:.2f}")

        def start_cell_edit(item, column_key):
            if not item:
                return
            destroy_inline_editor()

            try:
                column_index = columns.index(column_key)
            except ValueError:
                return

            column_id = f"#{column_index + 1}"
            bbox = tree.bbox(item, column_id)
            if not bbox:
                tree.see(item)
                bbox = tree.bbox(item, column_id)
                if not bbox:
                    return

            x, y, width, height = bbox
            current_value = tree.set(item, column_key)
            display_value = current_value if current_value is not None else ''

            if column_key == 'product_name':
                editor = ttk.Combobox(tree, values=product_values, state="normal")
                editor.set(display_value)
            elif column_key == 'unit':
                editor = ttk.Combobox(tree, values=unit_values, state="normal")
                editor.set(display_value)
            elif column_key == 'source':
                editor = ttk.Combobox(tree, values=source_values, state="readonly")
                editor.set(display_value)
            else:
                editor = ttk.Entry(tree)
                editor.insert(0, display_value)

            inline_editor['widget'] = editor
            editor.place(x=x, y=y, width=width, height=height)
            editor.focus_set()

            commit_state = {'done': False}

            def commit_value():
                if commit_state['done']:
                    return True
                value = editor.get().strip()
                if column_key == 'product_name' and value:
                    value = value.strip()
                    product_values[:] = sorted(set(product_values + [value]))
                    ensure_config_value(self.db, 'part', value)
                if column_key == 'unit' and value:
                    value = value.strip()
                    unit_values[:] = sorted(set(unit_values + [value]))
                    ensure_config_value(self.db, 'retail_unit', value)

                numeric_columns_set = {'quantity', 'unit_price', 'amount', 'cost'}
                if column_key in numeric_columns_set:
                    try:
                        number = float(value or 0)
                        value = f"{number:.2f}"
                    except ValueError:
                        messagebox.showerror("错误", "请输入有效数字")
                        editor.focus_set()
                        return False

                row_values = list(tree.item(item, 'values'))
                row_values[column_index] = value

                if column_key in ('quantity', 'unit_price'):
                    try:
                        qty = float(row_values[columns.index('quantity')] or 0)
                        price = float(row_values[columns.index('unit_price')] or 0)
                        row_values[columns.index('amount')] = f"{qty * price:.2f}"
                    except ValueError:
                        row_values[columns.index('amount')] = "0.00"

                tree.item(item, values=row_values)
                commit_state['done'] = True
                destroy_inline_editor()
                update_totals()
                return True

            def finish_edit(callback=None):
                if commit_value():
                    if callback:
                        self.after(40, callback)

            def handle_tab(event):
                forward = not bool(event.state & 0x0001)
                if event.keysym in ('ISO_Left_Tab', 'Shift_L', 'Shift_R'):
                    forward = False

                def move_focus():
                    target_item, target_key = get_adjacent_cell(item, column_key, forward)
                    if target_item is NEW_ROW_SENTINEL:
                        target_item = insert_blank_row(auto_start=False)
                    if target_item and target_key:
                        start_cell_edit(target_item, target_key)

                finish_edit(move_focus)
                return "break"

            def handle_escape(event):
                destroy_inline_editor()
                return "break"

            editor.bind('<Return>', lambda e: finish_edit())
            editor.bind('<FocusOut>', lambda e: finish_edit())
            editor.bind('<Escape>', handle_escape)
            editor.bind('<Tab>', handle_tab)
            editor.bind('<Shift-Tab>', handle_tab)

            if isinstance(editor, ttk.Combobox):
                editor.bind('<<ComboboxSelected>>', lambda e: finish_edit())

        def insert_blank_row(auto_start=True):
            new_values = ('', '', '', '', '', '', '', '')
            item_id = tree.insert('', 'end', values=new_values)
            tree.selection_set(item_id)
            tree.focus(item_id)
            update_totals()
            if auto_start:
                tree.after(50, lambda: start_cell_edit(item_id, 'product_name'))
            return item_id

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=5)

        def delete_row():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请先选择要删除的行！")
                return
            if messagebox.askyesno("确认", "确定要删除选中的行吗？"):
                for item in selection:
                    tree.delete(item)
                update_totals()
                if not tree.get_children():
                    new_item = insert_blank_row(auto_start=False)
                    tree.after(50, lambda: start_cell_edit(new_item, 'product_name'))

        def edit_selected_row(event=None):
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请先选择要编辑的行！")
                return
            column_key = 'product_name'
            if event and hasattr(event, 'x'):
                column_id = tree.identify_column(event.x)
                index = int(column_id.replace('#', '')) - 1 if column_id else 0
                column_key = columns[index] if 0 <= index < len(columns) else 'product_name'
            start_cell_edit(selection[0], column_key)

        tree.bind('<Double-1>', edit_selected_row)

        ttk.Button(btn_frame, text="新增空行", command=insert_blank_row).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="编辑选中行", command=edit_selected_row).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="删除选中行", command=delete_row).pack(side="left", padx=5)

        def ensure_default_row(auto_focus=False):
            first_item = None
            if not tree.get_children():
                first_item = insert_blank_row(auto_start=False)
            else:
                first_item = tree.get_children()[0]
            if auto_focus and first_item:
                tree.after(80, lambda: start_cell_edit(first_item, 'product_name'))

        def save_order():
            nonlocal order_id
            all_items = tree.get_children()
            valid_rows = []
            for item in all_items:
                values = list(tree.item(item, 'values'))
                if not values[0].strip():
                    continue
                valid_rows.append(values)

            if not valid_rows:
                messagebox.showwarning("警告", "请至少填写一个完整的商品行！")
                return

            total_amount = float(total_label.cget("text") or 0)
            profit = float(profit_label.cget("text") or 0)
            total_cost = total_amount - profit

            customer_unit = customer_entry.get().strip()
            order_note = order_note_entry.get().strip()
            payment_method_val = payment_method_combo.get().strip() or '待定'

            order_fields = [
                ('customer_unit', customer_unit),
                ('total_amount', total_amount),
                ('total_cost', total_cost),
                ('profit', profit),
                ('notes', order_note),
                ('payment_method', payment_method_val)
            ]
            if self.db.has_column('retail_orders', 'created_at') and not is_edit:
                order_fields.append(('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            if self.db.has_column('retail_orders', 'selling_price'):
                order_fields.append(('selling_price', total_amount))
            if self.db.has_column('retail_orders', 'product_name'):
                order_fields.append(('product_name', ''))

            try:
                if is_edit:
                    set_clause = ', '.join(f"{col}=?" for col, _ in order_fields)
                    params = [val for _, val in order_fields] + [order_id]
                    self.db.execute_query(
                        f"UPDATE retail_orders SET {set_clause} WHERE id=?",
                        params
                    )
                    self.db.execute_query('DELETE FROM retail_order_items WHERE order_id=?', (order_id,))
                else:
                    columns_sql = ', '.join(col for col, _ in order_fields)
                    placeholders = ', '.join('?' for _ in order_fields)
                    order_id_local = self.db.execute_query(
                        f"INSERT INTO retail_orders ({columns_sql}) VALUES ({placeholders})",
                        tuple(val for _, val in order_fields)
                    )
                    order_id = order_id_local

                if not order_id:
                    messagebox.showerror("错误", "保存零售订单失败，无法获取订单编号。")
                    return

                for values in valid_rows:
                    self.db.execute_query(
                        '''
                        INSERT INTO retail_order_items
                        (order_id, product_name, unit, quantity, unit_price, amount, source, cost, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            order_id,
                            values[0],
                            values[1],
                            values[2],
                            values[3],
                            values[4],
                            values[5],
                            values[6],
                            values[7]
                        )
                    )

                messagebox.showinfo("成功", f"零售订单已{'更新' if is_edit else '保存'}！\n订单号: {order_id}")
                window.destroy()
                self.refresh_retail_orders()
            except Exception as exc:
                messagebox.showerror("错误", f"保存失败: {exc}")

        def load_order():
            if not is_edit:
                return

            order = self.db.fetch_one(
                '''
                SELECT customer_unit, total_amount, total_cost, profit, notes, payment_method
                FROM retail_orders
                WHERE id=?
                ''',
                (order_id,)
            )
            if not order:
                messagebox.showerror("错误", f"无法找到零售订单 ID: {order_id}")
                window.destroy()
                return

            customer_unit, total_amount_val, total_cost_val, profit_val, notes, payment_method_value = order
            customer_entry.insert(0, customer_unit or '')
            order_note_entry.insert(0, notes or '')
            if payment_method_value and payment_method_value in payment_methods:
                payment_method_combo.set(payment_method_value)

            items = self.db.fetch_all(
                '''
                SELECT product_name, unit, quantity, unit_price, amount, source, cost, notes
                FROM retail_order_items
                WHERE order_id=?
                ''',
                (order_id,)
            )
            for row in items:
                tree.insert('', 'end', values=row)
            update_totals()

        ttk.Button(main_frame, text="保存零售单", command=save_order).pack(side="left", padx=5, pady=5)
        ttk.Button(main_frame, text="关闭窗口", command=window.destroy).pack(side="left", padx=5, pady=5)

        load_order()
        ensure_default_row(auto_focus=not is_edit)

