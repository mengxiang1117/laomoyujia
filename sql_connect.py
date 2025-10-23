import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

print("Config:", USER, PASSWORD, HOST, PORT, DBNAME)

try:
    connection = psycopg2.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        dbname=DBNAME
    )
    print("✅ Connection successful!")
    
    cursor = connection.cursor()

    # 🔧 创建 users 表（如果不存在）
    create_users_table_query = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        gender VARCHAR(10),
        age INTEGER,
        job VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_users_table_query)
    connection.commit()
    print("✅ Table 'users' created or already exists.")

    # 🔧 创建 user_work_info 表（如果不存在）
    create_user_work_info_table_query = """
    CREATE TABLE IF NOT EXISTS user_work_info (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        work_start_time TIME,
        work_end_time TIME,
        break_start_time TIME,
        break_end_time TIME,
        daily_salary DECIMAL(10,2),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_user_work_info_table_query)
    connection.commit()
    print("✅ Table 'user_work_info' created or already exists.")

    # 🔧 创建 slacking_records 表（如果不存在）
    create_slacking_records_table_query = """
    CREATE TABLE IF NOT EXISTS slacking_records (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        duration INTEGER,
        project VARCHAR(255),
        earnings DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_slacking_records_table_query)
    connection.commit()
    print("✅ Table 'slacking_records' created or already exists.")

    # 🔧 创建 overtime_records 表（如果不存在）
    create_overtime_records_table_query = """
    CREATE TABLE IF NOT EXISTS overtime_records (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        duration INTEGER,
        project VARCHAR(255),
        earnings DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_overtime_records_table_query)
    connection.commit()
    print("✅ Table 'overtime_records' created or already exists.")

    # 🔧 创建 slacking_tips 表（如果不存在）
    create_slacking_tips_table_query = """
    CREATE TABLE IF NOT EXISTS slacking_tips (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        title VARCHAR(100),
        steps TEXT,
        notice TEXT,
        experience TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_slacking_tips_table_query)
    connection.commit()
    print("✅ Table 'slacking_tips' created or already exists.")

    # 🔧 创建 tip_likes 表（如果不存在）
    create_tip_likes_table_query = """
    CREATE TABLE IF NOT EXISTS tip_likes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        tip_id INTEGER REFERENCES slacking_tips(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_tip_likes_table_query)
    connection.commit()
    print("✅ Table 'tip_likes' created or already exists.")

    # 🔧 创建 tip_comments 表（如果不存在）
    create_tip_comments_table_query = """
    CREATE TABLE IF NOT EXISTS tip_comments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        tip_id INTEGER REFERENCES slacking_tips(id),
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_tip_comments_table_query)
    connection.commit()
    print("✅ Table 'tip_comments' created or already exists.")

    # 🔧 创建 feedback 表（如果不存在）
    create_feedback_table_query = """
    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reply TEXT,
        reply_at TIMESTAMP
    );
    """
    cursor.execute(create_feedback_table_query)
    connection.commit()
    print("✅ Table 'feedback' created or already exists.")

    # 🧪 可选：插入一条测试数据
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING;",
        ("testuser", "testpassword")
    )
    connection.commit()
    print("✅ Test user inserted (if not exists).")

    # 🔍 查询数据验证
    cursor.execute("SELECT * FROM users;")
    rows = cursor.fetchall()
    print("📋 Current users in table:")
    for row in rows:
        print(row)

except Exception as e:
    print(f"❌ Failed to connect or execute: {e}")

finally:
    # 确保关闭连接
    if 'cursor' in locals():
        cursor.close()
    if 'connection' in locals():
        connection.close()
    print("🔌 Connection closed.")