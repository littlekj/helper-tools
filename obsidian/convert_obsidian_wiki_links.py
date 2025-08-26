"""
需求：

将 Obsidian 笔记中的内部链接格式转换为 Markdown 链接格式

处理 Obsidian 文档中的内部链接格式范围：

1. Obsidian 支持的 Wiki 链接格式

- 当前文件内锚点链接：`[[#标题]]`     
- 当前文件内块标识符链接：`[[#^块标识符]]`
- 普通文件链接：`[[assets/file1.md]]`
- 支持文件带锚点：`[[assets/file2.md#标题]]`
- 支持文件带块标识符：`[[assets/file3.md#^块标识符]]`
- 支持文件带别名：`[[assets/file4.md|别名]]`
- 支持文件带锚点和别名：`[[assets/file5.md#标题|别名]]`
- 支持文件带块标识符和别名：`[[assets/file6.md#^块标识符|别名]]`
- 图片资源链接：`![[assets/image1.png]]`
- 支持图片带尺寸声明：`![[assets/image2.png | 400x300]]`
- 支持图片仅指定宽度：`![[assets/image3.png | 400]]`

2. Obsidian 特殊嵌入格式

- 当前文件内锚点嵌入：`![[#标题]]`
- 当前文件内块标识符嵌入：`![[#^块标识符]]`
- 嵌入文件内容：`![[assets/file10.md]]`
- 嵌入 PDF 页面指定页数：`![[assets/doc.pdf#page=3]]`


转换后的 Markdown 链接格式：

1. 标准 Markdown 链接格式

- 当前文件内锚点链接：`[别名](#标题)`
- 普通文件链接：`[别名](assets/file7.md)`
- 支持文件带锚点：`[别名](assets/file8.md#标题)`
- 图片资源链接：`![描述](assets/image4.png)`
- 普通资源链接指向图片：`[描述](assets/image5.png)`
   
2. Obsidian Markdown 扩展

- 当前文件内锚点嵌入：`![别名](#标题)`
- 当前文件内块标识符嵌入`![别名](#^块标识符)`
- 当前文件内块标识符链接：`[别名](#^块标识符)`
- 支持文件带块标识符：`[别名](assets/file9.md#^块标识符)`
- 支持图片带尺寸声明：`![400x300](assets/image6.png)`
- 支持图片带描述和尺寸声明：`![描述 | 400x300](assets/image7.png)`
- 支持图片带描述和仅宽度声明：`![描述 | 400](assets/image8.png)`

"""
import os
import shutil
import re
from urllib.parse import urlparse, unquote, quote
import sys
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('ObsidianLinkConverter')

# 配置路径
source_folder = "Default"
source_note_dir = fr'D:\Obsidian\Default'
target_note_dir = fr'D:\Obsidian\Middle\wikiformat'
internal_link_prefix = r''  # 内部链接前缀
# external_link_prefix = r''  # 外部链接前缀
# external_link_prefix = r'https://raw.githubusercontent.com/littlekj/linkres/master/obsidian/'
external_link_prefix = '/'  # 相对地址前缀添加 / 生成绝对路径，拼接 GitHub 仓库地址便于 Web 访问

# Obsidian 支持的文件格式
supported_extensions = {
    'markdown': ['md'],
    'image': ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'avif', 'webp', 'svg'],
    'audio': ['flac', 'm4a', 'mp3', 'ogg', 'wav', 'webm', '3gp'],
    'video': ['mkv', 'mov', 'mp4', 'ogv', 'webm', 'avi'],
    'pdf': ['pdf']
}

# 构建所有扩展名的正则表达式模式
all_extensions = []
for category in supported_extensions.values():
    all_extensions.extend(category)
extensions_pattern = '|'.join(all_extensions)

# 全局资源缓存（避免重复查找）
resource_cache = {}


