function postMessage() {
    const content = document.getElementById('postContent').value;
    const postsDiv = document.getElementById('posts');
    const postElement = document.createElement('p');
    postElement.innerText = content;
    postsDiv.appendChild(postElement);
}