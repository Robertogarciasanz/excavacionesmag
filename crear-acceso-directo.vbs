Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\🚀 Optimizador PC.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "D:\archivos del pincho\limpiador\OPTIMIZADOR-PC.bat"
oLink.WorkingDirectory = "D:\archivos del pincho\limpiador"
oLink.Description = "Optimizador Completo de PC - Diagnostico y Mantenimiento"
oLink.IconLocation = "C:\Windows\System32\imageres.dll,109"
oLink.Save

MsgBox "✅ Acceso directo creado en el Escritorio!" & vbCrLf & vbCrLf & "Nombre: 🚀 Optimizador PC" & vbCrLf & vbCrLf & "Para ejecutar con permisos de administrador:" & vbCrLf & "Click derecho → 'Ejecutar como administrador'", vbInformation, "Acceso Directo Creado"