# 匹配内联代码 和 多行代码块（反引号/波浪号，3个或以上）
# 改进的正则：为每种情况设置捕获组，并确保内容被捕获
CODE_PATTERN = re.compile(
    r'(`[^`]+?`)'                                  # group 1: 内联代码
    r'|(~{3,})([a-zA-Z][\w-]*)?\s*\n'              # group 2: 波浪号开始, group 3: 语言
    r'([\s\S]*?)\n'                                # group 4: 波浪号内容
    r'(~{3,})(?=\n|$)'                             # group 5: 波浪号结束
    r'|(`{3,})([a-zA-Z][\w-]*)?\s*\n'              # group 6: 反引号开始, group 7: 语言
    r'([\s\S]*?)\n'                                # group 8: 反引号内容
    r'(`{3,})(?=\n|$)',                            # group 9: 反引号结束
    re.MULTILINE
)


def save_code_blocks(content):
    code_blocks = []
    placeholder_counter = 0

    def replace_func(match):
        nonlocal placeholder_counter
        placeholder_counter += 1
        placeholder = f"__CODE_BLOCK_{placeholder_counter}__"

        if match.group(1):  # 内联代码
            code = match.group(1)
        elif match.group(2):  # 波浪号代码块
            start_delim = match.group(2)   # ~~~
            lang = match.group(3) or ""    # 可选语言
            body = match.group(4)
            end_delim = match.group(5)     # ~~~
            # 保留语言标识
            code = f"{start_delim}{lang}\n{body}\n{end_delim}"
        else:  # 反引号代码块
            start_delim = match.group(6)   # ```
            lang = match.group(7) or ""    # 可选语言
            body = match.group(8)
            end_delim = match.group(9)     # ```
            # 保留语言标识
            code = f"{start_delim}{lang}\n{body}\n{end_delim}"

        code_blocks.append((placeholder, code))
        return placeholder

    new_content = CODE_PATTERN.sub(replace_func, content)
    return new_content, code_blocks


def restore_code_blocks(content, code_blocks):
    """
    将占位符替换回原始代码块
    """
    for placeholder, code in code_blocks:
        content = content.replace(placeholder, code)
    return content


# Wiki 链接正则（支持路径/标题/块/尺寸/别名，竖线前后可有空格）
wiki_link_regex = r"""
    (!?)                           # 1: 可选 "!"（embed）
    \[\[
        (?:([^\]\|\n#^]+?)\s*)?    # 2: 路径（可选，自动去掉尾空格）
        (?:\#(?:
            (?!\^)([^\]\|\n#^]+)   # 3: 标题（#xxx）
          | \^([^\]\|\n#]+)        # 4: 块标识符（#^xxx）
        ))?
        (?:\s*\|\s*(\d{1,4}(?:x\d{1,4})?))?   # 5: 尺寸（400 或 400x300）
        (?:\s*\|\s*([^\]\n|]+))?              # 6: 别名
    \]\]
"""

wiki_link_pattern = re.compile(wiki_link_regex, re.VERBOSE)


def parse_desc_size(raw_desc_or_size, size_group):
    """解析图片描述和尺寸"""
    if not size_group:
        if raw_desc_or_size and re.match(r'^\d{1,4}(?:x\d{1,4})?$', raw_desc_or_size):
            return None, raw_desc_or_size
        return raw_desc_or_size, None

    return raw_desc_or_size, size_group


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


def extract_wiki_links(text):
    """Obsidian Wiki 链接解析"""
    matches = []
    for match in wiki_link_pattern.finditer(text):
        path = match.group(2) or None
        # isImage = path and is_image(match.group(2))
        # print("image_path:", match.group(2))
        full_match = match.group(0)
        embed = bool(match.group(1))
        title = match.group(3)
        block_id = match.group(4)
        desc = match.group(6)
        size = match.group(5)

        matches.append({
            'full_match': full_match,
            'type': 'wiki',
            'embed': embed,
            'path': path,
            'title': title,
            'block_id': block_id,
            'desc': desc,
            'size': size,
            'start': match.start(),
            'end': match.end(),
        })
            
    return matches


