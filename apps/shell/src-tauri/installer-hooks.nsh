; Marvex NSIS installer hooks: register and start the always-on backend Windows
; service so "Hey Marvex" runs 24/7 from boot, and remove it on uninstall.
; marvex-service.exe is shipped as a bundled resource next to the app.

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Registering Marvex backend service (Hey Marvex, 24/7)..."
  nsExec::ExecToLog '"$INSTDIR\marvex-service.exe" --install'
  Pop $0
  DetailPrint "marvex-service --install exit code: $0"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Removing Marvex backend service..."
  nsExec::ExecToLog '"$INSTDIR\marvex-service.exe" --uninstall'
  Pop $0
  DetailPrint "marvex-service --uninstall exit code: $0"
!macroend
