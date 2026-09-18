Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = files.GetParentFolderName(WScript.ScriptFullName)
script = files.BuildPath(root, "Start-DSH.ps1")
shell.CurrentDirectory = root
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34), 1, False
