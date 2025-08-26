import os
import subprocess
import time
import logging
from datetime import datetime, time as dtime, timedelta
import pytz

"""
实现系统在目标时间段内使用特定时区，在非目标时间段自动切换回原始时区
"""

# 获取当前脚本所在的目录
log_dir = os.path.dirname(os.path.abspath(__file__))

# 日志文件完整路径
log_file = os.path.join(log_dir, "timezone_manager.log")

# 配置日志记录
logging.basicConfig(
    # 设置日志记录级别为 INFO
    level=logging.INFO,

    # 定义日志消息格式
    format='%(asctime)s - %(levelname)s - %(message)s',

    # 配置日志处理器（输出目标）
    handlers=[
        # 将日志写入文件 "timezone_manager.log"
        logging.FileHandler(log_file, encoding="utf-8"),

        # 将日志输出到控制台（标准输出）
        # logging.StreamHandler()
    ]
)

# Windows时区到pytz的映射
WINDOWS_TO_PYTZ = {
    'Dateline Standard Time': 'Etc/GMT+12',
    'UTC-11': 'Etc/GMT+11',
    'Hawaiian Standard Time': 'Pacific/Honolulu',
    'Alaskan Standard Time': 'America/Anchorage',
    'Pacific Standard Time': 'America/Los_Angeles',
    'Mountain Standard Time': 'America/Denver',
    'Central Standard Time': 'America/Chicago',
    'Eastern Standard Time': 'America/New_York',
    'Atlantic Standard Time': 'America/Halifax',
    'Newfoundland Standard Time': 'America/St_Johns',
    'E. South America Standard Time': 'America/Sao_Paulo',
    'UTC-02': 'Etc/GMT+2',
    'UTC': 'UTC',
    'GMT Standard Time': 'Europe/London',
    'W. Europe Standard Time': 'Europe/Berlin',
    'Central Europe Standard Time': 'Europe/Budapest',
    'Romance Standard Time': 'Europe/Paris',
    'E. Europe Standard Time': 'Europe/Bucharest',
    'Egypt Standard Time': 'Africa/Cairo',
    'South Africa Standard Time': 'Africa/Johannesburg',
    'Russian Standard Time': 'Europe/Moscow',
    'West Asia Standard Time': 'Asia/Tashkent',
    'Central Asia Standard Time': 'Asia/Almaty',
    'SE Asia Standard Time': 'Asia/Bangkok',
    'China Standard Time': 'Asia/Shanghai',
    'Tokyo Standard Time': 'Asia/Tokyo',
    'AUS Eastern Standard Time': 'Australia/Sydney',
    'New Zealand Standard Time': 'Pacific/Auckland',
    'UTC+12': 'Etc/GMT-12',
    'Line Islands Standard Time': 'Pacific/Kiritimati'
}

# 配置目标时区及其切换时间范围
TARGET_TIMEZONES = {
    "China Standard Time": {
        "switch_to": "Line Islands Standard Time",
        "switch_window": (dtime(0, 0), dtime(6, 30, 00)),  # 北京时间某个时间段切换
        "description": "北京时间 (东八区)"
    },
    "Line Islands Standard Time": {
        "switch_to": "China Standard Time",
        "switch_window": (dtime(6, 30, 30), dtime(23, 59, 59)),  # 北京时间某个时间段切换
        "description": "基里巴斯时间 (UTC+14)"
    }
}

# 默认时区（当其他时区不在管理范围内时切换回此时区）
DEFAULT_TIMEZONE = "China Standard Time"


def get_current_timezone():
    """获取当前系统时区"""
    try:
        tz_cmd = "tzutil /g"
        tz_output = subprocess.check_output(tz_cmd, shell=True).strip()
        return tz_output.decode('utf-8')
    except subprocess.CalledProcessError as e:
        logging.error(f"获取时区失败：{e}")
        return None
    except Exception as e:
        logging.errror(f"获取时区时发生未知错误：{e}")
        return None


