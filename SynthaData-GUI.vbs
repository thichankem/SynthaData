' Chay SynthaData-GUI.bat o che do AN -> mo GUI khong nhay cua so console.
' Dung lam dich cho shortcut tren desktop. Portable: tu lay thu muc cua chinh no.
Dim d
d = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
CreateObject("WScript.Shell").Run """" & d & "SynthaData-GUI.bat""", 0, False
