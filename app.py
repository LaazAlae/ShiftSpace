import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template, redirect, request, url_for, make_response, jsonify, send_from_directory
from collections import defaultdict, deque
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from flask import request, make_response
from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from hashlib import sha256
from uuid import uuid4
from time import time
import filetype
import secrets
import bcrypt
import uuid
import html
import os
from collections import defaultdict
from time import time
from flask import request, make_response
from pytz import timezone, utc


app = Flask(__name__)
socketio = SocketIO(app,
    cors_allowed_origins=[
        "https://friendsgotogether.com",
        "http://localhost:8080"
    ],
    transport=['websocket']
)



#DOs Protection
####################################################################################################################################################################################
ip_requests = defaultdict(deque)
blocked = {}

def get_real_ip():
    return request.headers.get('X-Real-IP', request.remote_addr)

def check_rate_limit():
    ip = get_real_ip()
    print(f"IP Address: {ip}")
    current_time = time()
    
    if ip in blocked:
        if current_time - blocked[ip] >= 30:
            del blocked[ip]
            ip_requests[ip].clear()
        else:
            return False
            
    ip_requests[ip].append(current_time)
    
    while ip_requests[ip] and current_time - ip_requests[ip][0] > 10:
        ip_requests[ip].popleft()
        request_count = len(ip_requests[ip])
        print(f"Request count for {ip}: {request_count}")
    
    if len(ip_requests[ip]) > 50:
        blocked[ip] = current_time
        return False
    
    return True
#######################################################################################################################################################################################################################




mongo_client = MongoClient("mongodb://mongo:27017/")
db = mongo_client["shiftSpace"]
usercred_collection = db["credentials"]


mongo_client = MongoClient("mongodb://mongo:27017/")
db = mongo_client["shiftSpace"]
TI_collection = db["TravelInfo"]

connected = {}


#load cities and states once when the application starts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'us-cities.txt'), 'r') as f:
    us_cities = set(line.strip().lower() for line in f if line.strip())

with open(os.path.join(BASE_DIR, 'us-states.txt'), 'r') as f:
    us_states = set(line.strip().lower() for line in f if line.strip())




####################################################################################################################################################################################
@app.route('/')
def home():
    authtoken = request.cookies.get('authtoken')
    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()
    user = usercred_collection.find_one({"authtoken": hashedtoken})
    if not user:
        return redirect(url_for('login'))
    
    xsrfToken = secrets.token_hex(32)
    theme_mode = user.get('theme_mode', 'dark')
    
    usercred_collection.update_one(
        {"authtoken": hashedtoken},
        {
            "$set": {
                "xsrf_token": xsrfToken,
                "theme_mode": theme_mode
            }
        }
    )
    
    return render_template(
        'index.html', 
        usrnm=user["username"], 
        xsrf_token=xsrfToken,
        theme_mode=theme_mode
    )
####################################################################################################################################################################################    




####################################################################################################################################################################################
@app.route('/update_theme', methods=['POST'])
def update_theme():
    authtoken = request.cookies.get('authtoken')
    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()
    theme_mode = request.json.get('theme_mode')
    
    usercred_collection.update_one(
        {"authtoken": hashedtoken},
        {"$set": {"theme_mode": theme_mode}}
    )
    return jsonify({"status": "success"})
####################################################################################################################################################################################



####################################################################################################################################################################################
@socketio.on('connect')
def connect():
    authtoken = request.cookies.get('authtoken')
    if not authtoken:
        disconnect()
        return

    hashedtoken = sha256(str(authtoken).encode('utf-8')).hexdigest()
    user = usercred_collection.find_one({"authtoken": hashedtoken})
    if not user:
        disconnect()
        return

    userId = user["_id"]
    connected[request.sid] = userId
    print(f'user {user["username"]} with _id({userId}) connected: {connected}')
####################################################################################################################################################################################





####################################################################################################################################################################################
@socketio.on('disconnect')
def disconnect():
    id = request.sid
    connected.pop(id, None)
    print(connected)
####################################################################################################################################################################################







