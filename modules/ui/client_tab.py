"""
客户管理标签页相关逻辑
"""
import tkinter as tk
from tkinter import messagebox, ttk

from modules.ui_helpers import make_treeview_sortable


class ClientTabMixin:
    """客户管理标签页的 Mixin 类，需要混入到主 App 类中使用"""

    def setup_clients_tab(self):
        client_list_frame = ttk.LabelFrame(self.clients_tab, text="客户列表")
        client_list_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        columns = ('id', 'name', 'phone')
        column_names = {
            'id': 'ID',
            'name': '姓名/公司',
            'phone': '联系电话'
        }
        self.client_tree = ttk.Treeview(client_list_frame, columns=columns, show='headings')

        for col in columns:
            self.client_tree.heading(col, text=column_names[col])
            self.client_tree.column(col, width=150)

        self.client_tree.column('id', width=40)
        self.client_tree.pack(fill="both", expand=True)
        make_treeview_sortable(self.client_tree, numeric_columns={'id'})

        self.client_tree.bind('<<TreeviewSelect>>', self.load_client_detail)

        detail_frame = ttk.LabelFrame(self.clients_tab, text="编辑客户信息")
        detail_frame.pack(side="right", fill="y", padx=10, pady=10, ipadx=5, ipady=5)

        tk.Label(detail_frame, text="客户 ID:").pack(pady=5, anchor="w")
        self.edit_client_id = tk.Label(detail_frame, text="未选择", fg="gray")
        self.edit_client_id.pack(fill="x", padx=5)
        self.current_client_id = None

        tk.Label(detail_frame, text="姓名/公司:").pack(pady=5, anchor="w")
        self.edit_client_name = tk.Entry(detail_frame)
        self.edit_client_name.pack(fill="x", padx=5)

        tk.Label(detail_frame, text="联系电话 (非必填):").pack(pady=5, anchor="w")
        self.edit_client_phone = tk.Entry(detail_frame)
        self.edit_client_phone.pack(fill="x", padx=5)

        ttk.Button(detail_frame, text="更新信息", command=self.update_client).pack(fill="x", pady=10, padx=5)
        ttk.Button(detail_frame, text="查看关联工单", command=self.view_client_jobs).pack(fill="x", padx=5)

        self.refresh_client_list()

    def refresh_client_list(self):
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)

        query = "SELECT id, name, phone FROM clients ORDER BY id DESC"
        clients = self.db.fetch_all(query)
        for client in clients:
            self.client_tree.insert('', 'end', values=client)

    def load_client_detail(self, event):
        selected_item = self.client_tree.focus()
        if not selected_item:
            return

        client_data = self.client_tree.item(selected_item, 'values')
        client_id, name, phone = client_data
        self.current_client_id = client_id

        self.edit_client_id.config(text=str(client_id))

        self.edit_client_name.delete(0, tk.END)
        self.edit_client_name.insert(0, name)
        self.edit_client_phone.delete(0, tk.END)
        self.edit_client_phone.insert(0, phone)

    def update_client(self):
        if not self.current_client_id:
            messagebox.showwarning("警告", "请先选择一个客户进行更新。")
            return

        client_id = self.current_client_id
        name = self.edit_client_name.get().strip()
        phone = self.edit_client_phone.get().strip()

        if not name:
            messagebox.showwarning("输入错误", "客户姓名不能为空！")
            return

        update_query = '''
            UPDATE clients SET name=?, phone=? WHERE id=?
        '''
        if self.db.execute_query(update_query, (name, phone or '', client_id)) is not None:
            messagebox.showinfo("成功", f"客户 ID: {client_id} 的信息已更新！")
            self.refresh_client_list()
        else:
            messagebox.showerror("失败", "更新客户信息失败。")

    def view_client_jobs(self):
        if not self.current_client_id:
            messagebox.showwarning("警告", "请先选择一个客户。")
            return

        client_name = self.edit_client_name.get()

        jobs = self.db.fetch_all(
            "SELECT id, device_info, status, created_at FROM job_orders WHERE client_id = ? ORDER BY created_at DESC",
            (self.current_client_id,)
        )

        if not jobs:
            messagebox.showinfo("历史工单", f"客户 {client_name} 暂无历史工单记录。")
            return

        job_win = tk.Toplevel(self)
        job_win.title(f"{client_name} 的历史工单 ({len(jobs)} 份)")
        self._set_window_icon(job_win)

        self.center_window_manual(job_win, 500, 300)

        job_tree = ttk.Treeview(job_win, columns=('id', 'device', 'status', 'date'), show='headings')
        job_tree.heading('id', text='工单ID')
        job_tree.column('id', width=60)
        job_tree.heading('device', text='设备信息')
        job_tree.column('device', width=180)
        job_tree.heading('status', text='状态')
        job_tree.column('status', width=80)
        job_tree.heading('date', text='日期')
        job_tree.column('date', width=120)

        for job in jobs:
            job_tree.insert('', 'end', values=job)

        job_tree.pack(fill="both", expand=True, padx=10, pady=10)
        make_treeview_sortable(job_tree, numeric_columns={'id'})

