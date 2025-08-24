"""
需求目标

将 Markdown 文件中引用的本地资源路径（如图片、文件）自动转换为可通过 Web 访问的外部 URL 格式。

处理 Obsidian 文档中的链接格式范围：

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

2. 标准 Markdown 链接格式

- 当前文件内锚点链接：`[别名](#标题)`
- 普通文件链接：`[别名](assets/file7.md)`
- 支持文件带锚点：`[别名](assets/file8.md#标题)`
- 图片资源链接：`![描述](assets/image4.png)`
- 普通资源链接指向图片：`[描述](assets/image5.png)`
   
3. Obsidian Markdown 扩展

- 当前文件内锚点嵌入：`![别名](#标题)`
- 当前文件内块标识符嵌入`![别名](#^块标识符)`
- 当前文件内块标识符链接：`[别名](#^块标识符)`
- 支持文件带块标识符：`[别名](assets/file9.md#^块标识符)`
- 支持图片带尺寸声明：`![400x300](assets/image6.png)`
- 支持图片带描述和尺寸声明：`![描述 | 400x300](assets/image7.png)`
- 支持图片带描述和仅宽度声明：`![描述 | 400](assets/image8.png)`

4. Obsidian 特殊嵌入格式

- 当前文件内锚点嵌入：`![[#标题]]`
- 当前文件内块标识符嵌入：`![[#^块标识符]]`
- 嵌入文件内容：`![[assets/file10.md]]`
- 嵌入 PDF 页面指定页数：`![[assets/doc.pdf#page=3]]`

5. 补充：

- ![描述](http://example.com/image.png)
- ![描述](https://example.com/audio.mp3)
- ![描述|400x300](assets/image%20copy.png)

处理说明:

- 将所有本地资源路径转换为外部 URL 格式，并保留原始链接的别名和描述。
- 嵌入图片链接，生成嵌入式图片的 HTML，可保留原始链接的描述和尺寸声明。
- 非嵌入图片链接，生成图片的 Markdown 链接，可保留原始链接的描述。
- 普通文件链接，生成文件的 Markdown 链接，可保留原始链接的锚点标题和别名，但不保留块标识符。

"""
import os
import shutil
import re
from urllib.parse import quote
import sys
from pathlib import Path
import logging

import argparse
import subprocess
import shlex
from typing import Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('ObsidianLinkConverter')

# 配置路径
source_folder = "Default"
source_note_dir = fr'D:\Obsidian\Middle\Default'
target_note_dir = fr'D:\Obsidian\Middle\obsidianlinks'
# external_link_prefix = r'https://raw.githubusercontent.com/littlekj/linkres/master/obsidian/'
external_link_prefix = '/'  # 相对地址前缀添加 / 生成绝对路径，拼接 GitHub 仓库地址便于 Web 访问
# external_link_prefix = ''

# 定义所有支持的文件类型（扩展列表）
supported_extensions = {
    'image': ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'svg'],
    'document': ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md'],
    'audio': ['mp3', 'wav', 'ogg', 'flac', 'm4a'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz']
}

# 构建所有扩展名的正则表达式模式
all_extensions = []
for category in supported_extensions.values():
    all_extensions.extend(category)
    
# 全局资源缓存（避免重复查找）
resource_cache = {}


# 只在 Windows 平台导入 pywin32 模块
if os.name == 'nt':
    try:
        import win32file
        import pywintypes
    except ImportError:
        print("请安装 pywin32 库以修复目录的时间戳")  


def fix_directory_timestamps(src_dir: str, dst_dir: str):
    """
    修复 Windows 下目标目录时间戳（创建、修改、访问）
    """
    if not os.path.exists(dst_dir):
        print(f"无法修复时间戳：目标目录不存在 {dst_dir}")
        return

    try:
        src_stat = os.stat(src_dir)
        ctime = pywintypes.Time(src_stat.st_ctime)
        atime = pywintypes.Time(src_stat.st_atime)
        mtime = pywintypes.Time(src_stat.st_mtime)

        handle = win32file.CreateFile(
            dst_dir,
            win32file.GENERIC_WRITE,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_FLAG_BACKUP_SEMANTICS,  # 用于操作目录
            None
        )
        try:
            win32file.SetFileTime(handle, ctime, atime, mtime)
        finally:
            handle.close()
    except Exception as e:
        print(f"修复目录时间戳失败 {dst_dir}: {e}")


