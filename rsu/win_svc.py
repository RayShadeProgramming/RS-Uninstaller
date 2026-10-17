"""Windows 服务枚举与删除（ctypes 直接调用 SCM API，无第三方依赖）。"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

SC_MANAGER_CONNECT = 0x0001
SC_MANAGER_ENUMERATE_SERVICE = 0x0004
SERVICE_QUERY_CONFIG = 0x0001
SERVICE_QUERY_STATUS = 0x0004
SERVICE_STOP = 0x0020
SERVICE_DELETE = 0x10000
SC_ENUM_PROCESS_INFO = 0
SERVICE_WIN32 = 0x00000030
SERVICE_STATE_ALL = 0x00000003
SERVICE_CONTROL_STOP = 0x00000001
SERVICE_STOPPED = 0x00000001

ERROR_MORE_DATA = 234
ERROR_SERVICE_DOES_NOT_EXIST = 1060
ERROR_SERVICE_MARKED_FOR_DELETE = 1072


class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


class SERVICE_STATUS_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwServiceFlags", wintypes.DWORD),
    ]


class ENUM_SERVICE_STATUS_PROCESSW(ctypes.Structure):
    _fields_ = [
        ("lpServiceName", wintypes.LPWSTR),
        ("lpDisplayName", wintypes.LPWSTR),
        ("ServiceStatusProcess", SERVICE_STATUS_PROCESS),
    ]


class QUERY_SERVICE_CONFIGW(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwStartType", wintypes.DWORD),
        ("dwErrorControl", wintypes.DWORD),
        ("lpBinaryPathName", wintypes.LPWSTR),
        ("lpLoadOrderGroup", wintypes.LPWSTR),
        ("dwTagId", wintypes.DWORD),
        ("lpDependencies", wintypes.LPWSTR),
        ("lpServiceStartName", wintypes.LPWSTR),
        ("lpDisplayName", wintypes.LPWSTR),
    ]


_advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
_advapi32.OpenSCManagerW.restype = wintypes.HANDLE
_advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
_advapi32.OpenServiceW.restype = wintypes.HANDLE
_advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
_advapi32.EnumServicesStatusExW.argtypes = [
    wintypes.HANDLE, ctypes.c_int, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR,
]
_advapi32.EnumServicesStatusExW.restype = wintypes.BOOL
_advapi32.QueryServiceConfigW.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.QueryServiceConfigW.restype = wintypes.BOOL
_advapi32.ControlService.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SERVICE_STATUS),
]
_advapi32.ControlService.restype = wintypes.BOOL
_advapi32.QueryServiceStatus.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS),
]
_advapi32.QueryServiceStatus.restype = wintypes.BOOL
_advapi32.DeleteService.argtypes = [wintypes.HANDLE]
_advapi32.DeleteService.restype = wintypes.BOOL


def _query_image(scm, name: str) -> str:
    handle = _advapi32.OpenServiceW(scm, name, SERVICE_QUERY_CONFIG)
    if not handle:
        return ""
    try:
        needed = wintypes.DWORD(0)
        _advapi32.QueryServiceConfigW(handle, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            return ""
        buffer = ctypes.create_string_buffer(needed.value)
        if not _advapi32.QueryServiceConfigW(handle, ctypes.cast(buffer, ctypes.c_void_p),
                                             needed.value, ctypes.byref(needed)):
            return ""
        config = ctypes.cast(buffer, ctypes.POINTER(QUERY_SERVICE_CONFIGW)).contents
        return config.lpBinaryPathName or ""
    finally:
        _advapi32.CloseServiceHandle(handle)


def list_services() -> list[dict]:
    """返回 [{'name', 'display', 'image'}]，无权限时返回空列表。"""
    services: list[dict] = []
    scm = _advapi32.OpenSCManagerW(None, None, SC_MANAGER_ENUMERATE_SERVICE)
    if not scm:
        return services

    try:
        size = 64 * 1024
        for _ in range(8):
            buffer = ctypes.create_string_buffer(size)
            needed = wintypes.DWORD(0)
            returned = wintypes.DWORD(0)
            resume = wintypes.DWORD(0)
            ok = _advapi32.EnumServicesStatusExW(
                scm, SC_ENUM_PROCESS_INFO, SERVICE_WIN32, SERVICE_STATE_ALL,
                ctypes.cast(buffer, ctypes.c_void_p), size,
                ctypes.byref(needed), ctypes.byref(returned),
                ctypes.byref(resume), None,
            )
            if not ok:
                if ctypes.get_last_error() == ERROR_MORE_DATA:
                    size = max(size * 2, needed.value)
                    continue
                break

            array = ctypes.cast(buffer, ctypes.POINTER(ENUM_SERVICE_STATUS_PROCESSW))
            for index in range(returned.value):
                entry = array[index]
                name = entry.lpServiceName or ""
                display = entry.lpDisplayName or ""
                if name:
                    services.append({
                        "name": name,
                        "display": display,
                        "image": _query_image(scm, name),
                    })
            if resume.value == 0:
                break
    finally:
        _advapi32.CloseServiceHandle(scm)

    return services


def stop_and_delete(name: str) -> tuple[bool, str]:
    scm = _advapi32.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
    if not scm:
        return False, f"无法打开服务管理器（错误 {ctypes.get_last_error()}）"

    handle = _advapi32.OpenServiceW(scm, name, SERVICE_STOP | SERVICE_DELETE | SERVICE_QUERY_STATUS)
    if not handle:
        code = ctypes.get_last_error()
        _advapi32.CloseServiceHandle(scm)
        if code == ERROR_SERVICE_DOES_NOT_EXIST:
            return True, ""
        return False, f"无法打开服务（错误 {code}）"

    try:
        status = SERVICE_STATUS()
        _advapi32.ControlService(handle, SERVICE_CONTROL_STOP, ctypes.byref(status))
        for _ in range(30):
            if _advapi32.QueryServiceStatus(handle, ctypes.byref(status)):
                if status.dwCurrentState == SERVICE_STOPPED:
                    break
            time.sleep(0.1)

        ok = _advapi32.DeleteService(handle)
        code = ctypes.get_last_error()
        if not ok and code != ERROR_SERVICE_MARKED_FOR_DELETE:
            return False, f"删除服务失败（错误 {code}）"
        return True, ""
    finally:
        _advapi32.CloseServiceHandle(handle)
        _advapi32.CloseServiceHandle(scm)
