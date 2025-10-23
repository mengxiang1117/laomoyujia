from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app

import psycopg2

from app.utils import utc_to_utc8



main = Blueprint('main', __name__)

@main.route('/')

def index():

    # 检查用户是否已登录

    if 'user_id' not in session:

        return redirect(url_for('main.login'))

    return render_template('index.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = current_app.get_db_connection()
        if not conn:
            return render_template('login.html', error='数据库连接失败')
        
        cur = conn.cursor()
        
        # 验证用户凭据
        cur.execute('SELECT id, username FROM users WHERE username = %s AND password = %s', 
                   (username, password))
        user = cur.fetchone()
        
        cur.close()
        current_app.put_db_connection(conn)
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    # GET请求时，如果用户已登录则重定向到首页
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 用户名验证：必须是数字和字母的组合，且不能包含admin/Admin等大小写混合
        if 'admin' in username.lower():
            return render_template('register.html', error='用户名不能包含admin')
        
        # 检查用户名是否为数字和字母的组合
        if not username.isalnum() or username.isdigit() or username.isalpha():
            return render_template('register.html', error='用户名必须是数字和字母的组合')
        
        # 检查密码是否为数字和字母的组合
        if not password.isalnum() or password.isdigit() or password.isalpha():
            return render_template('register.html', error='密码必须是数字和字母的组合')
        
        # 检查密码和确认密码是否一致
        if password != confirm_password:
            return render_template('register.html', error='密码和确认密码不一致')
        
        conn = current_app.get_db_connection()
        if not conn:
            return render_template('register.html', error='数据库连接失败')
        
        cur = conn.cursor()
        
        try:
            # 检查用户名是否已存在
            cur.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                cur.close()
                current_app.put_db_connection(conn)
                return render_template('register.html', error='用户名已存在')
            
            # 插入新用户
            cur.execute('INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id',
                       (username, password))
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # 初始化用户工作信息
            cur.execute('''INSERT INTO user_work_info (user_id, daily_salary) 
                          VALUES (%s, %s)''', (user_id, 0.00))
            conn.commit()
            
            cur.close()
            current_app.put_db_connection(conn)
            
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('main.index'))
        except Exception as e:
            cur.close()
            current_app.put_db_connection(conn)
            return render_template('register.html', error='注册失败，请重试')
    
    return render_template('register.html')

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@main.route('/tips')
def tips():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # 获取排序参数
    sort_by = request.args.get('sort', 'time')  # 默认按时间排序
    
    # 构建排序SQL
    if sort_by == 'likes':
        order_clause = 'like_count DESC'
    elif sort_by == 'comments':
        order_clause = 'comment_count DESC'
    else:  # time
        order_clause = 'st.created_at DESC'
    
    # 尝试从Redis缓存获取数据
    redis_client = current_app.get_redis_client()
    cache_key = f"all_tips_{sort_by}"
    
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                import json
                tips = json.loads(cached_data)
                return render_template('tips.html', tips=tips, sort_by=sort_by)
        except Exception as e:
            print(f"Error reading from Redis: {e}")
    
    # 获取所有摸鱼技巧
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    try:
        cur.execute(f'''SELECT st.id, st.title, st.steps, st.notice, st.experience, st.created_at, 
                      u.username, 
                      (SELECT COUNT(*) FROM tip_likes WHERE tip_id = st.id) as like_count,
                      (SELECT COUNT(*) FROM tip_comments WHERE tip_id = st.id) as comment_count
                      FROM slacking_tips st 
                      JOIN users u ON st.user_id = u.id 
                      ORDER BY {order_clause}''')
        tips = cur.fetchall()
        
        # 缓存结果1分钟
        if redis_client:
            try:
                import json
                # 将datetime对象转换为字符串以便JSON序列化
                tips_serializable = []
                for tip in tips:
                    tip_list = list(tip)
                    if tip_list[5]:  # created_at字段
                        #utc8_time = utc_to_utc8(tip_list[5])
                        tip_list[5] = tip_list[5].strftime('%Y-%m-%d %H:%M:%S')
                    tips_serializable.append(tip_list)
                
                redis_client.setex(cache_key, 60, json.dumps(tips_serializable))
            except Exception as e:
                print(f"Error writing to Redis: {e}")
        
        return render_template('tips.html', tips=tips, sort_by=sort_by)
    except Exception as e:
        print(f"查询技巧列表失败: {e}")
        return "数据查询失败", 500
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@main.route('/tips/new', methods=['GET', 'POST'])
def new_tip():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        title = request.form['title']
        steps = request.form['steps']
        notice = request.form['notice']
        experience = request.form['experience']
        user_id = session['user_id']
        
        conn = current_app.get_db_connection()
        if not conn:
            return render_template('new_tip.html', error='数据库连接失败')
        
        cur = conn.cursor()
        
        try:
            cur.execute('''INSERT INTO slacking_tips (user_id, title, steps, notice, experience) 
                          VALUES (%s, %s, %s, %s, %s)''',
                       (user_id, title, steps, notice, experience))
            conn.commit()
            
            # 清除相关缓存
            redis_client = current_app.get_redis_client()
            if redis_client:
                try:
                    # 清除技巧列表缓存
                    redis_client.delete("all_tips")
                    # 清除用户个人资料缓存
                    redis_client.delete(f"user_profile:{user_id}")
                except Exception as e:
                    print(f"Error clearing Redis cache: {e}")
            
            cur.close()
            current_app.put_db_connection(conn)
            return redirect(url_for('main.tips'))
        except Exception as e:
            cur.close()
            current_app.put_db_connection(conn)
            return render_template('new_tip.html', error='发布失败，请重试')
    
    return render_template('new_tip.html')

