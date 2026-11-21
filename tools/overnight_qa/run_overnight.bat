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
echo   2. Dong cua so FramePilot.exe cu (neu dang mo)
echo   3. Chuyen Unikey sang che do E (Tieng Anh)
echo.
echo Chon che do chay:
echo   [1] Kiem chung nhanh 15 giay (Chi doc, kiem tra ket noi CDP)
echo   [2] Chay test xuyen dem 6 tieng - 1 project - CHI DOC (An toan 100%%)
echo   [3] Chay test xuyen dem 6 tieng - 1 project - CO GHI (Bat buoc ten FP_TEST_*)
echo   [4] Chay nhanh 1 vong day du (~2-4 phut, chi doc)
echo   [5] Chay xuyen dem 6 tieng - XOAY VONG 2 PROJECT (co ho tro nguon 4K chua proxy)
echo.
set /p choice=Nhap so (1-5) roi bam Enter: 

set PY=C:\VideoAI_venv\Scripts\python.exe

if "%choice%"=="1" (
    "%PY%" -m tools.overnight_qa.runner --check-only
) else if "%choice%"=="2" (
    "%PY%" -m tools.overnight_qa.runner --hours 6 --mode readonly --suites smoke_e2e,ai_gpu,chaos_race
) else if "%choice%"=="3" (
    "%PY%" -m tools.overnight_qa.runner --hours 6 --mode sandbox_write --suites smoke_e2e,ai_gpu,chaos_race,sandbox_write
) else if "%choice%"=="4" (
    "%PY%" -m tools.overnight_qa.runner --cycles 1 --mode readonly --suites smoke_e2e,ai_gpu,chaos_race
) else if "%choice%"=="5" (
    echo.
    set /p p1=Nhap ten Project test 1 (vd FP_TEST_01): 
    set /p p2=Nhap ten Project test 2 (vd FP_TEST_3CAM): 
    echo Chon quyen voi DaVinci: [R] Chi doc (khuyen dung) hoac [W] Co ghi (ca 2 ten phai bat dau bang FP_TEST_)
    set /p rw=Nhap R hoac W roi bam Enter: 
    if /i "%rw%"=="W" (
        "%PY%" -m tools.overnight_qa.runner --hours 6 --mode sandbox_write --projects "%p1%,%p2%" --suites smoke_e2e,ai_gpu,chaos_race,sandbox_write
    ) else (
        "%PY%" -m tools.overnight_qa.runner --hours 6 --mode readonly --projects "%p1%,%p2%" --suites smoke_e2e,ai_gpu,chaos_race
    )
) else (
    echo Lua chon khong hop le.
)

echo.
pause
