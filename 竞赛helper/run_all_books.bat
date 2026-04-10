@echo off
cd /d E:\数学竞赛helper\竞赛helper
if not exist logs mkdir logs

echo Starting book extractions...
echo.

start /B python extract_concurrent.py --book secret2 --workers 3 --chunk-size 8 --resume > logs\secret2.log 2>&1
echo secret2 started

timeout /t 5 /nobreak > nul

start /B python extract_concurrent.py --book tip4 --workers 3 --chunk-size 8 --resume > logs\tip4.log 2>&1
echo tip4 started

timeout /t 5 /nobreak > nul

start /B python extract_concurrent.py --book tip9 --workers 3 --chunk-size 8 --resume > logs\tip9.log 2>&1
echo tip9 started

echo.
echo All 3 books started! Check logs folder for progress.
echo.
echo To monitor progress:
echo   type logs\secret2.log
echo   type logs\tip4.log
echo   type logs\tip9.log