def robocopy_copy(src: str, dst: str) -> bool:
    """
    Windows 系统下使用 robocopy 复制文件或目录，保留时间戳（创建、修改、访问）
    :param src: 源文件或目录路径
    :param dst: 目标路径（文件或目录）
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"源路径不存在: {src}")

    is_file = os.path.isfile(src)
    
    # 如果目标是文件且源是文件，robocopy 不支持，需后处理
    dst_is_file = (
        not dst.endswith(os.sep) and
        os.path.splitext(dst)[1] != '' and
        not os.path.isdir(dst)
    )
    
    if is_file:
        parent_src = os.path.dirname(src)
        parent_dst = os.path.dirname(dst) if dst_is_file else dst
        file_list = [os.path.basename(src)]
    else:
        parent_src = src
        parent_dst = dst
        file_list = []

    # 创建目标父目录
    os.makedirs(parent_dst, exist_ok=True)

    # 优先使用 shell=False + 列表
    # 构建 robocopy 命令
    cmd = [
        "robocopy",
        parent_src,
        parent_dst,
        *file_list,
        "/COPY:DAT",     # 复制数据、属性、时间戳
        "/DCOPY:T",      # 复制目录时间戳（创建、修改、访问）
        # "/E",            # 包含子目录（含空目录）
        "/R:0", "/W:0",  # 不重试
        "/NFL", "/NDL",  # 不输出文件和目录
        "/NJH", "/NJS",  # 无作业头和尾
        "/NC", "/NS",    # 不输出文件大小、摘要
        "/IS",           # 复制相同文件（不跳过）
        "/IT"            # 复制相同文件的时间戳（即使数据没变）
    ]

    if not is_file:
        cmd.append("/E")  # 包含子目录（含空目录）

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,    # 5分钟超时
            shell=False     # 避免 shell 注入
            # shell=True      # 支持内建命令和变量替换
        )

        # robocopy 返回码：0~7 成功，8+ 失败
        # 0: 无复制（文件已最新）
        # 1: 成功复制文件
        # 2: 有额外文件
        # 3: 1+2
        # 8+: 严重错误
        success = result.returncode < 8

        # 输出日志
        if result.stdout.strip():
            print("=== robocopy 输出 ===\n" + result.stdout)
        if result.stderr.strip():
            print("=== robocopy 错误 ===\n" + result.stderr)

        if success:
            # 如果目标是文件，robocopy 实际复制到了目标目录，替换成目标文件名
            if is_file and dst_is_file:
                temp_path = os.path.join(parent_dst, os.path.basename(src))
                if os.path.exists(temp_path):
                    os.replace(temp_path, dst)
            # 修复目录时间戳
            if os.path.isdir(dst) and os.path.isdir(src):
                fix_directory_timestamps(src, dst)
        else:
            print(f"复制失败（返回码: {result.returncode}")

        return success

    except subprocess.TimeoutExpired:
        print("robocopy 执行超时")
        return False
    except Exception as e:
        print(f"robocopy 执行失败: {e}")
        return False


def remote_path_type(user_host: str, remote_path: str) -> Optional[str]:
    """
    检查远程路径类型
    :return: 'file', 'directory', 'link', 'not_exists', None(执行失败)
    """
    quoted = shlex.quote(remote_path)
    check_cmd = (
        f"if [ -d {quoted} ]; then echo 'directory'; "
        f"elif [ -f {quoted} ]; then echo 'file'; "
        f"elif [ -L {quoted} ]; then echo 'link'; "
        f"else echo 'not_exists'; fi"
    )
    cmd = ["ssh", user_host, check_cmd]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        out = result.stdout.strip()
        if out in ('file', 'directory', 'link', 'not_exists'):
            return out
        return None
    except Exception as e:
        print(f"SSH 检查失败: {e}")
        return None


def ensure_remote_dir(user_host: str, remote_path: str) -> bool:
    """通过 SSH 确保远程目录存在"""
    cmd = ["ssh", user_host, f"mkdir -p {shlex.quote(remote_path)}"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0
    except Exception as e:
        print(f"创建远程目录失败: {e}")
        return False


def rsync_copy(src: str, dst: str) -> bool:
    """
    Unix 系统，使用 rsync 复制保留修改、访问时间戳
    支持：本地到本地、本地到远程的复制
    :param src: 源文件或目录路径
    :param dst: 目标路径（文件或目录），支持 user@host:/path
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"源路径不存在: {src}")

    src_path = src.rstrip('/') + '/' if os.path.isdir(src) else src

    # 检查是否是远程路径
    # is_remote = '@' in dst and ':' in dst
    # 使用正则解析远程路径（支持 IPv6）
    remote_match = r'^((?P<user>[^@]+)@)?(?P<host>\[[^\]]+\]|[^:]+):(?P<path>/.*)$'
    match = re.match(remote_match, dst)
    is_remote = bool(match)

    if is_remote:
        user = match.group('user') or ''
        host = match.group('host')
        user_host = f"{user}@{host}" if user else host
        remote_path = match.group('path').rstrip('/')
        remote_type = remote_path_type(user_host, remote_path)

        if remote_type is None:
            raise RuntimeError(f"无法确定远程路径类型：{dst}")

        if os.path.isdir(src):
            # 如果源是目录，则目标路径要确保是目录
            if remote_type in ("directory", "link"):
                final_dst = f"{user_host}:{remote_path}/"
            elif remote_type == 'not_exists':
                ensure_remote_dir(user_host, remote_path)
                final_dst = f"{user_host}:{remote_path}/"
            else:
                raise RuntimeError(f"源是目录，目标不能是文件: {dst}")
        else:  # 源是文件
            bname = os.path.basename(src)
            if remote_type == 'not_exists':
                if dst.endswith('/') or os.path.splitext(remote_path)[1] == '':
                    # 目标是目录
                    target_dir = remote_path.rstrip('/')
                    ensure_remote_dir(user_host, target_dir)
                    final_dst = f"{user_host}:{target_dir}/{bname}"
                else:
                    parent_remote = os.path.dirname(remote_path)
                    if parent_remote.strip('/') != "":  # 避免根目录
                        ensure_remote_dir(user_host, parent_remote)
                    final_dst = f"{user_host}:{remote_path}"
            elif remote_type == 'directory':
                final_dst = f"{user_host}:{remote_path}/{bname}"
            else:
                final_dst = f"{user_host}:{remote_path}"
    else:
        if os.path.isdir(src):
            # 源是目录，目标路径要确保是目录
            final_dst = dst.rstrip("/") + "/"
            os.makedirs(final_dst, exist_ok=True)
        else:
            # 源是文件，目标路径判断
            if dst.endswith('/') or os.path.splitext(dst)[1] == '':
                dst = dst.rstrip('/')
                final_dst = os.path.join(dst, os.path.basename(src))
            else:
                final_dst = dst
            os.makedirs(os.path.dirname(final_dst), exist_ok=True)

    # 构建 rsync 命令
    cmd = ["rsync", "-a", "--atimes", src_path, final_dst]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300
        )
        if result.returncode == 0:
            return True

        outerr = result.stderr.lower()

        if "permission denied" in outerr or "rsync error" in outerr:
            cmd_sudo = ["sudo"] + cmd
            try:
                result2 = subprocess.run(
                    cmd_sudo,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300
                )
                return result2.returncode == 0
            except Exception:
                pass
        print("rsync 失败:", result.stderr.strip())
        return False

    except subprocess.TimeoutExpired:
        print("rsync 执行超时")
        return False
    except FileNotFoundError:
        print("未找到 rsync，回退到 shutil.copy2")
        return fallback_copy(src, dst)
    except Exception as e:
        print(f"rsync 复制失败: {e}")
        return False


