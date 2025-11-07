# 打包说明

## ✅ 打包成功

EXE 文件已成功生成在 `dist` 目录下：
- **文件名**: `recovery_manager_app.exe`
- **大小**: 约 12 MB
- **位置**: `D:\recovery_manager_app\dist\recovery_manager_app.exe`

## 📦 打包信息

- **打包工具**: PyInstaller 6.16.0
- **Python 版本**: 3.11.6
- **平台**: Windows 10/11
- **图标**: 已包含 `icon.ico`
- **控制台**: 无控制台窗口（GUI 应用）

## 🚀 使用方法

### 方法 1: 使用 .spec 文件（推荐）

```powershell
# 激活虚拟环境
.\venv\Scripts\activate

# 使用 spec 文件打包
pyinstaller recovery_manager_app.spec --clean
```

### 方法 2: 直接使用 PyInstaller 命令

```powershell
# 激活虚拟环境
.\venv\Scripts\activate

# 打包命令
pyinstaller --name="简易维修管理系统" ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="icon.ico;." ^
    recovery_manager_app.py
```

## 📋 打包配置说明

当前 `.spec` 文件配置：
- ✅ 单文件模式（onefile）
- ✅ 无控制台窗口（windowed）
- ✅ 包含图标文件
- ✅ 包含必要的隐藏导入

## ⚠️ 注意事项

### 1. 首次运行
- EXE 文件首次运行时会在同目录下创建：
  - `recovery_manager.db` - 数据库文件
  - `settings.txt` - 配置文件
  - `app.log` - 日志文件

### 2. 文件分发
分发 EXE 文件时，建议：
- 将 EXE 文件放在单独的文件夹中
- 首次运行后，数据库和配置文件会在 EXE 同目录创建
- 可以预先准备 `icon.ico` 文件（可选，已嵌入）

### 3. 依赖项
EXE 文件已包含所有依赖，无需安装 Python 环境即可运行。

### 4. 杀毒软件
某些杀毒软件可能会误报 PyInstaller 打包的程序，这是正常现象。可以：
- 添加到杀毒软件白名单
- 使用代码签名证书（需要购买）

## 🔧 打包优化建议

### 减小文件大小
如果需要减小 EXE 文件大小，可以：

1. **排除不需要的模块**（在 .spec 文件中）：
```python
excludes=[
    'matplotlib',
    'numpy',
    'pandas',
    # 添加其他不需要的模块
]
```

2. **使用 UPX 压缩**（已启用）：
```python
upx=True,  # 在 .spec 文件中
```

### 添加版本信息
可以在 .spec 文件中添加版本信息：

```python
exe = EXE(
    # ... 其他配置 ...
    version='version_info.txt',  # 版本信息文件
)
```

创建 `version_info.txt` 文件：
```
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    # ... 其他版本信息
  ),
  # ...
)
```

## 🐛 常见问题

### 问题 1: 打包后无法运行
**解决方案**:
- 检查是否有错误日志
- 尝试在命令行运行查看错误信息
- 确保所有依赖都已正确安装

### 问题 2: 图标不显示
**解决方案**:
- 确保 `icon.ico` 文件存在
- 检查图标文件格式是否正确
- 在 .spec 文件中确认图标路径

### 问题 3: 缺少模块错误
**解决方案**:
- 在 `hiddenimports` 中添加缺失的模块
- 重新打包

### 问题 4: 文件过大
**解决方案**:
- 使用 `--exclude-module` 排除不需要的模块
- 使用 UPX 压缩（已启用）
- 考虑使用 `--onedir` 模式替代 `--onefile`

## 📝 打包命令参考

### 完整打包命令（带所有选项）
```powershell
pyinstaller recovery_manager_app.spec ^
    --clean ^
    --noconfirm ^
    --log-level=INFO
```

### 参数说明
- `--clean`: 清理临时文件
- `--noconfirm`: 覆盖输出文件时不询问
- `--log-level=INFO`: 设置日志级别

## 🎯 下一步

1. ✅ 测试 EXE 文件是否正常运行
2. ✅ 检查所有功能是否正常
3. ✅ 准备分发文件
4. ✅ 考虑添加版本号和更新日志

## 📞 技术支持

如有问题，请查看：
- `app.log` 日志文件
- PyInstaller 文档：https://pyinstaller.org/

