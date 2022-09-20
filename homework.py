import http
import logging
import os
import sys

import requests
import telegram
import time

from dotenv import load_dotenv
from exceptions import PracticumException
from http import HTTPStatus

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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


def send_message(bot, message):
    """отправляет сообщение в Telegram чат."""
    try:
        log = message.replace('\n', '')
        logging.info(f'Начата отправка сообщения в телеграм: {log}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except PracticumException as error:
        raise PracticumException(f'Ошибка отправки сообщения {error}')


def get_api_answer(current_timestamp):
    """делает запрос к единственному эндпоинту API-сервиса."""
    logging.info('Получение ответа от сервера')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except ValueError as error:
        raise PracticumException(f'Ошибка в значении {error}')
    except TypeError as error:
        raise PracticumException(f'Не корректный тип данных {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise PracticumException('Сервер yandex не доступен')
    return homework_statuses.json()


def check_response(response):
    """проверяет ответ API на корректность."""
    logging.debug('Проверка ответа API на корректность')
    if not isinstance(response, dict):
        raise TypeError('response не является словарем')
    if 'homeworks' not in response:
        raise PracticumException(
            'homeworks отсутсвует в response'
        )
    homeworks = response['homeworks']
    if 'homeworks' in homeworks or 'current_date' in homeworks:
        raise PracticumException(
            'homeworks или current_date присутсвует в response'
        )
    if not isinstance(response['homeworks'], list):
        raise PracticumException("response['homeworks'] не является списком")
    logging.debug('API проверен на корректность')
    return homeworks


def parse_status(homework):
    """
    извлекает из информации о конкретной.
    домашней работе статус этой работы
    """
    logging.debug(f'Парсим домашнее задание: {homework}')
    if 'homework_name' not in homework:
        raise PracticumException(
            'Не обнаружен ключ homework в словаре!'
        )
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise PracticumException(
            'Не обнаружен ключ homework в словаре!'
        )
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise PracticumException(
            f'{homework_status} отсутствует в списке статусов'
            f'домашних работ'
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """проверяет доступность переменных окружения."""
    return all(
        (PRACTICUM_TOKEN,
         TELEGRAM_TOKEN,
         TELEGRAM_CHAT_ID)
    )


def main():
    """Основная логика работы бота."""
    CHECK_STATUS_ERROR = True
    if not check_tokens():
        logging.critical('Отсутствует переменная(-ные) окружения')
        sys.exit('Отсутствует переменная(-ные) окружения')
    logging.debug('Бот запущен!')
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            CHECK_STATUS_ERROR = True
            homeworks = check_response(response)
            if homeworks is None:
                raise PracticumException('Задания не обнаружены')
            logging.info('Список домашних работ получен')
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
                logging.info('Сообщение отправлено')
            else:
                logging.info('Задания не обнаружены')
            current_timestamp = response['current_date']
        except PracticumException as error:
            logging.critical(f'Эндпоинт не доступен: {error}')
            if CHECK_STATUS_ERROR:
                send_message(bot, f'Эндпоинт не доступен: {error}')
            CHECK_STATUS_ERROR = False
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.critical(message)
            if CHECK_STATUS_ERROR:
                send_message(bot, message)
            CHECK_STATUS_ERROR = False
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