def fallback_copy(src: str, dst: str) -> bool:
    """回退复制方案（使用 shutil.copy2，保留基本时间戳）"""
    try:
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst, copy_function=shutil.copy2)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"回退复制失败: {e}")
        return False


def copy_with_timestamps(src: str, dst: str) -> bool:
    """统一接口：复制并保留时间戳"""
    if os.name == 'nt':  # Windows 
        return robocopy_copy(src, dst)
    else:  # Unix/Linux/macOS
        return rsync_copy(src, dst)
    

def copy_files_with_timestamps(source_note_dir, ignored_extensions=None):
    """复制源目录中所有文件到目标，并保留原始时间戳"""
    # try:
    #     from copy_with_timestamps import copy_with_timestamps
    # except ImportError:
    #     logger.error("无法导入 copy_with_timestamps 模块，请确保模块存在。")
    
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
        
        if os.path.isdir(source_path):
            copy_with_timestamps(source_path, destination_path)
            logger.info(f"复制目录：{source_path} -> {destination_path}")
        else:
            copy_with_timestamps(source_path, destination_path)
            logger.info(f"复制文件：{source_path} -> {destination_path}")


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

# Markdown 链接正则（支持路径/标题/块/尺寸，描述去掉尾空格）
markdown_link_regex = r"""
    (!)?                           # 1: 可选 "!"（embed）
    \[
        ([^\]\|\n]*?)\s*           # 2: 描述/别名（去尾空格）
        (?:\s*\|\s*
            (\d{1,4}(?:x\d{1,4})?) # 3: 尺寸（400 或 400x300）
        )?
    \]
    \(
        ([^()\n#^]+?)?             # 4: 路径（可选）
        (?:\#(?:
            (?!\^)([^()\n#^]+)     # 5: 标题（#xxx）
          | \^([^()\n#]+)          # 6: 块标识符（#^xxx）
        ))?
    \)
"""

