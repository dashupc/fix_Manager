import csv
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from shutil import copyfile
import smtplib
import socket
import sqlite3
import ssl
import sys
import threading
import time as time_module
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageDraw
import pystray
import webbrowser

from dateutil.relativedelta import relativedelta 


DATABASE_NAME = 'recovery_manager.db'
SETTINGS_FILE = 'settings.txt'
class DatabaseManager:
    """管理 SQLite 数据库连接和 CURD 操作"""
    def __init__(self, db_name):
        # 确保线程安全
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
        
    def create_tables(self):
        # Clients 表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT 
            )
        ''')
        
        # Job_orders 表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                serial_number TEXT,  
                device_info TEXT NOT NULL,
                fault_desc TEXT,
                repair_details TEXT, 
                status TEXT,
                initial_quote REAL,
                final_price REAL DEFAULT 0.0,
                cost REAL DEFAULT 0.0,
                other_cost REAL DEFAULT 0.0,
                payment_method TEXT DEFAULT '待定', 
                payment_notes TEXT, 
                created_at TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
        ''')
        
        # 检查并添加缺失的列 (兼容旧版本数据库)
        self._add_missing_column('job_orders', 'other_cost', 'REAL DEFAULT 0.0')
        self._add_missing_column('job_orders', 'serial_number', 'TEXT')
        self._add_missing_column('job_orders', 'repair_details', 'TEXT')
        self._add_missing_column('job_orders', 'payment_method', "TEXT DEFAULT '待定'")
        self._add_missing_column('job_orders', 'payment_notes', "TEXT")
        self._add_missing_column('job_orders', 'replaced_parts', "TEXT")
        self._add_missing_column('job_orders', 'part_source', "TEXT")
        self._add_missing_column('job_orders', 'part_cost', "REAL DEFAULT 0.0")
        self._add_missing_column('job_orders', 'fault_type', "TEXT")

        # financial_records 表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                record_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                date TEXT,
                FOREIGN KEY (job_id) REFERENCES job_orders(id)
            )
        ''')
        
        # 配置数据表（存储故障类型、配件、配件来源等）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_type TEXT NOT NULL,
                config_value TEXT NOT NULL,
                UNIQUE(config_type, config_value)
            )
        ''')
        
        # 初始化默认数据
        self._init_default_config()
        
        self.conn.commit()
    
    def _init_default_config(self):
        """初始化默认配置数据"""
        # 默认故障类型
        default_fault_types = ['不加电', '通电不显示', '数据恢复', '其他']
        for fault_type in default_fault_types:
            try:
                self.cursor.execute(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('fault_type', fault_type)
                )
            except:
                pass
        
        # 默认配件来源
        default_sources = ['自购', '客户提供', '其他']
        for source in default_sources:
            try:
                self.cursor.execute(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part_source', source)
                )
            except:
                pass
        
        self.conn.commit()

    def _add_missing_column(self, table_name, column_name, column_type):
        try:
            self.cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
        except sqlite3.OperationalError:
            try:
                 self.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                 self.conn.commit()
            except Exception:
                 pass

    def execute_query(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return None

    def fetch_all(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fetch_one(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()


class RecoveryManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("简易维修管理系统")
        
        self.APP_WIDTH = 1000
        self.APP_HEIGHT = 680 
        
        self.withdraw()
        self.geometry(f'{self.APP_WIDTH}x{self.APP_HEIGHT}') 
        self.update_idletasks()
        self.center_window_manual(self, self.APP_WIDTH, self.APP_HEIGHT)
        
        self._set_window_icon(self)
        self.deiconify()
        self.after(100, lambda: self._set_window_icon(self))
        
        self.db = DatabaseManager(DATABASE_NAME)
        self.load_settings()
        
        self.tray_icon = None
        self.tray_thread = None
        self.last_activity_time = time_module.time()
        self.idle_timer = None
        self.is_minimized_to_tray = False
        self.last_tray_click_time = 0

        self.status_bar = tk.Label(self, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.config(text="系统准备就绪。")
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)
        
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="备份设置", menu=file_menu)
        file_menu.add_command(label="备份数据库到本地", command=self.backup_database)
        file_menu.add_command(label="恢复数据库", command=self.restore_database)
        file_menu.add_separator()
        file_menu.add_command(label="设置邮箱备份", command=self.show_email_settings)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit_app)
        
        self.menubar.add_command(label="关于", command=self.show_about)
        self.menubar.add_command(label="隐藏到托盘", command=self.minimize_to_tray)
        
        # 使用 ttk notebook (标签页)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.job_tab = ttk.Frame(self.notebook); self.notebook.add(self.job_tab, text='工单管理'); self.setup_job_tab()
        self.finance_tab = ttk.Frame(self.notebook); self.notebook.add(self.finance_tab, text='财务统计'); self.setup_finance_tab()
        self.clients_tab = ttk.Frame(self.notebook); self.notebook.add(self.clients_tab, text='客户管理'); self.setup_clients_tab()
        
        self.schedule_daily_backup()
        
        self.bind_activity_events()
        self.start_idle_timer()
        self.setup_tray_icon()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        
    def _set_window_icon(self, window):
        """
        设置窗口图标，统一使用 icon.ico。使用 PyInstaller 兼容的路径检测。
        """
        icon_name = 'icon.ico'
        
        def get_resource_path(relative_path):
            """获取资源文件的绝对路径，优先使用 PyInstaller 运行时路径"""
            if getattr(sys, 'frozen', False):
                # 如果是 PyInstaller 打包后的可执行文件
                base_path = sys._MEIPASS
            else:
                # 如果是普通 Python 脚本运行
                base_path = os.path.dirname(os.path.abspath(__file__))
                
            full_path = os.path.join(base_path, relative_path)
            # 返回绝对路径，Windows 上使用反斜杠
            return os.path.abspath(full_path)

        # 使用 iconbitmap 设置图标 (.ico 文件)
        full_ico_path = get_resource_path(icon_name)
        
        if os.path.exists(full_ico_path):
            try:
                if isinstance(window, tk.Toplevel):
                    # Toplevel 窗口使用 wm_iconbitmap
                    window.wm_iconbitmap(bitmap=full_ico_path)
                else:
                    # 主窗口：先尝试使用绝对路径的字符串格式
                    # Windows 上需要确保路径格式正确
                    icon_path_str = full_ico_path.replace('\\', '/')
                    try:
                        window.iconbitmap(icon_path_str)
                    except:
                        # 如果失败，尝试原始路径
                        window.iconbitmap(full_ico_path)
                    
                    # 同时使用 wm_iconbitmap 确保任务栏图标生效
                    try:
                        window.wm_iconbitmap(bitmap=icon_path_str)
                    except:
                        window.wm_iconbitmap(bitmap=full_ico_path)
            except Exception as e:
                # 图标设置失败，打印错误信息用于调试
                print(f"图标设置失败: {e}, 路径: {full_ico_path}")
                pass
        else:
            # 图标文件不存在
            print(f"图标文件不存在: {full_ico_path}")
            pass
            
    def center_window_manual(self, window, width, height):
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')
        
    def quit_app(self):
        if hasattr(self, 'backup_timer') and self.backup_timer.is_alive():
            self.backup_timer.cancel()
        if self.tray_icon:
            self.tray_icon.stop()
        self.quit()
        self.destroy()
    
    def create_tray_image(self):
        """创建系统托盘图标"""
        try:
            icon_path = self._get_icon_path()
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                return image
        except:
            pass
        # 如果无法加载图标，创建一个简单的图标
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='blue')
        return image
    
    def _get_icon_path(self):
        """获取图标路径"""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'icon.ico')
    
    def setup_tray_icon(self):
        """设置系统托盘图标"""
        try:
            image = self.create_tray_image()
            
            def show_window_action(icon, item):
                """显示窗口的菜单项动作"""
                self.after(0, self.show_window)
            
            def quit_app_action(icon, item):
                """退出应用的菜单项动作"""
                self.after(0, self.quit_app)
            
            menu = pystray.Menu(
                pystray.MenuItem('显示窗口', show_window_action, default=True),
                pystray.MenuItem('退出', quit_app_action)
            )
            
            self.tray_icon = pystray.Icon(
                "维修管理系统", 
                image, 
                "简易维修管理系统", 
                menu
            )
            
            def run_tray():
                self.tray_icon.run()
            
            self.tray_thread = threading.Thread(target=run_tray, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            print(f"系统托盘设置失败: {e}")
    
    def show_window(self, icon=None, item=None):
        """从托盘恢复窗口"""
        self.deiconify()
        self.lift()
        self.focus_force()
        self.is_minimized_to_tray = False
        self.update_activity()
    
    def minimize_to_tray(self):
        """隐藏窗口到系统托盘"""
        self.withdraw()
        self.is_minimized_to_tray = True
        self.status_bar.config(text="程序已隐藏到系统托盘")
    
    def bind_activity_events(self):
        """绑定用户活动事件"""
        events = ['<Button-1>', '<KeyPress>', '<ButtonRelease>']
        for event in events:
            self.bind(event, self.on_activity)
        # Motion事件只绑定到主窗口，避免性能问题
        self.bind('<Motion>', self.on_activity)
    
    def on_activity(self, event=None):
        """用户活动时更新活动时间"""
        self.update_activity()
    
    def update_activity(self):
        """更新活动时间并重置空闲计时器"""
        self.last_activity_time = time_module.time()
        self.start_idle_timer()
    
    def start_idle_timer(self):
        """启动空闲计时器（10分钟）"""
        if self.idle_timer:
            self.after_cancel(self.idle_timer)
        self.idle_timer = self.after(600000, self.check_idle)  # 10分钟 = 600000毫秒
    
    def check_idle(self):
        """检查是否空闲超过10分钟"""
        idle_time = time_module.time() - self.last_activity_time
        if idle_time >= 600 and not self.is_minimized_to_tray:  # 10分钟 = 600秒
            self.minimize_to_tray()
    
    def on_closing(self):
        """窗口关闭事件处理：隐藏到托盘"""
        self.minimize_to_tray()
    
    def show_about(self):
        """显示关于窗口"""
        about_win = tk.Toplevel(self)
        about_win.title("关于")
        about_win.geometry("400x200")
        about_win.resizable(False, False)
        self._set_window_icon(about_win)
        self.center_window_manual(about_win, 400, 200)
        
        main_frame = ttk.Frame(about_win, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        title_label = tk.Label(main_frame, text="简易维修管理系统", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        contact_label = tk.Label(main_frame, text="联系方式：QQ 88179096", font=('Arial', 11))
        contact_label.pack(pady=5)
        
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(pady=5)
        
        url_label_text = tk.Label(url_frame, text="网址：", font=('Arial', 11))
        url_label_text.pack(side="left")
        
        url_label = tk.Label(url_frame, text="www.itvip.com.cn", 
                            font=('Arial', 11), fg="blue", cursor="hand2")
        url_label.pack(side="left")
        url_label.bind("<Button-1>", lambda e: webbrowser.open("http://www.itvip.com.cn"))
        url_label.bind("<Enter>", lambda e: url_label.config(fg="red"))
        url_label.bind("<Leave>", lambda e: url_label.config(fg="blue"))
        
        close_button = ttk.Button(main_frame, text="关闭", command=about_win.destroy)
        close_button.pack(pady=20)

    def load_settings(self):
        self.settings = {
            'sender_email': '',
            'sender_password': '', 
            'recipient_email': '',
            'backup_time_hour': 23,
            'backup_time_minute': 0
        }
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                for line in f:
                    try:
                        key, value = line.strip().split('=', 1)
                        if key in ['backup_time_hour', 'backup_time_minute']:
                            self.settings[key] = int(value)
                        else:
                            self.settings[key] = value
                    except ValueError:
                        continue

    def save_settings(self):
        with open(SETTINGS_FILE, 'w') as f:
            for key, value in self.settings.items():
                f.write(f'{key}={value}\n')
                
    def backup_database(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"Recovery_Manager_Backup_{timestamp}.db"
        
        backup_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            initialfile=default_filename,
            title="选择数据库备份保存位置",
            filetypes=(("Database files", "*.db"), ("All files", "*.*"))
        )
        
        if backup_path:
            try:
                # 必须关闭连接才能复制文件
                self.db.conn.close() 
                copyfile(DATABASE_NAME, backup_path)
                self.db = DatabaseManager(DATABASE_NAME) # 重新连接
                
                messagebox.showinfo("备份成功", f"数据库已成功备份到:\n{backup_path}")
            except Exception as e:
                # 重新连接以防中断
                self.db = DatabaseManager(DATABASE_NAME)
                messagebox.showerror("备份失败", f"备份过程中发生错误: {e}")
            
    def restore_database(self):
        backup_file = filedialog.askopenfilename(
            title="选择要恢复的数据库备份文件",
            filetypes=(("Database files", "*.db"), ("All files", "*.*"))
        )

        if not backup_file:
            messagebox.showinfo("恢复取消", "数据库恢复操作已取消。")
            return
            
        confirm = messagebox.askyesno(
            "数据恢复确认", 
            f"警告：此操作将使用文件:\n{backup_file}\n覆盖当前的数据库数据。所有未备份的当前数据将永久丢失！\n确定要继续吗？"
        )
        
        if not confirm:
            messagebox.showinfo("操作取消", "数据恢复已被用户取消。")
            return

        try:
            self.db.conn.close()
            copyfile(backup_file, DATABASE_NAME)
            self.db = DatabaseManager(DATABASE_NAME)
            
            self.refresh_job_list()
            self.refresh_client_list()
            self.refresh_finance_report()
            
            messagebox.showinfo("恢复成功", "数据库已成功恢复，系统已加载新数据。")

        except Exception as e:
            try:
                self.db = DatabaseManager(DATABASE_NAME)
            except:
                pass
            messagebox.showerror("恢复失败", f"数据恢复过程中发生错误: {e}\n请检查备份文件是否有效。")

    def show_email_settings(self):
        """显示邮箱设置和定时备份时间的窗口"""
        settings_win = tk.Toplevel(self)
        settings_win.title("邮箱备份设置")
        self._set_window_icon(settings_win) # <-- 设置图标
        self.center_window_manual(settings_win, 450, 500) 
        
        main_frame = ttk.Frame(settings_win, padding="15")
        main_frame.pack(fill="both", expand=True)

        # QQ 授权码提示
        ttk.Label(main_frame, text="⚠️ 重要提示：QQ 邮箱需使用**授权码**作为密码。", 
                  foreground="red", wraplength=400, font=('Arial', 10, 'bold')).pack(fill="x", pady=5)
        ttk.Label(main_frame, text="请在QQ邮箱设置-账户-开启SMTP服务中获取授权码。", 
                  foreground="darkorange", wraplength=400).pack(fill="x", pady=5)

        # 发件人设置
        sender_frame = ttk.LabelFrame(main_frame, text="发件邮箱 (QQ邮箱)")
        sender_frame.pack(fill="x", pady=10)
        
        tk.Label(sender_frame, text="QQ邮箱地址:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.sender_email_entry = tk.Entry(sender_frame, width=30)
        self.sender_email_entry.insert(0, self.settings['sender_email'])
        self.sender_email_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(sender_frame, text="授权码 (非密码):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.sender_password_entry = tk.Entry(sender_frame, show='*', width=30)
        self.sender_password_entry.insert(0, self.settings['sender_password'])
        self.sender_password_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # 接收人设置
        recipient_frame = ttk.LabelFrame(main_frame, text="接收邮箱")
        recipient_frame.pack(fill="x", pady=10)
        
        tk.Label(recipient_frame, text="接收邮箱地址:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.recipient_email_entry = tk.Entry(recipient_frame, width=30)
        self.recipient_email_entry.insert(0, self.settings['recipient_email'])
        self.recipient_email_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # 备份时间设置
        time_frame = ttk.LabelFrame(main_frame, text="每日备份时间")
        time_frame.pack(fill="x", pady=10)
        
        tk.Label(time_frame, text="时间 (时 HH: 0-23):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.backup_hour_entry = ttk.Combobox(time_frame, width=5, values=[f'{i:02d}' for i in range(24)], state="readonly")
        self.backup_hour_entry.set(f'{self.settings["backup_time_hour"]:02d}')
        self.backup_hour_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(time_frame, text="时间 (分 MM: 0-59):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.backup_minute_entry = ttk.Combobox(time_frame, width=5, values=[f'{i:02d}' for i in range(60)], state="readonly")
        self.backup_minute_entry.set(f'{self.settings["backup_time_minute"]:02d}')
        self.backup_minute_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # 按钮
        ttk.Button(main_frame, text="保存设置", 
                   command=lambda: self.save_email_settings(settings_win)).pack(fill="x", pady=10)
                   
        ttk.Button(main_frame, text="立即备份", 
                   command=self.test_email_settings).pack(fill="x")

    def save_email_settings(self, window):
        try:
            hour = int(self.backup_hour_entry.get())
            minute = int(self.backup_minute_entry.get())
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("时间范围错误")
                
            self.settings['sender_email'] = self.sender_email_entry.get().strip()
            self.settings['sender_password'] = self.sender_password_entry.get().strip()
            self.settings['recipient_email'] = self.recipient_email_entry.get().strip()
            self.settings['backup_time_hour'] = hour
            self.settings['backup_time_minute'] = minute
            
            self.save_settings()
            
            self.schedule_daily_backup()
            
            messagebox.showinfo("成功", "邮箱和备份时间设置已保存。")
            window.destroy()
            
        except ValueError as e:
            messagebox.showerror("错误", f"时间输入无效：{e}")
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败：{e}")

    def test_email_settings(self):
        """测试邮件设置是否能够成功发送"""
        temp_settings = {
            'sender_email': self.sender_email_entry.get().strip(),
            'sender_password': self.sender_password_entry.get().strip(),
            'recipient_email': self.recipient_email_entry.get().strip()
        }
        
        if not temp_settings['sender_email'] or not temp_settings['sender_password'] or not temp_settings['recipient_email']:
            messagebox.showwarning("测试失败", "请填写完整的发件邮箱、授权码和收件邮箱！")
            return

        test_file = f"temp_test_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
        
        # 1. 在主线程中关闭数据库连接，确保文件可以被复制
        try:
            self.db.conn.commit()
            self.db.conn.close() 
            copyfile(DATABASE_NAME, test_file)
            
        except Exception as e:
            # 尝试重新连接，防止程序崩溃
            try:
                self.db = DatabaseManager(DATABASE_NAME)
            except:
                pass
            messagebox.showerror("测试失败", f"创建测试备份文件失败，请关闭所有数据库引用并重试: {e}")
            return

        # 2. 重新连接数据库
        try:
            self.db = DatabaseManager(DATABASE_NAME) 
        except Exception as e:
            messagebox.showerror("测试失败", f"重新连接数据库失败: {e}")
            return
            
        # 3. 发送邮件
        try:
            self.send_email_with_attachment(
                temp_settings['sender_email'],
                temp_settings['sender_password'],
                temp_settings['recipient_email'],
                test_file,
                is_test=True
            )
            messagebox.showinfo("测试成功", "测试邮件已成功发送！请检查收件箱。")
        except smtplib.SMTPAuthenticationError:
             messagebox.showerror("测试失败", "授权码或用户名错误！请确认授权码（不是登录密码）是否正确，或QQ邮箱SMTP服务是否开启。")
        except smtplib.SMTPConnectError as e:
             messagebox.showerror("测试失败", "无法连接到 QQ 邮箱 SMTP 服务器！请检查您的网络连接或防火墙设置。")
        except smtplib.SMTPRecipientsRefused as e:
            messagebox.showerror("测试失败", f"收件人地址被拒绝:\n{str(e)}")
        except (smtplib.SMTPException, OSError, ValueError, FileNotFoundError) as e:
            error_msg = str(e) if e else "未知错误"
            messagebox.showerror("测试失败", f"邮件发送失败，请检查设置和授权码:\n错误信息: {error_msg}")
        except Exception as e:
            try:
                error_msg = str(e) if e else "未知错误"
                error_type = type(e).__name__
                messagebox.showerror("测试失败", f"邮件发送失败:\n错误类型: {error_type}\n错误信息: {error_msg}")
            except:
                messagebox.showerror("测试失败", "邮件发送失败，但无法获取详细错误信息。请检查网络连接和邮箱设置。")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


    def send_email_with_attachment(self, sender, password, recipient, file_path, is_test=False):
        """使用 QQ 邮箱发送带附件的邮件"""
        
        if not sender or not password or not recipient:
            raise ValueError("发件人、密码（授权码）或收件人不能为空。")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"备份文件不存在: {file_path}")

        subject_prefix = "[测试邮件] " if is_test else "[自动备份] "
        subject = f"{subject_prefix}数据恢复系统备份 - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"附件是日期为 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 的数据库备份文件：\n{os.path.basename(file_path)}"

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f"attachment; filename= {os.path.basename(file_path)}",
        )
        msg.attach(part)

        smtp_server = "smtp.qq.com"
        smtp_port = 465
        
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        try:
            server.login(sender, password)
            failed_recipients = server.sendmail(sender, [recipient], msg.as_string())
            if failed_recipients and recipient in failed_recipients:
                raise smtplib.SMTPRecipientsRefused(failed_recipients)
        finally:
            try:
                server.quit()
            except:
                pass
            

    def schedule_daily_backup(self):
        """计算下次备份时间并设置定时器，并更新状态栏"""
        
        if hasattr(self, 'backup_timer') and self.backup_timer.is_alive():
            self.backup_timer.cancel()
            
        target_hour = self.settings['backup_time_hour']
        target_minute = self.settings['backup_time_minute']
        
        if not self.settings['sender_email'] or not self.settings['recipient_email']:
            self.status_bar.config(text="⚠️ 邮箱自动备份未激活。请在[文件]-[设置邮箱备份]中配置。")
            return 

        now = datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        if now >= target_time:
            target_time += relativedelta(days=1)
        
        delay_seconds = (target_time - now).total_seconds()
        
        next_run_time_str = target_time.strftime('%Y-%m-%d %H:%M:%S')
        self.status_bar.config(text=f"✅ 每日数据库自动备份已激活。下一次运行时间: {next_run_time_str}")
        
        self.backup_timer = threading.Timer(delay_seconds, self.perform_daily_backup)
        self.backup_timer.daemon = True 
        self.backup_timer.start()
        
        print(f"定时备份已安排，下一次运行时间: {next_run_time_str}")


    def perform_daily_backup(self):
        """
        执行每日备份任务，修正状态更新逻辑
        """
        
        # 1. 在当前线程（Timer线程）中关闭主线程的数据库连接
        try:
            self.db.conn.commit()
            self.db.conn.close() 
        except Exception as e:
            print(f"【定时备份警告】尝试关闭主连接失败: {e}")
            pass

        self.after(0, lambda: self.status_bar.config(text=f"🔄 正在执行自动备份..."))
        
        backup_filename = f"Recovery_Manager_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        success = False
        
        # 2. 创建本地备份文件
        try:
            copyfile(DATABASE_NAME, backup_filename)
            
            # 3. 发送邮件
            try:
                self.send_email_with_attachment(
                    self.settings['sender_email'],
                    self.settings['sender_password'],
                    self.settings['recipient_email'],
                    backup_filename
                )
                print(f"【定时备份成功】备份文件 {backup_filename} 已成功发送到邮箱。")
                success = True # 标记为成功
                
            except Exception as e:
                # 邮件发送失败
                error_msg = f"邮件发送错误: {e}"
                if 'SMTPAuthenticationError' in str(e):
                     error_msg = "授权码错误或SMTP未开启"
                elif 'SMTPConnectError' in str(e):
                     error_msg = "SMTP连接失败"
                
                print(f"【定时备份失败】邮件发送错误: {e}")
                # 更新状态栏：邮件发送失败
                self.after(0, lambda: self.status_bar.config(text=f"❌ 自动备份失败 ({error_msg})"))
            
        except Exception as e:
            # 本地文件创建失败
            print(f"【定时备份失败】创建本地备份文件失败: {e}")
            # 更新状态栏：本地文件创建失败
            self.after(0, lambda: self.status_bar.config(text=f"❌ 自动备份失败 (本地文件创建错误: {e})"))

        finally:
            # 4. 无论邮件发送或文件创建是否成功，都要执行清理和重连
            
            # 如果邮件发送成功，这里设置最终的成功状态
            if success:
                self.after(0, lambda: self.status_bar.config(text=f"✅ 备份成功！文件已发送至 {self.settings['recipient_email']}。"))
            
            # 清理临时文件
            if os.path.exists(backup_filename):
                try:
                    os.remove(backup_filename)
                except Exception as e:
                    # 仅打印警告，不影响主流程
                    print(f"【定时备份警告】清理临时文件失败: {e}")
            
            # 5. 在主线程中重新打开数据库连接，并重新安排下一次备份
            self.after(0, lambda: setattr(self, 'db', DatabaseManager(DATABASE_NAME)))
            self.after(0, self.schedule_daily_backup)
                
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
            'device': '设备信息', 
            'fault_desc': '故障描述', 
            'status': '状态', 
            'quote': '初步报价(¥)', 
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
        
        # 配置标签颜色：非完成状态=红色
        self.job_tree.tag_configure('other', background='#FFF0F0', foreground='red')
        
        self.job_tree.pack(fill="both", expand=True)
        
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
        
        # 兼容工单列表双击和财务列表双击（伪造的 event.widget）
        selected_item = event.widget.focus()
        if not selected_item: return
        
        # 获取工单 ID
        job_data = event.widget.item(selected_item, 'values')
        # 无论从哪个列表过来，第一个值都是 ID
        job_id = job_data[0] 
        
        query = '''
            SELECT 
                j.id, c.name, c.phone, j.serial_number,
                j.device_info, j.fault_type, j.fault_desc, j.repair_details, j.status, 
                j.initial_quote, j.final_price, j.cost, j.other_cost, 
                j.payment_method, j.payment_notes, j.replaced_parts, 
                j.part_source, j.part_cost, j.created_at
            FROM job_orders j
            JOIN clients c ON j.client_id = c.id
            WHERE j.id = ?
        '''
        details = self.db.fetch_one(query, (job_id,))
        if not details:
            messagebox.showerror("错误", f"无法找到工单 ID: {job_id} 的详细信息。")
            return
            
        (job_id, client_name, client_phone, serial_number,
         device_info, fault_type, fault_desc, repair_details, status, 
         initial_quote, final_price, cost, other_cost, 
         payment_method, payment_notes, replaced_parts, 
         part_source, part_cost, created_at) = details
         
        replaced_parts = replaced_parts or ''
        part_source = part_source or ''
        part_cost = part_cost or 0.0
         
        net_profit = final_price - cost - other_cost - part_cost
        
        detail_win = tk.Toplevel(self)
        detail_win.title(f"工单详情 #{job_id} - {client_name}")
        self._set_window_icon(detail_win) # <-- 设置图标
        
        self.center_window_manual(detail_win, 600, 650) 
        
        main_frame = ttk.Frame(detail_win, padding="5")
        main_frame.pack(fill="both", expand=True)

        def add_detail_row(parent, label_text, value, row, color=None, font=None):
            tk.Label(parent, text=label_text, anchor="w", justify=tk.LEFT, font=('Arial', 10, 'bold')).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            tk.Label(parent, text=str(value) if value else 'N/A', anchor="w", justify=tk.LEFT, fg=color, font=font, wraplength=350).grid(row=row, column=1, padx=5, pady=2, sticky="w")

        details_frame = ttk.LabelFrame(main_frame, text="工单与客户信息")
        details_frame.pack(fill="x", pady=5)
        details_frame.columnconfigure(1, weight=1)
        details_frame.columnconfigure(3, weight=1)

        r = 0
        # 第一列
        tk.Label(details_frame, text="工单 ID:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(job_id) if job_id else 'N/A', anchor="w", wraplength=200).grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text="客户:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(client_name) if client_name else 'N/A', anchor="w", wraplength=200).grid(row=r, column=3, padx=5, pady=2, sticky="w")
        r += 1
        
        tk.Label(details_frame, text="电话:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(client_phone) if client_phone else 'N/A', anchor="w", wraplength=200).grid(row=r, column=1, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text="序列号:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(serial_number) if serial_number else 'N/A', anchor="w", wraplength=200).grid(row=r, column=3, padx=5, pady=2, sticky="w")
        r += 1
        
        tk.Label(details_frame, text="设备:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(device_info) if device_info else 'N/A', anchor="w", wraplength=200).grid(row=r, column=1, columnspan=3, padx=5, pady=2, sticky="w")
        r += 1
        
        tk.Label(details_frame, text="故障类型:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=2, sticky="w")
        tk.Label(details_frame, text=str(fault_type) if fault_type else 'N/A', anchor="w", wraplength=200).grid(row=r, column=1, columnspan=3, padx=5, pady=2, sticky="w")
        
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
        
        edit_frame = ttk.LabelFrame(main_frame, text="工单状态与财务信息")
        edit_frame.pack(fill="x", pady=5)
        edit_frame.columnconfigure(1, weight=1)
        edit_frame.columnconfigure(3, weight=1)
        
        r = 0
        # 第一列
        tk.Label(edit_frame, text="状态:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        status_var = tk.StringVar(value=status)
        statuses = ['待检测', '检测中', '报价中', '维修中', '完成', '取消']
        status_menu = ttk.Combobox(edit_frame, textvariable=status_var, values=statuses, state="readonly", width=18)
        status_menu.grid(row=r, column=1, padx=5, pady=3, sticky="ew")
        
        # 第二列
        tk.Label(edit_frame, text="最终实收", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        final_price_entry = tk.Entry(edit_frame)
        final_price_entry.insert(0, str(final_price))
        final_price_entry.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1
        
        # 第一列
        tk.Label(edit_frame, text="付款方式", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        payment_method_var = tk.StringVar(value=payment_method)
        payment_methods = ['待定', '现金', '微信', '支付宝', '收款码', '欠款']
        payment_method_menu = ttk.Combobox(edit_frame, textvariable=payment_method_var, values=payment_methods, state="readonly", width=18)
        payment_method_menu.grid(row=r, column=1, padx=5, pady=3, sticky="ew")
        
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
        
        # 配件信息
        parts_frame = ttk.LabelFrame(main_frame, text="配件信息")
        parts_frame.pack(fill="x", pady=5)
        parts_frame.columnconfigure(1, weight=1)
        parts_frame.columnconfigure(3, weight=1)
        
        r = 0
        tk.Label(parts_frame, text="更换配件:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        parts_list = self.load_parts()
        replaced_parts_var = tk.StringVar(value=replaced_parts)
        replaced_parts_combo = ttk.Combobox(parts_frame, textvariable=replaced_parts_var, values=parts_list, state="normal", width=18)
        replaced_parts_combo.grid(row=r, column=1, padx=5, pady=3, sticky="ew")
        
        tk.Label(parts_frame, text="配件来源:", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=2, padx=5, pady=3, sticky="w")
        sources_list = self.load_part_sources()
        part_source_var = tk.StringVar(value=part_source)
        part_source_combo = ttk.Combobox(parts_frame, textvariable=part_source_var, values=sources_list, state="normal", width=18)
        part_source_combo.grid(row=r, column=3, padx=5, pady=3, sticky="ew")
        r += 1
        
        tk.Label(parts_frame, text="配件成本(¥):", anchor="w", font=('Arial', 10, 'bold')).grid(row=r, column=0, padx=5, pady=3, sticky="w")
        part_cost_entry = tk.Entry(parts_frame)
        part_cost_entry.insert(0, str(part_cost))
        part_cost_entry.grid(row=r, column=1, padx=5, pady=3, sticky="ew")
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
                       part_cost_entry, replaced_parts_combo, part_source_combo, detail_win
                   )).grid(row=0, column=0, padx=5)

    def _save_all_job_info_from_window(self, job_id, edit_fault_desc_widget, edit_repair_details_widget, status_var, 
                                       final_price_entry, payment_method_var, payment_notes_entry, 
                                       cost_entry, other_cost_entry, replaced_parts_var, part_source_var,
                                       part_cost_entry, replaced_parts_combo, part_source_combo, window):
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
            
            # 如果配件不在列表中，添加到列表
            if replaced_parts:
                current_parts = self.load_parts()
                if replaced_parts not in current_parts:
                    current_parts.append(replaced_parts)
                    self.save_parts(current_parts)
                    replaced_parts_combo['values'] = current_parts
            
            # 如果配件来源不在列表中，添加到列表
            if part_source:
                current_sources = self.load_part_sources()
                if part_source not in current_sources:
                    current_sources.append(part_source)
                    self.save_part_sources(current_sources)
                    part_source_combo['values'] = current_sources
            
            update_query = '''
                UPDATE job_orders 
                SET fault_desc=?, repair_details=?, status=?, final_price=?, payment_method=?, 
                    payment_notes=?, cost=?, other_cost=?, replaced_parts=?, part_source=?, part_cost=?
                WHERE id=?
            '''
            if self.db.execute_query(update_query, (fault_desc, repair_details, status, final_price, 
                                                     payment_method, payment_notes, cost, 
                                                     other_cost, replaced_parts, part_source, part_cost, job_id)) is not None:
                messagebox.showinfo("成功", f"工单 #{job_id} 的所有信息已保存！")
                window.destroy()
                self.refresh_job_list()
            else:
                messagebox.showerror("失败", "保存工单信息失败。")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字（最终实收、内部成本、其他成本、配件成本）。")

    def get_client_names(self):
        """从数据库获取所有客户名称，用于 ComboBox 自动填充"""
        # 使用 DISTINCT 避免重复，并按字母顺序排序
        query = "SELECT DISTINCT name FROM clients WHERE name IS NOT NULL AND name != '' ORDER BY name ASC"
        names = self.db.fetch_all(query)
        # 返回一个包含名称字符串的列表
        return [name[0] for name in names]
    
    def load_fault_types(self):
        """从数据库加载故障类型列表"""
        try:
            results = self.db.fetch_all(
                'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
                ('fault_type',)
            )
            types = [row[0] for row in results] if results else []
            # 确保有默认类型
            default_types = ['不加电', '通电不显示', '数据恢复', '其他']
            if not types:
                for default_type in default_types:
                    self.db.execute_query(
                        'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('fault_type', default_type)
                    )
                return default_types
            # 确保默认类型都在列表中
            for default_type in default_types:
                if default_type not in types:
                    self.db.execute_query(
                        'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('fault_type', default_type)
                    )
                    types.append(default_type)
            return types
        except Exception as e:
            print(f"加载故障类型列表失败: {e}")
            return ['不加电', '通电不显示', '数据恢复', '其他']
    
    def save_fault_types(self, types):
        """保存故障类型列表到数据库"""
        try:
            # 先删除所有现有类型
            self.db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('fault_type',))
            # 插入新类型
            for fault_type in types:
                if fault_type.strip():
                    self.db.execute_query(
                        'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('fault_type', fault_type.strip())
                    )
        except Exception as e:
            print(f"保存故障类型列表失败: {e}")
    
    def load_parts(self):
        """从数据库加载配件列表"""
        try:
            results = self.db.fetch_all(
                'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
                ('part',)
            )
            return [row[0] for row in results] if results else []
        except Exception as e:
            print(f"加载配件列表失败: {e}")
            return []
    
    def save_parts(self, parts):
        """保存配件列表到数据库"""
        try:
            # 先删除所有现有配件
            self.db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('part',))
            # 插入新配件
            for part in parts:
                if part.strip():
                    self.db.execute_query(
                        'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('part', part.strip())
                    )
        except Exception as e:
            print(f"保存配件列表失败: {e}")
    
    def load_part_sources(self):
        """从数据库加载配件来源列表"""
        try:
            results = self.db.fetch_all(
                'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
                ('part_source',)
            )
            sources = [row[0] for row in results] if results else []
            # 确保有默认来源
            default_sources = ['自购', '客户提供', '其他']
            if not sources:
                for default_source in default_sources:
                    self.db.execute_query(
                        'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('part_source', default_source)
                    )
                return default_sources
            # 确保默认来源都在列表中
            for default_source in default_sources:
                if default_source not in sources:
                    self.db.execute_query(
                        'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('part_source', default_source)
                    )
                    sources.append(default_source)
            return sources
        except Exception as e:
            print(f"加载配件来源列表失败: {e}")
            return ['自购', '客户提供', '其他']
    
    def save_part_sources(self, sources):
        """保存配件来源列表到数据库"""
        try:
            # 先删除所有现有来源
            self.db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('part_source',))
            # 插入新来源
            for source in sources:
                if source.strip():
                    self.db.execute_query(
                        'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                        ('part_source', source.strip())
                    )
        except Exception as e:
            print(f"保存配件来源列表失败: {e}")

    def add_new_job_window(self):
        new_job_win = tk.Toplevel(self)
        new_job_win.title("新增工单")
        self._set_window_icon(new_job_win) # <-- 设置图标
        
        self.center_window_manual(new_job_win, 500, 500) 
        
        main_frame = ttk.Frame(new_job_win, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # 获取现有客户名称列表
        client_names = self.get_client_names()
        
        client_frame = ttk.LabelFrame(main_frame, text="客户信息")
        client_frame.pack(fill="x", pady=10)
        
        tk.Label(client_frame, text="姓名/公司:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.new_client_name = ttk.Combobox(client_frame, width=37, values=client_names)
        self.new_client_name.config(state='normal') 
        self.new_client_name.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(client_frame, text="联系电话:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.new_client_phone = tk.Entry(client_frame)
        self.new_client_phone.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        client_frame.columnconfigure(1, weight=1)

        device_frame = ttk.LabelFrame(main_frame, text="设备及故障信息")
        device_frame.pack(fill="x", pady=10)
        
        tk.Label(device_frame, text="型号/容量:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.new_device_info = tk.Entry(device_frame)
        self.new_device_info.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(device_frame, text="序列号:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.new_serial_number = tk.Entry(device_frame)
        self.new_serial_number.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(device_frame, text="初步报价(¥):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.new_initial_quote = tk.Entry(device_frame)
        self.new_initial_quote.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.new_initial_quote.insert(0, "0.00")
        
        tk.Label(device_frame, text="故障类型:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        types = self.load_fault_types()
        self.new_recovery_type = ttk.Combobox(device_frame, values=types, state="normal")
        self.new_recovery_type.set('其他')
        self.new_recovery_type.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(device_frame, text="故障描述:").grid(row=4, column=0, padx=5, pady=5, sticky="nw")
        self.new_fault_desc = tk.Text(device_frame, height=5, width=40)
        self.new_fault_desc.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        device_frame.columnconfigure(1, weight=1)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=20)
        
        ttk.Button(button_frame, text="保存工单", 
                   command=lambda: self.save_new_job(new_job_win)).pack(side="left", expand=True, padx=5)
        ttk.Button(button_frame, text="取消", command=new_job_win.destroy).pack(side="right", expand=True, padx=5)

    def save_new_job(self, window):
        """
        保存新的工单
        """
        client_name = self.new_client_name.get().strip()
        client_phone = self.new_client_phone.get().strip()
        serial_number = self.new_serial_number.get().strip() 
        
        device_info = self.new_device_info.get().strip()
        initial_quote = self.new_initial_quote.get().strip()
        fault_desc = self.new_fault_desc.get("1.0", tk.END).strip()
        
        # 获取故障类型，如果不在列表中则添加
        recovery_type = self.new_recovery_type.get().strip()
        if recovery_type:
            current_types = self.load_fault_types()
            if recovery_type not in current_types:
                current_types.append(recovery_type)
                self.save_fault_types(current_types)
                # 更新Combobox的值列表
                self.new_recovery_type['values'] = current_types
        
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
                # 如果电话匹配，更新姓名 (可能客户改名了)
                self.db.execute_query(
                    "UPDATE clients SET name = ? WHERE id = ?", (client_name, client_id)
                )
        
        # 2. 如果电话未匹配，尝试通过姓名查找现有客户 (解决 Combo Box 选中项)
        if client_id is None:
             client_data = self.db.fetch_one("SELECT id, phone FROM clients WHERE name = ?", (client_name,))
             if client_data:
                 client_id, existing_phone = client_data
                 # 如果姓名匹配，但输入了新的电话，则更新电话
                 if client_phone and client_phone != existing_phone:
                     self.db.execute_query(
                        "UPDATE clients SET phone = ? WHERE id = ?", (client_phone, client_id)
                    )
        
        # 3. 如果以上都没有匹配到，则创建新客户
        if client_id is None:
            client_id = self.db.execute_query(
                "INSERT INTO clients (name, phone) VALUES (?, ?)", (client_name, client_phone or '')
            )
            
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        job_id = self.db.execute_query(
            '''
            INSERT INTO job_orders 
            (client_id, serial_number, device_info, fault_desc, fault_type, status, initial_quote, final_price, 
             created_at, cost, other_cost, repair_details, payment_method, payment_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, '', '待定', '')
            ''',
            (client_id, serial_number or '', device_info, fault_desc, recovery_type or '其他', '待检测', quote, quote, 
             current_time)
        )
        
        if job_id:
            print(f"✅ 新工单 #{job_id} 已创建！初步报价 (¥{quote:.2f}) 已自动填充至最终实收。")
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
            # 筛选当天的工单
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
            # 如果有搜索关键词，添加WHERE条件
            # 搜索工单ID、客户姓名、电话、序列号、设备信息
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
            # 没有搜索关键词，显示所有工单
            query = '''
                SELECT 
                    j.id, c.name, c.phone, j.serial_number, j.device_info, j.fault_desc, j.status, j.initial_quote, j.created_at
                FROM job_orders j
                JOIN clients c ON j.client_id = c.id
                ORDER BY j.created_at DESC
            '''
            jobs = self.db.fetch_all(query)
        
        for job in jobs:
            # job的结构: (id, name, phone, serial_number, device_info, fault_desc, status, initial_quote, created_at)
            # status在索引6
            status = job[6] if len(job) > 6 else ''
            # 如果状态不是"完成"，使用红色标签
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
            # 设置默认列宽
            self.finance_tree.column(col, width=120) 
            
        # 调整列宽
        self.finance_tree.column('job_id', width=60, anchor='center')
        self.finance_tree.column('client_name', width=120)
        self.finance_tree.column('device_info', width=150)
        self.finance_tree.column('amount', width=100, anchor='e')
        self.finance_tree.column('description', width=300)
        self.finance_tree.column('date', width=100)
        
        self.finance_tree.pack(fill="both", expand=True)
        self.finance_tree.bind('<Double-1>', self.show_finance_job_detail)

        self.finance_tree.tag_configure('income', background='#E6F9E6')
        self.finance_tree.tag_configure('expense', background='#FFF0F0')
        # 新增：欠款标记为红色背景和红色文字
        self.finance_tree.tag_configure('debt', background='#FFCCCC', foreground='red') 
        
        self.refresh_finance_report()
        
    def set_finance_date_range(self, period):
        """
        设置财务统计的日期筛选范围（当月或当日）
        """
        now = datetime.now()
        
        if period == 'day':
            # 当日：起始日期和结束日期都是今天
            start_date = now.strftime('%Y-%m-%d')
            end_date = now.strftime('%Y-%m-%d')
        elif period == 'month':
            # 当月：起始日期是当月 1 号，结束日期是今天
            start_date = now.strftime('%Y-%m-01')
            end_date = now.strftime('%Y-%m-%d')
        else:
            return

        # 更新输入框
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, start_date)
        
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, end_date)
        
        # 自动触发筛选
        self.refresh_finance_report()
        
    def show_finance_job_detail(self, event):
        """
        处理财务统计列表的双击事件，弹出对应工单的详情窗口。
        """
        selected_item = self.finance_tree.focus()
        if not selected_item: 
            return
            
        # values 列表现在是：(job_id, client_name, device_info, amount, description, date)
        record_data = self.finance_tree.item(selected_item, 'values')
        
        job_id = record_data[0]
        
        if not job_id or not str(job_id).isdigit():
            messagebox.showinfo("提示", "该记录没有关联有效的工单 ID，无法查看详情。")
            return
            
        # 确保 job_id 是字符串（Treeview值）
        job_id_str = str(job_id)
        try:
            class MockItem:
                def __init__(self, job_id):
                    self.job_id = job_id
                def item(self, item_id, option):
                    if option == 'values':
                        # 返回 job_id 作为列表的第一个元素
                        return (self.job_id, ) + tuple([''] * 7) 

            # 模拟一个 Treeview 对象，用于事件处理
            class MockTreeview:
                def focus(self): return 'mock_item'
                def item(self, item_id, option): return MockItem(job_id_str).item(item_id, option)
                    
            # 构造一个模拟事件对象
            class MockEvent:
                def __init__(self, widget):
                    self.widget = widget
                    
            mock_tree = MockTreeview()
            mock_event = MockEvent(mock_tree)

            # 调用已有的 show_job_detail_window 方法
            self.show_job_detail_window(mock_event)
            
        except Exception as e:
            messagebox.showerror("错误", f"无法加载工单详情 (ID: {job_id_str})。错误: {e}")
            
    def show_debt_report(self):
        """显示所有状态为'完成'且付款方式为'欠款'的工单列表"""
        
        debt_win = tk.Toplevel(self)
        debt_win.title("欠款工单查询")
        self._set_window_icon(debt_win) # <-- 设置图标
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

        tk.Label(debt_win, text=f"总欠款金额合计: ¥ {total_debt:.2f}", 
                 font=('Arial', 14, 'bold'), fg='red', pady=10).pack()
        
        tk.Label(debt_win, text="提示: 欠款结清请在'工单管理'中修改该工单的付款方式。", fg='blue').pack()

        
    def add_manual_expense(self):
        expense_win = tk.Toplevel(self)
        expense_win.title("添加手动支出")
        self._set_window_icon(expense_win) # <-- 设置图标
        
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
        
        # 2. 准备工单信息缓存 (通过一次查询获取所有相关工单的客户名和设备信息)
        # 找出所有涉及的工单ID
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
                
        # 3. 插入正常的财务记录 (收入/手动支出)
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
                    # 更新描述以包含类型信息 (客户可能忘记工单是收入)
                    description = f'[收入] {description}' 
                elif job_id:
                    description = f'[收入] 工单 #{job_id} (信息缺失)'
                    
            elif record_type == 'Expense':
                display_amount = -amount
                # 对于手动支出，清空工单相关字段
                if job_id is None:
                    description = f'[支出] {description}'
                    display_job_id = ''
                # elif job_id: # 如果未来工单成本也记录在这里
                #     if job_id in job_info_cache:
                #         client_name, device_info = job_info_cache[job_id]
                #         description = f'[工单成本] {description}'

            self.finance_tree.insert(
                '', 
                'end', 
                values=(display_job_id, client_name, device_info, f'{display_amount:.2f}', description, date), 
                tags=(tag,)
            )

        # 4. 新增逻辑：显示欠款工单 (标记为红色)
        # 该查询需要获取 c.name 和 j.device_info
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
        
        # 4.5. 显示所有已完成且已付款的工单（不包括欠款，因为欠款已经在上面显示了）
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
            # 构建描述信息
            payment_info = f'付款方式: {payment_method}'
            if payment_notes:
                payment_info += f' (备注: {payment_notes})'
            description = f'[工单收入] {payment_info}'
            
            self.finance_tree.insert(
                '', 
                'end', 
                values=(str(job_id), client_name, device_info, f'{amount:.2f}', description, date),
                tags=('income',) # 应用收入标签
            )
        
        # 5. 统计总览计算
        # 5.1 从财务记录表中获取收入
        total_income_res = self.db.fetch_one(
            f"SELECT SUM(amount) FROM financial_records {date_filter_clause_fr} AND record_type='Income'",
            date_params
        )
        income_from_records = total_income_res[0] or 0.0
        
        # 5.2 从已完成工单中获取收入（不包括已在财务记录中的工单）
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
        
        # 总收入 = 财务记录中的收入 + 已完成工单的收入
        income = income_from_records + income_from_jobs

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
        
        expense = manual_expense + job_cost
        profit = income - expense
        
        self.income_label.config(text=f"总收入 ({start_date_str} 至 {end_date_str}): ¥ {income:.2f}")
        self.expense_label.config(text=f"总支出 : ¥ {expense:.2f}") 
        self.profit_label.config(text=f"净利润: ¥ {profit:.2f}", fg='green' if profit >= 0 else 'red')
        
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
        if not selected_item: return
            
        client_data = self.client_tree.item(selected_item, 'values')
        client_id, name, phone = client_data
        self.current_client_id = client_id
        
        self.edit_client_id.config(text=str(client_id))

        self.edit_client_name.delete(0, tk.END); self.edit_client_name.insert(0, name)
        self.edit_client_phone.delete(0, tk.END); self.edit_client_phone.insert(0, phone)

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
        self._set_window_icon(job_win) # <-- 设置图标
        
        self.center_window_manual(job_win, 500, 300)
        
        job_tree = ttk.Treeview(job_win, columns=('id', 'device', 'status', 'date'), show='headings')
        job_tree.heading('id', text='工单ID'); job_tree.column('id', width=60)
        job_tree.heading('device', text='设备信息'); job_tree.column('device', width=180)
        job_tree.heading('status', text='状态'); job_tree.column('status', width=80)
        job_tree.heading('date', text='日期'); job_tree.column('date', width=120)
        
        for job in jobs:
            job_tree.insert('', 'end', values=job)
            
        job_tree.pack(fill="both", expand=True, padx=10, pady=10)


if __name__ == '__main__':
    # 在 __main__ 块中添加一个顶级 try-except 来捕获未处理的错误
    try:
        app = RecoveryManagerApp()
        app.mainloop()
    except Exception as e:
        # 当程序启动失败或遇到其他致命错误时显示错误信息
        if 'tk.TclError' in str(e) and 'icon' in str(e):
             # 针对图标的特定错误
             try:
                 root = tk.Tk()
                 root.withdraw()
                 messagebox.showerror("系统致命错误 - 图标", 
                                      f"应用程序启动失败，可能是由于图标文件 'icon.ico' 缺失/格式错误：{e}")
                 root.destroy()
             except:
                 pass
        else:
             try:
                 root = tk.Tk()
                 root.withdraw()
                 messagebox.showerror("系统致命错误", f"应用程序启动失败: {e}")
                 root.destroy()
             except:
                 pass