let info = [];
const ws = true;
let socket = null;
let currentMessageId = null;
let cities = [];
let states = [];

function loadCitiesAndStates() {
    fetch('/static/us-cities.txt')
        .then(response => response.text())
        .then(text => {
            cities = text.split('\n').map(city => city.trim()).filter(city => city !== '');
        });
    fetch('/static/us-states.txt')
        .then(response => response.text())
        .then(text => {
            states = text.split('\n').map(state => state.trim()).filter(state => state !== '');
        });
}

function filterDatalist(input, list, datalistId) {
    const datalist = document.getElementById(datalistId);
    const value = input.value.trim().toLowerCase();

    datalist.innerHTML = '';

    if (value === '') {
        return;
    }

    const filteredList = list.filter(item => item.toLowerCase().startsWith(value));

    const maxSuggestions = 10;
    filteredList.slice(0, maxSuggestions).forEach(item => {
        const option = document.createElement('option');
        option.value = item;
        datalist.appendChild(option);
    });
}

function validateInput(input, list) {
    const value = input.value.trim().toLowerCase();
    const found = list.some(item => item.toLowerCase() === value);
    if (found || value === '') {
        input.style.borderColor = '';
    } else {
        input.style.borderColor = 'red';
    }
}

function disablePastDates() {
    const today = new Date().toISOString().split('T')[0];
    const travelDateInput = document.getElementById('travel-date');
    const lookupDateInput = document.getElementById('lookup-date');

    if (travelDateInput) {
        travelDateInput.setAttribute('min', today);
    }

    if (lookupDateInput) {
        lookupDateInput.setAttribute('min', today);
    }
}

function start() {
    loadCitiesAndStates();
    updateInfo();
    document.getElementById('home-btn').classList.add('active');

    if (ws) {
        initWS();
    } else {
        setInterval(updateInfo, 3000);
    }

    const cityInputs = [
        document.getElementById('from-city'),
        document.getElementById('to-city'),
        document.getElementById('lookup-from-city'),
        document.getElementById('lookup-to-city')
    ];

    const stateInputs = [
        document.getElementById('from-state'),
        document.getElementById('to-state'),
        document.getElementById('lookup-from-state'),
        document.getElementById('lookup-to-state')
    ];

    cityInputs.forEach(input => {
        input.addEventListener('input', function() {
            filterDatalist(this, cities, 'cities-list');
            validateInput(this, cities);
            validateForm();
        });
    });

    stateInputs.forEach(input => {
        input.addEventListener('input', function() {
            filterDatalist(this, states, 'states-list');
            validateInput(this, states);
            validateForm();
        });
    });

    const postDetailsInput = document.getElementById('post-details');
    const postDetailsCount = document.getElementById('post-details-count');
    postDetailsInput.addEventListener('input', function() {
        updateCharacterCount(this, postDetailsCount, 300);
        validateForm();
    });

    const travelDateInput = document.getElementById('travel-date');
    travelDateInput.addEventListener('input', validateForm);

    validateForm();
    disablePastDates();
}


function updateCharacterCount(textarea, countDisplay, maxChars) {
    const currentLength = textarea.value.length;
    countDisplay.textContent = `${currentLength}/${maxChars} characters`;

    const postButton = document.getElementById('create-post');

    if (currentLength > maxChars) {
        textarea.style.borderColor = 'red';
        countDisplay.classList.add('exceeded');
        postButton.disabled = true; 
    } else {
        textarea.style.borderColor = '';
        countDisplay.classList.remove('exceeded');
        postButton.disabled = false; 
    }
}

function initWS() {
    //initialize the Socket.IO connection
    socket = io({
        transports: ['websocket'],
        path: '/socket.io/',  
        secure: true 
    });

    //listen for messages from the server
    socket.on('message', function (message) {
        addInfo(message);
    });

    //listen for new posts or interaction updates
    socket.on('new_post', function (message) {
        addInfo(message);
    });

    socket.on('update_interaction', function (message) {
        optionupdateWs(message);
    });

    socket.on('connect_error', function (error) {
        console.error("WebSocket connection error:", error);
    });
}


