Set WshShell = CreateObject("WScript.Shell")
strScriptPath = WScript.ScriptFullName
strScriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(strScriptPath)
strCmd = "python """ & strScriptDir & "\code\daemon.py"""
WshShell.Run strCmd, 0, False
