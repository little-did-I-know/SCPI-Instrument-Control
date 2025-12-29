@echo off
echo Starting Siglent GUI with debug logging...
echo.
echo Look for these messages when you enable live view:
echo   - "Live view update started"
echo   - "Channel X: enabled=True/False"
echo   - "PLOTTING X waveforms"
echo   - "PyQtGraph _update_plot called"
echo.
echo Press Ctrl+C to exit
echo.
python -m siglent.gui.app
pause