def get_cst_time(current_tz):
    """获取当前东八区时间"""
    try:
        if current_tz in WINDOWS_TO_PYTZ:
            local_tz = pytz.timezone(WINDOWS_TO_PYTZ[current_tz])
            local_time = datetime.now(local_tz)
            cst_tz = pytz.timezone('Asia/Shanghai')
            return local_time.timezone(cst_tz)  # 将时间转换为指定时区的时间
        # 如果当前时区不在映射表中，直接返回北京时间
        return datetime.now(pytz.timezone('Asia/Shanghai'))
    except Exception as e:
        logging.error(f"计算东八区时间出错: {e}")
        # 返回UTC时间并转换为北京时间作为后备
        return datetime.now(pytz.timezone('Asia/Shanghai'))


def set_timezone(timezone):
    """设置系统时区"""
    try:
        tz_cmd = f'tzutil /s "{timezone}"'
        subprocess.run(tz_cmd, shell=True, check=True)
        # 验证是否设置成功
        new_tz = get_current_timezone()
        if new_tz == timezone:
            logging.info(f"成功设置时区为：{timezone}")
            return True
        logging.warnging(f"时区设置验证失败：预期 {timezone}， 实际 {new_tz}")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"设置时区失败：{timezone}, 错误：{e}")
        return False
    except Exception as e:
        logging.error(f"设置时区时发生未知错误：{e}")
        return False


def should_switch_timezone(target_config, cst_time):
    """检查是否应该切换时区"""
    if not target_config:
        return False

    current_time = cst_time.time()
    start, end = target_config["switch_window"]

    # 处理跨午夜的时间范围
    if start < end:
        return start <= current_time <= end
    else:
        return start <= current_time or end >= current_time


def manage_timezone_switching():
    """主管理函数"""
    check_interval = 60  # 检查间隔(秒)
    max_retries = 3
    retry_delay = 300  # 重试间隔(秒)

    # 记录最后一次成功切换的时间
    last_switch_time = None

    logging.info("时区管理服务启动")

    while True:
        try:
            current_tz = get_current_timezone()
            if not current_tz:
                logging.warning("无法获取当前时区，等待下次检查")
                time.sleep(check_interval)
                continue

            cst_time = get_cst_time(current_tz)
            logging.info(
                f"当前时区: {current_tz}, 东八区时间: {cst_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 检查当前时区是否在管理列表中
            if current_tz in TARGET_TIMEZONES:
                target_config = TARGET_TIMEZONES[current_tz]

                if should_switch_timezone(target_config, cst_time):
                    target_tz = target_config["switch_to"]
                    logging.info(f"满足切换条件: {current_tz} -> {target_tz}")

                    # 尝试切换时区
                    success = False
                    for attempt in range(max_retries):
                        if set_timezone(target_tz):
                            success = True
                            last_switch_time = datetime.now()
                            print(f"{current_tz} -> {target_tz} 时区切换成功")
                            break
                        logging.warning(
                            f"切换时区失败 ({attempt+1}/{max_retries}), {retry_delay}秒后重试...")
                        time.sleep(retry_delay)

                    if not success:
                        logging.error(f"无法切换时区到 {target_tz}, 已达到最大重试次数")
                        print("时区切换失败，请检查")
                else:
                    logging.debug(f"当前时间不在切换窗口内: {cst_time.time()}")
            else:
                # 当前时区不在管理列表中，切换回默认时区
                logging.warning(
                    f"当前时区 {current_tz} 不在管理列表中，将切换回默认时区 {DEFAULT_TIMEZONE}")

                for attempt in range(max_retries):
                    if set_timezone(DEFAULT_TIMEZONE):
                        break
                    logging.warning(
                        f"恢复默认时区失败 ({attempt+1}/{max_retries}), {retry_delay}秒后重试...")
                    time.sleep(retry_delay)

            time.sleep(check_interval)

        except Exception as e:
            logging.exception(f"发生未预期错误: {e}")
            time.sleep(check_interval)


if __name__ == "__main__":
    manage_timezone_switching()
