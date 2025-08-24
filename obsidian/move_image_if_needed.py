"""
需求目标

- Obsidian 中 md 文件移动后，将文件中插入的图片资源移动到对应子目录。

- Obsidian 文档库的默认目录结构：
  - .\source_folder
  - .\source_folder\file.md
  - .\source_floder\res\image.png

- 遍历给定的文件夹，检查每个 md 文件中的图片链接，如果图片不在指定路径，则尝试从默认文件夹查找图片并移动图片到指定子目录。

处理 Obsidian 文档中的链接格式范围

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

匹配规则

对于链接格式，以叹号开头的有可能是嵌入文件，不以叹号开头的也有可能是图片资源。

定义匹配规则时，优选考虑匹配链接格式中的各部分内容，后续根据需要过滤普通文件和图片资源。

描述和尺寸处理思路：

- 正则匹配分离描述和尺寸：
    - 如果存在 `|`，`|` 后面的内容优先作为尺寸。
    - 如果不存在 `|`，捕获原始整体内容为 raw，分配到描述分组，尺寸组为 None。
- 在 Python 端再做判断：
    - 当整体内容 raw 符合 WxH 或 W 格式时，则作为尺寸。
    - 否则作为描述。

这种方式比把所有逻辑写到正则里更灵活，尤其是考虑只指定宽度或 WxH 的情况。

链接格式过滤

- 忽略代码块和行内代码中的链接
    - 需要在匹配链接格式前对代码块特殊处理，避免匹配受影响
    - 对文档中的代码块匹配并用占位符处理，然后在处理匹配链接
    - 最后，恢复代码块的内容
- 忽略非图片 ULR 格式链接
- 忽略 Web 访问的外部 URL 格式链接
"""

import os
import shutil
import re
import logging
from urllib.parse import urlparse, unquote, quote
import argparse
import subprocess
import shlex
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 指定待遍历的文件夹和默认查找图片的文件夹路径
# source_folder = search_folder = r'D:\Obsidian\Default'
# 备份原始资源目录
# source_folder_bak = r'D:\Obsidian\Middle\\Backup'

    
def copy_files(src: str, dst: str) -> bool:
    """复制备份文件"""
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
        print(f"复制失败：{e}")
        return False  
    

def copy_files_with_timestamps(source_note_dir, target_note_dir, ignored_extensions=None):
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