function optionupdateWs(infoJSON) {
    console.log("optionupdateWs:", infoJSON);
    const messageElement = document.getElementById(`message_${infoJSON.uniqueid}`);
    if (!messageElement) {
        console.error(`Info from WS not found.`);
        return;
    }
    const newHtmlContent = infoHTML(infoJSON);

    // Replace the existing post with the updated content
    messageElement.outerHTML = newHtmlContent;

    // Update the info array with the updated post
    const index = info.findIndex(item => item.uniqueid === infoJSON.uniqueid);
    if (index !== -1) {
        info[index] = infoJSON;
    }

    // If the comment modal is open for this post, update it
    if (currentMessageId === infoJSON.uniqueid) {
        updateCommentModal(infoJSON);
    }
}



function updateCommentModal(post) {
    const modalComments = document.getElementById("modal-comments");

    // Clear previous comments
    modalComments.innerHTML = '';

    // Ensure post.comments is an array
    const comments = Array.isArray(post.comments) ? post.comments : [];

    // Display existing comments
    comments.forEach(comment => {
        // Determine if the comment is from the current user
        const isCurrentUser = comment.username === usrnm;

        // Create a comment bubble
        const commentBubble = document.createElement('div');
        commentBubble.classList.add('comment-bubble');
        if (isCurrentUser) {
            commentBubble.classList.add('my-comment');
        } else {
            commentBubble.classList.add('other-comment');
        }

        // Add content to the bubble
        commentBubble.innerHTML = `
            <div class="comment-username">${comment.username}</div>
            <div class="comment-text">${comment.text}</div>
        `;

        // Append the bubble to the modal comments container
        modalComments.appendChild(commentBubble);
    });

    // Scroll to the bottom of the modal to show the latest comment
    modalComments.scrollTop = modalComments.scrollHeight;
}



function updateInteractionsAJAX(data) {
    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const updatedPost = JSON.parse(this.responseText);
            optionupdateWs(updatedPost);
        }
    };
    request.open("POST", "/update-interactions");
    request.setRequestHeader("Content-Type", "application/json");
    request.send(JSON.stringify(data));
}



function sendinfo() {
    if (document.getElementById('create-post').disabled) {
        return;
    }

    //input elements
    const fromCityInput = document.getElementById("from-city");
    const fromStateInput = document.getElementById("from-state");
    const toCityInput = document.getElementById("to-city");
    const toStateInput = document.getElementById("to-state");
    const travelDateInput = document.getElementById("travel-date");
    const postDetailsInput = document.getElementById("post-details");

    //input values
    const fromCity = fromCityInput.value.trim();
    const fromState = fromStateInput.value.trim();
    const toCity = toCityInput.value.trim();
    const toState = toStateInput.value.trim();
    const travelDate = travelDateInput.value.trim();
    const postDetails = postDetailsInput.value.trim();

    //validate inputs
    if (fromCity === "") {
        fromCityInput.focus();
    } else if (fromState === "") {
        fromStateInput.focus();
    } else if (toCity === "") {
        toCityInput.focus();
    } else if (toState === "") {
        toStateInput.focus();
    } else if (travelDate === "") {
        travelDateInput.focus();
    } else if (postDetails === "") {
        postDetailsInput.focus();
    } else if (postDetails.length > 300) {
        alert('Post description cannot exceed 300 characters.');
        postDetailsInput.focus();
    } else {
        // If all inputs valid sendifno
        const xsrf = document.getElementById("xsrf_token").value;
        const infoJSON = {
            "from_city": fromCity,
            "from_state": fromState,
            "to_city": toCity,
            "to_state": toState,
            "travel_date": travelDate,
            "post_details": postDetails,
            "xsrf_token": xsrf
        };

        if (ws && socket) {
            socket.emit('newPost', infoJSON);
        } else {
            const request = new XMLHttpRequest();
            request.onreadystatechange = function () {
                if (this.readyState === 4 && this.status === 200) {
                    console.log(this.response);
                }
            };
            request.open("POST", "/travel-info");
            request.setRequestHeader("Content-Type", "application/json");
            request.send(JSON.stringify(infoJSON));
        }

        //clear input fields
        fromCityInput.value = "";
        fromStateInput.value = "";
        toCityInput.value = "";
        toStateInput.value = "";
        travelDateInput.value = "";
        postDetailsInput.value = "";

        updateCharacterCount(postDetailsInput, document.getElementById('post-details-count'), 300);

        //disable the post button since the form is now empty
        document.getElementById('create-post').disabled = true;
        
        //focus back to first input
        fromCityInput.focus();
        
        //revalidate the form
        validateForm();
    }
}


