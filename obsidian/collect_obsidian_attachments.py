"""
需求：将所有附件资源汇总到一个新目录，以便后续上传到图床。
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
source_note_dir = fr'D:\Obsidian\{source_folder}'
new_resource_dir = fr'D:\Obsidian\Middle\linkres'
new_resource_subfolder = "obsidian"


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


def get_file_type(file_path):
    """根据文件扩展名获取文件类型"""
    ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
    for file_type, extensions in supported_extensions.items():
        if ext in extensions:
            return file_type
    return 'other'


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
    
    
def copy_attachments_with_timestamps(source_dir, target_dir):
    """复制附件资源，并保留原始时间戳"""
    try:
        from copy_with_timestamps import copy_with_timestamps
    except ImportError:
        logger.error("无法导入 copy_with_timestamps 模块，请确保模块存在。")
    
    os.makedirs(target_dir, exist_ok=True)

    ignored_dirs = get_ignore_list(source_dir)
    copied_count = 0
    
    for root, dirs, files in os.walk(source_dir):
        # 排除特定子目录
        dirs[:] = [d for d in dirs if d not in ignored_dirs]

        for file in files:
            file_type = get_file_type(file)
            if file_type != 'markdown' and file_type != 'other':
                source_file_path = os.path.join(root, file)
                target_file_path = os.path.join(target_dir, file)
                copy_with_timestamps(source_file_path, target_file_path)
                copied_count += 1
                
    logger.info(f"共复制 {copied_count} 个资源文件")
    
    
def main():
    # 确认删除目标目录
    safe_remove_if_exists(new_resource_dir)
    # 创建新目录
    os.makedirs(new_resource_dir, exist_ok=True)

    logger.info("开始处理...")
    logger.info(f"源目录: {source_note_dir}")
    # logger.info(f"目标目录: {target_note_dir}")
    logger.info(f"附件资源汇总目录: {os.path.join(new_resource_dir, new_resource_subfolder)}")

    # 汇总资源
    target_resource_dir = os.path.join(new_resource_dir, new_resource_subfolder)
    copy_attachments_with_timestamps(source_note_dir, target_resource_dir)

    logger.info("\n✅ 处理完成！")
    logger.info(f"资源文件已汇总: {target_resource_dir}")


if __name__ == "__main__":
    # 设置日志级别
    logger.setLevel(logging.INFO)
    main()
