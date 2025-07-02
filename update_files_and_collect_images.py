"""
需求：

- 若把 Markdown 笔记渲染到网页，需要将图片资源上传到云端图床，使用图片的外部链接方式。
- 由于，本地 Markdown 笔记插入图片时使用的是内部链接方式。
- 所以，复制源目录到目标目录，遍历目标目录中的所有文件，对文件中的图片链接使用正则表达式匹配更新，并将所有图片汇总到一个新目录，以便后续上传到图床。
"""
import os
import shutil
import re
from urllib.parse import quote
import sys

# 配置路径
source_folder = "Default"  # 源目录名称
source_note_dir = fr'D:\Obsidian\{source_folder}'  # 源目录路径
new_note_dir = fr'D:\Obsidian\Middle\{source_folder}'  # 目标目录路径
new_image_dir = fr'D:\Obsidian\Middle\linkres'  # 图片汇总根目录路径
new_image_folder = "obsidian"  # 汇总目录中的子目录
# external_link_prefix = r'https://raw.githubusercontent.com/littlekj/linkres/master/obsidian/'  # GitHub 原始链接前缀
external_link_prefix = r''


# 创建新目录（如果不存在）
os.makedirs(new_note_dir, exist_ok=True)  # 如果目标目录不存在，则创建
os.makedirs(new_image_dir, exist_ok=True)  # 如果图片汇总目录不存在，则创建

# 定义支持的图片扩展名
image_extensions = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'svg']
# image_extensions = []
extensions_pattern = '|'.join(image_extensions)  # 构建正则表达式模式

# 正则表达式匹配图片路径
image_regex = re.compile(
    fr'(?<!`)(!?\[\[(.+?\.(?:{extensions_pattern}))(?:\|(\d+)(?:x(\d+))?)?\]\])(?!`)',
    re.MULTILINE
)

def remove_if_exists(file_path):
    """删除文件或目录，如果存在的话。"""
    if os.path.exists(file_path):  # 检查文件或目录是否存在
        if os.path.isfile(file_path):  # 如果是文件，则删除文件
            os.remove(file_path)
        elif os.path.isdir(file_path):  # 如果是目录，删除目录及其内容
            shutil.rmtree(file_path)


def copy_files(source_note_dir, ignored_extensions=None):
    """复制源目录中的所有文件到目标目录。"""
    ignored_extensions = ignored_extensions or []  # 如果未提供忽略扩展名，默认设置为空列表
    for item in os.listdir(source_note_dir):  # 遍历源目录中的所有项目
        source_path = os.path.join(source_note_dir, item)  # 源文件路径
        destination_path = os.path.join(new_note_dir, item)  # 目录文件路径
        if any(source_path.endswith(ext) for ext in ignored_extensions):  # 如果文件扩展名在忽略列表中，跳过
            continue

        remove_if_exists(destination_path)  # 删除目录路径中的文件或目录（如果存在）
        if os.path.isdir(source_path):  # 如果是源路径是目录，则递归复制目录及其内容
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        else:  # 如果是文件复制文件
            shutil.copy2(source_path, destination_path)

# 忽略部分路径下文件的操作
def ignore_files(new_note_dir):
    ignore_files_path = os.path.join(new_note_dir, '.gitignore')
    content = [] 
    with open(ignore_files_path, 'r', encoding='utf-8', newline='') as f:
        lines = f.readlines()
        for line in lines:
            stripped_line = line.strip()  # 去掉前后空白字符（包括换行符）
            if stripped_line:  #  忽略空行
                content.append(stripped_line.rstrip('/'))  # 去掉末尾的斜杠
    # print("content:", content)    
    return content
 

def iterate_files(new_note_dir):
    """遍历目标目录中的所有笔记文件更新图片链接并复制图片。"""
    for root, dirs, files in os.walk(new_note_dir):  # 遍历目标目录及其子目录
        # 排除特定子目录
        ignored_dirs = []
        ignored_dirs = ignore_files(new_note_dir)
        dirs[:] = [dir for dir in dirs if dir not in ignored_dirs ]
        
        for file in files:
            if file.endswith('.md'):  # 仅处理 Markdown 文件
                note_file_path = os.path.join(root, file)  # Markdown 文件路径
                print("note_file_path:", note_file_path)
                update_file_and_copy_imgs(note_file_path)  # 更新文件中的图片链接并复制图片


def update_file_and_copy_imgs(note_file_path):
    """更新文件中的图片链接，并将图片复制到汇总目录。"""
    with open(note_file_path, 'r', encoding='utf-8', newline='') as file:
        content = file.read()  # 读取文件内容

    def replacement(match):
        """处理正则表达式匹配的图片链接"""
        # print("match:", match)
        # print("match.group(0):", match.group(0))
        image_path = match.group(2)  # 图片路径
        width = match.group(3) if match.group(3) else ''  # 图片宽度（可选）
        height = match.group(4) if match.group(4) else ''  # 图片高度（可选）

        image_abs_path = ''
        if not os.path.isabs(image_path):  # 如果图片路径是相对路径
            note_file_directory_path = os.path.dirname(
                note_file_path)  # Markdown 文件目录
            # 图片的绝对路径
            image_abs_path = os.path.join(
                note_file_directory_path, 'res', os.path.basename(image_path.strip()))

        if os.path.isfile(image_abs_path):  # 如果图片文件存在
            new_image_dir_path = os.path.join(
                new_image_dir, new_image_folder)  # 图片文件目录路径
            os.makedirs(new_image_dir_path, exist_ok=True)  # 创建图片文件目录路径（如果不存在）
            file_name = os.path.basename(image_path)  # 图片文件名
            new_image_path = os.path.join(
                new_image_dir_path, file_name)  # 图片文件路径

            shutil.copy2(image_abs_path, new_image_path)  # 复制图片到新路径

            # 计算图片的 GitHub URL
            image_external_link = f'{external_link_prefix}{quote(file_name)}'

            # 根据图片尺寸构建新的 Markdown 图片链接
            if width and not height:
                new_image_url = f'![{file_name}|{width}]({image_external_link})'
            elif width and height:
                new_image_url = f'![{file_name}|{width}x{height}]({image_external_link})'
            else:
                new_image_url = f'![{file_name}]({image_external_link})'
            
            # print('new_image_url', new_image_url)

            return new_image_url  # 返回更新后的图片链接

        # return match.group(0)  #  如果图片文件不存在，返回原始匹配内容
        else:
            # 记录无法找到的图片路径
            print(f'Warning: Image not found - {image_abs_path}')
            # 提示检查其他目录是否存在该图片
            print(f'Does the image exist in {source_note_dir}')

            sys.exit(1)  # 退出程序，状态为 1 表示发生错误

    # 使用正则表达式替换图片链接
    updated_content = image_regex.sub(replacement, content)

    # 使用 'newline=''' 参数禁用自动换行符转换
    with open(note_file_path, 'w', encoding='utf-8', newline='') as file:
        file.write(updated_content)  # 将更新后的内容写回文件


def main():
    """执行文件复制和更新操作"""
    ignored_extensions = ['.tmp', '.git']  # 忽略的文件扩展名和目录
    copy_files(source_note_dir, ignored_extensions)  # 复制文件
    iterate_files(new_note_dir)  # 遍历文件更新图片链接并复制图片
 

if __name__ == "__main__":
    main()