####################################################################################################################################################################################
@socketio.on('newPost')
def newPost(data):
    authtoken = request.cookies.get('authtoken')
    if not authtoken or request.sid not in connected:
        #user not authenticated
        return

    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user or data.get("xsrf_token") != user.get("xsrf_token"):
        #invalid XSRF token or authentication
        return 

    pfpsource = user.get("pfpsrc", "/static/images/default.png")
    if pfpsource.startswith("/app/userUploads/"):
       pfpsource = pfpsource.replace("/app/userUploads/", "/userUploads/")

    # Extract and sanitize input data
    from_city = data.get("from_city", "").strip()
    from_state = data.get("from_state", "").strip()
    to_city = data.get("to_city", "").strip()
    to_state = data.get("to_state", "").strip()
    travel_date = data.get("travel_date", "").strip()
    post_details = data.get("post_details", "").strip()

    #backend validation checks
    if not from_city or not from_state:
        return

    if not to_city or not to_state:
        return

    if not travel_date:
        return

    if not post_details or len(post_details) > 300:
        #post details invalid or exceed maximum length
        return

    #validate cities and states
    if from_city.lower() not in us_cities or from_state.lower() not in us_states:
        #invalid starting city or state
        return

    if to_city.lower() not in us_cities or to_state.lower() not in us_states:
        #invalid destination city or state
        return

    #validate travel date 
    try:
        travel_date_obj = datetime.strptime(travel_date, '%Y-%m-%d').date()
        today = datetime.now().date()
        if travel_date_obj < today:
            return
    except ValueError:
        return

    #Create the post
    postData = {
        "from_city": html.escape(from_city),
        "from_state": html.escape(from_state),
        "to_city": html.escape(to_city),
        "to_state": html.escape(to_state),
        "travel_date": html.escape(travel_date),
        "post_details": html.escape(post_details),
        "username": user["username"],
        "pfpsrc": pfpsource,
        "uniqueid": str(uuid4()),
        "likes": [],
        "saves": [],
        "comments": []
    }

    #insert post into the database
    result = TI_collection.insert_one(postData)
    postData['_id'] = str(result.inserted_id)
    emit('new_post', postData, broadcast=True)
####################################################################################################################################################################################





####################################################################################################################################################################################
@app.route('/search-posts', methods=['POST'])
def search_posts():
    authtoken = request.cookies.get('authtoken')
    data = request.get_json()
    xsrf_token = data.get("xsrf_token")

    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user or xsrf_token != user.get("xsrf_token"):
        return jsonify({"status": "error", "message": "User not authenticated"}), 401

    query = {}
    if data.get("from_city"):
        query["$expr"] = {"$eq": [{"$toLower": "$from_city"}, html.escape(data["from_city"]).lower()]}
    if data.get("from_state"):
        query["$expr"] = {"$eq": [{"$toLower": "$from_state"}, html.escape(data["from_state"]).lower()]}
    if data.get("to_city"):
        query["$expr"] = {"$eq": [{"$toLower": "$to_city"}, html.escape(data["to_city"]).lower()]}
    if data.get("to_state"):
        query["$expr"] = {"$eq": [{"$toLower": "$to_state"}, html.escape(data["to_state"]).lower()]}
    if data.get("travel_date"):
        query["$expr"] = {"$eq": [{"$toLower": "$travel_date"}, html.escape(data["travel_date"]).lower()]}

    posts = list(TI_collection.find(query))
    for post in posts:
        post['_id'] = str(post['_id'])
        if 'comments' not in post:
            post['comments'] = []
        if 'likes' not in post:
            post['likes'] = []
        if 'saves' not in post:
            post['saves'] = []

    return jsonify(posts), 200
####################################################################################################################################################################################




####################################################################################################################################################################################
@socketio.on('request_time')
def handle_time_request(data):
    from datetime import datetime, timedelta
    import pytz

    est = pytz.timezone('America/New_York')

    message_id = data.get('messageId')
    post = TI_collection.find_one({"uniqueid": message_id})
    travel_date = post.get('travel_date')
    
    travel_date_obj = datetime.fromisoformat(travel_date)
    travel_date_obj = est.localize(travel_date_obj)
    travel_date_obj = travel_date_obj + timedelta(days=1)
    travel_date_str = travel_date_obj.strftime('%Y-%m-%d')
    
    server_time_est = datetime.now(est).isoformat()

    print("travel_date:", travel_date_str)
    print("time now:", server_time_est)

    emit('response_time', {
        'server_time': server_time_est,
        'travel_date': travel_date_str
    }, room=request.sid)

#####################################################################

