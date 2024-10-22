from flask import Flask, render_template, redirect, request, url_for, make_response
from pymongo import MongoClient
from hashlib import sha256
import html
import bcrypt
from uuid import uuid4



app = Flask(__name__)


mongo_client = MongoClient("mongodb://mongo:27017/")
db = mongo_client["shiftSpace"]
usercred_collection = db["credentials"]




@app.route('/')
def home():
    authtoken = request.cookies.get('authtoken')

    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()

    user = usercred_collection.find_one({"authtoken": hashedtoken})

    if not user:
        return redirect(url_for('login'))

    return render_template('index.html', usrnm = html.unescape( user["username"] ))
        




@app.route('/login', methods=['GET', 'POST'])
def login():

    authtoken = request.cookies.get('authtoken')
    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()
    user = usercred_collection.find_one({"authtoken": hashedtoken})
    if user:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        #prepare username for db lookup
        safeusername = html.escape(username)

        #find user by username in db
        user = usercred_collection.find_one({"username": safeusername})

        if not user:
            return render_template('login.html', error="Username not found, please register.")
        
        elif bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            authtoken = uuid4()

            hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()

            usercred_collection.update_one({"username": safeusername}, {"$set": {"authtoken": hashedtoken}})

            response = make_response(redirect(url_for('home')))
            response.set_cookie('authtoken', str(authtoken), max_age = 60 * 60, httponly=True)

            return response
        
        else:
            return render_template('login.html', error="Incorrect Password, Please try again")
        
    return render_template('login.html')




@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        verification = request.form.get('password verification')

        if verification != password:
            return render_template('register.html', error="Passwords dont't match")

        user = usercred_collection.find_one({"username": username})
        if not user:

            #prepare password and username for db storage
            safeusername = html.escape(username)
            salt = bcrypt.gensalt(rounds=12)  
            hashedpassword = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

            is_valid, message = validate_password(password)
            if not is_valid:
                return render_template('register.html', error=message)
            
            # If password is valid, proceed with registration
            registered_user = {"username": safeusername, "password": hashedpassword}
            usercred_collection.insert_one(registered_user)
            return redirect(url_for('login'))
           
        else:
            return render_template('register.html', error="Username already exists, please login or chose a different one.")

    return render_template('register.html')




@app.route('/logout', methods = ['POST'])
def logout():
    authtoken = request.cookies.get('authtoken')

    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()

    user = usercred_collection.find_one({"authtoken": hashedtoken})

    if not user or authtoken == None:
        return redirect(url_for('login'))
    
    usercred_collection.update_one({"authtoken": hashedtoken},{"$unset": {"authtoken": ""}})

    return redirect(url_for('login'))




def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    has_lower = False
    has_upper = False
    has_digit = False
    has_special = False

    for char in password:
        if char.islower():
            has_lower = True
        elif char.isupper():
            has_upper = True
        elif char.isdigit():
            has_digit = True
        elif char in {'!', '@', '#', '$', '%', '^', '&', '(', ')', '-', '_', '='}:
            has_special = True

    if not has_lower:
        return False, "Password must contain at least one lowercase letter."
    if not has_upper:
        return False, "Password must contain at least one uppercase letter."
    if not has_digit:
        return False, "Password must contain at least one digit."
    if not has_special:
        return False, "Password must contain at least one special character (e.g., !, @, #)."

    # If all checks pass
    return True, ""





@app.after_request
def set_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)