from datetime import datetime, timezone, timedelta

def utc_to_utc8(utc_time):
    """
    将UTC时间转换为UTC+8时间
    
    Args:
        utc_time: UTC时间 (datetime对象，可以是naive或aware)
    
    Returns:
        UTC+8时间 (datetime对象，带时区信息)
    """
    if not utc_time:
        return None
    
    # 如果输入是naive datetime，假设它是UTC时间
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    # 如果输入已经是带时区的datetime，确保它是UTC时区
    elif utc_time.tzinfo != timezone.utc:
        # 转换为UTC时区
        utc_time = utc_time.astimezone(timezone.utc)
    
    # 转换为UTC+8时间
    utc8_time = utc_time.astimezone(timezone(timedelta(hours=8)))
    return utc8_time

def format_utc8_time(utc_time, format_str='%Y-%m-%d %H:%M:%S'):
    """
    将UTC时间转换为UTC+8时间并格式化为字符串
    
    Args:
        utc_time: UTC时间 (datetime对象)
        format_str: 格式化字符串
    
    Returns:
        格式化后的UTC+8时间字符串
    """
    if not utc_time:
        return ''
    
    utc8_time = utc_to_utc8(utc_time)
    return utc8_time.strftime(format_str) if utc8_time else ''