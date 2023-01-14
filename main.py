import locale
from TelegramClient import TelegramClient


def main():
    locale.setlocale(locale.LC_ALL, locale.normalize("RU"))

    bot = TelegramClient()
    bot.run()


if __name__ == "__main__":
    main()
