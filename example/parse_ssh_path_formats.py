import re
from typing import Tuple, Optional

def parse_destination(dst: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    解析目标路径，判断是否为远程 SSH 路径。
    
    返回值：
        (is_remote, path, user, host)
    """
    # 匹配 SSH 格式 [user@]host:/absolute/path
    # host: 支持 IPv4 / IPv6（用 [] 包裹） / 主机名
    pattern = r'^((?P<user>[^@]+)@)?(?P<host>\[[^\]]+\]|[^:]+):(?P<path>/.*)$'
    match = re.match(pattern, dst)

    if not match:
        return False, dst, None, None

    user = match.group('user')
    host = match.group('host')
    path = match.group('path')

    # 去掉 IPv6 host 的方括号
    if host and host.startswith('[') and host.endswith(']'):
        host = host[1:-1]

    return True, path, user, host


if __name__ == "__main__":
    test_cases = [
        "user@host:/backup",
        "user@[2001:db8::1]:/data",
        "host:/path",
        "my@local:path",
        "/local/path/to@file",
        "user@192.168.1.10:/backup",
        "user@192.168.1.10:/backup/",
        "@host:/path",  # 无用户名
    
    ]

    for dst in test_cases:
        is_remote, path, user, host = parse_destination(dst)
        if is_remote:
            print(f"✅ 远程: {dst} → user={user}, host={host}, path={path}")
        else:
            print(f"📁 本地: {dst}")
