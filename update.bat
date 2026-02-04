@echo off
title Aktualizace GitHub Repozitare
color 0A

echo ==========================================
echo      NAHRAVANI ZMEN NA GITHUB
echo ==========================================
echo.

:: 1. Pridani vsech souboru
echo [1/3] Pridavam zmeny do fronty...
git add .

:: 2. Vytvoreni commitu s vasim komentarem
echo.
set /p commit_msg="[2/3] Napiste popis zmeny (napr. oprava grafu): "
git commit -m "%commit_msg%"

:: 3. Odeslani na GitHub
echo.
echo [3/3] Odesilam na GitHub...
git push

echo.
echo ==========================================
echo   HOTOVO! Streamlit se brzy aktualizuje.
echo ==========================================
echo.
pause