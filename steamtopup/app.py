from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import json
import subprocess
import sys
import os

app = Flask(__name__)
CORS(app)  # Добавляем поддержку CORS

# Читаем HTML файл
def get_html_content():
    main_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main', 'main.html')
    with open(main_html_path, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/')
def index():
    return get_html_content()



@app.route('/process_payment', methods=['POST'])
def process_payment():
    try:
        # Проверяем, что запрос содержит JSON
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Неверный формат запроса. Ожидается JSON.'
            }), 400
        
        data = request.get_json()
        steam_login = data.get('steam_login')
        amount = data.get('amount')
        
        print(f"Получен запрос: login={steam_login}, amount={amount}")  # Отладочная информация
        print(f"Тип amount: {type(amount)}")  # Проверяем тип данных
        
        if not steam_login or not amount:
            return jsonify({
                'success': False,
                'error': 'Необходимо указать логин Steam и сумму'
            }), 400
        
        # Проверяем, что файл скрипта существует
        script_path = os.path.join(os.path.dirname(__file__), 'steam_topup.py')
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'error': 'Скрипт steam_topup.py не найден'
            }), 500
        
        # Запускаем Python скрипт с параметрами
        cmd = [sys.executable, script_path, '--login', steam_login, '--amount', str(amount)]
        print(f"Запускаем команду: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        print(f"Код возврата скрипта: {result.returncode}")  # Отладочная информация
        print(f"Вывод скрипта: {result.stdout}")  # Отладочная информация
        print(f"Ошибки скрипта: {result.stderr}")  # Отладочная информация
        
        if result.returncode == 0:
            # Ищем ID заказа в выводе
            output_lines = result.stdout.split('\n')
            order_id = None
            for line in output_lines:
                if 'ID заказа:' in line:
                    order_id = line.split('ID заказа:')[1].split(',')[0].strip()
                    break
            
            return jsonify({
                'success': True,
                'order_id': order_id or 'N/A',
                'message': 'Заказ успешно создан'
            })
        else:
            # Ищем ошибку в выводе
            error_message = 'Произошла ошибка при обработке заказа'
            for line in result.stderr.split('\n'):
                if 'Ошибка' in line or 'error' in line.lower():
                    error_message = line.strip()
                    break
            
            return jsonify({
                'success': False,
                'error': error_message
            }), 400
            
    except Exception as e:
        print(f"Исключение в process_payment: {str(e)}")  # Отладочная информация
        return jsonify({
            'success': False,
            'error': f'Ошибка сервера: {str(e)}'
        }), 500

@app.route('/steamtopup/<path:filename>')
def steamtopup_static(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__)), filename)

@app.route('/allgames/allgames.html')
def allgames_page():
    allgames_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'allgames')
    return send_from_directory(allgames_path, 'allgames.html')

@app.route('/steamtopup/steamtopup.html')
def steamtopup_page():
    steamtopup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'steamtopup')
    return send_from_directory(steamtopup_path, 'steamtopup.html')

@app.route('/parser/games.json')
def serve_games_json():
    import os
    parser_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'parser')
    return send_from_directory(parser_dir, 'games.json')

@app.route('/parser/<path:filename>')
def parser_static(filename):
    import os
    parser_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'parser')
    return send_from_directory(parser_dir, filename)

@app.route('/playstation/<path:filename>')
def playstation_static(filename):
    import os
    playstation_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'playstation')
    return send_from_directory(playstation_dir, filename)

@app.route('/xbox/<path:filename>')
def xbox_static(filename):
    import os
    xbox_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'xbox')
    return send_from_directory(xbox_dir, filename)

@app.route('/nintendo/<path:filename>')
def nintendo_static(filename):
    import os
    nintendo_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'nintendo')
    return send_from_directory(nintendo_dir, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)