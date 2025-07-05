"""
需求：
- 将 Markdown 笔记中的本地资源内部链接格式转换为标准的 Markdown 链接格式
- 处理所有类型的 Obsidian 链接：[[文件]] 和 ![[文件]]

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
# external_link_prefix = r'https://raw.githubusercontent.com/littlekj/linkres/master/obsidian/'
# external_link_prefix = '/'  # 前缀添加 / 生成绝对路径，拼接 GitHub 仓库地址便于 Web 访问
external_link_prefix = ''

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
extensions_pattern = '|'.join(all_extensions)

# 正则表达式匹配所有 Obsidian 链接
# test_cases = [
#     "[[#标题]]",                  # 纯锚点
#     "[[#标题|见上文]]",            # 锚点 + 别名
#     "[[页面]]",                   # 纯资源
#     "[[页面#标题]]",               # 资源 + 锚点
#     "[[页面#标题|显示文本]]",       # 资源 + 锚点 + 别名
#     "[[页面|显示文本]]",           # 资源 + 别名
#     "![[图片.png|200]]",          # 图片 + 宽度
#     "![[图片.png|200x300]]",      # 图片 + 尺寸
#     "![[图片.png|别名|200x300]]",  # 图片 + 别名 + 尺寸
# ]

link_regex = re.compile(
    r'(!?)\[\[([^\]\|\n#]*?)(?:#([^\]\|\n]*?))?(?:\|([^\]\|\n]*?))?(?:\|(\d+)(?:x(\d+))?)?\]\]',
    re.MULTILINE
)

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

# 创建新目录
os.makedirs(target_note_dir, exist_ok=True)

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


def update_resource_links(note_file_path):
    """
    更新文件中的资源链接为外部链接
    :param note_file_path: 笔记文件路径
    """
    with open(note_file_path, 'r', encoding='utf-8', newline='') as file:
        content = file.read()

    # 提取代码内容并用占位符替换
    content, code_blocks = save_code_blocks(content)
    
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
        resource_rel_path = find_resource_file(target_note_dir, resource_path, current_note_dir)

        if not resource_rel_path:
            logger.warning(f"⚠️ 警告: 资源未找到： {resource_path}")
            logger.warning(f"📝 在笔记中: {note_file_path}")
            logger.warning("⏩ 跳过此资源链接")
            return full_match  # 保留原始链接

        # 计算相对仓库根目录的路径
        rel_path = resource_rel_path.replace('\\', '/')  # 统一使用正斜杠

        # 计算外部链接
        # encode_path = quote(rel_path, encoding='utf-8')
        external_link = f'{external_link_prefix}{rel_path}'

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
