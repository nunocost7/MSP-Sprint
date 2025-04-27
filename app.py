from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Secret key
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'flalblalkslecletkley')

# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plate TEXT,
        brand TEXT,
        model TEXT,
        type TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        origin TEXT,
        destination TEXT
    )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['user_email'] = email
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid email or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('index'))

@app.route('/vehicle', methods=['GET', 'POST'])
def vehicle():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (user_email,))
    user = c.fetchone()

    if not user:
        conn.close()
        return render_template('vehicle.html', error="User not found. Please log in again.")

    user_id = user[0]

    if request.method == 'POST':
        plate = request.form['plate']
        brand = request.form['brand']
        model = request.form['model']
        vehicle_type = request.form['type']


        import re
        if not re.match(r'^[A-Z0-9]{2}-[A-Z0-9]{2}-[A-Z0-9]{2}$', plate):
            conn.close()
            return render_template('vehicle.html', error="Invalid plate format. Use XX-XX-XX with letters and numbers.")

        c.execute("INSERT INTO vehicles (user_id, plate, brand, model, type) VALUES (?, ?, ?, ?, ?)",
                  (user_id, plate, brand, model, vehicle_type))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('vehicle.html')

@app.route('/route', methods=['GET', 'POST'])
def route():
    if request.method == 'POST':
        user_id = request.form['user_id']
        origin = request.form['origin']
        destination = request.form['destination']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO routes (user_id, origin, destination) VALUES (?, ?, ?)", (user_id, origin, destination))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('route.html')

@app.route('/car_info', methods=['GET'])
def car_info():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    user_email = session['user_email']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (user_email,))
    user_id = c.fetchone()[0]


    c.execute("SELECT type, plate, brand, model FROM vehicles WHERE user_id = ?", (user_id,))
    vehicles = c.fetchall()
    conn.close()

    return render_template('car_info.html', vehicles=vehicles)

@app.route('/api/route', methods=['GET'])
def proxy_route():
    print("Entered /api/route endpoint")
    api_key = '5b3ce3597851110001cf62482161737e1cc343318fbfac42d9c4497d'
    start = request.args.get('start')
    end = request.args.get('end')

    print(f"Received start: {start}, end: {end}")

    if not start or not end:
        print("Missing 'start' or 'end' parameter")
        return {"error": "Missing 'start' or 'end' parameter"}, 400

    url = f"https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        "Authorization": api_key
    }
    params = {
        "start": start,
        "end": end
    }

    print(f"Requesting route from {start} to {end} with profile 'driving-car'")

    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Response status code: {response.status_code}")
        response.raise_for_status()
        route_data = response.json()
        print(f"Route data received: {route_data}")

        if 'features' not in route_data or not route_data['features']:
            print(f"Error: 'features' key missing or empty in response: {route_data}")
            return {"error": "No route found. Please check the coordinates and try again."}, 400

        distance = route_data['features'][0]['properties']['segments'][0]['distance']
        duration = route_data['features'][0]['properties']['segments'][0]['duration']

        speed_limit = None
        if 'extras' in route_data['features'][0]['properties']:
            speed_limit_data = route_data['features'][0]['properties']['extras'].get('speed', {}).get('values', [])
            if speed_limit_data:
                speed_limit = speed_limit_data[0][2]

        print(f"Extracted distance: {distance}, duration: {duration}, speed limit: {speed_limit}")

        return {
            "distance": distance,
            "duration": duration,
            "speed_limit": speed_limit,
            "route": route_data
        }
    except requests.RequestException as e:
        print(f"RequestException: {e}")
        return {"error": "An error occurred while fetching the route data."}, 500
    except KeyError as e:
        print(f"KeyError: {e}")
        return {"error": "Unexpected response format from the API."}, 500


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
