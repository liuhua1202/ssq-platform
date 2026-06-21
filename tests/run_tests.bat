@echo off
chcp 65001 >nul
echo ========================================
echo 双色球预测平台 - 单元测试
echo ========================================
echo.

python tests\test_core.py
set TEST_RESULT=%ERRORLEVEL%

echo.
echo ========================================
if %TEST_RESULT% EQU 0 (
    echo ✓ 所有测试通过！
) else (
    echo ✗ 部分测试失败，请查看上方输出
)
echo ========================================

pause
