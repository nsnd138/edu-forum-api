from flask import Flask, request, jsonify, send_from_directory, render_template
   from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
   import sqlite3
   import os
   from datetime import datetime
   from werkzeug.security import generate_password_hash, check_password_hash
   from werkzeug.utils import secure_filename
   import uuid
   from PIL import Image
   from dotenv import load_dotenv

   load_dotenv()

   app = Flask(__name__)
   app.config['JSON_AS_ASCII'] = False
   app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'vmu-secret-key-2025')
   app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'Uploads')
   app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
   app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

   os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

   jwt = JWTManager(app)

   def get_db_connection():
       db_path = os.path.join(os.path.dirname(__file__), 'forum.db')
       conn = sqlite3.connect(db_path, check_same_thread=False)
       conn.row_factory = sqlite3.Row
       conn.execute('''CREATE TABLE IF NOT EXISTS users (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           username TEXT NOT NULL UNIQUE,
                           password TEXT NOT NULL,
                           role TEXT NOT NULL DEFAULT 'student')''')
       conn.execute('''CREATE TABLE IF NOT EXISTS posts (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           title TEXT NOT NULL,
                           content TEXT NOT NULL,
                           author_id INTEGER NOT NULL,
                           created_at TEXT NOT NULL,
                           image_url TEXT,
                           FOREIGN KEY (author_id) REFERENCES users (id))''')
       conn.execute('''CREATE TABLE IF NOT EXISTS comments (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           post_id INTEGER NOT NULL,
                           author_id INTEGER NOT NULL,
                           comment TEXT NOT NULL,
                           created_at TEXT NOT NULL,
                           FOREIGN KEY (post_id) REFERENCES posts (id),
                           FOREIGN KEY (author_id) REFERENCES users (id))''')
       return conn

   def allowed_file(filename):
       return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

   @app.route('/register', methods=['GET', 'POST'])
   def register():
       if request.method == 'GET':
           return render_template('register.html')
       data = request.json
       if not data or 'username' not in data or 'password' not in data or 'role' not in data:
           return jsonify({"error": "Thiếu thông tin"}), 400
       username = data['username']
       password = generate_password_hash(data['password'])
       role = data.get('role', 'student')
       if role not in ['student', 'teacher', 'admin']:
           return jsonify({"error": "Vai trò không hợp lệ"}), 400

       conn = get_db_connection()
       try:
           conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                        (username, password, role))
           conn.commit()
           return jsonify({"message": "Đăng ký thành công"}), 201
       except sqlite3.IntegrityError:
           return jsonify({"error": "Tên người dùng đã tồn tại"}), 400
       finally:
           conn.close()

   @app.route('/login', methods=['GET', 'POST'])
   def login():
       if request.method == 'GET':
           return render_template('login.html')
       data = request.json
       if not data or 'username' not in data or 'password' not in data:
           return jsonify({"error": "Thiếu thông tin"}), 400
       username = data['username']
       password = data['password']

       conn = get_db_connection()
       user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
       conn.close()

       if user and check_password_hash(user['password'], password):
           access_token = create_access_token(identity={'username': username, 'role': user['role']})
           return jsonify({"access_token": access_token, "role": user['role']}), 200
       return jsonify({"error": "Tên người dùng hoặc mật khẩu sai"}), 401

   @app.route('/posts', methods=['GET', 'POST'])
   @jwt_required()
   def handle_posts():
       identity = get_jwt_identity()
       conn = get_db_connection()

       if request.method == 'GET':
           page = request.args.get('page', 1, type=int)
           per_page = 10
           offset = (page - 1) * per_page
           cursor = conn.execute(
               "SELECT p.id, p.title, p.content, u.username AS author, p.created_at, p.image_url "
               "FROM posts p JOIN users u ON p.author_id = u.id "
               "ORDER BY p.created_at DESC LIMIT ? OFFSET ?",
               (per_page, offset)
           )
           posts = [dict(row) for row in cursor.fetchall()]
           conn.close()
           return jsonify(posts)

       elif request.method == 'POST':
           user = conn.execute("SELECT id FROM users WHERE username = ?", (identity['username'],)).fetchone()
           if not user:
               conn.close()
               return jsonify({"error": "Người dùng không tồn tại"}), 400

           if 'multipart/form-data' in (request.content_type or ''):
               title = request.form.get('title')
               content = request.form.get('content')
               image = request.files.get('image')
               image_url = None

               if not title or not content:
                   conn.close()
                   return jsonify({"error": "Thiếu tiêu đề hoặc nội dung"}), 400

               if image and allowed_file(image.filename):
                   filename = secure_filename(f"{uuid.uuid4()}.{image.filename.rsplit('.', 1)[1].lower()}")
                   image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                   image.save(image_path)
                   with Image.open(image_path) as img:
                       img.thumbnail((800, 800))
                       img.save(image_path, quality=85)
                   image_url = f"/uploads/{filename}"

               conn.execute(
                   "INSERT INTO posts (title, content, author_id, created_at, image_url) "
                   "VALUES (?, ?, ?, datetime('now'), ?)",
                   (title, content, user['id'], image_url)
               )
               conn.commit()
               conn.close()
               return jsonify({"message": "Bài viết đã tạo"}), 201

           return jsonify({"error": "Yêu cầu không hợp lệ"}), 400

   @app.route('/posts/<int:id>', methods=['DELETE'])
   @jwt_required()
   def delete_post(id):
       identity = get_jwt_identity()
       if identity['role'] != 'admin':
           return jsonify({"error": "Yêu cầu quyền admin"}), 403

       conn = get_db_connection()
       post = conn.execute("SELECT * FROM posts WHERE id = ?", (id,)).fetchone()
       if not post:
           conn.close()
           return jsonify({"error": "Bài viết không tồn tại"}), 404

       conn.execute("DELETE FROM comments WHERE post_id = ?", (id,))
       conn.execute("DELETE FROM posts WHERE id = ?", (id,))
       if post['image_url']:
           image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(post['image_url']))
           if os.path.exists(image_path):
               os.remove(image_path)
       conn.commit()
       conn.close()
       return jsonify({"message": "Bài viết đã xóa"}), 200

   @app.route('/posts/search', methods=['GET'])
   def search_posts():
       query = request.args.get('q', '')
       if not query:
           return jsonify({"error": "Thiếu từ khóa tìm kiếm"}), 400

       conn = get_db_connection()
       cursor = conn.execute(
           "SELECT p.id, p.title, p.content, u.username AS author, p.created_at, p.image_url "
           "FROM posts p JOIN users u ON p.author_id = u.id "
           "WHERE p.title LIKE ? OR p.content LIKE ?",
           (f'%{query}%', f'%{query}%')
       )
       posts = [dict(row) for row in cursor.fetchall()]
       conn.close()
       return jsonify(posts)

   @app.route('/comments/<int:post_id>', methods=['GET', 'POST'])
   @jwt_required()
   def handle_comments(post_id):
       identity = get_jwt_identity()
       conn = get_db_connection()

       if request.method == 'GET':
           cursor = conn.execute(
               "SELECT c.id, c.post_id, u.username AS author, c.comment, c.created_at "
               "FROM comments c JOIN users u ON c.author_id = u.id "
               "WHERE c.post_id = ?",
               (post_id,)
           )
           comments = [dict(row) for row in cursor.fetchall()]
           conn.close()
           return jsonify(comments)

       elif request.method == 'POST':
           data = request.json
           if not data or 'comment' not in data:
               conn.close()
               return jsonify({"error": "Thiếu nội dung bình luận"}), 400

           user = conn.execute("SELECT id FROM users WHERE username = ?", (identity['username'],)).fetchone()
           if not user:
               conn.close()
               return jsonify({"error": "Người dùng không tồn tại"}), 400

           conn.execute(
               "INSERT INTO comments (post_id, author_id, comment, created_at) "
               "VALUES (?, ?, ?, datetime('now'))",
               (post_id, user['id'], data['comment'])
           )
           conn.commit()
           conn.close()
           return jsonify({"message": "Bình luận đã được thêm!"}), 201

   @app.route('/uploads/<filename>')
   def uploaded_file(filename):
       return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

   @app.route('/')
   def home():
       return render_template('index.html')

   if __name__ == '__main__':
       port = int(os.environ.get('PORT', 5000))
       app.run(host='0.0.0.0', port=port, debug=True)