@echo off
title OBNOVA DAT Z GITHUBU (RESET)
color 0C
echo POZOR: Toto smaze vsechny tvoje neulozene zmeny a vrati stav podle GitHubu.
echo.
pause
echo [1/2] Stahuji informace ze serveru...
git fetch origin
echo.
echo [2/2] Resetuji vsechny soubory...
git reset --hard origin/main
echo.
echo HOTOVO. Tvoje slozka je nyni presna kopie GitHubu.
pause