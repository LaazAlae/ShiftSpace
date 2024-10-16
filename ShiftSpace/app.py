from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)

@app.route('/')
def home():
    username = session.get('username', 'Guest') if session.get('username') else 'Guest'
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    session['username'] = username
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.after_request
def set_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)