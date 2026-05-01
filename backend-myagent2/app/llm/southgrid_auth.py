"""
南网推理平台 (southgrid) HMAC-SHA256 认证模块
"""
from __future__ import annotations

import base64
import hmac
from hashlib import sha256
from datetime import datetime, timedelta


def get_sign(data: str, key: str) -> str:
    """生成HMAC-SHA256签名"""
    sign = base64.b64encode(
        hmac.new(key.encode("utf-8"), data.encode("utf-8"), digestmod=sha256).digest()
    )
    return sign.decode("utf-8")


def build_auth_headers(custcode: str, api_key: str) -> dict[str, str]:
    """
    生成南网推理平台认证 headers

    Returns:
        dict with 'x-date', 'Authorization', 'Content-Type'
    """
    gmt_format = "%a, %d %b %Y %H:%M:%S GMT"
    x_date = (datetime.now() - timedelta(hours=8)).strftime(gmt_format)
    str_to_sign = "x-date: " + x_date
    sign_str = get_sign(str_to_sign, api_key)
    authorization = (
        f'hmac username="{custcode}", '
        f'algorithm="hmac-sha256", '
        f'headers="x-date", '
        f'signature="{sign_str}"'
    )
    return {
        "Content-Type": "application/json",
        "x-date": x_date,
        "Authorization": authorization,
    }
