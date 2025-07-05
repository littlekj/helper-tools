"""
需求目标

- 将 Markdown 文件中引用的本地资源路径（如图片、文件）自动转换为可通过 Web 访问的外部 URL 格式

处理范围

1. Obsidian 特有的 Wiki 链接格式：
   - 普通文件链接：`[[文件路径]]`
   - 图片资源链接：`![[图片路径]]`
   - 支持带锚点的链接：`[[文件路径#锚点]]`
   - 支持带别名的链接：`[[文件路径|别名]]`

2. 标准 Markdown 链接格式：
   - 普通超链接：`[描述](文件路径)`
   - 图片链接：`![描述](图片路径)`
   - 支持带锚点的链接：`[描述](文件路径#锚点)`
   - 支持图片尺寸声明：`![200x300](图片.png)`

"""
import os
import shutil
import re
from urllib.parse import quote
import sys
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('ObsidianLinkConverter')

# 配置路径
source_folder = "Default"
# source_note_dir = fr'D:\Obsidian\{source_folder}'
source_note_dir = fr'D:\Obsidian\bak\Default - origin'
target_note_dir = fr'D:\Obsidian\Middle\{source_folder}'
# new_image_dir = fr'D:\Obsidian\Middle\linkres'
# new_image_subfolder = "obsidian"
external_link_prefix = r'https://raw.githubusercontent.com/littlekj/linkres/master/obsidian/'
# external_link_prefix = '/'  # 前缀添加 / 生成绝对路径，拼接 GitHub 仓库地址便于 Web 访问


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
    
# 匹配 Obsidian 特有的 Wiki 链接格式
# 格式：[[文件]] 或 ![[文件]]
link_regex = re.compile(
    r'(!?)\[\[([^\]\|\n#]*?)(?:#([^\]\|\n]*?))?(?:\|([^\]\|\n]*?))?(?:\|(\d+)(?:x(\d+))?)?\]\]',
    re.MULTILINE
)

# 匹配标准的 Markdown 超链接语法（包括图片链接）
# 如 [描述](链接) 或 ![描述](链接)
link_pattern = r'''
    (!)?                    # 图片标识（可选）
    \[                      # 开始括号 [
    (                       # 捕获组：链接文本/图片描述
        (?:                 # 非捕获组（处理尺寸或别名部分）
            [^\]\|\n]*      # 除 ]、|、换行外的任意字符
            (?:\|           # 分隔符 |（可选）
                [^\]\n]*    # 除 ]、换行外的任意字符
            )?              # 分隔符部分结束
        )                   # 非捕获组结束
    )                       # 捕获组结束
    \]                      # 结束括号 ]
    \(                      # 开始括号 (
    (                       # 捕获组：URL/路径
        (?:                 # 允许括号出现在URL中
            [^()\n]         # 非括号字符
            |               # 或
            \([^()\n]*\)    # 成对的括号内容
        )*                  # 重复多次
        [^)\n]*             # 最后可以有一些非括号字符
    )                       # URL捕获组结束
    \)                      # 结束括号 )
'''

compiled_pattern = re.compile(link_pattern, re.VERBOSE)


# 代码块匹配正则（同时匹配多行代码块和单行内联代码）
code_pattern = re.compile(
    r'(?s)(```.*?```|~~~.*?~~~|`[^`]+?`)',
    re.DOTALL
)

# 全局资源缓存（避免重复查找）
resource_cache = {}

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

# 确认删除目标目录
safe_remove_if_exists(target_note_dir)
# safe_remove_if_exists(new_image_dir)

# 创建新目录
os.makedirs(target_note_dir, exist_ok=True)
# os.makedirs(new_image_dir, exist_ok=True)


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

        remove_if_exists(destination_path)
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

def get_file_type(file_path):
    """根据文件扩展名获取文件类型"""
    ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
    for file_type, extensions in supported_extensions.items():
        if ext in extensions:
            return file_type
    return 'other'


def save_code_blocks(content):
    """
    提取所有代码块和内联代码，并用占位符替代
    """
    # 提取所有代码块和内联代码
    code_blocks = code_pattern.findall(content)
    
    # 用占位符替代代码块和内联代码
    content = code_pattern.sub('__CODE_BLOCK__', content)

    return content, code_blocks


def restore_code_blocks(content, code_blocks):
    """
    按顺序将占位符替换回代码块和内联代码
    """
    for code_block in code_blocks:
        content = content.replace('__CODE_BLOCK__', code_block, 1)
    return content


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


