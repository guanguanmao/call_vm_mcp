"""Small Windows Credential Manager wrapper used by the local MCP server."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_CredentialPointer = ctypes.POINTER(_CredentialW)


def _api() -> ctypes.WinDLL:
    if os.name != "nt":
        raise RuntimeError("Windows Credential Manager is available only on Windows.")
    advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_CredentialPointer)]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return advapi


def read_generic_credential(target: str) -> tuple[str, str] | None:
    """Return a generic credential, or None when no credential exists for target."""
    advapi = _api()
    credential_ptr = _CredentialPointer()
    if not advapi.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(credential_ptr)):
        error = ctypes.get_last_error()
        if error == _ERROR_NOT_FOUND:
            return None
        raise ctypes.WinError(error)
    try:
        credential = credential_ptr.contents
        blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return credential.UserName, blob.decode("utf-16-le")
    finally:
        advapi.CredFree(credential_ptr)


def write_generic_credential(target: str, username: str, password: str) -> None:
    """Store a generic credential under the current Windows user's profile."""
    if not username or not password:
        raise ValueError("Username and password must not be empty.")
    encoded_password = password.encode("utf-16-le")
    blob = ctypes.create_string_buffer(encoded_password)
    credential = _CredentialW()
    credential.Type = _CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.UserName = username
    credential.CredentialBlobSize = len(encoded_password)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_byte))
    credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
    if not _api().CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError(ctypes.get_last_error())
