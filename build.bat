@echo off
echo ============================================
echo   Screen Recorder -- .exe bana rahe hain
echo ============================================
echo.

pip install -r requirements.txt

echo.
echo Compiling... (2-3 minute lag sakta hai)
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "ScreenRecorder" ^
  --icon "me-holding-a-pic.ico" ^
  --add-data "ffmpeg;ffmpeg" ^
  --add-data "me-holding-a-pic.ico;." ^
  --exclude-module cv2 ^
  --exclude-module PIL ^
  --exclude-module numpy ^
  recorder.py

echo.
echo ============================================
echo   Tayyar!
echo   Poora "dist\ScreenRecorder" folder copy karein
echo   Us ke andar ScreenRecorder.exe hai
echo   Desktop par shortcut bana dein — bas!
echo ============================================
pause
