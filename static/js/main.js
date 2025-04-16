const API_URL = 'http://localhost:5000';
let token = localStorage.getItem('token');
let role = localStorage.getItem('role');

document.addEventListener('DOMContentLoaded', () => {
    updateUserInfo();
    loadPosts();
    document.getElementById('search-input').addEventListener('input', debounce(searchPosts, 500));
});

function updateUserInfo() {
    const userInfo = document.getElementById('user-info');
    if (token) {
        document.getElementById('post-form').style.display = 'block';
        userInfo.innerHTML = `
            <span class="navbar-text me-2">Xin chào, ${localStorage.getItem('username')} (${role})</span>
            <button class="btn btn-outline-danger" onclick="logout()">Đăng xuất</button>
        `;
    } else {
        userInfo.innerHTML = `
            <a href="/login" class="btn btn-outline-primary me-2">Đăng nhập</a>
            <a href="/register" class="btn btn-outline-success">Đăng ký</a>
        `;
    }
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    window.location.reload();
}

async function loadPosts(page = 1) {
    try {
        const response = await fetch(`${API_URL}/posts?page=${page}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const posts = await response.json();
        displayPosts(posts);
    } catch (error) {
        console.error('Lỗi tải bài viết:', error);
    }
}

function displayPosts(posts) {
    const postsDiv = document.getElementById('posts');
    postsDiv.innerHTML = '';
    posts.forEach(post => {
        const postCard = document.createElement('div');
        postCard.className = 'card post-card';
        postCard.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${post.title}</h5>
                <p class="card-text">${post.content}</p>
                ${post.image_url ? `<img src="${API_URL}${post.image_url}" class="img-fluid mb-3" alt="Post image">` : ''}
                <p class="card-text"><small class="text-muted">Đăng bởi ${post.author} vào ${post.created_at}</small></p>
                ${role === 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deletePost(${post.id})">Xóa</button>` : ''}
                <div class="comments"></div>
                <form class="comment-form mt-2" onsubmit="event.preventDefault(); addComment(${post.id}, this);">
                    <div class="input-group">
                        <input type="text" name="comment" class="form-control" placeholder="Viết bình luận..." required>
                        <button type="submit" class="btn btn-primary">Gửi</button>
                    </div>
                </form>
            </div>
        `;
        postsDiv.appendChild(postCard);
        loadComments(post.id, postCard.querySelector('.comments'));
    });
}

async function searchPosts() {
    const query = document.getElementById('search-input').value;
    if (!query) {
        loadPosts();
        return;
    }
    try {
        const response = await fetch(`${API_URL}/posts/search?q=${encodeURIComponent(query)}`);
        const posts = await response.json();
        displayPosts(posts);
    } catch (error) {
        console.error('Lỗi tìm kiếm:', error);
    }
}

async function loadComments(postId, commentsDiv) {
    try {
        const response = await fetch(`${API_URL}/comments/${postId}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const comments = await response.json();
        commentsDiv.innerHTML = comments.map(c => `
            <div class="comment">
                <strong>${c.author}</strong>: ${c.comment} <small>(${c.created_at})</small>
            </div>
        `).join('');
    } catch (error) {
        console.error('Lỗi tải bình luận:', error);
    }
}

async function addComment(postId, form) {
    if (!token) {
        alert('Vui lòng đăng nhập để bình luận!');
        return;
    }
    const comment = form.querySelector('input[name="comment"]').value;
    try {
        const response = await fetch(`${API_URL}/comments/${postId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ comment })
        });
        if (response.ok) {
            form.reset();
            loadComments(postId, form.closest('.card-body').querySelector('.comments'));
        } else {
            alert('Lỗi khi thêm bình luận');
        }
    } catch (error) {
        console.error('Lỗi thêm bình luận:', error);
    }
}

async function deletePost(postId) {
    if (!confirm('Bạn có chắc muốn xóa bài viết này?')) return;
    try {
        const response = await fetch(`${API_URL}/posts/${postId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            loadPosts();
        } else {
            alert('Lỗi khi xóa bài viết');
        }
    } catch (error) {
        console.error('Lỗi xóa bài viết:', error);
    }
}

document.getElementById('new-post-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!token) {
        alert('Vui lòng đăng nhập để đăng bài!');
        return;
    }
    const formData = new FormData(e.target);
    try {
        const response = await fetch(`${API_URL}/posts`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        if (response.ok) {
            e.target.reset();
            loadPosts();
        } else {
            alert('Lỗi khi đăng bài');
        }
    } catch (error) {
        console.error('Lỗi đăng bài:', error);
    }
});

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}