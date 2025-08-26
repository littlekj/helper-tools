import argparse
import subprocess
import os
import re
import shlex
import shutil
from typing import Optional


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


def is_target_directory(src: str, dst: str) -> bool:
    """
    判断目标路径是否是目录（考虑隐藏文件特殊性）
    """
    # 如果目标路径已存在，则判断是否是目录
    if os.path.exists(dst):
        if os.path.isdir(dst):
            return True
        else: 
            raise FileExistsError(f"目标路径已存在且不是目录: {dst}")
    
    # 以路径分隔符结尾，则认为是目录
    if dst.endswith('/') or dst.endswith('\\'):
        return True
    
    # 如果源是隐藏文件，且目标路径无扩展名但以 . 开头，则视为文件
    if src and os.path.isfile(src):
        src_name = os.path.basename(src)
        if src_name.startswith('.'):
            dst_name = os.path.basename(dst)
            if dst_name.startswith('.') and os.path.splitext(dst)[1] == '':
                return False
    
    # 如果源是目录，则认为目标路径是目录     
    elif src and os.path.isdir(src):
            return True
    
    # 一般情况：如果目标路径无扩展名，则认为是目录
    return os.path.splitext(dst)[1] == ''
            
    
def robocopy_copy(src: str, dst: str) -> bool:
    """
    Windows 系统下使用 robocopy 复制文件或目录，保留时间戳（创建、修改、访问）
    :param src: 源文件或目录路径
    :param dst: 目标路径（文件或目录）
    """
    if not os.path.exists(src):
        raise FileNotFoundError(f"源路径不存在: {src}")

    is_file = os.path.isfile(src)
    src_name = os.path.basename(src)

    dst_is_directory = is_target_directory(src, dst)
    if dst_is_directory:
        # 目标是目录，复制到该目录下，使用原文件名
        parent_dst = dst.rstrip('/\\')
        final_dst = os.path.join(parent_dst, src_name)
    else:
        # 目标是文件，直接使用目标文件名
        parent_dst = os.path.dirname(dst) or '.'  # 假如 data.txt 父目录为空，使用当前目录
        final_dst = dst
    
    # 确保父目录存在 
    os.makedirs(parent_dst, exist_ok=True)
    
    if is_file:
        parent_src = os.path.dirname(src)
        file_list = [src_name]
    else:
        parent_src = src
        file_list = []


    # 优先使用 shell=False + 列表
    # 构建 robocopy 命令
    cmd = [
        "robocopy",
        parent_src,      # 指定源目录
        parent_dst,      # 指定目标目录（robocopy 只支持目录）
        *file_list,      # 指定文件名列表
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
            # 文件场景：robocopy 实际复制到了 parent_dst/src_name，需重命名为 final_dst
            if is_file:
                temp_copied = os.path.join(parent_dst, src_name)
                if os.path.exists(temp_copied) and temp_copied != final_dst:
                    os.replace(temp_copied, final_dst)
            # 修复目录时间戳（可选）
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='复制文件或目录，保留时间戳')
    parser.add_argument('src', type=str, help='源文件或目录路径')
    parser.add_argument('dst', type=str, help='目标文件或目录路径')
    args = parser.parse_args()

    success = copy_with_timestamps(args.src, args.dst)
    if success:
        print("保留时间戳的复制成功！")
    else:
        print("保留时间戳的复制失败！")
    exit(0 if success else 1)


# 使用示例
# Windows 系统：
#   源是目录：src = r'C:\source\dir'
#   源是文件：src = r'C:\source\file.txt'
#   目标：    dst = r'D:\backup\dir' 或 r'D:\backup\file.txt'

# Linux / macOS：
#   本地复制：
#       src = '/local/source/dir'
#       dst = '/local/backup/dir'
#   复制到远程：
#       src = '/local/source/dir'
#       dst = 'user@remote:/remote/backup/dir'

# 命令行调用：
#   sudo python3 copy_with_timestamps.py /local/source/dir /local/backup/dir
#   sudo python3 copy_with_timestamps.py /local/source/file.txt user@remote:/remote/backup/