def extract_resource_links(content):
    """
    提取笔记中资源的链接
    """
    matches = []
    for match in compiled_pattern.finditer(content):
        is_image = match.group(1) is not None
        link_text = match.group(2)
        url = match.group(3).strip()  # 去除首尾空格
        url = decode_url_space_only(url)
        size_info = None
        alt_text = link_text
        
        if is_image:
            if re.match(r'^\d+$', link_text):
                width = link_text.split('x')
                size_info = f"width={width}"
                
            elif re.match(r'^\d+x\d+$', link_text):
                width, height = link_text.split('x')
                size_info = f"width={width}, height={height}"
                
            elif '|' in link_text:
                parts = link_text.split('|', 1)
                alt_text = parts[0]
                size_part = parts[1]
                
                if re.match(r'^\d+x\d+$', size_part):
                    width, height = size_part.split('x')
                    size_info = f"width={width}, height={height}"
                elif re.match(r'^\d+$', size_part):
                    size_info = f"width={size_part}"
                    
        match_info = {
            'type': 'image' if is_image else 'link',
            'full_match': match.group(0),
            'text': alt_text,
            'url': url,
            'size': size_info,
            'start': match.start(),
            'end': match.end()
        }
        matches.append(match_info)
        
    return matches

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

def convert_obsidian_wiki_links(note_file_path, content):
    """
    将 Obsidian 的 wiki 链接转换为标准 Markdown 链接格式
    """
    # 当前笔记所在目录
    current_note_dir = os.path.dirname(note_file_path)

    def replacement(match):
        """处理正则表达式匹配的资源链接"""
        full_match = match.group(0)  # 完整匹配
        sign = match.group(1)  # 匹配开头的 !（可选）
        resource_path = match.group(2)  # 资源路径（可能为空）
        anchor = match.group(3) if match.group(3) else ''  # 锚点（可选）
        alias_or_param = match.group(4) if match.group(4) else ''  # 别名或参数（可选）
        width = match.group(5) if match.group(5) else ''  # 图片宽度（可选）
        height = match.group(6) if match.group(6) else ''  # 图片高度（可选）
        
        # 形如：[[#标题|见上文]]，文件内上下文的链接
        if not resource_path:
            resource_path = note_file_path

        resource_name = os.path.basename(resource_path)
        resource_relpath = find_resource_file(target_note_dir, resource_path, current_note_dir)

        if not resource_relpath:
            logger.warning(f"⚠️ 警告: 资源未找到： {resource_path}")
            logger.warning(f"📝 在笔记中: {note_file_path}")
            logger.warning("⏩ 跳过此资源链接")
            return full_match  # 保留原始链接

        # 计算相对仓库根目录的路径
        rel_path = resource_relpath.replace('\\', '/')  # 统一使用正斜杠

        # 生成外部链接格式
        # encode_path = quote(rel_path, encoding='utf-8')
        # external_link = f'{external_link_prefix}{rel_path}'
        external_link = f'{rel_path}'

        # 添加锚点（如果存在）
        if anchor:
            # encoded_anchor = quote(anchor, encoding='utf-8')
            external_link += f'#{anchor}'
        
        # 对空格进行编码
        external_link = encode_url_space_only(external_link)
        
        # 获取文件类型
        file_type = get_file_type(resource_path)

        # 根据文件类型构建不同的链接
        if file_type == 'image':
            # 图片处理：支持尺寸参数
            alt_text = alias_or_param or resource_name
            if width and height:
                return f'<img src="{external_link}" width="{width}" height="{height}" alt="{alt_text}" />'
            elif width:
                return f'<img src="{external_link}" width="{width}" alt="{alt_text}" />'
            elif height:
                return f'<img src="{external_link}" height="{height}" alt="{alt_text}" />'
            else:
                return f'![{alt_text}]({external_link})'
        else:
            # 其他文件类型处理：支持别名
            display_text = alias_or_param or anchor or resource_name
            if full_match.startswith('!'):
                return f'![{display_text}]({external_link})'
            return f'[{display_text}]({external_link})'

    # 使用正则表达式替换资源链接
    updated_content = link_regex.sub(replacement, content)
    
    return updated_content
    

