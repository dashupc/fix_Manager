"""
配置数据加载和保存辅助函数
"""
import logging

logger = logging.getLogger(__name__)


def load_fault_types(db):
    """从数据库加载故障类型列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('fault_type',)
        )
        types = [row[0] for row in results] if results else []
        default_types = ['不加电', '通电不显示', '数据恢复', '其他']
        if not types:
            for default_type in default_types:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('fault_type', default_type)
                )
            return default_types
        for default_type in default_types:
            if default_type not in types:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('fault_type', default_type)
                )
                types.append(default_type)
        return types
    except Exception as e:
        logger.error(f"加载故障类型列表失败: {e}")
        return ['不加电', '通电不显示', '数据恢复', '其他']


def save_fault_types(db, types):
    """保存故障类型列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('fault_type',))
        for fault_type in types:
            if fault_type.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('fault_type', fault_type.strip())
                )
    except Exception as e:
        logger.error(f"保存故障类型列表失败: {e}")


def load_parts(db):
    """从数据库加载配件列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('part',)
        )
        return [row[0] for row in results] if results else []
    except Exception as e:
        logger.error(f"加载配件列表失败: {e}")
        return []


def save_parts(db, parts):
    """保存配件列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('part',))
        for part in parts:
            if part.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part', part.strip())
                )
    except Exception as e:
        logger.error(f"保存配件列表失败: {e}")


def load_part_sources(db):
    """从数据库加载配件来源列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('part_source',)
        )
        sources = [row[0] for row in results] if results else []
        default_sources = ['自购', '客户提供', '其他']
        if not sources:
            for default_source in default_sources:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part_source', default_source)
                )
            return default_sources
        for default_source in default_sources:
            if default_source not in sources:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part_source', default_source)
                )
                sources.append(default_source)
        return sources
    except Exception as e:
        logger.error(f"加载配件来源列表失败: {e}")
        return ['自购', '客户提供', '其他']


def save_part_sources(db, sources):
    """保存配件来源列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('part_source',))
        for source in sources:
            if source.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('part_source', source.strip())
                )
    except Exception as e:
        logger.error(f"保存配件来源列表失败: {e}")


def load_units(db):
    """从数据库加载单位列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('unit',)
        )
        return [row[0] for row in results] if results else []
    except Exception as e:
        logger.error(f"加载单位列表失败: {e}")
        return []


def load_retail_units(db):
    """加载零售商品单位列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('retail_unit',)
        )
        units = [row[0] for row in results] if results else []
        default_units = ['个', '件', '台', '套', '块', '张', '支']
        if not units:
            units = default_units.copy()
        for default in default_units:
            if default not in units:
                units.append(default)
        for unit in units:
            db.execute_query(
                'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                ('retail_unit', unit)
            )
        return units
    except Exception as e:
        logger.error(f"加载零售单位列表失败: {e}")
        return ['个', '件', '台', '套', '块']


def save_units(db, units):
    """保存单位列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('unit',))
        for unit in units:
            if unit.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('unit', unit.strip())
                )
    except Exception as e:
        logger.error(f"保存单位列表失败: {e}")


def load_departments(db):
    """从数据库加载部门列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('department',)
        )
        return [row[0] for row in results] if results else []
    except Exception as e:
        logger.error(f"加载部门列表失败: {e}")
        return []


def save_departments(db, departments):
    """保存部门列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('department',))
        for department in departments:
            if department.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('department', department.strip())
                )
    except Exception as e:
        logger.error(f"保存部门列表失败: {e}")


def load_device_categories(db):
    """从数据库加载设备类别列表"""
    try:
        results = db.fetch_all(
            'SELECT config_value FROM config_data WHERE config_type = ? ORDER BY id',
            ('device_category',)
        )
        categories = [row[0] for row in results] if results else []
        default_categories = ['笔记本', '台式机', '服务器', '存储设备', '其他']
        if not categories:
            for default_category in default_categories:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('device_category', default_category)
                )
            return default_categories
        for default_category in default_categories:
            if default_category not in categories:
                db.execute_query(
                    'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('device_category', default_category)
                )
                categories.append(default_category)
        return categories
    except Exception as e:
        logger.error(f"加载设备类别列表失败: {e}")
        return ['笔记本', '台式机', '服务器', '存储设备', '其他']


def save_device_categories(db, categories):
    """保存设备类别列表到数据库"""
    try:
        db.execute_query('DELETE FROM config_data WHERE config_type = ?', ('device_category',))
        for category in categories:
            if category.strip():
                db.execute_query(
                    'INSERT INTO config_data (config_type, config_value) VALUES (?, ?)',
                    ('device_category', category.strip())
                )
    except Exception as e:
        logger.error(f"保存设备类别列表失败: {e}")


def ensure_config_value(db, config_type, value):
    """确保某个 config_data 项存在"""
    if not value:
        return
    try:
        db.execute_query(
            'INSERT OR IGNORE INTO config_data (config_type, config_value) VALUES (?, ?)',
            (config_type, value.strip())
        )
    except Exception as e:
        logger.error(f"写入配置 {config_type}:{value} 失败: {e}")


def get_client_names(db):
    """从数据库获取所有客户名称，用于 ComboBox 自动填充"""
    query = "SELECT DISTINCT name FROM clients WHERE name IS NOT NULL AND name != '' ORDER BY name ASC"
    names = db.fetch_all(query)
    return [name[0] for name in names]