def confirm_delete(path):
    """确认是否删除指定路径"""
    confirm = input(f"⚠️  确认删除内容：{path}？(y/N): ").strip().lower()
    return confirm == 'y'    

def remove_if_exists(path):
    """删除文件或目录，如果存在"""
    if os.path.exists(path):
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        logger.info(f"已删除: {path}")

def safe_remove_if_exists(path):
    """安全删除目录，先确认再执行"""
    if confirm_delete(path):
        remove_if_exists(path)
    else:
        print("❌ 已取消删除操作。")  
        sys.exit(1)  # 立即退出程序


def copy_files(source_note_dir, ignored_extensions=None):
    """复制源目录中的所有文件到目标目录"""
    ignored_extensions = ignored_extensions or []
    for item in os.listdir(source_note_dir):
        source_path = os.path.join(source_note_dir, item)
        destination_path = os.path.join(target_note_dir, item)

        # 跳过忽略的文件类型
        if any(source_path.endswith(ext) for ext in ignored_extensions):
            continue

        # # 跳过特定系统文件
        # if item.startswith('.') or item in ['Thumbs.db', 'desktop.ini']:
        #     continue

        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
            logger.info(f"复制目录: {source_path} -> {destination_path}")
        else:
            shutil.copy2(source_path, destination_path)
            logger.info(f"复制文件: {source_path} -> {destination_path}")


def copy_files_with_timestamps(source_note_dir, ignored_extensions=None):
    """复制源目录中所有文件到目标，并保留原始时间戳"""
    try:
        from copy_with_timestamps import copy_with_timestamps
    except ImportError:
        logger.error("无法导入 copy_with_timestamps 模块，请确保模块存在。")
    
    ignored_extensions = ignored_extensions or []
    for item in os.listdir(source_note_dir):
        source_path = os.path.join(source_note_dir, item)
        if item.startswith('.') and os.path.isfile(source_path):
            # 隐藏文件复制时，不在复制命令的目标路径中指定文件
            destination_path = os.path.join(target_note_dir)
            # print("destination_path", destination_path)
        else:
            destination_path = os.path.join(target_note_dir, item)
        
        # 跳过忽略的文件类型
        if any(source_path.endswith(ext) for ext in ignored_extensions):
            continue
        
        # remove_if_exists(destination_path)
        if os.path.isdir(source_path):
            copy_with_timestamps(source_path, destination_path)
            logger.info(f"复制目录：{source_path} -> {destination_path}")
        else:
            copy_with_timestamps(source_path, destination_path)
            logger.info(f"复制文件：{source_path} -> {destination_path}")


def get_ignore_list(target_dir):
    """获取忽略文件列表"""
    ignore_files_path = os.path.join(target_dir, '.gitignore')
    if not os.path.exists(ignore_files_path):
        return []

    ignored = []
    with open(ignore_files_path, 'r', encoding='utf-8', newline='') as f:
        for line in f:
            stripped_line = line.strip()
            if stripped_line and not stripped_line.startswith('#'):
                # 处理目录忽略（移除结尾的/）
                if stripped_line.endswith('/'):
                    stripped_line = stripped_line[:-1]
                ignored.append(stripped_line)
    return ignored


