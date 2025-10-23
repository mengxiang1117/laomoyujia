from flask import Flask
from config import Config
import psycopg2
from psycopg2 import pool
import atexit
import redis

# 创建数据库连接池
db_pool = None
# 创建Redis连接
redis_client = None

def create_app():
    global db_pool, redis_client
    
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = 'your-secret-key-here'  # 用于session加密
    
    # 初始化Redis连接
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        # 测试Redis连接
        redis_client.ping()
        print("✅ Redis connection established successfully")
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        redis_client = None
    
    # 初始化数据库连接池 - 减少最大连接数以避免达到服务器限制
    if db_pool is None:
        try:
            db_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,  # 最小1个连接，最大10个连接（降低以避免连接数限制）
                host=app.config['DB_HOST'],
                port=app.config['DB_PORT'],
                dbname=app.config['DB_NAME'],
                user=app.config['DB_USER'],
                password=app.config['DB_PASSWORD'],
                # 设置连接超时等参数
                connect_timeout=10,
                # 设置时区为UTC+8
                options='-c timezone=Asia/Shanghai'
            )
            print("✅ Database connection pool created successfully")
        except Exception as e:
            print(f"❌ Error creating database connection pool: {e}")
            db_pool = None
    
    # 获取数据库连接的函数
    def get_db_connection():
        global db_pool
        if db_pool:
            try:
                conn = db_pool.getconn()
                # 测试连接是否有效
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                # 设置会话时区为UTC+8
                cursor.execute("SET timezone TO 'Asia/Shanghai'")
                cursor.close()
                return conn
            except Exception as e:
                print(f"Error getting connection from pool: {e}")
                # 如果连接无效，尝试重建连接池
                try:
                    db_pool.putconn(conn)
                except:
                    pass
                return None
        return None
    
    # 归还数据库连接的函数
    def put_db_connection(conn):
        global db_pool
        if db_pool and conn:
            try:
                # 在归还连接前检查连接状态
                if not conn.closed:
                    db_pool.putconn(conn)
            except Exception as e:
                print(f"Error putting connection back to pool: {e}")
                try:
                    conn.close()
                except:
                    pass
    
    # 获取Redis客户端的函数
    def get_redis_client():
        global redis_client
        return redis_client
    
    # 将函数添加到应用上下文中
    app.get_db_connection = get_db_connection
    app.put_db_connection = put_db_connection
    app.get_redis_client = get_redis_client
    
    # 应用关闭时关闭连接池
    @app.teardown_appcontext
    def close_db(error):
        pass  # 我们使用自定义函数管理连接
    
    # 注册蓝图
    from app.views import main
    from app.controllers.api import api
    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix='/api')
    
    return app

# 应用关闭时关闭连接池
def close_db_pool():
    global db_pool
    if db_pool:
        try:
            db_pool.closeall()
            print("🔌 Database connection pool closed")
        except Exception as e:
            print(f"Error closing connection pool: {e}")

# 确保应用退出时关闭连接池
atexit.register(close_db_pool)