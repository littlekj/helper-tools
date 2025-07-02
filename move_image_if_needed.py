"""
需求：Obsidian 中 md 文件移动后，将文件中插入的图片资源移动到对应子目录。
图片插入使用的是 Obsidian 的内部链接格式的相对路径，目录结构：
.\folder_path
.\folder_path\file.md
.\floder_path\res\image.png
遍历给定的文件夹，检查每个 md 文件中的图片链接，如果图片不在指定路径，则尝试从默认文件夹查找图片并移动图片到指定子目录。
"""

import os
import shutil
import re

# 指定待遍历的文件夹和默认查找图片的文件夹路径
folder_path = r'D:\Obsidian\Default'
default_folder_path = r'D:\Obsidian'

# 定义支持的图片扩展名
image_extensions = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'svg']
extensions_pattern = '|'.join(image_extensions)  # 构建正则表达式模式

# 正则表达式匹配图片路径（Obsidian 内部链接格式）
image_regex = re.compile(
    fr'(?<!`)(!?\[\[(.+?\.(?:{extensions_pattern}))(?:\|(\d+)(?:x(\d+))?)?\]\])(?!`)',
    re.MULTILINE
)


def move_image_if_needed(folder, default_folder):
    """
    遍历指定文件夹中的 Markdown 文件，检查图片链接是否存在，
    如果不存在则从默认文件夹中查找并移动图片到目标目录。
    """
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith('.md'):
                md_file_path = os.path.join(root, file)
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                """处理正则表达式匹配的图片链接"""
                for match in image_regex.finditer(content):
                    if match:
                        # print("match:", match)
                        image_path = match.group(2)  # 获取图片相对路径
                        image_name = os.path.basename(image_path)  # 获取图片文件名
                        excepted_image_dir = os.path.join(root, 'res')  # 图片预期目录
                        os.makedirs(excepted_image_dir, exist_ok=True)  # 创建图片预期的目录（如果不存在）
                        excepted_image_path = os.path.join(
                            excepted_image_dir, image_name)  # 目标图片路径
                        # print('excepted_image_path:', excepted_image_path)

                        # 如果目标路径没有图片，则从默认文件中中查找并移动图片
                        if not os.path.isfile(excepted_image_path):
                            flag = find_image_in_directory(
                                default_folder, image_name, excepted_image_path)
                            if flag:
                                print(
                                    f'Successfully moved {image_name} to {excepted_image_path}')
                            else:
                                print(
                                    f'{image_name} search operation failed, please check.')


def find_image_in_directory(directory, image_name, excepted_image_path):
    """
    在指定目录及其子目录中查找图片文件，找到后移动到目录路径
    """
    for root, dirs, files in os.walk(directory):
        if image_name in files:
            searched_image_path = os.path.join(root, image_name)
            print(f'Image found: {searched_image_path}')
            try:
                shutil.move(searched_image_path, excepted_image_path)
                return True
            except Exception as e:
                print(f'Image movement failed: {e}')
    return False


if __name__ == '__main__':

    move_image_if_needed(folder_path, default_folder_path)
