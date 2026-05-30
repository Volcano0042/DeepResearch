#***********************************************
#      Filename: utils.py
#   Description: 工具函数库
#***********************************************

import os
import yaml
from pathlib import Path
from datetime import datetime


# ===== UTILITY FUNCTIONS =====

import datetime  # 确保已导入


def get_today_str() -> str:
    """获取今天的日期并返回格式化的字符串

    注意：使用 %d 代替 %-d 以兼容 Windows 系统
    输出示例: Sat May 23, 2026 (如果原意需要无前导零，见下方注释)
    """
    now = datetime.datetime.now()
    # 方案 A: 直接使用标准格式 (兼容所有系统，May 23 或 May 05)
    # 如果需要严格去掉前导零，可以使用下面的方案 B
    return now.strftime("%a %b %d, %Y").replace(" 0", " ")

def get_current_dir() -> Path:
    """获取当前的目录"""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


# ===== CONFIG LOADER =====

def get_config_yml(path, section_name, subsection_name=None):
    """读取yaml文件"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: {path}")

    with open(path, encoding="utf8") as f:
        data = yaml.safe_load(f)
        try:
            return (
                data[section_name]
                if subsection_name is None
                else data[section_name][subsection_name]
            )
        except KeyError as e:
            raise KeyError(
                f"No such section or subsection in config file: {section_name}, {subsection_name}. Config file: {path}"
            ) from e


def load_config(stage_name=None, config_path=None):
    """加载配置"""
    return get_config_yml(
        path=config_path, section_name="stages", subsection_name=stage_name
    )