wiki_link_pattern = re.compile(wiki_link_regex, re.VERBOSE)
markdown_link_pattern = re.compile(markdown_link_regex, re.VERBOSE)


# def is_image(path: str) -> bool:
#     """判断是否为图片链接"""
#     extensions_with_dot = tuple(f'.{ext}' for ext in IMAGE_EXT)
#     return path.lower().endswith(extensions_with_dot)


def parse_desc_size(raw_desc_or_size, size_group):
    """解析图片描述和尺寸"""
    if not size_group:
        if raw_desc_or_size and re.match(r'^\d{1,4}(?:x\d{1,4})?$', raw_desc_or_size):
            return None, raw_desc_or_size
        return raw_desc_or_size, None

    return raw_desc_or_size, size_group


def extract_wiki_links(text):
    """Obsidian Wiki 链接解析"""
    matches = []
    for match in wiki_link_pattern.finditer(text):
        # isImage = is_image(match.group(2))
        # if isImage:
        #     print("image_path:", match.group(2))
        full_match = match.group(0)
        # print("full_match:", full_match)
        embed = bool(match.group(1))
        path = match.group(2)
        title = match.group(3)
        block_id = match.group(4)
        desc = match.group(6)
        size = match.group(5)
        if desc and size:
                desc = 'a' + desc + 'b'
                size = 'c' + size + 'd'
                
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


