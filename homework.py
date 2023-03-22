import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (ApiNotAllow, DataError, NoneHwName, StatusCodeError,
                        StrangeStatus, TokenError)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

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

ERROR_LIST = []


def check_error_list(bot: telegram.Bot, error: str) -> None:
    """
    При отсутсвии ошибки в глобальном списке ошибок добавляет ее в список.
    Отправляет сообщение об ошибки в чат, если ошибки не было в списке.
    """
    if error not in ERROR_LIST:
        ERROR_LIST.append(error)
        send_message(bot, error)
    logging.error(error)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    vars = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    if not all((var is not None and type(var) == str) for var in vars):
        logging.critical('Токены отсутствуют или имеют не верный тип')
        raise TokenError()


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено в чат')
    except telegram.error.TelegramError as e:
        logging.error(f'Ошибка отправки сообщения {e}')


def get_api_answer(timestamp: float) -> dict:
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
    expected_keys = ('homeworks', 'current_date')
    if type(response) != dict:
        raise TypeError('Неверный тип данных в ответе на запрос')
    if not all(key in response for key in expected_keys):
        raise DataError('В ответе API нет нужных данных')
    if not type(response['homeworks']) == list:
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


def main():
    """
    Делает запрос к API домашних работ.
    При наличии обновлений или ошибок отправляет сообщение о событии в чат.
    """
    current_hw_status = {}
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = time.time()

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

        except DataError as e:
            check_error_list(bot, str(e))

        except StrangeStatus as e:
            check_error_list(bot, str(e))

        except NoneHwName as e:
            check_error_list(bot, str(e))

        except TypeError as e:
            check_error_list(bot, str(e))

        except Exception as e:
            logging.error(f'Сбой в работе программы: {e}')

        finally:
            if not new_updates:
                logging.debug('Нет новых обновлений')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
