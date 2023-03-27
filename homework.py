import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (ApiNotAllow, DataError, NoneHwName, StatusCodeError,
                        StrangeStatus, TokenError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('prac_token')
TELEGRAM_TOKEN = os.getenv('token')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_error_list(bot: telegram.Bot, error: Exception) -> None:
    """
    Проверяет тип ошибки и наличие сообщения о ней в глобальном списке ошибок.
    При отсутсвии сообщения о такой ошибки добавляет ее в список.
    Отправляет сообщение об ошибки в чат бота, если ошибки не было в списке.
    Логирует все типы ошибок.
    """
    #Типы ошибок, о которых следует единажды отправлять сообщение в чат бота.
    global ERROR_LIST
    e_types_for_chat = (DataError, NoneHwName, TypeError, StrangeStatus)
    if type(error) in e_types_for_chat and str(error) not in ERROR_LIST:
        ERROR_LIST.append(str(error))
        send_message(bot, str(error))
    logging.error(f'Сбой в работе программы: {error}')


def check_tokens() -> None:
    """Проверяет доступность переменных окружения."""
    vars = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    if not all(vars):
        logging.critical('Токены отсутствуют или имеют не верный тип')
        raise TokenError()


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено в чат')
    except telegram.error.TelegramError as e:
        logging.error(f'Ошибка отправки сообщения {e}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS,
            params={'from_date': timestamp}
        )
    except Exception as e:
        logging.error(f'Ошибка запроса к API {e}')
        raise ApiNotAllow()
    else:
        if response.status_code != 200:
            logging.error(f'Статус-код ответа: {response.status_code}')
            raise StatusCodeError()
        return response.json()


def check_response(response: dict) -> None:
    """Проверяет ответ API на соответствие документации."""
    expected_key: str = 'homeworks'
    if type(response) != dict:
        raise TypeError('Неверный тип данных в ответе на запрос')
    if expected_key not in response:
        raise DataError('В ответе API нет нужных данных')
    if type(response['homeworks']) != list:
        raise TypeError('Неверный тип данных по ключу "homeworks"')


def parse_status(homework: dict) -> str:
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name: str = homework.get('homework_name')
    if not homework_name:
        raise NoneHwName('Нет названия домашней работы')
    status: str = homework.get('status')
    verdict: str = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise StrangeStatus('Получен нестандартный статус домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """
    Делает запрос к API домашних работ.
    При наличии обновлений или ошибок отправляет сообщение о событии в чат.
    """
    current_hw_status = {}
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        new_updates = 0
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            for hw in homeworks:
                hw_id: int = hw.get('id')
                cur_message: str = current_hw_status.setdefault(hw_id, '')
                resp_message: str = parse_status(hw)
                if resp_message != cur_message:
                    current_hw_status[hw_id] = resp_message
                    send_message(bot, resp_message)
                    new_updates += 1
        except Exception as e:
            check_error_list(bot, e)
        finally:
            if not new_updates:
                logging.debug('Нет новых обновлений')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    ERROR_LIST = []

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s'
    )

    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    main()
