let info = [];
const ws = true;
let socket = null;
let currentMessageId = null;

function start() {
    updateInfo();

    if (ws) {
        initWS();
    } else {
        setInterval(updateInfo, 3000);
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

    // Validate inputs
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
    } else {
        //if all inputs are filled
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

        //Clear input fields
        fromCityInput.value = "";
        fromStateInput.value = "";
        toCityInput.value = "";
        toStateInput.value = "";
        travelDateInput.value = "";
        postDetailsInput.value = "";

        //set focus back to the first input
        fromCityInput.focus();
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
    openCommentModal(messageId);
}




function openCommentModal(messageId) {
    currentMessageId = messageId;
    const modal = document.getElementById("comment-modal");
    const newCommentInput = document.getElementById("new-comment");

    modal.style.display = "flex";
    newCommentInput.value = '';

    newCommentInput.addEventListener("keypress", handleCommentKeyPress);

    const post = info.find(item => item.uniqueid === messageId);
    if (post) {
        updateCommentModal(post);
    }

    newCommentInput.focus();
    modal.classList.add('active');
}


function handleCommentKeyPress(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submitComment();
    }
}



function closeCommentModal() {
    const modal = document.getElementById("comment-modal");
    modal.style.display = "none";
    currentMessageId = null;

    const newCommentInput = document.getElementById("new-comment");
    newCommentInput.removeEventListener("keypress", handleCommentKeyPress);
    modal.classList.remove('active');
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
