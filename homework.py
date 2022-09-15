import logging, time, os, requests, telegram

from dotenv import load_dotenv

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

CHECK_STATUS_ERROR = True
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='main.log'
)

logging.debug('Бот запущен!')


class PracticumException(Exception):
    """Исключения бота."""
    pass


def send_message(bot, message):
    log = message.replace('\n', '')
    logging.info(f"Отправка сообщения в телеграм: {log}")
    return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    logging.info("Получение ответа от сервера")
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    payload = {'from_date': 0}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except ValueError as error:
        raise PracticumException(f"Ошибка в значении {error}")
    except TypeError as error:
        raise PracticumException(f"Не корректный тип данных {error}")
    if homework_statuses.status_code != 200:
        raise PracticumException("Сервер yandex не доступен")
    return homework_statuses.json()


def check_response(response):
    logging.debug("Проверка ответа API на корректность")
    if response['homeworks'] is None:
        raise PracticumException("Задания не обнаружены")
    if not isinstance(response['homeworks'], list):
        raise PracticumException("response['homeworks'] не является списком")
    logging.debug("API проверен на корректность")
    return response['homeworks']


def parse_status(homework):
    logging.debug(f"Парсим домашнее задание: {homework}")
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise PracticumException(
            "Обнаружен новый статус, отсутствующий в списке!"
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    if (
            PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None
    ):
        return False
    return True


def main():
    """Основная логика работы бота."""
    global CHECK_STATUS_ERROR
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        logging.critical("Отсутствует переменная(-ные) окружения")
    while True:
        try:
            response = get_api_answer(current_timestamp)
            CHECK_STATUS_ERROR == True
            homeworks = check_response(response)
            logging.info("Список домашних работ получен")
            if ((type(homeworks) is list)
                    and (len(homeworks) > 0)
                    and homeworks):
                send_message(bot, parse_status(homeworks[0]))
                logging.info("Сообщение отправлено")
            else:
                logging.info("Задания не обнаружены")
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)
        except PracticumException as error:
            logging.critical(f"Эндпоинт не доступен: {error}")
            if CHECK_STATUS_ERROR == True:
                send_message(bot, f"Эндпоинт не доступен: {error}")
            CHECK_STATUS_ERROR = False
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.critical(message)
            if CHECK_STATUS_ERROR == True:
                send_message(bot, message)
            CHECK_STATUS_ERROR = False
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
