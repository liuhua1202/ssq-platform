@echo off
chcp 65001 >nul
echo ==================================================
echo  双色球预测平台
echo ==================================================
echo.
echo  [使用说明]
echo   - 本脚本用于开发环境快速启动 (python app.py)
echo   - 生产环境部署请使用 gunicorn:
echo       gunicorn -w 2 -b 0.0.0.0:5000 app:app
echo   - 生产部署前必须设置以下环境变量:
echo       set SECRET_KEY=...   (必填, Flask session 加密密钥)
echo       set API_TOKEN=...    (必填, 写操作鉴权 token)
echo       set FLASK_DEBUG=False
echo       set LIMITER_STORAGE_URI=redis://...   (多 worker 必须)
echo.
echo  [生成密钥]
echo   python -c "import secrets; print(secrets.token_hex(32))"
echo.
echo  [更多]
echo   完整部署指南见 README.md "生产部署" 章节.
echo ==================================================
echo.

REM 检查 SECRET_KEY 是否设置
if "%SECRET_KEY%"=="" (
    echo [WARNING] SECRET_KEY 未设置, DEBUG 模式将自动生成临时密钥.
    echo           生产部署前必须显式设置 SECRET_KEY.
    echo.
)

python app.py
pause
