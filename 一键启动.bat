@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0" || exit /b 1
echo ==========================================
echo 正在启动跨库检索式智能转译系统...
echo ==========================================
echo.
echo 提示：如果启动失败，请确保已安装依赖：
echo python -m pip install -r requirements.txt
echo.

python -m streamlit run app.py

popd
pause
