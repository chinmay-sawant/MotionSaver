import win32con
import win32ts
import win32process
import win32event
import win32profile
import win32api
import win32security
import pywintypes
import os
import sys

def launch_in_user_session(command, workdir=None):
    # Get the active session ID
    session_id = win32ts.WTSGetActiveConsoleSessionId()
    if session_id == 0xFFFFFFFF:
        raise RuntimeError("No active user session found.")

    # Get the user token from the session
    hUserToken = win32ts.WTSQueryUserToken(session_id)

    # Define the parameters for DuplicateTokenEx clearly
    existing_token_handle = hUserToken
    impersonation_level = win32security.SecurityImpersonation # For primary tokens, this is often set to SecurityImpersonation
    desired_access = win32security.TOKEN_DUPLICATE | \
                    win32security.TOKEN_QUERY | \
                    win32security.TOKEN_ASSIGN_PRIMARY
    token_type = win32security.TokenPrimary # You need a primary token for CreateProcessAsUser
    token_attributes = None # Use None for default security attributes

    # Duplicate the token for use in CreateProcessAsUser
    hUserTokenDup = win32security.DuplicateTokenEx(
        existing_token_handle,
        impersonation_level,
        desired_access,
        token_type,
        token_attributes
    )
    # Get the user environment
    user_env = win32profile.CreateEnvironmentBlock(hUserTokenDup, False)

    # Prepare startup info
    startup = win32process.STARTUPINFO()
    startup.dwFlags |= win32con.STARTF_USESHOWWINDOW
    startup.wShowWindow = win32con.SW_SHOW

    # Launch the process in the user's session
    proc_info = win32process.CreateProcessAsUser(
        hUserTokenDup,           # User token
        None,                    # Application name
        command,                 # Command line
        None,                    # Process attributes
        None,                    # Thread attributes
        False,                   # Inherit handles
        16, # Creation flags
        user_env,                # Environment
        workdir or os.path.dirname(sys.executable), # Working directory
        startup                  # Startup info
    )
    return proc_info