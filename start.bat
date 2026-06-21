@echo off
echo ========================================
echo    渠道线索判重服务启动脚本
echo ========================================
echo.

echo [1/3] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

echo.
echo [2/3] 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/3] 初始化种子数据...
python scripts/init_seed_data.py

echo.
echo ========================================
echo    服务启动中...
echo ========================================
echo.
echo  API 文档地址: http://127.0.0.1:8000/docs
echo  健康检查地址: http://127.0.0.1:8000/health
echo.
echo  按 Ctrl+C 停止服务
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