IMAGE_EXT = ('png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'svg')

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


def is_image(path: str) -> bool:
    """判断是否为图片链接"""
    extensions_with_dot = tuple(f'.{ext}' for ext in IMAGE_EXT)
    return path.lower().endswith(extensions_with_dot)


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
        # print("match.groups():", match.groups())
        path = match.group(2) or None
        isImage = path and is_image(match.group(2))
        if isImage:
            # print("image_path:", match.group(2))
            embed = bool(match.group(1))
            title = match.group(3)
            block_id = match.group(4)
            desc = match.group(6)
            size = match.group(5)

            matches.append({
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
    isImage = False
    for match in markdown_link_pattern.finditer(text):
        # print("match.groups():", match.groups())
        path = match.group(4)
        if path and not is_web_link(path):
            isImage = is_image(match.group(4))
            if isImage:
                embed = bool(match.group(1))
                raw_desc_or_size = match.group(2)
                size_group = match.group(3)
                path = match.group(4)
                desc, size = parse_desc_size(raw_desc_or_size, size_group)
                title = match.group(5)
                block_id = match.group(6)
                
                
                matches.append({
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


def find_image_in_directory(search_folder, image_name, excepted_image_path):
    """
    在指定目录及其子目录中查找图片文件，找到后移动到目录路径
    :param directory: 指定搜索目录
    :param image_name: 图片文件名
    :param excepted_image_path: 图片移动到的预期目录
    :return: 是否找到并移动图片
    """
    for root, dirs, files in os.walk(search_folder):
        if image_name in files:
            searched_image_path = os.path.join(root, image_name)
            print(f'Image found: {searched_image_path}')
            try:
                shutil.move(searched_image_path, excepted_image_path)
                return True
            except Exception as e:
                print(f'Image movement failed: {e}')
    return False


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


def update_image_resources_and_links(note_file_path, content, matches):
    """
    更新 Obsidian 图片资源位置以及图片链接
    """
    # 当前笔记所在目录
    current_note_dir = os.path.dirname(note_file_path)
    
    # print("matches:", matches)
    # 按链接在文档中的位置排序
    matches.sort(key=lambda m: m['start'])

    parts = []  # 用于存储处理后的内容片段
    last_end = 0   # 记录上一次匹配结束的位置
    
    updated = False  # 用于标记是否有更新

    for match in matches:
        parts.append(content[last_end:match['start']])
        flag = False
        if match['path']:
            image_path = match['path']
            # print(f'Processing image "{image_path}" in file "{note_file_path}"')
            image_path = unquote(image_path)
            image_name = os.path.basename(image_path)
            excepted_image_dir = os.path.join(current_note_dir, 'res')
            os.makedirs(excepted_image_dir, exist_ok=True)
            excepted_image_path = os.path.join(
                excepted_image_dir, image_name)

            if not os.path.isfile(excepted_image_path):
                flag = find_image_in_directory(search_folder, image_name, excepted_image_path)
                if flag:
                    updated = True  # 如果图片被成功移动，标记为更新
                    print(
                        f'Image "{image_name}" moved to "{excepted_image_path}"')
                else:
                    print(
                        f'Image "{image_name}" not found. Please check the original link "{match["path"]}" in file "{note_file_path}"'
                    )

        # 更新文档中图片链接至最新
        if match['type'] == 'wiki':
            if match['embed']:
                full_path = f'![['
            else:
                full_path = f'[['
            if match['path'] and flag:
                excepted_image_path = 'res/' + image_name
                full_url = f'{excepted_image_path}'
            elif match['path'] and not flag:
                full_url = f'{match["path"]}'
            if match['title'] and not match['block_id']:
                full_url += f'#{match["title"]}'
            if (not match['title']) and match['block_id']:
                full_url += f'#^{match["block_id"]}'
            full_path += full_url
            if match['desc']:
                full_path += f'|{match["desc"]}'
            if match['size']:
                full_path += f'|{match["size"]}'
            full_path += f']]'
        elif match['type'] == 'markdown':
            if match['embed']:
                full_path = f'!['
            else:
                full_path = f'['
            if match['desc']:
                full_path += f'{match["desc"]}'
                if match['size']:
                    full_path += f'|{match["size"]}'
            else:
                full_path += f'{match["size"]}'
            full_path += f']('
            if match['path'] and flag:
                excepted_image_path = 'res/' + image_name
                full_url = f'{excepted_image_path}'
            elif match['path'] and not flag:
                full_url = f'{match["path"]}'
            # excepted_image_path = 'res/' + image_name
            # full_url = f'{excepted_image_path}'
            if match['title'] and not match['block_id']:
                full_url += f'#{match["title"]}'
            if (not match['title']) and match['block_id']:
                full_url += f'#^{match["block_id"]}'
            full_url = decode_url_space_only(full_url)
            full_url = encode_url_space_only(full_url)
            full_path += full_url + ')'

        # 添加匹配到的链接到内容片段
        parts.append(full_path)
        last_end = match['end']

    # 添加最后一个片段
    parts.append(content[last_end:])

    # 将所有片段重新组合成新的内容
    updated_content = ''.join(parts)

    return updated_content, updated


def move_image_if_needed(resource_folder):
    """
    遍历指定文件夹中的 Markdown 文件，检查图片是否在指定链接路径，
    如果不存在则从默认文件夹中查找并移动图片到指定目录路径。
    """
    no_updates = True  # 添加一个标志，记录是否有更新
    for root, dirs, files in os.walk(resource_folder):
        for file in files:
            if file.endswith('.md'):
                md_file_path = os.path.join(root, file)
                with open(md_file_path, 'r', encoding='utf-8', newline='') as file:
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
                # print("updated_content:", updated_content)
                
                # 遍历所有匹配到的链接
                matches = extract_wiki_links(updated_content)
                matches += extract_markdown_links(updated_content)
                # print("matches:", matches)
                if matches:
                    # 移动图片资源 并更新文档中的链接
                    updated_content, updated = update_image_resources_and_links(
                        md_file_path, updated_content, matches)
                    if updated:
                        no_updates = False  # 只有真正更新时才设置为 False
          
                # 恢复代码块
                updated_content = restore_code_blocks(updated_content, code_blocks)

                with open(md_file_path, 'w', encoding='utf-8', newline='') as file:
                    try:
                        file.write(updated_content)
                    except Exception as e:
                        logger.error(f"Error writing to file: {e}")
                        
    # 如果遍历完所有文档，发现没有任何更新，打印提示信息
    if no_updates:
        print("所有文件中的图片链接及位置均未更新。")


if __name__ == '__main__':
    
    source_folder = r'D:\Obsidian\Default'
    search_folder = r'D:\Obsidian\Middle\Default'
    source_folder_bak = r'D:\Obsidian\Middle\Default'
    
    # 备份资源文件夹
    copy_files_with_timestamps(source_folder, source_folder_bak)

    # 移动图片以及更新文档中的链接
    move_image_if_needed(resource_folder=source_folder_bak)
