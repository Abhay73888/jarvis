Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName) & "\jarvis"
WshShell.CurrentDirectory = ScriptDir

VenvPython = ScriptDir & "\.venv\Scripts\pythonw.exe"
If Not FSO.FileExists(VenvPython) Then
    VenvPython = "pythonw.exe"
End If

WshShell.Run """" & VenvPython & """ """ & ScriptDir & "\run.py"" app", 0, False