@main.route('/tips/<int:tip_id>')
def tip_detail(tip_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # 尝试从Redis缓存获取数据
    redis_client = current_app.get_redis_client()
    cache_key = f"tip_detail:{tip_id}"
    
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                import json
                data = json.loads(cached_data)
                # 将字符串转换回datetime对象
                tip = data['tip']
                comments = data['comments']
                return render_template('tip_detail.html', tip=tip, comments=comments)
        except Exception as e:
            print(f"Error reading from Redis: {e}")
    
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    try:
        # 获取技巧详情
        cur.execute('''SELECT st.id, st.title, st.steps, st.notice, st.experience, st.created_at, 
                      u.username,
                      (SELECT COUNT(*) FROM tip_likes WHERE tip_id = st.id) as like_count
                      FROM slacking_tips st 
                      JOIN users u ON st.user_id = u.id 
                      WHERE st.id = %s''', (tip_id,))
        tip = cur.fetchone()
        
        if not tip:
            return "技巧不存在", 404
        
        # 获取评论
        cur.execute('''SELECT tc.content, tc.created_at, u.username 
                      FROM tip_comments tc 
                      JOIN users u ON tc.user_id = u.id 
                      WHERE tc.tip_id = %s 
                      ORDER BY tc.created_at ASC''', (tip_id,))
        comments = cur.fetchall()
        
        # 缓存结果30秒
        if redis_client:
            try:
                import json
                # 准备可序列化的数据
                tip_serializable = list(tip)
                if tip_serializable[5]:  # created_at字段
                    #tip_serializable[5] = utc_to_utc8(tip_serializable[5])
                    tip_serializable[5] = tip_serializable[5].strftime('%Y-%m-%d %H:%M:%S')
                
                comments_serializable = []
                for comment in comments:
                    comment_list = list(comment)
                    if comment_list[1]:  # created_at字段
                        #comment_list[1] = utc_to_utc8(comment_list[1])
                        comment_list[1] = comment_list[1].strftime('%Y-%m-%d %H:%M:%S')
                    comments_serializable.append(comment_list)
                
                data = {
                    'tip': tip_serializable,
                    'comments': comments_serializable
                }
                
                redis_client.setex(cache_key, 30, json.dumps(data))
            except Exception as e:
                print(f"Error writing to Redis: {e}")
        
        return render_template('tip_detail.html', tip=tip, comments=comments)
    except Exception as e:
        print(f"查询技巧详情失败: {e}")
        return "数据查询失败", 500
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@main.route('/tips/<int:tip_id>/like', methods=['POST'])
def like_tip(tip_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '请先登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        # 检查是否已经点赞
        cur.execute('SELECT id FROM tip_likes WHERE user_id = %s AND tip_id = %s',
                   (user_id, tip_id))
        existing_like = cur.fetchone()
        
        if existing_like:
            # 取消点赞
            cur.execute('DELETE FROM tip_likes WHERE user_id = %s AND tip_id = %s',
                       (user_id, tip_id))
        else:
            # 添加点赞
            cur.execute('INSERT INTO tip_likes (user_id, tip_id) VALUES (%s, %s)',
                       (user_id, tip_id))
        
        conn.commit()
        
        # 获取新的点赞数
        cur.execute('SELECT COUNT(*) FROM tip_likes WHERE tip_id = %s', (tip_id,))
        like_count = cur.fetchone()[0]
        
        # 清除相关缓存
        redis_client = current_app.get_redis_client()
        if redis_client:
            try:
                # 清除技巧详情缓存
                redis_client.delete(f"tip_detail:{tip_id}")
                # 清除技巧列表缓存
                redis_client.delete("all_tips")
                # 清除排行榜缓存
                redis_client.delete("ranking_data")
            except Exception as e:
                print(f"Error clearing Redis cache: {e}")
        
        return jsonify({'success': True, 'like_count': like_count, 
                       'liked': not existing_like if existing_like else True})
        
    except Exception as e:
        # 发生异常时回滚事务
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        # 确保游标和连接被正确关闭和归还
        if cur:
            cur.close()
        current_app.put_db_connection(conn)

@main.route('/tips/<int:tip_id>/comment', methods=['POST'])
def comment_tip(tip_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '请先登录'})
    
    content = request.form.get('content')
    user_id = session['user_id']
    
    if not content:
        return jsonify({'success': False, 'error': '评论内容不能为空'})
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('INSERT INTO tip_comments (user_id, tip_id, content) VALUES (%s, %s, %s)',
                   (user_id, tip_id, content))
        conn.commit()
        
        # 清除相关缓存
        redis_client = current_app.get_redis_client()
        if redis_client:
            try:
                # 清除技巧详情缓存
                redis_client.delete(f"tip_detail:{tip_id}")
                # 清除技巧列表缓存
                redis_client.delete("all_tips")
            except Exception as e:
                print(f"Error clearing Redis cache: {e}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        # 发生异常时回滚事务
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        # 确保游标和连接被正确关闭和归还
        if cur:
            cur.close()
        current_app.put_db_connection(conn)

@main.route('/ranking')
def ranking():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # 尝试从Redis缓存获取数据
    redis_client = current_app.get_redis_client()
    cache_key = "ranking_data"
    
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                import json
                ranking_data = json.loads(cached_data)
                return render_template('ranking.html', 
                                     red_ranking=ranking_data['red_ranking'], 
                                     black_ranking=ranking_data['black_ranking'])
        except Exception as e:
            print(f"Error reading from Redis: {e}")
    
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    try:
        # 获取摸鱼收益排行榜（红榜）
        cur.execute('''SELECT u.username, COALESCE(SUM(sr.earnings), 0) as total_earnings
                      FROM users u
                      LEFT JOIN slacking_records sr ON u.id = sr.user_id
                      GROUP BY u.id, u.username
                      ORDER BY total_earnings DESC
                      LIMIT 10''')
        red_ranking = cur.fetchall()
        
        # 获取加班负收益排行榜（黑榜）
        cur.execute('''SELECT u.username, COALESCE(SUM(or_.earnings), 0) as total_earnings
                      FROM users u
                      LEFT JOIN overtime_records or_ ON u.id = or_.user_id
                      GROUP BY u.id, u.username
                      ORDER BY total_earnings DESC
                      LIMIT 10''')
        black_ranking = cur.fetchall()
        
        # 缓存结果5分钟
        if redis_client:
            try:
                import json
                ranking_data = {
                    'red_ranking': red_ranking,
                    'black_ranking': black_ranking
                }
                redis_client.setex(cache_key, 300, json.dumps(ranking_data))
            except Exception as e:
                print(f"Error writing to Redis: {e}")
        
        return render_template('ranking.html', red_ranking=red_ranking, black_ranking=black_ranking)
        
    except Exception as e:
        # 记录错误日志
        print(f"排行榜查询错误: {e}")
        return "数据查询失败", 500
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@main.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    # 尝试从Redis缓存获取数据
    redis_client = current_app.get_redis_client()
    cache_key = f"user_profile:{user_id}"
    
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                import json
                profile_data = json.loads(cached_data)
                # 将字符串转换回datetime对象

                user_info = profile_data['user_info']

                work_info = profile_data['work_info']

                slacking_records = profile_data['slacking_records']

                overtime_records = profile_data['overtime_records']

                tips = profile_data['tips']

                

                # 处理时间字段

                if user_info[5]:

                    from datetime import datetime

                    user_info[5] = datetime.strptime(user_info[5], '%Y-%m-%d %H:%M:%S')
                
                # 从缓存中获取今日收益统计
                today_earnings = profile_data.get('today_earnings', {'slacking': 0, 'overtime': 0})
                
                return render_template('profile.html', 
                                     user_info=user_info, 
                                     work_info=work_info,
                                     slacking_records=slacking_records, 
                                     overtime_records=overtime_records,
                                     tips=tips,
                                     today_earnings=today_earnings)
        except Exception as e:
            print(f"Error reading from Redis: {e}")
    
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    try:
        # 获取用户信息
        cur.execute('''SELECT username, gender, age, job, email, created_at 
                      FROM users WHERE id = %s''', (user_id,))
        user_info = cur.fetchone()
        
        # 转换注册时间为UTC+8
        if user_info and user_info[5]:
            user_info = list(user_info)
            #user_info[5] = utc_to_utc8(user_info[5])
        
        # 获取用户工作信息
        cur.execute('''SELECT work_start_time, work_end_time, break_start_time, 
                      break_end_time, daily_salary FROM user_work_info WHERE user_id = %s''', 
                   (user_id,))
        work_info = cur.fetchone()
        
        # 获取用户摸鱼记录
        cur.execute('''SELECT project, duration, earnings, id
                      FROM slacking_records WHERE user_id = %s 
                      ORDER BY created_at DESC''', (user_id,))
        slacking_records = cur.fetchall()
        
        # 获取用户加班记录
        cur.execute('''SELECT project, duration, earnings, id
                      FROM overtime_records WHERE user_id = %s 
                      ORDER BY created_at DESC''', (user_id,))
        overtime_records = cur.fetchall()
        
        # 获取用户分享的技巧
        cur.execute('''SELECT id, user_id, title, steps, notice, experience, created_at, updated_at 
                      FROM slacking_tips WHERE user_id = %s 
                      ORDER BY created_at DESC''', (user_id,))
        tips = cur.fetchall()
        
        # 计算今日收益统计
        today_earnings = {'slacking': 0, 'overtime': 0}
        
        # 缓存结果30秒
        if redis_client:
            try:
                import json
                # 准备可序列化的数据

                user_info_serializable = list(user_info)

                if user_info_serializable[5]:  # created_at字段

                    #user_info_serializable[5] = utc_to_utc8(user_info_serializable[5])

                    user_info_serializable[5] = user_info_serializable[5].strftime('%Y-%m-%d %H:%M:%S')

                

                profile_data = {

                    'user_info': user_info_serializable,

                    'work_info': work_info,

                    'slacking_records': slacking_records,

                    'overtime_records': overtime_records,

                    'tips': tips,

                    'today_earnings': today_earnings

                }
                
                redis_client.setex(cache_key, 30, json.dumps(profile_data))
            except Exception as e:
                print(f"Error writing to Redis: {e}")
        
        return render_template('profile.html', user_info=user_info, work_info=work_info,
                              slacking_records=slacking_records, overtime_records=overtime_records,
                              tips=tips, today_earnings=today_earnings)
    except Exception as e:
        print(f"查询用户信息失败: {e}")
        return "数据查询失败", 500
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@main.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return render_template('edit_profile.html', error='数据库连接失败')
    
    cur = conn.cursor()
    
    try:
        # 获取当前用户信息
        cur.execute('''SELECT gender, age, job, email FROM users WHERE id = %s''', (user_id,))
        user_info = cur.fetchone()
        
        if request.method == 'POST':
            # 获取表单数据，如果字段为空则保持原值
            gender = request.form.get('gender') or user_info[0]
            age = request.form.get('age') or user_info[1]
            job = request.form.get('job') or user_info[2]
            email = request.form.get('email') or user_info[3]
            
            cur.execute('''UPDATE users SET gender = %s, age = %s, job = %s, email = %s 
                          WHERE id = %s''',
                       (gender, age, job, email, user_id))
            conn.commit()
            return redirect(url_for('main.profile'))
    except Exception as e:
        conn.rollback()
        return render_template('edit_profile.html', user_info=user_info, error='更新失败，请重试')
    finally:
        cur.close()
        current_app.put_db_connection(conn)
    
    return render_template('edit_profile.html', user_info=user_info)

@main.route('/tips/<int:tip_id>/edit', methods=['GET', 'POST'])
def edit_tip(tip_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    # 检查技巧是否存在且属于当前用户
    cur.execute('SELECT * FROM slacking_tips WHERE id = %s AND user_id = %s', (tip_id, user_id))
    tip = cur.fetchone()
    
    if not tip:
        cur.close()
        current_app.put_db_connection(conn)
        return "技巧不存在或无权限编辑", 404
    
    if request.method == 'POST':
        title = request.form['title']
        steps = request.form['steps']
        notice = request.form['notice']
        experience = request.form['experience']
        
        try:
            cur.execute('''UPDATE slacking_tips SET title = %s, steps = %s, notice = %s, 
                          experience = %s, updated_at = CURRENT_TIMESTAMP 
                          WHERE id = %s''',
                       (title, steps, notice, experience, tip_id))
            conn.commit()
            
            # 清除相关缓存
            redis_client = current_app.get_redis_client()
            if redis_client:
                try:
                    # 清除技巧详情缓存
                    redis_client.delete(f"tip_detail:{tip_id}")
                    # 清除技巧列表缓存
                    redis_client.delete("all_tips")
                    # 清除用户个人资料缓存
                    redis_client.delete(f"user_profile:{user_id}")
                except Exception as e:
                    print(f"Error clearing Redis cache: {e}")
            
            cur.close()
            current_app.put_db_connection(conn)
            return redirect(url_for('main.tip_detail', tip_id=tip_id))
        except Exception as e:
            cur.close()
            current_app.put_db_connection(conn)
            return render_template('edit_tip.html', tip=tip, error='更新失败，请重试')
    
    cur.close()
    current_app.put_db_connection(conn)
    
    return render_template('edit_tip.html', tip=tip)

@main.route('/tips/<int:tip_id>/delete', methods=['POST'])
def delete_tip(tip_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '请先登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        # 检查技巧是否存在且属于当前用户
        cur.execute('SELECT id FROM slacking_tips WHERE id = %s AND user_id = %s', 
                   (tip_id, user_id))
        tip = cur.fetchone()
        
        if not tip:
            cur.close()
            current_app.put_db_connection(conn)
            return jsonify({'success': False, 'error': '技巧不存在或无权限删除'})
        
        # 删除相关评论和点赞
        cur.execute('DELETE FROM tip_comments WHERE tip_id = %s', (tip_id,))
        cur.execute('DELETE FROM tip_likes WHERE tip_id = %s', (tip_id,))
        
        # 删除技巧
        cur.execute('DELETE FROM slacking_tips WHERE id = %s', (tip_id,))
        conn.commit()
        
        # 清除相关缓存
        redis_client = current_app.get_redis_client()
        if redis_client:
            try:
                # 清除技巧详情缓存
                redis_client.delete(f"tip_detail:{tip_id}")
                # 清除技巧列表缓存
                redis_client.delete("all_tips")
                # 清除用户个人资料缓存
                redis_client.delete(f"user_profile:{user_id}")
                # 清除排行榜缓存
                redis_client.delete("ranking_data")
            except Exception as e:
                print(f"Error clearing Redis cache: {e}")
        
        cur.close()
        current_app.put_db_connection(conn)
        
        return jsonify({'success': True})
        
    except Exception as e:
        cur.close()
        current_app.put_db_connection(conn)
        return jsonify({'success': False, 'error': str(e)})

@main.route('/feedback')
def feedback():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return "数据库连接失败", 500
    
    cur = conn.cursor()
    
    # 获取用户反馈记录
    cur.execute('''SELECT id, user_id, content, created_at, reply, reply_at 
                  FROM feedback WHERE user_id = %s 
                  ORDER BY created_at DESC''', (user_id,))
    feedbacks = cur.fetchall()
    
    # 转换反馈时间字段为UTC+8
    feedbacks_with_utc8 = []
    for feedback in feedbacks:
        feedback_list = list(feedback)
        # 转换created_at
        if feedback_list[3]:
            #feedback_list[3] = utc_to_utc8(feedback_list[3])
            feedback_list[3] = feedback_list[3].strftime('%Y-%m-%d %H:%M:%S')
        # 转换reply_at
        if feedback_list[5]:
            #feedback_list[5] = utc_to_utc8(feedback_list[5])
            feedback_list[5] = feedback_list[5].strftime('%Y-%m-%d %H:%M:%S')
        feedbacks_with_utc8.append(tuple(feedback_list))
    
    cur.close()
    current_app.put_db_connection(conn)
    
    return render_template('feedback.html', feedbacks=feedbacks_with_utc8)

@main.route('/feedback/new', methods=['GET', 'POST'])
def new_feedback():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        content = request.form['content']
        user_id = session['user_id']
        
        conn = current_app.get_db_connection()
        if not conn:
            return render_template('new_feedback.html', error='数据库连接失败')
        
        cur = conn.cursor()
        
        try:
            cur.execute('''INSERT INTO feedback (user_id, content) 
                          VALUES (%s, %s)''',
                       (user_id, content))
            conn.commit()
            cur.close()
            current_app.put_db_connection(conn)
            return redirect(url_for('main.feedback'))
        except Exception as e:
            cur.close()
            current_app.put_db_connection(conn)
            return render_template('new_feedback.html', error='提交失败，请重试')
    
    return render_template('new_feedback.html')