function validateForm() {
    const fromCityInput = document.getElementById("from-city");
    const fromStateInput = document.getElementById("from-state");
    const toCityInput = document.getElementById("to-city");
    const toStateInput = document.getElementById("to-state");
    const travelDateInput = document.getElementById("travel-date");
    const postDetailsInput = document.getElementById("post-details");

    const fromCity = fromCityInput.value.trim();
    const fromState = fromStateInput.value.trim();
    const toCity = toCityInput.value.trim();
    const toState = toStateInput.value.trim();
    const travelDate = travelDateInput.value.trim();
    const postDetails = postDetailsInput.value.trim();

    let isValid = true;

    // validate From City
    if (fromCity === "" || !cities.some(city => city.toLowerCase() === fromCity.toLowerCase())) {
        isValid = false;
    }

    //validate From State
    if (fromState === "" || !states.some(state => state.toLowerCase() === fromState.toLowerCase())) {
        isValid = false;
    }

    //validate To City
    if (toCity === "" || !cities.some(city => city.toLowerCase() === toCity.toLowerCase())) {
        isValid = false;
    }

    //To State
    if (toState === "" || !states.some(state => state.toLowerCase() === toState.toLowerCase())) {
        isValid = false;
    }

    // Validate Travel Date
    if (travelDate === "") {
        isValid = false;
    } else {
        const today = new Date().toISOString().split('T')[0];
        if (travelDate < today) {
            isValid = false;
        }
    }

    //post Details
    if (postDetails === "" || postDetails.length > 300) {
        isValid = false;
    }

    const postButton = document.getElementById('create-post');

    if (isValid) {
        postButton.disabled = false;
    } else {
        postButton.disabled = true;
    }
}

function updateInfo() {
    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            updateUI(JSON.parse(this.response));
        }
    };
    request.open("GET", "/travel-info");
    request.send();
}

function updateUI(serverInfo) {
    const travelInfo = document.getElementById("travel-info");
    travelInfo.innerHTML = '';

    serverInfo.forEach(infoItem => {
        addInfo(infoItem);
    });

    info = serverInfo;
}

function addInfo(infoJSON) {
    console.log("addInfo called with:", infoJSON);
    const travelInfo = document.getElementById("travel-info");
    if (!travelInfo) {
        console.error('Travel info not found.');
        return;
    }

    const htmlContent = infoHTML(infoJSON);
    travelInfo.insertAdjacentHTML("afterbegin", htmlContent); 

    info.unshift(infoJSON); 
    console.log("Current info array:", info);
}


function infoHTML(infoJSON) {
    const {
        username,
        pfpsrc,
        from_city,
        from_state,
        to_city,
        to_state,
        travel_date,
        post_details,
        uniqueid,
        likes = [],
        saves = [],
        comments = []
    } = infoJSON;

    // Format the travel date to be more readable
    const formattedDate = travel_date.split('-').slice(1).join('/') + '/' + travel_date.split('-')[0];

    return `
    <div id='message_${uniqueid}' class="travel-post">
        <div class="post-header">
            <img src="${pfpsrc}" alt="${username}'s profile" class="profile-image">
            <div class="user-info">
                <h3 class="username">${username}</h3>
            </div>
            <div class="post-toggle" onclick="toggleDetails('${uniqueid}')">
                <span class="toggle-text">Journey details</span>
                <span class="toggle-arrow">▼</span>
            </div>
        </div>
        
        <div class="travel-route">
            <div class="route-location">
                <div class="city">${from_city}</div>
                <div class="state">${from_state}</div>
            </div>
            <div class="route-arrow">→</div>
            <div class="route-location">
                <div class="city">${to_city}</div>
                <div class="state">${to_state}</div>
            </div>
        </div>
        
        <div class="travel-date">
            <span class="date-icon"></span>
            <span>${formattedDate}</span>
        </div>
        
        <div class="post-details-container">
            <p class="post-details">${post_details}</p>
        </div>
        
        <div class="post-footer">
            <button class="interaction-btn like-btn ${likes.includes(usrnm) ? 'active' : ''}" 
                    onclick="handleLike('${uniqueid}')">
                <span class="material-symbols-outlined">
                    ${likes.includes(usrnm) ? 'favorite' : 'favorite_border'}
                </span>
                <span class="count">${likes.length}</span>
            </button>
            
            <button class="interaction-btn save-btn ${saves.includes(usrnm) ? 'active' : ''}" 
                    onclick="handleSave('${uniqueid}')">
                <span class="material-symbols-outlined">
                    ${saves.includes(usrnm) ? 'star' : 'star_border'}
                </span>
                <span class="count">${saves.length}</span>
            </button>
            
            <button class="interaction-btn comment-btn" 
                    onclick="handleComment('${uniqueid}')">
                <span class="material-symbols-outlined">chat_bubble</span>
                <span class="count">${comments.length}</span>
            </button>
        </div>
    </div>
    `;
}



