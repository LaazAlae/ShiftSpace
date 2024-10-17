from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
import extraFunction
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

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    if len(username) < 6:
        flash('Username must be at least 6 characters long.', 'error')
        return redirect(url_for('home'))

    if extraFunction.validate_password == False:
        flash('Passwords Requirement Missing', 'error')
        return redirect(url_for('home'))

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('home'))
    
    #==================================================================
    #######========== store to db right here ==================########
    #==================================================================
    flash('Registration successful! Please log in.', 'success')
    return redirect(url_for('home'))

@app.after_request
def set_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)