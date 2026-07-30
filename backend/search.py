# -*- coding: utf-8 -*-
"""
search.py —— 查询类型识别

模仿 bgp.tools 的全局搜索框：自动识别用户输入是
ASN（AS13335 / 13335）、IP 前缀（8.8.8.0/24）、单个 IP、
DNS 域名或 MAC 地址，并返回前端应跳转的页面路径。
"""
import re
import ipaddress


def classify(query: str) -> dict:
    """识别查询类型。

    返回 {"type": ..., "redirect": ..., "label": ...}
    type ∈ asn / prefix / ip / dns / mac / unknown
    """
    q = (query or "").strip()
    if not q:
        return {"type": "unknown", "redirect": "", "label": ""}

    # 1) MAC 地址
    if re.match(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$", q):
        return {"type": "mac", "redirect": f"/mac/{q}", "label": q}

    # 2) ASN：AS123 / as123 / 纯数字（4字节 ASN 最多 10 位）
    m = re.match(r"^(?:as)?(\d{1,10})$", q, re.IGNORECASE)
    if m:
        return {"type": "asn", "redirect": f"/as/{m.group(1)}", "label": f"AS{m.group(1)}"}

    # 3) IP 前缀
    if "/" in q:
        try:
            net = ipaddress.ip_network(q, strict=False)
            return {"type": "prefix", "redirect": f"/prefix/{net}", "label": str(net)}
        except ValueError:
            pass

    # 4) 单个 IP
    try:
        ip = ipaddress.ip_address(q)
        return {"type": "ip", "redirect": f"/ip/{ip}", "label": str(ip)}
    except ValueError:
        pass

    # 5) DNS 域名 / 主机名
    if re.match(r"^[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9\-]*[A-Za-z0-9])?)+$", q):
        return {"type": "dns", "redirect": f"/dns/{q}", "label": q}

    return {"type": "unknown", "redirect": "", "label": q}
