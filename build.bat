@echo off
echo Installing dependencies...
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo Building ecur.exe...
pyinstaller --clean ecur.spec

echo Done! The executable is located in dist/ecur.exe
pause

