import datetime


TELEGRAM_TOKEN = ""
ADMINS = {}

USERS_INFORMATION_DB_NAME = "data/users_inf.db"
GEOLOCATION_PATH = "data/map.png"

TIMEZONE = datetime.timedelta(hours=0)
TIME_STEP = datetime.timedelta(minutes=15)
SERVICE_TIME = datetime.timedelta(hours=1)
WORKING_HOURS = [(datetime.time(hour=11), datetime.time(hour=20))]
DESC_WIGTH = 61
