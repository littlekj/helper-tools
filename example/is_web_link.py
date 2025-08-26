# 测试用例
links = [
    # === Web 链接（外部网络资源）===
    "http://example.com",
    "https://www.example.org/path/to/resource",
    "ftp://files.com/file.zip",
    "mailto:user@example.com",
    "tel:+123456789",
    "www.example.com",
    "example.com",
    "sub.domain.co.uk",
    "my.blog",
    "app.dev",
    "store.online",
    "example.com:8080",
    "example.com/path?query=1#hash",
    "//cdn.example.com/style.css",  # 协议相对
    "https://example.com.",         # 末尾有点（合法）
    
    # === 本地链接（非 Web）===
    "obsidian://open?vault=my%20vault",
    "file:///C:/Users/User/Documents/file.pdf",
    "file://localhost/path/to/file",
    "Document.pdf",
    "note.md",
    "image.png",
    "config.sys",
    "archive.tar.gz",               # 多级扩展名
    "./relative/path/to/local",
    "../parent/dir/resource",
    "/absolute/path/to/local",
    "C:\\Windows\\path\\local",     # Windows 路径
    "\\\\server\\share\\file.txt",  # 网络共享路径
    "localhost",
    "localhost:3000",
    "127.0.0.1",
    "192.168.1.1:8080",
    "internal.service",
    "intranet",
    "dashboard",
    "index.html",                   # 仅文件名，无路径
    "README",                       # 无扩展名文件
    "temp",                         # 纯单词
    "a.b",                          # 模糊：可能是域名，也可能是文件
    "x.yz",                         # 模糊：yz 不是常见 TLD
    
    # === 边界/异常情况 ===
    "",
    "   ",
    "invalid|pipe.com",
    "space in.com",
    "special@char.com",
    "xn--fsq.xn--0zwm56d",          # IDN（中文域名编码）
    "https://",
    "http://",
    "www.",
    "com",
    ".",
    "..",
    "/",
    "http:///",
    "://malformed",
]

import re

# 常见顶级域名（TLD），用于区分 Web 链接和本地文件
COMMON_TLDS = {
    # 通用
    'com', 'org', 'net', 'edu', 'gov', 'mil', 'int', 'biz', 'info', 'name', 'pro',
    'museum', 'coop', 'aero', 'post', 'geo', 'kid', 'law', 'mail', 'sco', 'web',
    # 国家
    'cn', 'uk', 'de', 'fr', 'jp', 'au', 'ca', 'ru', 'in', 'br', 'it', 'es', 'nl',
    # 新通用
    'app', 'dev', 'io', 'ai', 'co', 'tv', 'xyz', 'online', 'site', 'store', 'tech',
    'cloud', 'space', 'blog', 'news', 'wiki', 'shop', 'bank', 'sport', 'game',
    'music', 'movie', 'photo', 'art', 'design', 'studio', 'today', 'world',
    # 其他常见
    'us', 'uk', 'eu', 'me', 'tv', 'cc', 'la', 'pw', 'info', 'mobi',
}

# 文件扩展名黑名单（明确不是 TLD 的）
FILE_EXTS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'md', 'markdown', 'rtf', 'log',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    'zip', 'rar', '7z', 'tar', 'gz', 'iso',
    'exe', 'dll', 'bin', 'apk', 'pkg',
    'mp3', 'wav', 'flac', 'mp4', 'avi', 'mkv', 'mov',
    'css', 'js', 'json', 'xml', 'html', 'htm',
    'py', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'ts', 'sh',
    'tmp', 'bak', 'old', 'swp', 'lock',
}

def is_web_link(link: str) -> bool:
    """
    判断链接是否为网页链接（外部网络资源）
    
    策略：
    1. 先排除明确的本地链接
    2. 再判断明确的 Web 链接
    3. 最后用 TLD + 格式判断模糊情况
    """
    if not isinstance(link, str) or not link.strip():
        return False
    link = link.strip()
    if not link:
        return False

    # 1. 明确的本地或特殊协议链接 → 非 Web
    private_ipprivate_ip_pattern = re.compile(
        r'\b127\.0\.0\.1\b'                    # 回环地址
        r'|\b192\.168\.\d+\.\d+\b'             # 192.168.x.x
        r'|\b10\.\d+\.\d+\.\d+\b'              # 10.x.x.x
        r'|\b172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+\b'  # 172.16.0.0 ~ 172.31.255.255
    )
    if (
        link.startswith('obsidian://') or
        link.startswith('file://') or
        'localhost' in link.lower() or
        private_ipprivate_ip_pattern.search(link)
    ):
        return False

    # 2. 协议头明确的 Web 链接
    if link.startswith(('http://', 'https://', 'ftp://', 'mailto:', 'tel:')):
        return True

    # 3. 协议相对链接（//example.com）
    if link.startswith('//'):
        return True

    # 4. 相对路径或绝对路径 → 本地路径链接
    if link.startswith(('./', '../', '/')) or '\\' in link or link.startswith('\\\\'):
        return False
    
    # 5. 纯文件名判断（优先于域名判断）
    # 如果是 xxx.yyy 格式，且 yyy 不是常见 TLD，则视为文件
    filename_match = re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*\.([a-zA-Z0-9]{2,6})$', link)
    if filename_match:
        ext = filename_match.group(1).lower()
        # 如果扩展名在文件黑名单中 → 本地
        if ext in FILE_EXTS:
            return False
        # 如果扩展名是公认 TLD → Web
        if ext in COMMON_TLDS:
            return True
        # 模糊情况：不在 TLD 列表中 → 倾向于本地（保守策略）
        return False

    # 6. 严格域名格式 + TLD 检查
    # 修改正则：明确捕获 TLD
    domain_pattern = re.compile(
        r'^'
        r'(?:[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'  # 子域（可选）
        r'[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'         # 主域名（如 example）
        r'\.'                                                  # 必须有一个点
        r'[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'            # 顶级域（如 com, org, xn--）
        r'(?::\d{1,5})?'                                       # 可选端口（:8080）
        r'(?:/[^\s]*)?'                                        # 可选路径（/path/to/page）
        r'$', re.IGNORECASE
    )
    if domain_pattern.match(link):
        tld = link.split('.')[-1].lower()
        if tld in COMMON_TLDS:
            return True

    # 7. 其他情况视为本地链接
    return False

for link in links:
    if not link.strip():
        result = "Invaild"
    else:
        try:
            result = "Web Link" if is_web_link(link) else "Local Link"
        except Exception as e:
            result = f"Error: {e}"
    print(f"Link: {link:<40} -> {result}")