function toggleDetails(uniqueid) {
    const postElement = document.getElementById(`message_${uniqueid}`);
    const detailsContainer = postElement.querySelector('.post-details-container');

    if (postElement.classList.contains('expanded')) {
        // Collapse the details
        detailsContainer.style.maxHeight = `${detailsContainer.scrollHeight}px`;
        // Trigger reflow to apply the current max-height before transitioning to 0
        detailsContainer.offsetHeight;
        detailsContainer.style.maxHeight = '0';
        postElement.classList.remove('expanded');
    } else {
        // Expand the details
        detailsContainer.style.maxHeight = `${detailsContainer.scrollHeight}px`;
        postElement.classList.add('expanded');

        // After the transition, remove the inline max-height to allow for content changes
        detailsContainer.addEventListener('transitionend', function handler() {
            detailsContainer.style.maxHeight = 'none';
            detailsContainer.removeEventListener('transitionend', handler);
        });
    }
}

// Ensure the function is accessible globally
window.toggleDetails = toggleDetails;



function handleOption(option, messageId, OP) {
    const xsrf = document.getElementById("xsrf_token").value;
    const interactionsJSON = {
        "messageId": messageId,
        "option": option,
        "xsrf_token": xsrf,
        "OP": OP,
        "interactuser": usrnm
    };

    if (ws && socket) {
        socket.emit('updateInteractions', interactionsJSON);
    } else {
        const request = new XMLHttpRequest();
        request.onreadystatechange = function () {
            if (this.readyState === 4 && this.status === 200) {
                updateInfo();
            }
        };
        request.open("POST", "/update-interactions");
        request.setRequestHeader("Content-Type", "application/json");
        request.send(JSON.stringify(interactionsJSON));
    }
}


function searchPosts() {
    const fromCity = document.getElementById("lookup-from-city").value;
    const fromState = document.getElementById("lookup-from-state").value;
    const toCity = document.getElementById("lookup-to-city").value;
    const toState = document.getElementById("lookup-to-state").value;
    const travelDate = document.getElementById("lookup-date").value;
    const xsrf = document.getElementById("xsrf_token").value;

    const searchData = {
        "from_city": fromCity,
        "from_state": fromState,
        "to_city": toCity,
        "to_state": toState,
        "travel_date": travelDate,
        "xsrf_token": xsrf
    };

    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const posts = JSON.parse(this.responseText);
            updateUI(posts);
        }
    };
    request.open("POST", "/search-posts");
    request.setRequestHeader("Content-Type", "application/json");
    request.send(JSON.stringify(searchData));
}



function handleLike(messageId) {
    const xsrf = document.getElementById("xsrf_token").value;
    const interactionsJSON = {
        "messageId": messageId,
        "action": "like",
        "xsrf_token": xsrf,
        "interactuser": usrnm
    };

    if (ws && socket) {
        socket.emit('updateInteractions', interactionsJSON);
    } else {
        updateInteractionsAJAX(interactionsJSON);
    }
}

function handleSave(messageId) {
    const xsrf = document.getElementById("xsrf_token").value;
    const interactionsJSON = {
        "messageId": messageId,
        "action": "save",
        "xsrf_token": xsrf,
        "interactuser": usrnm
    };

    if (ws && socket) {
        socket.emit('updateInteractions', interactionsJSON);
    } else {
        updateInteractionsAJAX(interactionsJSON);
    }
}

function handleComment(messageId) {
    socket.emit('request_time', { messageId });

    socket.once('response_time', (data) => {
        const serverTime = new Date(data.server_time);   
        const travelDate = new Date(data.travel_date); 

        travelDate.setHours(travelDate.getHours() + 5);

        console.log("ogdate", travelDate);  

        openCommentModal(messageId, serverTime, travelDate); 
    });
}