def find_resource_file(source_dir, resource_path, current_note_dir):
    """
    在仓库中查找资源文件，支持各种相对路径格式
    :param source_dir: 仓库根目录
    :param resource_path: 资源路径（可能包含相对路径）
    :param current_note_dir: 当前笔记所在目录
    :return: 基于仓库根目录的相对路径，如果找不到返回None
    """
    # 转换URL编码的空格为普通空格
    resource_path = decode_url_space_only(resource_path)

    # 检查缓存
    cache_key = (resource_path, current_note_dir)
    if cache_key in resource_cache:
        return resource_cache[cache_key]

    # 尝试可能的路径组合
    possible_paths = []

    # 相对于当前笔记的路径
    relative_to_note = os.path.join(current_note_dir, resource_path)
    possible_paths.append(relative_to_note)
    
    # 相对于仓库根目录的路径
    relative_to_root = os.path.join(source_dir, resource_path)
    possible_paths.append(relative_to_root)
    
    # 尝试解析绝对路径（以 / 开头）
    if resource_path.startswith('/'):
        abs_path = os.path.abspath(os.path.join(source_dir, resource_path[1:]))
        possible_paths.append(abs_path)
        
    # 尝试解析相对路径（以 ./ 或 ../ 开头）
    elif resource_path.startswith(('./', '../')):
        abs_path = os.path.abspath(os.path.join(current_note_dir, resource_path))

        # 确保路径在仓库根目录内
        if not abs_path.startswith(os.path.abspath(source_dir)):
            logger.warning(f"资源路径超出仓库范围：{abs_path}")
            resource_cache[cache_key] = None
            return None

        possible_paths.append(abs_path)
        
    # 尝试解析其他相对路径
    else:
        # 尝试相对于当前仓库的相对路径
        direct_path = os.path.normpath(os.path.join(source_dir, resource_path))
        possible_paths.append(direct_path)
        
        # 尝试相对于当前笔记的隐式相对路径
        abs_path = os.path.normpath(os.path.join(current_note_dir, resource_path))
        possible_paths.append(abs_path)
        
    for path in possible_paths:
        # 判断路径是否为文件
        if os.path.isfile(path):
            rel_path = os.path.relpath(path, source_dir)
            resource_cache[cache_key] = rel_path
            return rel_path
        # 文件名形如：file.ext.ext，但插入的可能是 file.ext
        # 尝试直接添加扩展名
        else:
            for ext in all_extensions:
                extended_path = f"{path}.{ext}"
                if os.path.isfile(extended_path):
                    rel_path = os.path.relpath(extended_path, source_dir)
                    resource_cache[cache_key] = rel_path
                    return rel_path

    # 尝试全库文件名搜索     
    filename = os.path.basename(resource_path)
    for root, _, files in os.walk(source_dir):
        for file in files:
            # 匹配文件名（带扩展名或不带扩展名）
            if file == filename or any(file == f"{filename}.{ext}" for ext in all_extensions):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path, source_dir)
                    resource_cache[cache_key] = rel_path
                    return rel_path

    # 未找到资源
    resource_cache[cache_key] = None
    return None


def get_file_type(file_path):
    """根据文件扩展名获取文件类型"""
    ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
    for file_type, extensions in supported_extensions.items():
        if ext in extensions:
            return file_type
    return 'other'


def encode_url_space_only(url):
    """
    仅对URL中的空格进行编码
    """
    return url.replace(" ", "%20")

def decode_url_space_only(url):
    """
    仅对URL中的空格进行解码
    """
    return url.replace("%20", " ")


