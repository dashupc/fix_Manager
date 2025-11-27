import logging
import sqlite3


logger = logging.getLogger(__name__)


class DatabaseManager:
    """管理 SQLite 数据库连接和 CURD 操作"""

    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT
            )
            '''
        )

        self.cursor.execute(
            '''
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
            '''
        )

        self._add_missing_column('job_orders', 'other_cost', 'REAL DEFAULT 0.0')
        self._add_missing_column('job_orders', 'serial_number', 'TEXT')
        self._add_missing_column('job_orders', 'repair_details', 'TEXT')
        self._add_missing_column('job_orders', 'payment_method', "TEXT DEFAULT '待定'")
        self._add_missing_column('job_orders', 'payment_notes', "TEXT")
        self._add_missing_column('job_orders', 'replaced_parts', "TEXT")
        self._add_missing_column('job_orders', 'part_source', "TEXT")
        self._add_missing_column('job_orders', 'part_cost', "REAL DEFAULT 0.0")
        self._add_missing_column('job_orders', 'fault_type', "TEXT")
        self._add_missing_column('job_orders', 'device_category', "TEXT")
        self._add_missing_column('job_orders', 'invoice_amount', "REAL DEFAULT 0.0")
        self._add_missing_column('job_orders', 'invoice_date', "TEXT")
        self._add_missing_column('job_orders', 'is_urgent', "INTEGER DEFAULT 0")

        self._add_missing_column('clients', 'unit', 'TEXT')
        self._add_missing_column('clients', 'department', 'TEXT')

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS financial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                record_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                date TEXT,
                FOREIGN KEY (job_id) REFERENCES job_orders(id)
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS config_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_type TEXT NOT NULL,
                config_value TEXT NOT NULL,
                UNIQUE(config_type, config_value)
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS retail_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_unit TEXT,
                total_amount REAL DEFAULT 0.0,
                total_cost REAL DEFAULT 0.0,
                profit REAL DEFAULT 0.0,
                created_at TEXT,
                notes TEXT,
                payment_method TEXT DEFAULT '待定'
            )
            '''
        )

        self._add_missing_column('retail_orders', 'customer_unit', 'TEXT')
        self._add_missing_column('retail_orders', 'total_amount', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_orders', 'total_cost', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_orders', 'profit', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_orders', 'created_at', 'TEXT')
        self._add_missing_column('retail_orders', 'notes', 'TEXT')
        self._add_missing_column('retail_orders', 'payment_method', "TEXT DEFAULT '待定'")

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS retail_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_name TEXT NOT NULL,
                unit TEXT,
                quantity REAL DEFAULT 1.0,
                unit_price REAL DEFAULT 0.0,
                amount REAL DEFAULT 0.0,
                source TEXT,
                cost REAL DEFAULT 0.0,
                notes TEXT,
                FOREIGN KEY (order_id) REFERENCES retail_orders(id)
            )
            '''
        )

        self._add_missing_column('retail_order_items', 'order_id', 'INTEGER')
        self._add_missing_column('retail_order_items', 'product_name', 'TEXT')
        self._add_missing_column('retail_order_items', 'unit', 'TEXT')
        self._add_missing_column('retail_order_items', 'quantity', 'REAL DEFAULT 1.0')
        self._add_missing_column('retail_order_items', 'unit_price', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_order_items', 'amount', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_order_items', 'source', 'TEXT')
        self._add_missing_column('retail_order_items', 'cost', 'REAL DEFAULT 0.0')
        self._add_missing_column('retail_order_items', 'notes', 'TEXT')

        self._init_default_config()
        self.conn.commit()

    def _init_default_config(self):
        default_fault_types = ['不加电', '通电不显示', '数据恢复', '其他']
        for fault_type in default_fault_types:
            try:
                self.cursor.execute(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('fault_type', fault_type)
                )
            except Exception:
                pass

        default_sources = ['自购', '客户提供', '其他']
        for source in default_sources:
            try:
                self.cursor.execute(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part_source', source)
                )
            except Exception:
                pass

        self.conn.commit()

    def _add_missing_column(self, table_name, column_name, column_type):
        try:
            self.cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
        except sqlite3.OperationalError:
            try:
                self.cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
                self.conn.commit()
            except Exception:
                pass

    def has_column(self, table_name, column_name):
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = self.cursor.fetchall()
            return any(col[1] == column_name for col in columns)
        except sqlite3.Error:
            return False

    def execute_query(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as err:
            logger.error("数据库执行错误: %s, 查询: %s", err, query[:100])
            return None

    def fetch_all(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as err:
            logger.error("数据库查询错误 (fetch_all): %s, 查询: %s", err, query[:100])
            return []

    def fetch_one(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except sqlite3.Error as err:
            logger.error("数据库查询错误 (fetch_one): %s, 查询: %s", err, query[:100])
            return None

