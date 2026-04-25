Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ProjectRoot = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run """" & ProjectRoot & "\run_daily.bat" & """", 0, False
