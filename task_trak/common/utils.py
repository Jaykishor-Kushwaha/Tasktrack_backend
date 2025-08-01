def format_timedelta(td):
    if td is None:
        return "None"
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days, {hours:02}:{minutes:02}:{seconds:02}"

def format_aprx_duration(interval):
    if interval is None:
        return '0 days, 00:00'
    total_seconds = interval.total_seconds()
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    # return f'{int(days)} days, {int(hours):02}:{int(minutes):02}:{int(seconds):02}'
    return f'{int(days)} days {int(hours):02}:{int(minutes):02}'