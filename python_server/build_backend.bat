@echo off
setlocal
echo [nexus-build] Activating venv...
call venv\Scripts\activate.bat

echo [nexus-build] Running PyInstaller...
pyinstaller nexus_backend.spec --clean --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo [nexus-build] BUILD FAILED. Exit code: %ERRORLEVEL%
    exit /b 1
)

echo [nexus-build] Build succeeded.
echo.
echo [nexus-build] Verifying critical files in output...
echo.

echo [nexus-build] Copying missing data files...
copy venv\Lib\site-packages\xgboost\VERSION dist\nexus_backend\_internal\xgboost\
copy venv\Lib\site-packages\prophet\__version__.py dist\nexus_backend\_internal\prophet\
echo [nexus-build] Done copying.
echo.
echo -- XGBoost DLL:
dir dist\nexus_backend\_internal\xgboost\lib\xgboost.dll

echo -- Prophet model:
dir dist\nexus_backend\_internal\prophet\stan_model\prophet_model.bin

echo -- SentenceTransformer model:
dir dist\nexus_backend\_internal\sentence_transformers_models\all-MiniLM-L6-v2\

echo.
echo [nexus-build] All checks done.
endlocal
