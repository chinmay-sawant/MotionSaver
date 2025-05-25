# import ctypes
# import sys
# import tkinter as tk
# import winreg
# import winreg

# def disable_ctrl_alt_del():
#     # This requires admin privileges and only works on Windows
#     # It modifies the registry to disable Task Manager (Ctrl+Alt+Del menu)
#     key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
#                            r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
#     winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
#     winreg.CloseKey(key)

# def enable_ctrl_alt_del():
#     key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
#                            r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
#     winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
#     winreg.CloseKey(key)

# def on_close():
#     enable_ctrl_alt_del()
#     root.destroy()
#     sys.exit()

# if __name__ == "__main__":
#     if sys.platform != "win32":
#         print("This script only works on Windows.")
#         sys.exit(1)

#     disable_ctrl_alt_del()

#     root = tk.Tk()
#     root.attributes('-fullscreen', True)
#     root.config(bg='black')
#     root.protocol("WM_DELETE_WINDOW", on_close)
#     root.bind("<Escape>", lambda e: on_close())

#     label = tk.Label(root, text="MotionSaver - Press ESC to exit", fg="white", bg="black", font=("Arial", 24))
#     label.pack(expand=True)

#     try:
#         root.mainloop()
#     finally:
#         enable_ctrl_alt_del()