def extract_markdown_links(text):
    """Obsidian Markdown 链接解析"""
    matches = []
    for match in markdown_link_pattern.finditer(text):
        # print("match.groups():", match.groups())
        full_match = match.group(0)
        embed = bool(match.group(1))
        raw_desc_or_size = match.group(2)
        size_group = match.group(3)
        path = match.group(4)
        desc, size = parse_desc_size(raw_desc_or_size, size_group)
        title = match.group(5)
        block_id = match.group(6)
        
        matches.append({
            'full_match': full_match,
            'type': 'markdown',
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
    在仓库中查找资源文件
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
            parts.append(updated_content[last_end:match['start']])
            resource_path = match['path']
            
            if not resource_path:
                resource_path = note_file_path
                
            resource_name = os.path.basename(resource_path)
            resource_relpath = find_resource_file(target_note_dir, resource_path, current_note_dir)
            
            if resource_relpath:
                # 计算相对仓库根目录的路径
                rel_path = resource_relpath.replace('\\', '/')  # 统一使用正斜杠
                # print('rel_path:', rel_path)
                
                # 计算外部链接
                full_url = f'{external_link_prefix}{rel_path}'
                
                # 构建新的链接内容
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


def convert_markdown_links(note_file_path, updated_content):
    """
    将 Markdown 链接转换为 Web 可访问的外部链接格式
    """
    # 当前笔记所在目录
    current_note_dir = os.path.dirname(note_file_path)
    
    # 提取所有资源链接和图片匹配项
    matches = extract_markdown_links(updated_content)
    
    # 按起始位置正向排序
    matches.sort(key=lambda m: m['start'])
    
    # 使用列表拼接构建新内容
    parts = []
    last_end = 0  # 记录上次处理结束位置
    
    if matches: 
        for match in matches:
            type = match['type']
            embed = match['embed']
            resource_path = match['path']
            title = match['title']
            block_id = match['block_id']
            desc = match['desc']
            size = match['size']
            if size:
                if 'x' in size:
                    width, height = size.split('x')[0], size.split('x')[1]
                else:
                    width, height = size, None
            else:
                width, height = None, None
            
            # 添加匹配前的文本
            parts.append(updated_content[last_end:match['start']])

            if not resource_path:
                resource_path = note_file_path

            # 处理本地资源链接
            if not is_web_link(resource_path):
                resource_path = decode_url_space_only(resource_path)
                resource_name = os.path.basename(resource_path)
                
                # 查找资源文件的相对路径
                resource_relpath = find_resource_file(target_note_dir, resource_path, current_note_dir)
                
                # 如果找到资源，生成外部链接格式
                if resource_relpath:
                    # 计算相对仓库根目录的路径
                    rel_path = resource_relpath.replace('\\', '/')  # 统一使用正斜杠
                    
                    # 计算外部链接
                    full_url = f'{external_link_prefix}{rel_path}'
                    
                    if match['title'] and not match['block_id']:
                        full_url += f'#{match["title"]}'
                    # if (not match['title']) and match['block_id']:
                    #     full_url += f'#^{match["block_id"]}'
                    full_url = decode_url_space_only(full_url)
                    full_url = encode_url_space_only(full_url)
                        
                    file_type = get_file_type(resource_name)
                    
                    if file_type == 'image':
                        alt_text = desc or resource_name
                        alt_text = decode_url_space_only(alt_text)
                        if embed:
                            # 生成嵌入式图片的 HTML
                            if width and height:
                                full_path = f'<img src="{full_url}" width="{width}" height="{height}" alt="{alt_text}" />'
                            elif width:
                                full_path = f'<img src="{full_url}" width="{width}" alt="{alt_text}" />'
                            elif height:
                                full_path = f'<img src="{full_url}" height="{height}" alt="{alt_text}" />'
                            else:
                                full_path = f'<img src="{full_url}" alt="{alt_text}" />'
                        else:
                            # 生成图片的 Markdown 链接
                            if width and height:
                                full_path = f'[{alt_text}|{width}x{height}]({full_url})'
                            elif width:
                                full_path = f'[{alt_text}|{width}]({full_url})'
                            elif height:
                                full_path = f'[{alt_text}|{height}]({full_url})'
                            else:
                                full_path = f'[{alt_text}]({full_url})'     
                    else:
                        # 生成其他文件的 Markdown 链接
                        display_text = desc or title or block_id or resource_name
                        display_text = decode_url_space_only(display_text)
                        if embed:
                            full_path = f'![{display_text}]({full_url})'
                        full_path = f'[{display_text}]({full_url})'
                else:
                    full_path = match['full_match']
                    logger.warning(f"⚠️ 警告: 资源未找到： {resource_path}")
                    logger.warning(f"📝 在笔记中: {note_file_path}")
                    logger.warning(f"⏩ 保留原始链接：{full_path}")
            
            else:
                full_path = match['full_match']
 
            # 添加匹配到的链接到内容片段
            parts.append(full_path)
            last_end = match['end']
            
        # 添加最后一个片段
        parts.append(updated_content[last_end:])
        
        # 拼接所有部分
        updated_content = ''.join(parts)
    
    return updated_content


def update_resource_links(note_file_path):
    """
    更新文件中的资源链接为外部访问链接
    :param note_file_path: 笔记文件路径
    """
    with open(note_file_path, 'r', encoding='utf-8', newline='') as file:
        try:
            content = file.read()
            # print("content[:100]:", content[:100])  # 打印前100个字符作为测试
        except IOError as e:
            print(f"IOError: {e}")
        except UnicodeDecodeError as e:
            print(f"UnicodeDecodeError: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    # 提取代码内容并用占位符替换
    updated_content, code_blocks = save_code_blocks(content)
    
    # 转换为 Markdown 链接格式
    updated_content = convert_wiki_links(note_file_path, updated_content)
    
    # 转换为 Web 可访问的外部链接格式
    updated_content = convert_markdown_links(note_file_path, updated_content)
    
    # 恢复代码块
    updated_content = restore_code_blocks(updated_content, code_blocks)

    with open(note_file_path, 'w', encoding='utf-8', newline='') as file:
        try:
            file.write(updated_content)
            # print(f"✅ 成功更新文件: {note_file_path}")
        except Exception as e:
            logger.error(f"⚠️ 写入文件时发生错误:{e}")


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
