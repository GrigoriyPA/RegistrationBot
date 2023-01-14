import sqlite3
import datetime
import threading
import telebot
from telebot import types
import markups
import config


class TelegramClient:
    def __init__(self):
        self.client = None
        self.handler_thread = None
        self.wait_mode = dict()
        self.reg_date = dict()
        self.free_id = -1
        self.geolocation = open(config.GEOLOCATION_PATH, 'rb')

        self.users_information_db_name = config.USERS_INFORMATION_DB_NAME
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users(user_id INT PRIMARY KEY, time TEXT, is_admin INT, comment TEXT, phone_number TEXT);")
        conn.commit()

        self.registrations = dict()
        cursor.execute("SELECT * FROM users;")
        for user in cursor.fetchall():
            if user[1] == "-":
                continue

            self.free_id = min(self.free_id, user[0] - 1)
            cur_date = user[1][:10]
            if cur_date not in self.registrations:
                self.registrations[cur_date] = dict()
            self.registrations[cur_date][user[1][11:]] = user[0]

    def __add_user(self, id):
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        if cursor.fetchone() is None:
            entry = (id, "-", 0, "", "?")
            cursor.execute("INSERT INTO users VALUES(?, ?, ?, ?, ?);", entry)
            conn.commit()
        if id not in self.wait_mode:
            self.wait_mode[id] = 0
        if id not in self.reg_date:
            self.reg_date[id] = ""

    def __reg_user(self, id, date, comment):
        cur_date = date.strftime("%Y-%m-%d")
        if cur_date not in self.registrations:
            self.registrations[cur_date] = dict()
        self.registrations[cur_date][date.strftime("%H-%M")] = id

        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET time='" + date.strftime("%Y-%m-%d-%H-%M") + "' WHERE user_id=" + str(id) + ";")
        cursor.execute("UPDATE users SET comment='" + comment + "' WHERE user_id=" + str(id) + ";")
        conn.commit()

    def __delete_user(self, id):
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        registration = cursor.fetchone()
        if registration[1] == "-":
            return False

        self.registrations[registration[1][:10]].pop(registration[1][11:])

        cursor.execute("UPDATE users SET time='-' WHERE user_id=" + str(id) + ";")
        conn.commit()

        return True

    def __is_admin(self, id):
        if id in config.ADMINS:
            return True

        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        return cursor.fetchone()[2]

    def __check_month(self, date):
        today = datetime.datetime.today()
        return date >= datetime.datetime(today.year, today.month, 1)

    def __check_date(self, date):
        today = datetime.datetime.today()
        if date < datetime.datetime(today.year, today.month, today.day):
            return False

        for hour in range(0, 24):
            cur_time = datetime.datetime(date.year, date.month, date.day, hour=hour)
            while cur_time.hour == hour:
                if self.__check_time(cur_time):
                    return True
                cur_time += config.TIME_STEP
        return False

    def __check_time(self, time):
        if time < datetime.datetime.now() + config.TIMEZONE:
            return False

        cur_date = time.strftime("%Y-%m-%d")
        if cur_date in self.registrations:
            for take_time in self.registrations[cur_date]:
                check_time = datetime.datetime.strptime(cur_date + "-" + take_time, "%Y-%m-%d-%H-%M")
                if max(check_time, time) < min(check_time, time) + config.SERVICE_TIME:
                    return False

        for cut in config.WORKING_HOURS:
            start = datetime.datetime(time.year, time.month, time.day, cut[0].hour, cut[0].minute)
            end = datetime.datetime(time.year, time.month, time.day, cut[1].hour, cut[1].minute)
            if start <= time and time + config.SERVICE_TIME <= end:
                return True
        return False

    def __compute_command_start(self, message):
        self.__add_user(message.chat.id)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        text = """
Здравствуйте, этот бот может использоваться для быстрой и удобной записи на примерку.
        """

        if self.__is_admin(message.chat.id):
            markup.add(types.KeyboardButton(text="Добавить запись"), types.KeyboardButton(text="Удалить запись"))
            if message.chat.id in config.ADMINS:
                markup.add(types.KeyboardButton(text="Добавить адм."), types.KeyboardButton(text="Удалить адм."))
            markup.add(types.KeyboardButton(text="Список клиентов"))
            markup.add(types.KeyboardButton(text="Помощь"))
            text = "Функционал администратора добавлен."
        else:
            markup.add(types.KeyboardButton(text="Записаться"), types.KeyboardButton(text="Удалить запись"))
            markup.add(types.KeyboardButton(text="Предоставить телефон", request_contact=True))

        self.client.send_message(message.chat.id, text=text, reply_markup=markup)

    def __compute_command_get_id(self, message):
        self.client.send_message(message.chat.id, text="id пользователя: " + str(message.chat.id))

    def __compute_command_stop(self, message):
        if not self.__is_admin(message.chat.id):
            return

        self.client.send_message(message.chat.id, text="Завершение работы.")
        self.client.stop_polling()

    def __compute_command_contact(self, message):
        self.__add_user(message.chat.id)
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone_number='+" + str(message.contact.phone_number) + "' WHERE user_id=" + str(message.chat.id) + ";")
        conn.commit()

    def __compute_wait_comment(self, message):
        self.wait_mode[message.chat.id] = 0
        comment = message.text
        cur_time = datetime.datetime.strptime(self.reg_date[message.chat.id], "%Y-%m-%d-%H-%M")
        id = message.chat.id
        if self.__is_admin(message.chat.id):
            id = self.free_id
            self.free_id -= 1
            self.__add_user(id)

        self.__reg_user(id, cur_time, comment)
        self.client.send_message(message.chat.id, text="Добавлена запись на время:\n" + cur_time.strftime("%d-%m-%Y %H:%M"))

    def __compute_callback_switch_month(self, data, message):
        cur_date = datetime.datetime.strptime(data[0], "%Y-%m-%d")
        markup = markups.get_calendar(cur_date, self.__check_date, self.__check_month)
        self.client.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=message.text, reply_markup=markup)

    def __compute_callback_set_date(self, data, message):
        cur_date = datetime.datetime.strptime(data[0], "%Y-%m-%d")
        markup = markups.get_time(cur_date, self.__check_time)
        self.client.send_message(message.chat.id, text="Выбрана дата " + cur_date.strftime("%d-%m-%Y") + "\nПожалуйста, выберете время", reply_markup=markup)

    def __compute_callback_update_date(self, data, message):
        cur_date = datetime.datetime.strptime(data[0], "%Y-%m-%d")
        markup = markups.get_calendar(cur_date, self.__check_date, self.__check_month)
        self.client.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=message.text, reply_markup=markup)

    def __compute_callback_set_time(self, data, message):
        cur_time = datetime.datetime.strptime(data[0], "%Y-%m-%d-%H-%M")
        if not self.__check_time(cur_time):
            return self.client.send_message(message.chat.id, text="Выбранное время уже заблокировано, обновите страницу выбора времени.")

        if self.__is_admin(message.chat.id):
            self.reg_date[message.chat.id] = data[0]
            self.wait_mode[message.chat.id] = self.__compute_wait_comment
            return self.client.send_message(message.chat.id, text="Введите коментарий к этой записи.")

        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(message.chat.id) + ";")

        self.__reg_user(message.chat.id, cur_time, cursor.fetchone()[4])
        self.client.send_photo(message.chat.id, self.geolocation, caption="Мы записали вас на число " +
                                                                          cur_time.strftime("%d-%m-%Y") +
                                                                          " на время " + cur_time.strftime("%H:%M") +
                                                                          " по адресу: Геологов 53, офис 40.")

    def __compute_callback_update_time(self, data, message):
        cur_date = datetime.datetime.strptime(data[0], "%Y-%m-%d")
        markup = markups.get_time(cur_date, self.__check_time)
        self.client.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=message.text, reply_markup=markup)

    def __compute_callback_desc(self, data, message):
        id = int(data[0])
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        text = cursor.fetchone()[3]
        if id > 0:
            user_desc = self.client.get_chat_member(id, id)
            if user_desc.user.first_name is not None or user_desc.user.last_name is not None:
                text += " ( "
                if user_desc.user.last_name is not None:
                    text += user_desc.user.last_name + " "
                if user_desc.user.first_name is not None:
                    text += user_desc.user.first_name + " )"
            if user_desc.user.username is not None:
                text += " [@" + user_desc.user.username + "]"

        self.client.send_message(message.chat.id, text=text)

    def __compute_callback_delete(self, data, message):
        id = int(data[0])
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        cur_date = datetime.datetime.strptime(cursor.fetchone()[1], "%Y-%m-%d-%H-%M")

        self.__delete_user(id)
        self.client.send_message(message.chat.id, text="Запись на дату " + cur_date.strftime("%d-%m-%Y %H:%M") + " удалена.")

        date = cur_date.strftime("%Y-%m-%d")
        keyboard = markups.get_client_list(date, self.registrations[date].copy(), add_time=(cur_date.strftime("%H-%M"), id))
        markup = types.InlineKeyboardMarkup(keyboard)
        self.client.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=message.text, reply_markup=markup)

    def __compute_callback_restore(self, data, message):
        id = int(data[0])
        cur_date = datetime.datetime.strptime(data[1], "%Y-%m-%d-%H-%M")
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        comment = cursor.fetchone()[3]
        if not self.__check_time(cur_date):
            return self.client.send_message(message.chat.id, text="Это время уже занято, для восстановления освободите его.")

        self.__reg_user(id, cur_date, comment)
        self.client.send_message(message.chat.id, text="Запись на дату " + cur_date.strftime("%d-%m-%Y %H:%M") + " восстановлена.")

        date = cur_date.strftime("%Y-%m-%d")
        keyboard = markups.get_client_list(date, self.registrations[date].copy())
        markup = types.InlineKeyboardMarkup(keyboard)
        self.client.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=message.text, reply_markup=markup)

    def __compute_keyboard_sign_up(self, message):
        if not self.__is_admin(message.chat.id):
            conn = sqlite3.connect(self.users_information_db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id=" + str(message.chat.id) + ";")
            registration = cursor.fetchone()
            if registration[1] != "-":
                cur_time = datetime.datetime.strptime(registration[1], "%Y-%m-%d-%H-%M")
                return self.client.send_message(message.chat.id, text="Вы уже записаны на время:\n" + cur_time.strftime("%d-%m-%Y %H:%M"))

            if not self.__is_admin(message.chat.id) and registration[4] == "?":
                return self.client.send_message(message.chat.id, text="Пожалуйста, предоставьте номер телефона.")

        today = datetime.datetime.today()
        markup = markups.get_calendar(datetime.datetime(today.year, today.month, 1), self.__check_date, self.__check_month)
        return self.client.send_message(message.chat.id, text="Пожалуйста, выберете дату", reply_markup=markup)

    def __compute_keyboard_sign_out(self, message):
        if not self.__is_admin(message.chat.id):
            if not self.__delete_user(message.chat.id):
                return self.client.send_message(message.chat.id, text="Вы ещё не записаны ни на какое время.")

            return self.client.send_message(message.chat.id, text="Запись удалена.")

        if self.wait_mode[message.chat.id] == 0:
            self.wait_mode[message.chat.id] = self.__compute_keyboard_sign_out
            return self.client.send_message(message.chat.id, text="Введите дату записи, которую нужно удалить.")

        self.wait_mode[message.chat.id] = 0
        try:
            cut_date = datetime.datetime.strptime(message.text, "%d-%m-%Y %H:%M")
        except:
            return self.client.send_message(message.chat.id, text="Некорректная дата.")

        date = cut_date.strftime("%Y-%m-%d")
        time = cut_date.strftime("%H-%M")
        if date not in self.registrations or time not in self.registrations[date]:
            return self.client.send_message(message.chat.id, text="На дату " + cut_date.strftime("%d-%m-%Y %H:%M") + " нет записей.")

        self.__delete_user(self.registrations[date][time])
        self.client.send_message(message.chat.id, text="Запись на дату " + cut_date.strftime("%d-%m-%Y %H:%M") + " удалена.")

    def __compute_keyboard_help(self, message):
        if not self.__is_admin(message.chat.id):
            return

        self.client.send_message(message.chat.id, text="""
Доступные команды:
/start - обновляет функционал (в зависимости от выданных прав)
/get_id - возвращает id пользователя
/stop - завершение работы бота
        """)

    def __compute_keyboard_client_list(self, message):
        if not self.__is_admin(message.chat.id):
            return

        empty = True
        for date in sorted(self.registrations.keys()):
            if len(self.registrations[date]) == 0:
                continue

            text = "+" + "-" * (config.DESC_WIGTH // 2 - 6) + date[8:] + date[4:8] + date[:4] + "-" * (config.DESC_WIGTH // 2 - 6) + "+\n"
            keyboard = markups.get_client_list(date, self.registrations[date].copy())

            if len(keyboard) > 0:
                empty = False
                self.client.send_message(message.chat.id, text=text, reply_markup=types.InlineKeyboardMarkup(keyboard))

        if empty:
            self.client.send_message(message.chat.id, text="Нет записавшихся клиентов.")

    def __compute_keyboard_add_admin(self, message):
        if message.chat.id not in config.ADMINS:
            return

        if self.wait_mode[message.chat.id] == 0:
            self.wait_mode[message.chat.id] = self.__compute_keyboard_add_admin
            return self.client.send_message(message.chat.id, text="Введите id пользователя, которому нужно выдать права администратора.")

        self.wait_mode[message.chat.id] = 0
        try:
            id = int(message.text.strip())
        except:
            return self.client.send_message(message.chat.id, text="Некорректный id пользователя.")

        try:
            user_desc = self.client.get_chat_member(id, id)
        except:
            return self.client.send_message(message.chat.id, text="Неизвестный пользователь.")
        username = user_desc.user.username
        if username is None:
            username = str(id)

        if user_desc.user.id in config.ADMINS:
            return self.client.send_message(message.chat.id, text="Запрещено менять права доступа пользователя " + username + ".")

        self.__add_user(id)
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        if cursor.fetchone()[2]:
            return self.client.send_message(message.chat.id, text="Пользователь " + username + " уже обладает правами администратора.")

        cursor.execute("UPDATE users SET is_admin=1 WHERE user_id=" + str(id) + ";")
        conn.commit()

        self.client.send_message(message.chat.id, text="Пользователю " + username + " выданы права администратора.")
        self.client.send_message(id, text="Вам выданы права администратора. Используйте /start для обновления функционала.")

    def __compute_keyboard_delete_admin(self, message):
        if message.chat.id not in config.ADMINS:
            return

        if self.wait_mode[message.chat.id] == 0:
            self.wait_mode[message.chat.id] = self.__compute_keyboard_delete_admin
            return self.client.send_message(message.chat.id, text="Введите id пользователя, которого нужно лишить прав администратора.")

        self.wait_mode[message.chat.id] = 0
        try:
            id = int(message.text.strip())
        except:
            return self.client.send_message(message.chat.id, text="Некорректный id пользователя.")

        try:
            user_desc = self.client.get_chat_member(id, id)
        except:
            return self.client.send_message(message.chat.id, text="Неизвестный пользователь.")
        username = user_desc.user.username
        if username is None:
            username = str(id)

        if user_desc.user.id in config.ADMINS:
            return self.client.send_message(message.chat.id, text="Запрещено менять права доступа пользователя " + username + ".")

        self.__add_user(id)
        conn = sqlite3.connect(self.users_information_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=" + str(id) + ";")
        if not cursor.fetchone()[2]:
            return self.client.send_message(message.chat.id, text="Пользователь " + username + " не обладает правами администратора.")

        cursor.execute("UPDATE users SET is_admin=0 WHERE user_id=" + str(id) + ";")
        conn.commit()

        self.client.send_message(message.chat.id, text="Пользователь " + username + " лишён прав администратора.")
        self.client.send_message(id, text="Вы были лишены прав администратора. Используйте /start для обновления функционала.")

    def __handler(self):
        print("TG client started.")

        @self.client.message_handler(content_types=['contact'])
        def contact_handler(message):
            self.__compute_command_contact(message)

        @self.client.message_handler(commands=['stop'])
        def stop(message):
            self.__compute_command_stop(message)

        @self.client.message_handler(commands=['get_id'])
        def get_id(message):
            self.__compute_command_get_id(message)

        @self.client.message_handler(commands=['start'])
        def start(message):
            self.__compute_command_start(message)

        @self.client.callback_query_handler(func=lambda call: True)
        def callback_inline(call):
            self.client.answer_callback_query(callback_query_id=call.id)
            data = call.data.split()
            if data[0] == "SWITCH_MONTH":
                self.__compute_callback_switch_month(data[1:], call.message)
            elif data[0] == "SET_DATE":
                self.__compute_callback_set_date(data[1:], call.message)
            elif data[0] == "UPDATE_DATE":
                self.__compute_callback_update_date(data[1:], call.message)
            elif data[0] == "SET_TIME":
                self.__compute_callback_set_time(data[1:], call.message)
            elif data[0] == "UPDATE_TIME":
                self.__compute_callback_update_time(data[1:], call.message)
            elif data[0] == "DESC":
                self.__compute_callback_desc(data[1:], call.message)
            elif data[0] == "DELETE":
                self.__compute_callback_delete(data[1:], call.message)
            elif data[0] == "RESTORE":
                self.__compute_callback_restore(data[1:], call.message)

        @self.client.message_handler(content_types=["text"])
        def on_message(message):
            if message.chat.id != message.from_user.id:
                return
            self.__add_user(message.chat.id)

            if self.wait_mode[message.chat.id] != 0:
                self.wait_mode[message.chat.id](message)
            elif message.text == "Добавить запись" or message.text == "Записаться":
                self.__compute_keyboard_sign_up(message)
            elif message.text == "Удалить запись":
                self.__compute_keyboard_sign_out(message)
            elif message.text == "Помощь":
                self.__compute_keyboard_help(message)
            elif message.text == "Список клиентов":
                self.__compute_keyboard_client_list(message)
            elif message.text == "Добавить адм.":
                self.__compute_keyboard_add_admin(message)
            elif message.text == "Удалить адм.":
                self.__compute_keyboard_delete_admin(message)

        self.client.infinity_polling()

    def run(self):
        self.client = telebot.TeleBot(config.TELEGRAM_TOKEN)
        self.handler_thread = threading.Thread(target=self.__handler)
        self.handler_thread.start()
