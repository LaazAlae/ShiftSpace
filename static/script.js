let info = {};


function start() {

    document.addEventListener("keypress", function (event) {
        if (event.code === "Enter") {
            sendinfo();
        }
    });

    var myDiv = document.getElementById("myDiv");
    myDiv.innerHTML = "New friendships and unforgettable memories await you.";

    updateInfo();

    setInterval(updateInfo, 3000);
}


function sendinfo() {

    const cityTextbox = document.getElementById("city")
    const stateTextbox = document.getElementById("state")
    const selfTextbox = document.getElementById("self")

    if (cityTextbox.value == ""){
        cityTextbox.focus();

    } else if (stateTextbox.value == ""){
        stateTextbox.focus();

    } else if (selfTextbox.value == ""){
        selfTextbox.focus();
        
    } else{

        const city = cityTextbox.value;
        const state = stateTextbox.value;
        const self = selfTextbox.value;
    
        cityTextbox.value = "";
        stateTextbox.value = "";
        selfTextbox.value = "";
    
        const xsrf = document.getElementById("xsrf_token").value;
    
        const request = new XMLHttpRequest();
        request.onreadystatechange = function () {
            if (this.readyState === 4 && this.status === 200) {
                console.log(this.response);
            }
        }
        cityTextbox.focus();
        stateTextbox.focus();
        selfTextbox.focus();
    
        const infoJSON = {"city": city, "state": state, "self": self, "xsrf_token": xsrf};
    
        request.open("POST", "/travel-info");
        request.setRequestHeader("Content-Type", "application/json");
        request.send(JSON.stringify(infoJSON));
    

    }
}



function updateInfo() {
    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            updateUI(JSON.parse(this.response));
        }
    }
    request.open("GET", "/travel-info");
    request.send();

}



function updateUI(serverInfo) {
    const travelInfo = document.getElementById("travel-info");
    
    const scrollPosition = travelInfo.scrollTop;

    travelInfo.innerHTML = '';

    serverInfo.forEach(info => {
        addInfo(info);
    });

    travelInfo.scrollTop = scrollPosition;
    info = serverInfo;
}



function addInfo(infoJSON) {
    console.log("addInfo called with:", infoJSON);
    const travelInfo = document.getElementById("travel-info");
    if (!travelInfo) {
        console.error("Element with id 'travel-info' not found.");
        return;
    }

    const existingMessage = document.getElementById(`message_${infoJSON.uniqueid}`);
    if (existingMessage) {
        console.log(`Message with ID ${infoJSON.uniqueid} already exists. Skipping.`);
        return; 
    }

    const htmlContent = infoHTML(infoJSON);
    travelInfo.insertAdjacentHTML("beforeend", htmlContent);
}



function infoHTML(infoJSON){
    const username = infoJSON.username;
    const city = infoJSON.city;
    const state = infoJSON.state;
    const self = infoJSON.self;
    const infoId = infoJSON.uniqueid;
    const drivers = infoJSON.drivers;
    const cars = infoJSON.cars;
    const passengers = infoJSON.passengers;
 
    let ourHTML = `<div id='message_${infoId}'>`;
 
    ourHTML +=
    `
    <div class="card">
        <div class="card-header">
            ${username}
        </div>

        <div class="card-body">
            <p>${username} wants to go to:</p>
            <p>${city}/${state}</p>
            <p>${self}</p>
        </div>

        <div class="card-footer">   
            <div class="button-group">
                <button class="option-btn ${drivers.includes(usrnm) ? 'active' : ''} " onclick="handleOption('driver', '${infoId}', '${username}')">
                    I can drive
                    <span class="count">${drivers.length}</span>
                </button>
                <button class="option-btn ${cars.includes(usrnm) ? 'active' : ''} " onclick="handleOption('car', '${infoId}', '${username}')">
                    I have a car
                    <span class="count">${cars.length}</span>
                </button>
                <button class="option-btn ${passengers.includes(usrnm) ? 'active' : '' } " onclick="handleOption('passenger', '${infoId}', '${username}')">
                    I'm a passenger
                    <span class="count">${passengers.length}</span>
                </button>
            </div>
        </div>
    </div>`;
   
    return ourHTML;
}


function handleOption(option, messageId, OP) {
    const xsrf = document.getElementById("xsrf_token").value;
    const request = new XMLHttpRequest();
    
    request.onreadystatechange = function () {
        if (this.readyState === 4) {
            if (this.status === 200) {
                updateInfo();
            } 
        }
    }

    const interactionsJSON = {
        "messageId": messageId,
        "option": option,
        "xsrf_token": xsrf,
        "OP": OP,
        "interactuser": usrnm
    };

    request.open("POST", "/update-interactions");
    request.setRequestHeader("Content-Type", "application/json");
    request.send(JSON.stringify(interactionsJSON));
}
 