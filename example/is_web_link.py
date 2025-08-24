import re

def is_web_link(link):
    """
    判断链接是否为网页链接
    """
    # 1. 如果以http://或https://开头
    if link.startswith(('http://', 'https://')):
        return True
    
    # 2. 常见网络协议
    if link.startswith(('ftp://', 'mailto:', 'tel:')):
        return True
    
    # 3. 标准URL格式（带域名）
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # 域名
        r'(?::\d+)?'  # 端口
        r'(?:/[^\s]*)?$'  # 路径
    )
    if domain_pattern.match(link):
        return True
    
    # 4. 协议相对URL（视为外部链接）
    if link.startswith('//'):
        return True
    
    # 5. 本地网络地址（视为本地链接）
    if 'localhost' in link.lower() or '127.0.0.1' in link.lower():
        return False
    
    # 6. 其他情况视为本地链接
    return False

links = [
    "http://example.com",
    "https://www.example.org/path/to/resource",
    "./relative/path/to/local/resource",
    "/absolute/path/to/local/resource",
    "file:///C:/Users/User/Documents/file.pdf",
    "www.example.net/resource",
    "example.com/about",
    "images/logo.png",
    "../assets/file.txt"
]

for link in links:
    print(f"Link: {link} -> {'Web Link' if is_web_link(link) else 'Local Link'}")