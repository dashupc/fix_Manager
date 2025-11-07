@echo off
chcp 65001 >nul
echo ========================================
echo 简易维修管理系统 - EXE打包脚本
echo ========================================
echo.

REM 检查是否在虚拟环境中
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境，请先创建虚拟环境！
    echo 创建命令: python -m venv venv
    pause
    exit /b 1
)

echo [1/4] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [2/4] 检查并安装依赖...
pip install -r requirements.txt
pip install pyinstaller

echo [3/4] 清理旧的构建文件...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo [4/4] 开始打包...
echo 这可能需要几分钟，请耐心等待...
echo.

pyinstaller recovery_manager_app.spec

if %errorlevel% neq 0 (
    echo.
    echo 使用spec文件打包失败，尝试使用命令行参数打包...
    pyinstaller --name="简易维修管理系统" ^
        --onefile ^
        --windowed ^
        --icon=icon.ico ^
        --add-data="icon.ico;." ^
        --hidden-import=pystray ^
        --hidden-import=PIL ^
        --hidden-import=PIL.Image ^
        --hidden-import=PIL.ImageDraw ^
        --hidden-import=dateutil ^
        --hidden-import=dateutil.relativedelta ^
        --collect-all=pystray ^
        --collect-all=PIL ^
        --noconsole ^
        --clean ^
        recovery_manager_app.py
)

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo 打包成功！
    echo ========================================
    echo 可执行文件位置: dist\简易维修管理系统.exe
    echo.
    echo 注意：
    echo 1. 首次运行exe时，会在exe同目录下创建 recovery_manager.db 数据库文件
    echo 2. 请将exe文件与icon.ico放在同一目录（已自动包含在exe中）
    echo 3. 如果运行时缺少文件，请检查是否所有资源文件都已包含
    echo.
) else (
    echo.
    echo ========================================
    echo 打包失败！请检查错误信息
    echo ========================================
)

pause

