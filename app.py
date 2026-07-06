import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, g

app = Flask(__name__)
DATABASE = 'arrab.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Enable Foreign Keys
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Create Tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT CHECK(user_type IN ('student', 'admin', 'teacher')) DEFAULT 'student',
            governorate TEXT NOT NULL,
            avatar_url TEXT,
            points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_name TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS main_tabs (
            tab_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_name TEXT NOT NULL UNIQUE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT NOT NULL UNIQUE,
            color_code TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade_id INTEGER NOT NULL,
            tab_id INTEGER NOT NULL,
            branch_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_text TEXT,
            video_url TEXT,
            order_index INTEGER NOT NULL,
            is_offline_available BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grade_id) REFERENCES grades(grade_id) ON DELETE CASCADE,
            FOREIGN KEY (tab_id) REFERENCES main_tabs(tab_id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT CHECK(question_type IN ('mcq', 'true_false')) DEFAULT 'mcq',
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT,
            option_d TEXT,
            correct_option CHAR(1) NOT NULL,
            explanation TEXT,
            points_reward INTEGER DEFAULT 10,
            FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_progress (
            progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            status TEXT CHECK(status IN ('not_started', 'in_progress', 'completed')) DEFAULT 'not_started',
            completion_percentage REAL DEFAULT 0.0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE,
            UNIQUE(user_id, lesson_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS flashcards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            front_content TEXT NOT NULL,
            back_content TEXT NOT NULL,
            color_tag TEXT,
            FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS flashcard_favorites (
            favorite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (card_id) REFERENCES flashcards(card_id) ON DELETE CASCADE,
            UNIQUE(user_id, card_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS glossary (
            word_id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE,
            meaning TEXT NOT NULL,
            synonyms TEXT,
            antonyms TEXT,
            context_sentence TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_vocabulary (
            user_vocab_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (word_id) REFERENCES glossary(word_id) ON DELETE CASCADE,
            UNIQUE(user_id, word_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS duels (
            duel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER NOT NULL,
            opponent_id INTEGER NOT NULL,
            status TEXT CHECK(status IN ('pending', 'active', 'completed', 'declined')) DEFAULT 'pending',
            winner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (challenger_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (opponent_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (winner_id) REFERENCES users(user_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_posters (
            poster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            poster_image_url TEXT NOT NULL,
            approved_by_admin INTEGER,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (approved_by_admin) REFERENCES users(user_id)
        );
        """)

        # Insert Lookup Seeds
        cursor.execute("INSERT OR IGNORE INTO grades (grade_name) VALUES ('الصف الأول الثانوي'), ('الصف الثاني الثانوي'), ('الصف الثالث الثانوي');")
        cursor.execute("INSERT OR IGNORE INTO main_tabs (tab_name) VALUES ('شرح'), ('مراجعة'), ('اختبر نفسك');")
        
        branches_data = [
            ('نحو', '#10B981'),      # Emerald Green for Grammar
            ('بلاغة', '#3B82F6'),     # Blue
            ('أدب', '#8B5CF6'),       # Purple
            ('قراءة', '#F59E0B'),     # Amber
            ('نصوص', '#EC4899'),      # Pink
            ('قصة', '#6B7280')        # Slate
        ]
        for name, color in branches_data:
            cursor.execute("INSERT OR IGNORE INTO branches (branch_name, color_code) VALUES (?, ?);", (name, color))

        # Insert Sample Users
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, full_name, email, password_hash, user_type, governorate, avatar_url, points) VALUES 
        (1, 'أحمد محمود البدري', 'ahmed@arrab.com', 'scrypt:32768:8:1$hash', 'student', 'القاهرة', 'https://api.dicebear.com/7.x/bottts/svg?seed=ahmed', 1450),
        (2, 'فاطمة عمر الشريف', 'fatma@arrab.com', 'scrypt:32768:8:1$hash', 'student', 'الإسكندرية', 'https://api.dicebear.com/7.x/bottts/svg?seed=fatma', 1820),
        (3, 'الأستاذ عرّاب المصري', 'admin@arrab.com', 'scrypt:32768:8:1$hash', 'admin', 'الجيزة', 'https://api.dicebear.com/7.x/bottts/svg?seed=admin', 0);
        """)

        # Insert Sample Glossary Words
        cursor.execute("""
        INSERT OR IGNORE INTO glossary (word_id, word, meaning, synonyms, antonyms, context_sentence) VALUES 
        (1, 'العنان', 'السماء أو الأفق المرتفع', 'الأفق، السحاب', 'الثرى، الأرض', 'حلقت طموحات الشاعر في العنان لتعانق آمال جيل الشباب.'),
        (2, 'الوهن', 'الضعف والفتور في القوة والبدن', 'الخور، الارتخاء', 'القوة، الجسارة', 'ما أصاب الأمة من وهن زال بتماسك قادتها المخلصين.');
        """)

        # Insert Sample Flashcards ( الامتحان تريكات)
        cursor.execute("""
        INSERT OR IGNORE INTO flashcards (card_id, branch_id, title, front_content, back_content, color_tag) VALUES 
        (1, 1, 'الفرق بين واو المعية وواو الحال', 'كيف نفرق بين واو المعية وواو الحال في الجملة بسهولة؟', 'واو الحال يأتي بعدها جملة اسمية كاملة في محل نصب حال (مثال: ذهبت والليلُ مظلمٌ). أما واو المعية فيأتي بعدها اسم منصوب مفعول معه ولا يصح مشاركته للفعل (مثال: سرتُ والنيلَ).', 'المرفوعات والمنصوبات'),
        (2, 2, 'سر جمال التشبيه البليغ', 'كيف نحدد سر جمال التشبيه في الامتحان (تشخيص، تجسيم، توضيح)؟', '1. تشخيص: عند تشبيه غير عاقل بعاقل (الكتاب صديق).
2. تجسيم: تشبيه معنوي بمادي (العلم مفتاح).
3. توضيح: تشبيه مادي بمادي أو معنوي بمعنوي (الأسد كالرجل القوي).', 'البلاغة الموجزة');
        """)

        # Insert Sample Lessons
        cursor.execute("""
        INSERT OR IGNORE INTO lessons (lesson_id, grade_id, tab_id, branch_id, title, content_text, video_url, order_index, is_offline_available) VALUES 
        (1, 3, 1, 1, 'كان وأخواتها التامة والناقصة', 'كان الناقصة هي التي لا تكتفي بمركوعها وتحتاج لخبر ليتمم المعنى، أما التامة فهي تكتفي بفاعلها وتدل على حدث وزمن.', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 1, 1),
        (2, 3, 1, 1, 'أفعال المقاربة والرجاء والشروع', 'أفعال تعمل عمل كان بشرط أن يكون خبرها جملة فعلية فعلها مضارع.', 'https://www.youtube.com/embed/dQw4w9WgXcQ', 2, 1);
        """)

        # Insert Sample Questions
        cursor.execute("""
        INSERT OR IGNORE INTO questions (question_id, lesson_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation) VALUES 
        (1, 1, 'حدد نوع كان في الآية الكريمة: "وإن كان ذو عسرة فنظرة إلى ميسرة"', 'ناقصة والفاعل ضمير مستتر', 'تامة و "ذو" فاعل مرفوع بالواو', 'ناقصة و "ذو" اسمها مرفوع بالواو', 'زائدة لا عمل لها', 'B', 'كان هنا بمعنى وُجد أو حدث، فهي تامة تكتفي بفاعلها "ذو" وهو مرفوع بالواو لأنه من الأسماء الخمسة.'),
        (2, 2, 'ما حكم اقتران خبر "عسى" بأن المصدرية؟', 'يمتنع', 'يقل', 'يجب', 'يكثر', 'D', 'يكثر اقتران خبر عسى وأوشك بأن المصدرية، بينما يجب مع حرى واخلولق، ويمتنع مع أفعال الشروع.');
        """)

        db.commit()

init_db()

@app.route('/')
def index():
    db = get_db()
    
    # Simple Dashboard calculations
    # Count of completed lessons for student 1
    total_lessons = db.execute("SELECT COUNT(*) as cnt FROM lessons").fetchone()['cnt'] or 1
    completed_lessons = db.execute("SELECT COUNT(*) as cnt FROM student_progress WHERE user_id = 1 AND status = 'completed'").fetchone()['cnt']
    progress_percentage = int((completed_lessons / total_lessons) * 100)
    
    # Leaderboard entries
    leaderboard = db.execute("SELECT full_name, governorate, points FROM users WHERE user_type = 'student' ORDER BY points DESC LIMIT 10").fetchall()
    
    # Community poster of the week
    poster = db.execute("""
        SELECT cp.*, u.full_name 
        FROM community_posters cp 
        JOIN users u ON cp.student_id = u.user_id 
        ORDER BY cp.published_at DESC LIMIT 1
    """).fetchone()
    
    # Flashcard count
    flashcards_cnt = db.execute("SELECT COUNT(*) as cnt FROM flashcards").fetchone()['cnt']
    
    return render_template('dashboard.html', 
                           progress=progress_percentage, 
                           leaderboard=leaderboard, 
                           poster=poster, 
                           flashcards_cnt=flashcards_cnt)

@app.route('/grades')
def list_grades():
    db = get_db()
    grades = db.execute("SELECT * FROM grades").fetchall()
    return render_template('grades.html', grades=grades)

@app.route('/grade/<int:grade_id>')
def grade_tabs(grade_id):
    db = get_db()
    grade = db.execute("SELECT * FROM grades WHERE grade_id = ?", (grade_id,)).fetchone()
    tabs = db.execute("SELECT * FROM main_tabs").fetchall()
    return render_template('grade_tabs.html', grade=grade, tabs=tabs)

@app.route('/grade/<int:grade_id>/tab/<int:tab_id>')
def tab_branches(grade_id, tab_id):
    db = get_db()
    grade = db.execute("SELECT * FROM grades WHERE grade_id = ?", (grade_id,)).fetchone()
    tab = db.execute("SELECT * FROM main_tabs WHERE tab_id = ?", (tab_id,)).fetchone()
    branches = db.execute("SELECT * FROM branches").fetchall()
    return render_template('tab_branches.html', grade=grade, tab=tab, branches=branches)

@app.route('/grade/<int:grade_id>/tab/<int:tab_id>/branch/<int:branch_id>')
def branch_lessons(grade_id, tab_id, branch_id):
    db = get_db()
    grade = db.execute("SELECT * FROM grades WHERE grade_id = ?", (grade_id,)).fetchone()
    tab = db.execute("SELECT * FROM main_tabs WHERE tab_id = ?", (tab_id,)).fetchone()
    branch = db.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
    lessons = db.execute("""
        SELECT l.*, 
        (SELECT status FROM student_progress WHERE user_id = 1 AND lesson_id = l.lesson_id) as progress_status
        FROM lessons l 
        WHERE l.grade_id = ? AND l.tab_id = ? AND l.branch_id = ?
        ORDER BY l.order_index ASC
    """, (grade_id, tab_id, branch_id)).fetchall()
    return render_template('lessons.html', grade=grade, tab=tab, branch=branch, lessons=lessons)

@app.route('/lesson/<int:lesson_id>')
def view_lesson(lesson_id):
    db = get_db()
    lesson = db.execute("""
        SELECT l.*, g.grade_name, t.tab_name, b.branch_name 
        FROM lessons l
        JOIN grades g ON l.grade_id = g.grade_id
        JOIN main_tabs t ON l.tab_id = t.tab_id
        JOIN branches b ON l.branch_id = b.branch_id
        WHERE l.lesson_id = ?
    """, (lesson_id,)).fetchone()
    
    questions = db.execute("SELECT * FROM questions WHERE lesson_id = ?", (lesson_id,)).fetchall()
    return render_template('lesson_view.html', lesson=lesson, questions=questions)

@app.route('/complete-lesson/<int:lesson_id>', methods=['POST'])
def complete_lesson(lesson_id):
    db = get_db()
    db.execute("""
        INSERT INTO student_progress (user_id, lesson_id, status, completion_percentage)
        VALUES (1, ?, 'completed', 100.0)
        ON CONFLICT(user_id, lesson_id) DO UPDATE SET status='completed', completion_percentage=100.0
    """, (lesson_id,))
    # Reward points
    db.execute("UPDATE users SET points = points + 50 WHERE user_id = 1")
    db.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/flashcards')
def flashcards():
    db = get_db()
    cards = db.execute("""
        SELECT f.*, b.branch_name, 
        (SELECT COUNT(*) FROM flashcard_favorites WHERE user_id = 1 AND card_id = f.card_id) as is_fav
        FROM flashcards f
        JOIN branches b ON f.branch_id = b.branch_id
    """).fetchall()
    return render_template('flashcards.html', cards=cards)

@app.route('/flashcard/toggle-fav/<int:card_id>', methods=['POST'])
def toggle_flashcard_fav(card_id):
    db = get_db()
    existing = db.execute("SELECT 1 FROM flashcard_favorites WHERE user_id = 1 AND card_id = ?", (card_id,)).fetchone()
    if existing:
        db.execute("DELETE FROM flashcard_favorites WHERE user_id = 1 AND card_id = ?", (card_id,))
    else:
        db.execute("INSERT INTO flashcard_favorites (user_id, card_id) VALUES (1, ?)", (card_id,))
    db.commit()
    return jsonify(success=True)

@app.route('/glossary', methods=['GET', 'POST'])
def glossary():
    db = get_db()
    search_query = request.form.get('query', '') if request.method == 'POST' else request.args.get('query', '')
    if search_query:
        words = db.execute("""
            SELECT g.*, (SELECT COUNT(*) FROM user_vocabulary WHERE user_id = 1 AND word_id = g.word_id) as is_saved
            FROM glossary g 
            WHERE g.word LIKE ? OR g.meaning LIKE ?
        """, (f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        words = db.execute("""
            SELECT g.*, (SELECT COUNT(*) FROM user_vocabulary WHERE user_id = 1 AND word_id = g.word_id) as is_saved
            FROM glossary g
        """).fetchall()
    return render_template('glossary.html', words=words, query=search_query)

@app.route('/glossary/toggle-vocab/<int:word_id>', methods=['POST'])
def toggle_vocab(word_id):
    db = get_db()
    existing = db.execute("SELECT 1 FROM user_vocabulary WHERE user_id = 1 AND word_id = ?", (word_id,)).fetchone()
    if existing:
        db.execute("DELETE FROM user_vocabulary WHERE user_id = 1 AND word_id = ?", (word_id,))
    else:
        db.execute("INSERT INTO user_vocabulary (user_id, word_id) VALUES (1, ?)", (word_id,))
    db.commit()
    return jsonify(success=True)

# Admin Panel Route to dynamic additions
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    db = get_db()
    if request.method == 'POST':
        # Add new lesson
        grade_id = request.form.get('grade_id')
        tab_id = request.form.get('tab_id')
        branch_id = request.form.get('branch_id')
        title = request.form.get('title')
        content = request.form.get('content')
        video_url = request.form.get('video_url')
        order_index = request.form.get('order_index', 1)
        
        db.execute("""
            INSERT INTO lessons (grade_id, tab_id, branch_id, title, content_text, video_url, order_index, is_offline_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (grade_id, tab_id, branch_id, title, content, video_url, order_index))
        db.commit()
        return redirect(url_for('admin_panel'))
        
    grades = db.execute("SELECT * FROM grades").fetchall()
    tabs = db.execute("SELECT * FROM main_tabs").fetchall()
    branches = db.execute("SELECT * FROM branches").fetchall()
    lessons = db.execute("""
        SELECT l.*, g.grade_name, t.tab_name, b.branch_name 
        FROM lessons l
        JOIN grades g ON l.grade_id = g.grade_id
        JOIN main_tabs t ON l.tab_id = t.tab_id
        JOIN branches b ON l.branch_id = b.branch_id
    """).fetchall()
    return render_template('admin.html', grades=grades, tabs=tabs, branches=branches, lessons=lessons)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