@socketio.on('updateInteractions')
def updateInteractions(data):
    from datetime import datetime
    import pytz
    import html
    from hashlib import sha256

    est = pytz.timezone('America/New_York')

    authtoken = request.cookies.get('authtoken')
    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user or data.get("xsrf_token") != user.get("xsrf_token"):
        emit('error', {'message': 'Invalid XSRF token or authentication'}, room=request.sid)
        return

    post = TI_collection.find_one({"uniqueid": data.get("messageId")})
    if not post:
        emit('error', {'message': 'Post not found'}, room=request.sid)
        return

    username = data.get("interactuser")
    action = data.get("action")

    if action == "like":
        likes = post.get("likes", [])
        if username in likes:
            likes.remove(username)
        else:
            likes.append(username)
        post["likes"] = likes

    elif action == "save":
        saves = post.get("saves", [])
        if username in saves:
            saves.remove(username)
        else:
            saves.append(username)
        post["saves"] = saves

    elif action == "comment":
        travel_date_str = post.get('travel_date')
        travel_date_obj = datetime.fromisoformat(travel_date_str)
        travel_date_obj = est.localize(travel_date_obj)
        travel_date_obj = travel_date_obj.replace(hour=23, minute=59, second=59)
        print("comment date: ", travel_date_obj)
        current_time_est = datetime.now(est)
        if current_time_est > travel_date_obj:
            return
        
        comment_text = data.get("comment_text", "").strip()
        if not comment_text:
            emit('error', {'message': 'Comment text is empty'}, room=request.sid)
            return
        
        comment = {
            "username": username,
            "text": html.escape(comment_text)
        }
        comments = post.get("comments", [])
        comments.append(comment)
        post["comments"] = comments

    else:
        emit('error', {'message': 'Invalid action'}, room=request.sid)
        return

    TI_collection.update_one({"uniqueid": data["messageId"]}, {"$set": post})

    if '_id' in post:
        post['_id'] = str(post['_id'])

    emit('update_interaction', post, broadcast=True)

#############################################
    
@app.route('/update-interactions', methods=['POST'])
def updateInteractions():
    #get authentication token from cookies
    authtoken = request.cookies.get('authtoken')
    decodeInfo = request.get_json()
    xsrfFromHtml = decodeInfo.get("xsrf_token")

    #verify user authentication
    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user:
        return jsonify({"status": "error", "message": "User not authenticated"}), 401

    #verify XSRF token
    if xsrfFromHtml != user["xsrf_token"]:
        return jsonify({"status": "error", "message": "Invalid XSRF token"}), 403

   #get the current user's username
    username = decodeInfo["interactuser"]
    option = decodeInfo["option"]

    #find post
    post = TI_collection.find_one({"uniqueid": decodeInfo["messageId"]})
    if not post:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    #remove user from all interaction arrays 
    post["drivers"] = [user for user in post["drivers"] if user != username]
    post["cars"] = [user for user in post["cars"] if user != username]
    post["passengers"] = [user for user in post["passengers"] if user != username]

    #add user to selected option
    if option in ["drivers", "cars", "passengers"]:
        usersinteracted = post[option]
        if username not in usersinteracted:
            usersinteracted.append(username)
            post[option] = usersinteracted

    #update the post in the database
    TI_collection.update_one(
        {"uniqueid": decodeInfo["messageId"]},
        {"$set": {
            "drivers": post["drivers"],
            "cars": post["cars"],
            "passengers": post["passengers"]
        }}
    )

    return jsonify({
        "status": "success",
        "message": "Interaction updated",
        "updated": {
            "drivers": post["drivers"],
            "cars": post["cars"],
            "passengers": post["passengers"]
        }
    }), 200
####################################################################################################################################################################################







####################################################################################################################################################################################
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

#####################################################################

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

#####################################################################

@app.route('/logout', methods = ['POST'])
def logout():
    authtoken = request.cookies.get('authtoken')

    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()

    user = usercred_collection.find_one({"authtoken": hashedtoken})

    if not user or authtoken == None:
        return redirect(url_for('login'))
    
    usercred_collection.update_one({"authtoken": hashedtoken},{"$unset": {"authtoken": ""}})

    return redirect(url_for('login'))

#####################################################################

