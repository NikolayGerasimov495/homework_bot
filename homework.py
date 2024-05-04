import json
import logging
import os
import time
from datetime import datetime, timedelta
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from except_help import CustomAPIResponseError, JSONDecodeError

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(name)s - '
           '(%(filename)s).%(funcName)s(%(lineno)d) - %(message)s',
    handlers=[
        # Логи будут записываться в файл program.log
        logging.FileHandler("program.log"),
        logging.StreamHandler()  # Логи также будут выводиться в консоль
    ]
)
logger = logging.getLogger(__name__)
logger.debug('Начало работы бота')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical('Проблема с переменными окружения')
        exit()
    logger.debug('Доступность переменных окружения прошли корректно')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}')
    except Exception as telegram_error:
        logger.error(f'Сбой при отправке сообщения: {telegram_error}')
#telegram.TelegramError выдает ошибку и тесты на сервере не проходят импортировал все

def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка {error}')
    if response.status_code != HTTPStatus.OK:
        raise CustomAPIResponseError(
            f'Неуспешный статус ответа API: {response.status_code}')
    try:
        return response.json()
    except json.JSONDecodeError as error:
        raise JSONDecodeError(f'Ошибка при декодировании JSON: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации из.
    урока «API сервиса Практикум Домашка».
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')
    if 'homeworks' not in response or 'current_date' not in response:
        raise ValueError('В ответе API отсутствуют обязательные ключи')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks должны быть списком')
    if not homeworks:
        raise ValueError('Список homeworks пуст')
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise TypeError('current_date должен быть целым числом')
    return homeworks, current_date


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    required_keys = {'status', 'homework_name'}
    if not required_keys.issubset(homework.keys()):
        raise KeyError(
            f'Словарь homework должен содержать ключи: {required_keys}')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Такого статуса домашней работы нет: {homework.get("status")}')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_date = datetime.now()
    one_month_ago = current_date - timedelta(days=1)
    timestamp = int(one_month_ago.timestamp())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks, current_date = check_response(response)
            # Обновление timestamp для следующего запроса
            timestamp = current_date
            # Если новых статусов нет, отправляем сообщение об этом
            if not homeworks:
                message = 'Нет новых статусов домашних работ.'
                send_message(bot, message)
                logger.info(message)
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
                    logger.info(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
