Unicode True
SetCompressor /SOLID lzma

!define APP_NAME    "IG Automation"
!define APP_VERSION "1.0"
!define APP_DIR     "C:\IGAutomation"
!define PUBLISHER   "IGAutomation"
!define UNINSTALLER "Uninstall.exe"

Name "${APP_NAME}"
OutFile "IGAutomation-Setup.exe"
InstallDir "${APP_DIR}"
InstallDirRegKey HKLM "Software\${PUBLISHER}\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show

!include "MUI2.nsh"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Welcome to IG Automation Setup"
!define MUI_WELCOMEPAGE_TEXT "This will install IG Automation on your computer.$\r$\n$\r$\nThe installer will:$\r$\n  - Install Node.js if needed$\r$\n  - Create a Desktop shortcut$\r$\n$\r$\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_TITLE "Installation Complete"
!define MUI_FINISHPAGE_TEXT "IG Automation has been installed.$\r$\n$\r$\nClick Finish to run the final setup.$\r$\nThis only takes a moment.$\r$\n$\r$\nWhen done, a shortcut will appear on your Desktop."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Complete setup now (recommended)"
!define MUI_FINISHPAGE_RUN_FUNCTION RunSetup
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install" SecMain
    ; Backend
    SetOutPath "${APP_DIR}\backend"
    File "payload\backend\backend.exe"
    File "payload\backend\.env.enc"

    ; Chromium browser (pre-bundled — exact version match, no download needed)
    SetOutPath "${APP_DIR}\browsers"
    File /r /nonfatal "payload\browsers\"

    ; Frontend (.next + node_modules pre-bundled — no npm install needed)
    SetOutPath "${APP_DIR}\frontend"
    File /r "payload\frontend\.next"
    File /r "payload\frontend\node_modules"
    File "payload\frontend\package.json"
    File /nonfatal "payload\frontend\next.config.js"
    File "payload\frontend\.env.enc"

    ; Root files
    SetOutPath "${APP_DIR}"
    File "setup.ps1"
    File "AppIcon.ico"

    ; Set PowerShell execution policy silently
    ExecWait '$WINDIR\system32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -Command "Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force"'

    ; Write run-setup.bat
    FileOpen $0 "$INSTDIR\run-setup.bat" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "title IG Automation Setup$\r$\n"
    FileWrite $0 "set PS=$WINDIR\system32\WindowsPowerShell\v1.0\powershell.exe$\r$\n"
    FileWrite $0 "if not exist $\"%PS%$\" set PS=$WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe$\r$\n"
    FileWrite $0 "if not exist $\"%PS%$\" ($\r$\n"
    FileWrite $0 "    echo [ERROR] PowerShell not found.$\r$\n"
    FileWrite $0 "    echo Please install from https://aka.ms/powershell$\r$\n"
    FileWrite $0 "    pause$\r$\n"
    FileWrite $0 "    exit /b 1$\r$\n"
    FileWrite $0 ")$\r$\n"
    FileWrite $0 "%PS% -ExecutionPolicy Bypass -NoProfile -File $INSTDIR\setup.ps1$\r$\n"
    FileWrite $0 "if errorlevel 1 ($\r$\n"
    FileWrite $0 "    echo.$\r$\n"
    FileWrite $0 "    echo [FAILED] Check log: $INSTDIR\setup-log.txt$\r$\n"
    FileWrite $0 "    pause$\r$\n"
    FileWrite $0 ") else ($\r$\n"
    FileWrite $0 "    echo [DONE] Setup complete! Close this window.$\r$\n"
    FileWrite $0 ")$\r$\n"
    FileClose $0

    WriteUninstaller "${APP_DIR}\${UNINSTALLER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "${APP_DIR}\${UNINSTALLER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${PUBLISHER}"
    WriteRegStr HKLM "Software\${PUBLISHER}\${APP_NAME}" "InstallDir" "${APP_DIR}"
SectionEnd

Function RunSetup
    Exec '$WINDIR\system32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -NoProfile -NoExit -File "$INSTDIR\setup.ps1"'
FunctionEnd

Section "Uninstall"
    Delete "$DESKTOP\IG Automation.lnk"
    Delete "${APP_DIR}\run-setup.bat"
    RMDir /r "${APP_DIR}"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKLM "Software\${PUBLISHER}\${APP_NAME}"
SectionEnd
