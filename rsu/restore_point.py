"""系统还原点创建（动态加载 srclient.dll）。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

BEGIN_SYSTEM_CHANGE = 100
MODIFY_SETTINGS = 12


class RESTOREPOINTINFOW(ctypes.Structure):
    _fields_ = [
        ("dwEventType", wintypes.DWORD),
        ("dwRestorePtType", wintypes.DWORD),
        ("llSequenceNumber", ctypes.c_longlong),
        ("szDescription", wintypes.WCHAR * 260),
    ]


class STATEMGRSTATUS(ctypes.Structure):
    _fields_ = [
        ("nStatus", wintypes.DWORD),
        ("llSequenceNumber", ctypes.c_longlong),
    ]


def create_restore_point(description: str) -> tuple[bool, str]:
    """返回 (是否成功, 错误信息)。"""
    try:
        dll = ctypes.WinDLL("srclient.dll")
    except OSError:
        return False, "无法加载 srclient.dll（系统还原组件不可用）"

    try:
        func = dll.SRSetRestorePointW
    except AttributeError:
        return False, "系统不支持 SRSetRestorePointW"

    func.argtypes = [ctypes.POINTER(RESTOREPOINTINFOW), ctypes.POINTER(STATEMGRSTATUS)]
    func.restype = wintypes.BOOL

    info = RESTOREPOINTINFOW()
    info.dwEventType = BEGIN_SYSTEM_CHANGE
    info.dwRestorePtType = MODIFY_SETTINGS
    info.llSequenceNumber = 0
    info.szDescription = description[:255]

    status = STATEMGRSTATUS()
    ok = func(ctypes.byref(info), ctypes.byref(status))
    if not ok:
        return False, f"创建还原点失败（状态码 {status.nStatus}），可能未开启系统保护"
    return True, ""