def convert_wiki_links(note_file_path, updated_content):
    """
    将文件中的 Obsidian Wiki 链接转换为 Markdown 超链接格式
    :param note_file_path: 笔记文件路径
    :param updated_content: 笔记内容
    """
    # 当前笔记所在目录
    current_note_dir = os.path.dirname(note_file_path)
    
    # 遍历所有匹配到的链接
    matches = extract_wiki_links(updated_content)
    
    # print("matches:", matches)
    # 按链接在文档中的位置排序
    matches.sort(key=lambda m: m['start'])
    
    parts = []  # 用于存储处理后的内容片段
    last_end = 0   # 记录上一次匹配结束的位置
    
    if matches:
        for match in matches:
            print('full_match:', match['full_match'])
            parts.append(updated_content[last_end:match['start']])
            resource_path = match['path']
 
            if not resource_path:
                resource_path = note_file_path
                
            resource_name = os.path.basename(resource_path)
            resource_relpath = find_resource_file(target_note_dir, resource_path, current_note_dir)
              
            if resource_relpath:
                # 计算相对仓库根目录的路径
                rel_path = resource_relpath.replace('\\', '/')  # 统一使用正斜杠
                print('rel_path:', rel_path)
                
                # 拼接成完整的 URL
                internal_link_prefix = r''
                full_url = f'{internal_link_prefix}{rel_path}'
                
                if match['embed']:
                    full_path = f'!['
                else:
                    full_path = f'['
                if not match['desc'] and not match['size']:
                    full_path += f'{resource_name}'
                elif match['desc']:
                    full_path += f'{match["desc"]}'
                    if match['size']:
                        full_path += f'|{match["size"]}'
                else:
                    full_path += f'{match["size"]}'
                full_path += f']('
                
                if match['title'] and not match['block_id']:
                    full_url += f'#{match["title"]}'
                if (not match['title']) and match['block_id']:
                    full_url += f'#^{match["block_id"]}'
                full_url = decode_url_space_only(full_url)
                full_url = encode_url_space_only(full_url)
                full_path += full_url + ')'   
            else:
                full_path = match['full_match']
                logger.warning(f"⚠️ 警告: 资源未找到： {resource_path}")
                logger.warning(f"📝 在笔记中: {note_file_path}")
                logger.warning(f"⏩ 此资源链接：{full_path}")
            
            # 添加匹配到的链接到内容片段
            parts.append(full_path)
            last_end = match['end']  # 更新上次处理结束位置

        # 添加最后一个片段
        parts.append(updated_content[last_end:])

        # 将所有片段重新组合成新的内容
        updated_content = ''.join(parts)

        return updated_content 
    
    return updated_content


def update_resource_links(note_file_path):
    """
    更新文件中的资源链接为 Markdown 超链接格式
    :param note_file_path: 笔记文件路径
    """
    with open(note_file_path, 'r', encoding='utf-8', newline='') as file:
        try:
            content = file.read()
        except IOError as e:
            print(f"IOError: {e}")
        except UnicodeDecodeError as e:
            print(f"Unicode")
        except Exception as e:
            print(f"Unexpected error: {e}")
        
    # 提取代码块并用占位符替换
    updated_content, code_blocks = save_code_blocks(content)
    
    # 提取所有资源链接转换为 Markdown 超链接
    updated_content = convert_wiki_links(note_file_path, updated_content)
    
    # 恢复代码块
    updated_content = restore_code_blocks(updated_content, code_blocks)
    
    with open(note_file_path, 'w', encoding='utf-8', newline='') as file:
        try:
            file.write(updated_content)
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
    

def iterate_files(target_note_dir):
    """遍历目标目录中的所有笔记文件更新链接"""
    ignored_dirs = get_ignore_list(target_note_dir)
    updated_count = 0
    for root, dirs, files in os.walk(target_note_dir):
        # 排除特定子目录
        dirs[:] = [d for d in dirs if d not in ignored_dirs]

        for file in files:
            if file.endswith('.md'):
                note_file_path = os.path.join(root, file)
                updated_count += 1
                logger.info(f"处理笔记: {note_file_path}")
                update_resource_links(note_file_path)
                
    return updated_count


def main():
    """执行文件复制和更新操作"""
    # 确认删除目标目录
    safe_remove_if_exists(target_note_dir)
    # 创建新目录
    os.makedirs(target_note_dir, exist_ok=True)
    
    logger.info("开始处理...")
    logger.info(f"源目录: {source_note_dir}")
    logger.info(f"目标目录: {target_note_dir}")

    # 复制文件（忽略特定扩展名）
    ignored_extensions = ['.tmp', '.DS_Store']
    # copy_files(source_note_dir, ignored_extensions)
    copy_files_with_timestamps(source_note_dir, ignored_extensions)

    # 更新笔记中的资源链接
    updated_count = iterate_files(target_note_dir)

    logger.info("\n✅ 处理完成！")
    logger.info(f"共处理 {updated_count} 个笔记: {target_note_dir}")


if __name__ == "__main__":
    # 设置日志级别
    logger.setLevel(logging.INFO)
    main()
