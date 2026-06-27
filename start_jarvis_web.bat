@echo off
cd /d "C:\Users\nikes\jarvis"
call .venv\Scripts\activate
start /B "" python -m web.server > web_out.txt 2> web_err.txt
ping 127.0.0.1 -n 8 >nul
start "" http://localhost:8080
