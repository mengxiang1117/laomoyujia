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

    # 为常用查询字段添加索引
    print("🔧 Creating indexes for better performance...")
    
    # 为 users 表的 username 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);")
    print("✅ Index on users.username created")
    
    # 为 user_work_info 表的 user_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_work_info_user_id ON user_work_info (user_id);")
    print("✅ Index on user_work_info.user_id created")
    
    # 为 slacking_records 表的 user_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slacking_records_user_id ON slacking_records (user_id);")
    print("✅ Index on slacking_records.user_id created")
    
    # 为 overtime_records 表的 user_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_overtime_records_user_id ON overtime_records (user_id);")
    print("✅ Index on overtime_records.user_id created")
    
    # 为 slacking_tips 表的 user_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slacking_tips_user_id ON slacking_tips (user_id);")
    print("✅ Index on slacking_tips.user_id created")
    
    # 为 slacking_tips 表的 created_at 字段添加索引（用于排序）
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slacking_tips_created_at ON slacking_tips (created_at DESC);")
    print("✅ Index on slacking_tips.created_at created")
    
    # 为 tip_likes 表的 user_id 和 tip_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tip_likes_user_id ON tip_likes (user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tip_likes_tip_id ON tip_likes (tip_id);")
    print("✅ Indexes on tip_likes.user_id and tip_likes.tip_id created")
    
    # 为 tip_comments 表的 tip_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tip_comments_tip_id ON tip_comments (tip_id);")
    print("✅ Index on tip_comments.tip_id created")
    
    # 为 feedback 表的 user_id 字段添加索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback (user_id);")
    print("✅ Index on feedback.user_id created")
    
    connection.commit()
    print("✅ All indexes created successfully!")

    # 分析表以更新统计信息
    print("📊 Analyzing tables...")
    cursor.execute("ANALYZE users;")
    cursor.execute("ANALYZE user_work_info;")
    cursor.execute("ANALYZE slacking_records;")
    cursor.execute("ANALYZE overtime_records;")
    cursor.execute("ANALYZE slacking_tips;")
    cursor.execute("ANALYZE tip_likes;")
    cursor.execute("ANALYZE tip_comments;")
    cursor.execute("ANALYZE feedback;")
    connection.commit()
    print("✅ Table analysis completed!")

    cursor.close()
    connection.close()
    print("🔌 Connection closed.")

except Exception as e:
    print(f"❌ Failed to connect or execute: {e}")