def convert_standard_markdown_links(note_file_path, content):
    """
    将标准 Markdown 链接转换为 Web 可访问的外部链接格式
    """
    # 当前笔记所在目录
    current_note_dir = os.path.dirname(note_file_path)
    
    # 提取所有资源链接和图片匹配项
    matches = extract_resource_links(content)
    
    # 按起始位置正向排序
    matches.sort(key=lambda m: m['start'])
    
    # 使用列表拼接构建新内容
    parts = []
    last_end = 0  # 记录上次处理结束位置
    
    for match in matches:
        full_match = match['full_match']  # 完整匹配
        type = match['type']  # 链接类型（link 或 image）
        text = match['text']  # 链接文本
        url = match['url']  # 链接地址
        size = match['size']  # 尺寸信息
        start = match['start']  # 起始位置
        end = match['end']  # 结束位置
        
        # 添加匹配前的文本
        parts.append(content[last_end:start])
        
        # 默认保留原始链接
        replacement_str = full_match
        
        # 处理本地资源链接
        if not is_web_link(url):
            resource_relpath = None
            anchor = None
            
            # 本地可能存在非图片格式：![alt text](file://path/to/file#anchor)
            # 处理内部锚点链接
            if url.startswith('#'):
                anchor = url[1:]
                resource_path = note_file_path
                resource_name = os.path.basename(resource_path)
                # 使用当前笔记目录计算相对路径
                resource_relpath = os.path.relpath(resource_path, target_note_dir)
            else:  
                # 处理带锚点的文件链接
                if '#' in url:
                    url_parts = url.split('#', 1)
                    resource_path = url_parts[0]
                    anchor = url_parts[1]
                # 处理普通文件链接
                else:
                    resource_path = url
                
                resource_name = os.path.basename(resource_path)

                # 查找资源文件的相对路径
                resource_relpath = find_resource_file(target_note_dir, resource_path, current_note_dir)
            
            # 如果找到资源，生成外部链接格式
            if resource_relpath:
                # 计算相对仓库根目录的路径
                rel_path = resource_relpath.replace('\\', '/')  # 统一使用正斜杠
                
                # 计算外部链接
                extended_link = f'{external_link_prefix}{rel_path}'
                
                # 对空格进行编码
                extended_link = encode_url_space_only(extended_link)
                
                # 添加锚点（如果存在）
                if anchor:
                    encoded_anchor = encode_url_space_only(anchor)
                    extended_link += f'#{encoded_anchor}'
                
                # 构建外部链接形式
                if type == 'link':
                    display_text = text or anchor or resource_name
                    replacement_str = f'[{display_text}]({extended_link})'  
                
                elif type == 'image':
                    alt_text = text or resource_name
                    if size:
                        replacement_str = f'<img src="{extended_link}" {size} alt="{alt_text}" />'
                    else:
                        replacement_str = f'![{alt_text}]({extended_link})'
                
            else:
                logger.warning(f"⚠️ 警告: 资源未找到： {resource_path}")
                logger.warning(f"📝 在笔记中: {note_file_path}")
                logger.warning("⏩ 保留原始链接")
 
        # 添加替换后的内容
        parts.append(replacement_str)
        last_end = end  # 更新上次处理结束位置
        
    # 添加最后一段文本
    parts.append(content[last_end:])
    
    # 拼接所有部分
    updated_content = ''.join(parts)
    
    return updated_content

def update_resource_links(note_file_path):
    """
    更新文件中的资源链接为外部访问链接
    :param note_file_path: 笔记文件路径
    """
    with open(note_file_path, 'r', encoding='utf-8', newline='') as file:
        content = file.read()

    # 提取代码内容并用占位符替换
    updated_content, code_blocks = save_code_blocks(content)
    
    # 转换为标准 Markdown 链接格式
    updated_content = convert_obsidian_wiki_links(note_file_path, updated_content)
    
    # 转换为 Web 可访问的外部链接格式
    updated_content = convert_standard_markdown_links(note_file_path, updated_content)
    
    # 恢复代码块
    updated_content = restore_code_blocks(updated_content, code_blocks)

    with open(note_file_path, 'w', encoding='utf-8', newline='') as file:
        file.write(updated_content)


def main():
    """执行文件复制和更新操作"""
    logger.info("开始处理...")
    logger.info(f"源目录: {source_note_dir}")
    logger.info(f"目标目录: {target_note_dir}")

    # 复制文件（忽略特定扩展名）
    ignored_extensions = ['.tmp', '.DS_Store']
    copy_files(source_note_dir, ignored_extensions)

    # 更新笔记中的资源链接
    updated_count = iterate_files(target_note_dir)

    logger.info("\n✅ 处理完成！")
    logger.info(f"共处理 {updated_count} 个笔记: {target_note_dir}")


if __name__ == "__main__":
    # 设置日志级别
    logger.setLevel(logging.INFO)
    main()
