; NSIS Installer Script for MotionSaver

Name "MotionSaver"
RequestExecutionLevel admin  ; Require admin rights

SetCompressor lzma
SetCompress auto

Function .onInit
  UserInfo::GetAccountType
  Pop $0
  StrCmp $0 "admin" done
    MessageBox MB_ICONSTOP "This installer requires administrator privileges. Please run as administrator." /SD IDOK
    Quit
  done:
FunctionEnd
OutFile "MotionSaver_Setup.exe"
InstallDir "$PROGRAMFILES\MotionSaver"

Page directory
Page instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  ; Include all files and folders from #codebase
  ; Exclude installer.nsi from being included
  File /r /x installer.nsi /x MotionSaver_Setup.exe "d:\MotionSaver_Staging\*.*"

  ; Write the uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Update userconfig.json drive letter if needed
  ExecWait '"$INSTDIR\\update_userconfig_drive.bat" "$INSTDIR"'
  
  ; Wait 1 second
  Sleep 3000
  
  ; Start MotionSaver
  ExecWait '"$INSTDIR\\MotionSaver.bat"'

  ; Wait 1 second
  Sleep 3000

  ; Register the service as admin using NSIS's built-in RunAs
  ExecWait '"$INSTDIR\\MotionSaver_Register_Service.bat"'

 

; Show success message with link and footer
MessageBox MB_ICONINFORMATION|MB_OK "Installation successful!" /SD IDOK
SectionEnd

Section "Uninstall"
  ; Call the service removal script before deleting files
  ExecWait '"$INSTDIR\\MotionSaver_Remove_Service.bat"'

  Delete "$INSTDIR\PhotoEngine.exe"
  Delete "$INSTDIR\Gui.bat"
  Delete "$INSTDIR\MotionSaver_Register_Service.bat"
  Delete "$INSTDIR\MotionSaver_Remove_Service.bat"
  Delete "$INSTDIR\MotionSaver.bat"
  Delete "$INSTDIR\StopMotionSaver.bat"
  Delete "$INSTDIR\unhooks.exe"
  Delete "$INSTDIR\vlc_snapshot_temp.png"
  Delete "$INSTDIR\raccon_circle_cropped.gif"
  Delete "$INSTDIR\raccon_circle.gif"
  Delete "$INSTDIR\AMG.mp4"
  ; Remove folders recursively
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\config"
  RMDir /r "$INSTDIR\logs"
  RMDir /r "$INSTDIR\PhotoEngine"
  RMDir "$INSTDIR"
SectionEnd

