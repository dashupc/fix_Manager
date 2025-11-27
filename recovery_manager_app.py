"""
简易维修管理系统 - 主程序入口

模块化结构:
- modules/database.py: 数据库管理
- modules/config_helpers.py: 配置数据加载/保存
- modules/ui_helpers.py: UI 辅助函数
- modules/ui/job_tab.py: 工单管理标签页
- modules/ui/retail_tab.py: 零售开单标签页
- modules/ui/finance_tab.py: 财务统计标签页
- modules/ui/client_tab.py: 客户管理标签页
"""
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
from shutil import copyfile
import smtplib
import ssl
import sys
import threading
import time as time_module
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from dateutil.relativedelta import relativedelta
import pystray

from modules.database import DatabaseManager
from modules.ui_helpers import make_treeview_sortable
from modules.ui import JobTabMixin, RetailTabMixin, FinanceTabMixin, ClientTabMixin

# 配置日志系统
LOG_FILE = 'app.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 导入 PIL（用于系统托盘图标）
try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow 未安装，系统托盘图标功能将不可用")


DATABASE_NAME = 'recovery_manager.db'
SETTINGS_FILE = 'settings.txt'


class RecoveryManagerApp(tk.Tk, JobTabMixin, RetailTabMixin, FinanceTabMixin, ClientTabMixin):
    """主应用程序类，通过 Mixin 组合各个标签页的功能"""

    def __init__(self):
        super().__init__()
        self.title("简易维修管理系统")

        self.APP_WIDTH = 1100
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

        self.menubar.add_command(label="关于", command=self.show_about)

        top_action_frame = ttk.Frame(self)
        top_action_frame.pack(fill="x", padx=10, pady=(5, 0))
        ttk.Button(top_action_frame, text="隐藏到托盘", command=self.minimize_to_tray).pack(side="right", padx=5)
        ttk.Button(top_action_frame, text="退出", command=self.quit_app).pack(side="right")

        # 配置标签页样式：加大加粗字号
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'))

        # 使用 ttk notebook (标签页)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        self.job_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.job_tab, text='工单管理')
        self.setup_job_tab()

        self.retail_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.retail_tab, text='零售开单')
        self.setup_retail_tab()

        self.finance_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.finance_tab, text='财务统计')
        self.setup_finance_tab()

        self.clients_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.clients_tab, text='客户管理')
        self.setup_clients_tab()

        self.schedule_daily_backup()

        self.bind_activity_events()
        self.start_idle_timer()
        self.setup_tray_icon()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _set_window_icon(self, window):
        """设置窗口图标，统一使用 icon.ico。使用 PyInstaller 兼容的路径检测。"""
        icon_name = 'icon.ico'

        def get_resource_path(relative_path):
            """获取资源文件的绝对路径，优先使用 PyInstaller 运行时路径"""
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            full_path = os.path.join(base_path, relative_path)
            return os.path.abspath(full_path)

        full_ico_path = get_resource_path(icon_name)

        if os.path.exists(full_ico_path):
            try:
                if isinstance(window, tk.Toplevel):
                    window.wm_iconbitmap(bitmap=full_ico_path)
                else:
                    icon_path_str = full_ico_path.replace('\\', '/')
                    try:
                        window.iconbitmap(icon_path_str)
                    except:
                        window.iconbitmap(full_ico_path)

                    try:
                        window.wm_iconbitmap(bitmap=icon_path_str)
                    except:
                        window.wm_iconbitmap(bitmap=full_ico_path)
            except Exception as e:
                logger.warning(f"图标设置失败: {e}, 路径: {full_ico_path}")
        else:
            logger.warning(f"图标文件不存在: {full_ico_path}")

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
        if not PIL_AVAILABLE:
            logger.warning("PIL 不可用，无法创建系统托盘图标")
            return None

        try:
            icon_path = self._get_icon_path()
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                return image
        except Exception as e:
            logger.warning(f"加载图标文件失败: {e}")

        try:
            image = Image.new('RGB', (64, 64), color='white')
            draw = ImageDraw.Draw(image)
            draw.rectangle([16, 16, 48, 48], fill='blue')
            return image
        except Exception as e:
            logger.error(f"创建默认图标失败: {e}")
            return None

    def _get_icon_path(self):
        """获取图标路径"""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'icon.ico')

    def setup_tray_icon(self):
        """设置系统托盘图标"""
        if not PIL_AVAILABLE:
            logger.warning("系统托盘功能不可用（PIL 未安装）")
            return

        try:
            image = self.create_tray_image()
            if image is None:
                logger.warning("无法创建托盘图标，系统托盘功能将被禁用")
                return

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
            logger.error(f"系统托盘设置失败: {e}")

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
        self.idle_timer = self.after(600000, self.check_idle)

    def check_idle(self):
        """检查是否空闲超过10分钟"""
        idle_time = time_module.time() - self.last_activity_time
        if idle_time >= 600 and not self.is_minimized_to_tray:
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
                self.db.conn.close()
                copyfile(DATABASE_NAME, backup_path)
                self.db = DatabaseManager(DATABASE_NAME)

                messagebox.showinfo("备份成功", f"数据库已成功备份到:\n{backup_path}")
            except Exception as e:
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
        self._set_window_icon(settings_win)
        self.center_window_manual(settings_win, 450, 500)

        main_frame = ttk.Frame(settings_win, padding="15")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="⚠️ 重要提示：QQ 邮箱需使用**授权码**作为密码。",
                  foreground="red", wraplength=400, font=('Arial', 10, 'bold')).pack(fill="x", pady=5)
        ttk.Label(main_frame, text="请在QQ邮箱设置-账户-开启SMTP服务中获取授权码。",
                  foreground="darkorange", wraplength=400).pack(fill="x", pady=5)

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

        recipient_frame = ttk.LabelFrame(main_frame, text="接收邮箱")
        recipient_frame.pack(fill="x", pady=10)

        tk.Label(recipient_frame, text="接收邮箱地址:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.recipient_email_entry = tk.Entry(recipient_frame, width=30)
        self.recipient_email_entry.insert(0, self.settings['recipient_email'])
        self.recipient_email_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

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

        try:
            self.db.conn.commit()
            self.db.conn.close()
            copyfile(DATABASE_NAME, test_file)

        except Exception as e:
            try:
                self.db = DatabaseManager(DATABASE_NAME)
            except:
                pass
            messagebox.showerror("测试失败", f"创建测试备份文件失败，请关闭所有数据库引用并重试: {e}")
            return

        try:
            self.db = DatabaseManager(DATABASE_NAME)
        except Exception as e:
            messagebox.showerror("测试失败", f"重新连接数据库失败: {e}")
            return

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

        logger.info(f"定时备份已安排，下一次运行时间: {next_run_time_str}")

    def perform_daily_backup(self):
        """执行每日备份任务"""

        try:
            self.db.conn.commit()
            self.db.conn.close()
        except Exception as e:
            logger.warning(f"【定时备份警告】尝试关闭主连接失败: {e}")

        self.after(0, lambda: self.status_bar.config(text="🔄 正在执行自动备份..."))

        backup_filename = f"Recovery_Manager_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        success = False

        try:
            copyfile(DATABASE_NAME, backup_filename)

            try:
                self.send_email_with_attachment(
                    self.settings['sender_email'],
                    self.settings['sender_password'],
                    self.settings['recipient_email'],
                    backup_filename
                )
                logger.info(f"【定时备份成功】备份文件 {backup_filename} 已成功发送到邮箱。")
                success = True

            except Exception as e:
                error_msg = f"邮件发送错误: {e}"
                if 'SMTPAuthenticationError' in str(e):
                    error_msg = "授权码错误或SMTP未开启"
                elif 'SMTPConnectError' in str(e):
                    error_msg = "SMTP连接失败"

                logger.error(f"【定时备份失败】邮件发送错误: {e}")
                self.after(0, lambda: self.status_bar.config(text=f"❌ 自动备份失败 ({error_msg})"))

        except Exception as e:
            logger.error(f"【定时备份失败】创建本地备份文件失败: {e}")
            self.after(0, lambda: self.status_bar.config(text=f"❌ 自动备份失败 (本地文件创建错误: {e})"))

        finally:
            if success:
                self.after(0, lambda: self.status_bar.config(text=f"✅ 备份成功！文件已发送至 {self.settings['recipient_email']}。"))

            if os.path.exists(backup_filename):
                try:
                    os.remove(backup_filename)
                except Exception as e:
                    logger.warning(f"【定时备份警告】清理临时文件失败: {e}")

            self.after(0, lambda: setattr(self, 'db', DatabaseManager(DATABASE_NAME)))
            self.after(0, self.schedule_daily_backup)


if __name__ == '__main__':
    try:
        app = RecoveryManagerApp()
        app.mainloop()
    except Exception as e:
        if 'tk.TclError' in str(e) and 'icon' in str(e):
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