function updateCountdown(serverTime, travelDate) {
    const countdownElement = document.getElementById('comment-countdown');
    const statusTitle = document.getElementById('comment-status-title');
    
    const serverDateTime = new Date(serverTime);
    const travelDateTime = new Date(travelDate);
    
    if (serverDateTime > travelDateTime) {
        statusTitle.textContent = 'Comment Section Closed';
        countdownElement.textContent = 'Travel date has passed';
        
        const newCommentInput = document.getElementById('new-comment');
        const sendButton = newCommentInput.nextElementSibling;
        newCommentInput.disabled = true;
        sendButton.disabled = true;
        newCommentInput.placeholder = 'Comments are closed';
        return;
    }

    const timeDiff = travelDateTime - serverDateTime;
    console.log(travelDateTime)
    console.log(serverDateTime)
    console.log(timeDiff)
    
    const days = Math.floor(timeDiff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((timeDiff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((timeDiff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((timeDiff % (1000 * 60)) / 1000);
    
    const countdownText = `Time remaining: ${days} days ${hours} hours ${minutes} minutes ${seconds} seconds`;
    
    statusTitle.textContent = 'Comments close after travel date';
    countdownElement.textContent = countdownText;
}


function openCommentModal(messageId, serverTime, travelDate) {
    currentMessageId = messageId;
    const modal = document.getElementById("comment-modal");
    const newCommentInput = document.getElementById("new-comment");
    
    modal.style.display = "flex";
    newCommentInput.value = '';
    newCommentInput.addEventListener("keypress", handleCommentKeyPress);
    
    let currentServerTime = new Date(serverTime);  
    updateCountdown(currentServerTime, travelDate);
    
    const countdownInterval = setInterval(() => {
        currentServerTime = new Date(currentServerTime.getTime() + 1000);
        updateCountdown(currentServerTime, travelDate);
    }, 1000);
    
    modal.dataset.countdownInterval = countdownInterval;
    
    const post = info.find(item => item.uniqueid === messageId);
    if (post) {
        updateCommentModal(post);
    }
    
    newCommentInput.focus();
    modal.classList.add('active');
}


function closeCommentModal() {
    const modal = document.getElementById("comment-modal");
    const newCommentInput = document.getElementById("new-comment");
    
    //Clear countdown interval
    if (modal.dataset.countdownInterval) {
        clearInterval(Number(modal.dataset.countdownInterval));
        delete modal.dataset.countdownInterval;
    }
    
    modal.style.display = "none";
    newCommentInput.removeEventListener("keypress", handleCommentKeyPress);
    modal.classList.remove('active');
}


function handleCommentKeyPress(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitComment();
    }
}



// Add event listener to close modal when clicking outside
document.getElementById("comment-modal").addEventListener('click', function (event) {
    if (event.target === this) {
        closeCommentModal();
    }
});

// Prevent scrolling of background when modal is open
document.getElementById("comment-modal").addEventListener('wheel', function (event) {
    const modalComments = document.getElementById("modal-comments");
    const modalCommentsScrollTop = modalComments.scrollTop;
    const modalCommentsScrollHeight = modalComments.scrollHeight;
    const modalCommentsClientHeight = modalComments.clientHeight;
    const isAtTop = modalCommentsScrollTop === 0;
    const isAtBottom = modalCommentsScrollTop + modalCommentsClientHeight >= modalCommentsScrollHeight;

    if ((event.deltaY < 0 && isAtTop) || (event.deltaY > 0 && isAtBottom)) {
        event.preventDefault();
    }
}, { passive: false });



function submitComment() {
    const xsrf = document.getElementById("xsrf_token").value;
    const newCommentInput = document.getElementById("new-comment");
    const commentText = newCommentInput.value.trim();

    if (commentText === "") {
        newCommentInput.focus();
        return;
    }

    const commentData = {
        "messageId": currentMessageId,
        "action": "comment",
        "xsrf_token": xsrf,
        "interactuser": usrnm,
        "comment_text": commentText
    };

    if (ws && socket) {
        socket.emit('updateInteractions', commentData);
    } else {
        updateInteractionsAJAX(commentData);
    }

    // Clear the input field
    newCommentInput.value = '';
}


function getSavedPosts() {
    const request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const posts = JSON.parse(this.responseText);
            updateUI(posts);
        }
    };
    request.open("GET", "/saved-posts");
    request.send();
}
