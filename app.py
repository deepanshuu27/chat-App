from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
from flask_pymongo import PyMongo
import random
from string import ascii_uppercase

# Initialize Flask app
app = Flask(__name__)

# Configure the secret key and MongoDB URI for the app
app.config["SECRET_KEY"] = "hjhjsdahhds"
app.config["MONGO_URI"] = "mongodb://localhost:27017/chatapp"  # Update with your MongoDB URI

# Initialize PyMongo for MongoDB interaction
mongo = PyMongo(app)

# Initialize Flask-SocketIO for real-time communication
socketio = SocketIO(app)

# Function to generate a unique room code
def generate_unique_code(length):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if not mongo.db.rooms.find_one({"code": code}):
            break
    return code

# Home route to handle both GET and POST requests
@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        # Validate user input
        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        # Create a new room
        if create != False:
            room = generate_unique_code(4)
            mongo.db.rooms.insert_one({"code": room, "members": 0, "messages": []})
        # Check if the room exists for joining
        elif not mongo.db.rooms.find_one({"code": code}):
            return render_template("home.html", error="Room does not exist.", code=code, name=name)
        
        # Store room and name in session and redirect to the room page
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

# Route to display the chat room
@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None:
        return redirect(url_for("home"))
    
    room_data = mongo.db.rooms.find_one({"code": room})
    if not room_data:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, room=session['room'], messages=room_data["messages"])

# Route to handle leaving the room
@app.route('/leave')
def leave():
    room = session.get("room")
    if room:
        mongo.db.rooms.update_one({"code": room}, {"$inc": {"members": -1}})
    session.clear()
    return redirect(url_for('home'))

# SocketIO event handler for receiving messages
@socketio.on("message")
def message(data):
    room = session.get("room")
    if not room:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    mongo.db.rooms.update_one({"code": room}, {"$push": {"messages": content}})
    send(content, to=room)
    print(f"{session.get('name')} said: {data['data']}")

# SocketIO event handler for new connections
@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return

    room_data = mongo.db.rooms.find_one({"code": room})
    if not room_data:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    mongo.db.rooms.update_one({"code": room}, {"$inc": {"members": 1}})
    print(f"{name} joined room {room}")

# SocketIO event handler for disconnections
@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room:
        mongo.db.rooms.update_one({"code": room}, {"$inc": {"members": -1}})

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

# Run the Flask app with SocketIO
if __name__ == "__main__":
    socketio.run(app, debug=True)
