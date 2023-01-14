import datetime
from telebot import types
import config


def get_calendar(start_date, check_date, check_month):
    last_month = datetime.datetime(start_date.year + (start_date.month - 2) // 12, (start_date.month - 2) % 12 + 1, 1)
    next_month = datetime.datetime(start_date.year + start_date.month // 12, start_date.month % 12 + 1, 1)

    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    keyboard = [[types.InlineKeyboardButton(text=month_names[int(start_date.strftime("%m")) - 1] + start_date.strftime(" %Y"), callback_data="NONE")]]

    row = []
    for name in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        row.append(types.InlineKeyboardButton(text=name, callback_data="NONE"))
    keyboard.append(row)

    cur_date = start_date
    week_name_id = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Вс": 6}
    while cur_date.month == start_date.month:
        row = [types.InlineKeyboardButton(text=" ", callback_data="NONE")] * 7
        while cur_date.month == start_date.month:
            if check_date(cur_date):
                row[week_name_id[cur_date.strftime("%a")]] = types.InlineKeyboardButton(text=str(cur_date.day), callback_data="SET_DATE " + cur_date.strftime("%Y-%m-%d"))
            cur_date += datetime.timedelta(days=1)
            if week_name_id[cur_date.strftime("%a")] == 0:
                break
        keyboard.append(row)

    row = [types.InlineKeyboardButton(text=" ", callback_data="NONE")] * 3
    if check_month(last_month):
        row[0] = types.InlineKeyboardButton(text="<", callback_data="SWITCH_MONTH " + last_month.strftime("%Y-%m-%d"))
    if check_month(next_month):
        row[2] = types.InlineKeyboardButton(text=">", callback_data="SWITCH_MONTH " + next_month.strftime("%Y-%m-%d"))
    row[1] = types.InlineKeyboardButton(text="обновить", callback_data="UPDATE_DATE " + start_date.strftime("%Y-%m-%d"))
    keyboard.append(row)

    return types.InlineKeyboardMarkup(keyboard)


def get_time(cur_date, check_time):
    keyboard = []
    for hour in range(0, 24):
        row = []
        add_row = False
        cur_time = datetime.datetime(cur_date.year, cur_date.month, cur_date.day, hour=hour)
        while cur_time.hour == hour:
            if check_time(cur_time):
                add_row = True
                row.append(types.InlineKeyboardButton(text=cur_time.strftime("%H:%M"), callback_data="SET_TIME " + cur_time.strftime("%Y-%m-%d-%H-%M")))
            else:
                row.append(types.InlineKeyboardButton(text=" ", callback_data="NONE"))
            cur_time += config.TIME_STEP
        if add_row:
            keyboard.append(row)

    keyboard.append([types.InlineKeyboardButton(text="обновить", callback_data="UPDATE_TIME " + cur_date.strftime("%Y-%m-%d"))])

    return types.InlineKeyboardMarkup(keyboard)


def get_client_list(date, times, add_time=None):
    keyboard = []
    if add_time is not None:
        times[add_time[0]] = add_time[1]
    for time in sorted(times.keys()):
        if datetime.datetime.strptime(date + "-" + time, "%Y-%m-%d-%H-%M") < datetime.datetime.now() + config.TIMEZONE:
            continue

        id = times[time]
        row = [types.InlineKeyboardButton(text=time[:2] + ":" + time[3:], callback_data="NONE")]
        row.append(types.InlineKeyboardButton(text="Описание", callback_data="DESC " + str(id)))
        if add_time is None or time != add_time[0]:
            row.append(types.InlineKeyboardButton(text="Удалить", callback_data="DELETE " + str(id)))
        else:
            row.append(types.InlineKeyboardButton(text="Восстановить", callback_data="RESTORE " + str(id) + " " + date + "-" + time))
        keyboard.append(row)
    return keyboard