app.config['UPLOAD_FOLDER'] = '/app/userUploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    #authenticate user
    authtoken = request.cookies.get('authtoken')
    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()
    user = usercred_collection.find_one({"authtoken": hashedtoken})
    if not user:
        return redirect(url_for('login'))

    #load their current data
    if request.method == 'GET':
        pfpsource = user.get("pfpsrc", "/static/images/default.png")
        bio = user.get("bio", "")  
        theme_mode = user.get("theme_mode", "dark")
        
        if pfpsource.startswith("/app/userUploads/"):
            pfpsource = pfpsource.replace("/app/userUploads/", "/userUploads/")
        
        xsrfToken = secrets.token_hex(32)
        usercred_collection.update_one(
            {"authtoken": hashedtoken}, 
            {"$set": {"xsrf_token": xsrfToken}}
        )
        
        return render_template('profile.html', 
                             usrnm=user["username"], 
                             pfpsrc=pfpsource, 
                             bio=bio,
                             theme_mode=theme_mode,
                             xsrf_token=xsrfToken)

    #updte data
    if request.method == 'POST':
        #new bio
        new_bio = html.escape(request.form.get('bio', ''))
        
        #andle profile picture upload
        pfppath = user.get("pfpsrc", "/static/images/default.png")
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file.filename != '':
                filename = secure_filename(file.filename)
                pfppath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(pfppath)
                
                if not is_image(pfppath):
                    os.remove(pfppath)
                    pfppath = "/static/images/default.png"
        
        pfppath = pfppath.replace("/app/userUploads/", "/userUploads/")
        
        #update user document with new bio and profile picture
        usercred_collection.update_one(
            {"username": user["username"]}, 
            {"$set": {
                "bio": new_bio,
                "pfpsrc": pfppath
            }}
        )
        
        #update profile picture in travel posts
        TI_collection.update_many(
            {"username": user["username"]}, 
            {"$set": {"pfpsrc": pfppath}}
        )
        
        return redirect(url_for('profile'))

@app.route('/userUploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
####################################################################################################################################################################################





####################################################################################################################################################################################
from pymongo import ASCENDING

@app.route('/travel-info', methods=['GET', 'POST'])
def travelInfo():
    if request.method == 'POST':
        return sendInfo(request)

    if request.method == 'GET':
        print("GET called on travel-info")
        # Sort the posts by '_id' in ascending order (oldest first)
        history = TI_collection.find({}).sort('_id', ASCENDING)
        documents = list(history)

        for a in documents:
            print(a["from_city"])

        listHistory = []
        for i in documents:
            i["_id"] = str(i["_id"])  
            if 'comments' not in i:
                i['comments'] = []
            listHistory.append(i)

        return jsonify(listHistory)
    
##################################################################
    
@app.route('/saved-posts', methods=['GET'])
def get_saved_posts():
    authtoken = request.cookies.get('authtoken')
    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user:
        return jsonify({"status": "error", "message": "User not authenticated"}), 401

    username = user["username"]
    saved_posts = list(TI_collection.find({"saves": username}))
    for post in saved_posts:
        post['_id'] = str(post['_id'])
        if 'comments' not in post:
            post['comments'] = []
        if 'likes' not in post:
            post['likes'] = []
        if 'saves' not in post:
            post['saves'] = []

    print(username,"has",len(saved_posts),"saved posts")
    return jsonify(saved_posts), 200
####################################################################################################################################################################################





#helper functions
####################################################################################################################################################################################
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

#################################################################

def sendInfo(request):
    authtoken = request.cookies.get('authtoken')
    decodeInfo = request.get_json()
    xsrfFromHtml = decodeInfo.get("xsrf_token")
    

    city = html.escape(decodeInfo.get("city", ""))
    state = html.escape(decodeInfo.get("state", ""))
    self = html.escape(decodeInfo.get("self", ""))

    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})

    if not user:
        return jsonify({"status": "error", "message": "User not authenticated"}), 401
    
    if xsrfFromHtml != user["xsrf_token"]:
            return jsonify({"status": "error", "message": "Invalid XSRF token"}), 403
    
    unique_id = str(uuid.uuid4())

    decodeInfo["city"] = city
    decodeInfo["state"] = state
    decodeInfo["self"] = self
    decodeInfo["username"] = user["username"]
    decodeInfo["uniqueid"] = unique_id
    decodeInfo["drivers"] = []
    decodeInfo["cars"] = []
    decodeInfo["passengers"] = []


    # Insert into database
    TI_collection.insert_one(decodeInfo)

    return jsonify({"status": "success", "message": "Info added"}), 200

#################################################################

#check file signature
def is_image(file_path):
    kind = filetype.guess(file_path)
    if kind is not None:
        return kind.mime.startswith('image/') 
    return False  
####################################################################################################################################################################################

cities = []





@app.before_request
def before_request():
    if not check_rate_limit():
        return make_response("Too many requests. Please try again in 30 seconds.", 429)


@app.after_request
def set_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)