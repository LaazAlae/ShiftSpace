import eventlet
eventlet.monkey_patch()


from flask import Flask, render_template, redirect, request, url_for, make_response, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from pymongo import MongoClient, DESCENDING
from hashlib import sha256
from uuid import uuid4
import filetype
import secrets
import bcrypt
import uuid
import html
import os


app = Flask(__name__)
socketio = SocketIO(app,
    cors_allowed_origins=[
        "https://friendsgotogether.com",
        "http://localhost:8080"
    ],
    transport=['websocket']
)


mongo_client = MongoClient("mongodb://mongo:27017/")
db = mongo_client["shiftSpace"]
usercred_collection = db["credentials"]


mongo_client = MongoClient("mongodb://mongo:27017/")
db = mongo_client["shiftSpace"]
TI_collection = db["TravelInfo"]

connected = {}




####################################################################################################################################################################################
@app.route('/')
def home():
    authtoken = request.cookies.get('authtoken')

    hashedtoken = (sha256(str(authtoken).encode('utf-8'))).hexdigest()

    user = usercred_collection.find_one({"authtoken": hashedtoken})

    if not user:
        return redirect(url_for('login'))
    
    xsrfToken = secrets.token_hex(32)

    usercred_collection.update_one({"authtoken": hashedtoken},{"$set": {"xsrf_token": xsrfToken}})

    return render_template('index.html', usrnm = user["username"], xsrf_token = xsrfToken )
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
        emit('error', {'message': 'User not authenticated'}, room=request.sid)
        return

    user = usercred_collection.find_one({"authtoken": sha256(str(authtoken).encode('utf-8')).hexdigest()})
    if not user or data.get("xsrf_token") != user.get("xsrf_token"):
        emit('error', {'message': 'Invalid XSRF token or authentication'}, room=request.sid)
        return 
    
    pfpsource = user.get("pfpsrc", "/static/images/default.png")
    if pfpsource.startswith("/app/userUploads/"):
       pfpsource = pfpsource.replace("/app/userUploads/", "/userUploads/")


    postDetails = data.get("post_details", "")
    if len(postDetails) > 500:
        emit('error', {'message': 'Journey details exceed maximum length'}, room=request.sid)
        return

    postData = {
        "from_city": html.escape(data.get("from_city", "")),
        "from_state": html.escape(data.get("from_state", "")),
        "to_city": html.escape(data.get("to_city", "")),
        "to_state": html.escape(data.get("to_state", "")),
        "travel_date": html.escape(data.get("travel_date", "")),
        "post_details": html.escape(postDetails),
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
@socketio.on('updateInteractions')
def updateInteractions(data):
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
        #toggle like
        likes = post.get("likes", [])
        if username in likes:
            likes.remove(username)
        else:
            likes.append(username)
        post["likes"] = likes

    elif action == "save":
        #toggle save
        saves = post.get("saves", [])
        if username in saves:
            saves.remove(username)
        else:
            saves.append(username)
        post["saves"] = saves

    elif action == "comment":
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

    #update post in the db
    TI_collection.update_one({"uniqueid": data["messageId"]}, {"$set": post})

    #convert ObjectId to string to avoid bug
    if '_id' in post:
        post['_id'] = str(post['_id'])

    #emit updated post to clients
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
        firstname = user.get("firstnm", "enter first name")
        lastname = user.get("lastnm", "enter last name")
        
        pfpsource = user.get("pfpsrc", "/static/images/default.png")
        if pfpsource.startswith("/app/userUploads/"):
            pfpsource = pfpsource.replace("/app/userUploads/", "/userUploads/")
        
        xsrfToken = secrets.token_hex(32)

        usercred_collection.update_one({"authtoken": hashedtoken}, {"$set": {"xsrf_token": xsrfToken}})
        return render_template('profile.html', usrnm=user["username"], firstnm=firstname, lastnm=lastname, pfpsrc=pfpsource, xsrf_token=xsrfToken)

    #update their data
    if request.method == 'POST': 
        newusername = html.escape(request.form.get('username'))
        newfirstnm = html.escape(request.form.get('first_name'))
        newlastnm = html.escape(request.form.get('last_name'))

        oldusername = user["username"]

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
        
        TI_collection.update_many({"username": oldusername}, {"$set": {"username": newusername, "pfpsrc": pfppath}})
        usercred_collection.update_one({"username": oldusername}, {"$set": {"username": newusername, "firstnm": newfirstnm, "lastnm": newlastnm, "pfpsrc": pfppath}})
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









@app.after_request
def set_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)