@echo off
chcp 65001 >nul
title FramePilot Overnight QA (Local - Offline)
cd /d D:\VideoAI\TroLyFileQuay

echo ============================================================
echo   FRAMEPILOT - CONG CU TEST XUYEN DEM (100%% LOCAL / OFFLINE)
echo ============================================================
echo.
echo Truoc khi chay, nho:
echo   1. Mo DaVinci Resolve va mo 1 project test (vd: FP_TEST_01)
echo   2. Chuyen Unikey sang che do E (Tieng Anh)
echo.
echo Chon che do chay:
echo   [1] Kiem chung nhanh 15 giay (Chi doc, kiem tra ket noi CDP)
echo   [2] Chay test xuyen dem 6 tieng - CHI DOC DaVinci (An toan 100%%)
echo   [3] Chay test xuyen dem 6 tieng - CO GHI DaVinci (Bat buoc project ten FP_TEST_*)
echo   [4] Chay nhanh 1 vong day du (khoang 2-3 phut, chi doc)
echo.
set /p choice=Nhap so (1-4) roi bam Enter: 

set PY=C:\VideoAI_venv\Scripts\python.exe

if "%choice%"=="1" (
    "%PY%" -m tools.overnight_qa.runner --check-only
) else if "%choice%"=="2" (
    "%PY%" -m tools.overnight_qa.runner --hours 6 --mode readonly --suites smoke_e2e,ai_gpu,chaos_race
) else if "%choice%"=="3" (
    "%PY%" -m tools.overnight_qa.runner --hours 6 --mode sandbox_write --suites smoke_e2e,ai_gpu,chaos_race,sandbox_write
) else if "%choice%"=="4" (
    "%PY%" -m tools.overnight_qa.runner --cycles 1 --mode readonly --suites smoke_e2e,ai_gpu,chaos_race
) else (
    echo Lua chon khong hop le.
)

echo.
pause
