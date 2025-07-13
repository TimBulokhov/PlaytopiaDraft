import requests
import argparse
import sys

def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Пополнение баланса Steam')
    parser.add_argument('--login', required=True, help='Логин Steam')
    parser.add_argument('--amount', type=float, required=True, help='Сумма пополнения в рублях (может быть с копейками)')
    
    args = parser.parse_args()
    
    API_KEY = '1d8036ce63f0416c5f5b262a6670b639'
    STEAM_LOGIN = args.login
    SERVICE_ID = '5955'  # ID для пополнения Steam
    COMMISSION = 0.07  # 7% комиссия (как указано на сайте)

    # 1. Проверка баланса
    balance_url = 'https://balancesteam.ru/api/v2/partner/balance'
    balance_data = {'apikey': API_KEY}
    balance_response = requests.post(balance_url, data=balance_data)
    balance_result = balance_response.json()
    print('Проверка баланса:', balance_result)

    if balance_result.get('error'):
        print('Ошибка при проверке баланса:', balance_result.get('message'))
        sys.exit(1)

    balance = float(balance_result.get('balance', 0))
    required_amount = round(args.amount * (1 + COMMISSION), 2)

    print(f'Сумма пополнения: {args.amount:.2f} руб.')
    print(f'Сумма списания с учетом комиссии: {required_amount:.2f} руб.')
    print(f'Доступный баланс: {balance:.2f} руб.')

    if balance < required_amount:
        print(f'Недостаточно средств. Нужно: {required_amount:.2f} руб., доступно: {balance:.2f} руб.')
        sys.exit(1)

    # 2. Проверка Steam логина
    check_url = 'https://balancesteam.ru/api/v2/partner/check'
    check_data = {
        'apikey': API_KEY,
        'login_or_email': STEAM_LOGIN,
        'service_id': SERVICE_ID
    }
    check_response = requests.post(check_url, data=check_data)
    check_result = check_response.json()
    print('Проверка логина:', check_result)

    if check_result.get('error'):
        print('Ошибка при проверке логина:', check_result.get('message'))
        sys.exit(1)
    if not check_result.get('status'):
        print('Нельзя пополнить этот аккаунт. Возможно, региональные ограничения или ошибка в логине.')
        sys.exit(1)

    # 3. Создание заказа на пополнение
    create_url = 'https://balancesteam.ru/api/v2/partner/create'
    create_data = {
        'apikey': API_KEY,
        'login_or_email': STEAM_LOGIN,
        'service_id': SERVICE_ID,
        'amount': round(args.amount, 2)
    }
    create_response = requests.post(create_url, data=create_data)
    create_result = create_response.json()
    print('Создание заказа:', create_result)

    if create_result.get('error'):
        print('Ошибка при создании заказа:', create_result.get('message'))
        sys.exit(1)

    print(f"Заказ успешно создан! ID заказа: {create_result.get('id')}, сумма пополнения: {args.amount:.2f} руб.")

if __name__ == '__main__':
    main()