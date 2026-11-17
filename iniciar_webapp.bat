@echo off
title PERT/CPM Studio
cd /d "%~dp0webapp"
echo ========================================================
echo   PERT/CPM Studio - Planificacion y Optimizacion
echo ========================================================
echo Iniciando servidor de desarrollo en http://localhost:5173 ...
echo Presione Ctrl+C para detener el servidor.
echo.
call npm.cmd run dev -- --open
pause
