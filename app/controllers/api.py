from flask import Blueprint, jsonify, request, session, current_app
import psycopg2
from datetime import datetime, time
import math
from app.utils import utc_to_utc8

api = Blueprint('api', __name__)

@api.route('/user-work-info', methods=['GET'])
def get_user_work_info():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('''SELECT work_start_time, work_end_time, break_start_time, 
                      break_end_time, daily_salary FROM user_work_info WHERE user_id = %s''', 
                   (user_id,))
        info = cur.fetchone()
        
        if info:
            return jsonify({
                'success': True,
                'info': {
                    'work_start_time': info[0].strftime('%H:%M') if info[0] else None,
                    'work_end_time': info[1].strftime('%H:%M') if info[1] else None,
                    'break_start_time': info[2].strftime('%H:%M') if info[2] else None,
                    'break_end_time': info[3].strftime('%H:%M') if info[3] else None,
                    'daily_salary': float(info[4]) if info[4] else 0
                }
            })
        else:
            return jsonify({'success': False, 'error': '未找到用户信息'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/user-work-info', methods=['POST'])
def save_user_work_info():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    work_start_time = request.form.get('work_start_time')
    work_end_time = request.form.get('work_end_time')
    break_start_time = request.form.get('break_start_time')
    break_end_time = request.form.get('break_end_time')
    daily_salary = request.form.get('daily_salary', 0)
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        # 检查是否已存在记录
        cur.execute('SELECT id FROM user_work_info WHERE user_id = %s', (user_id,))
        existing = cur.fetchone()
        
        if existing:
            # 更新现有记录
            cur.execute('''UPDATE user_work_info SET work_start_time = %s, work_end_time = %s, 
                          break_start_time = %s, break_end_time = %s, daily_salary = %s 
                          WHERE user_id = %s''',
                       (work_start_time, work_end_time, break_start_time, break_end_time, 
                        daily_salary, user_id))
        else:
            # 插入新记录
            cur.execute('''INSERT INTO user_work_info (user_id, work_start_time, work_end_time, 
                          break_start_time, break_end_time, daily_salary) 
                          VALUES (%s, %s, %s, %s, %s, %s)''',
                       (user_id, work_start_time, work_end_time, break_start_time, 
                        break_end_time, daily_salary))
        
        conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)



@api.route('/slacking-records', methods=['POST'])
def save_slacking_record():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    duration = request.form.get('slacking_duration')
    project = request.form.get('slacking_project')
    
    if not duration or not project:
        return jsonify({'success': False, 'error': '请填写完整信息'})
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT daily_salary, work_start_time, work_end_time, break_start_time, break_end_time FROM user_work_info WHERE user_id = %s', (user_id,))
        salary_info = cur.fetchone()
        
        if not salary_info or not salary_info[0] or not salary_info[1] or not salary_info[2]:
            return jsonify({'success': False, 'error': '请先设置完整的工作时间和日薪'})
        
        daily_salary = float(salary_info[0])
        work_start_time = salary_info[1]
        work_end_time = salary_info[2]
        break_start_time = salary_info[3]
        break_end_time = salary_info[4]
        
        # 计算工作时间(秒)
        work_duration = (
            datetime.combine(datetime.today(), work_end_time) - 
            datetime.combine(datetime.today(), work_start_time)
        ).total_seconds()
        
        # 如果工作时间跨过午夜
        if work_end_time < work_start_time:
            work_duration = (
                datetime.combine(datetime.today() + datetime.timedelta(days=1), work_end_time) - 
                datetime.combine(datetime.today(), work_start_time)
            ).total_seconds()
        
        # 减去休息时间
        if break_start_time and break_end_time:
            # 如果休息时间也跨过午夜
            if break_end_time < break_start_time:
                break_duration = (
                    datetime.combine(datetime.today() + datetime.timedelta(days=1), break_end_time) - 
                    datetime.combine(datetime.today(), break_start_time)
                ).total_seconds()
            else:
                break_duration = (
                    datetime.combine(datetime.today(), break_end_time) - 
                    datetime.combine(datetime.today(), break_start_time)
                ).total_seconds()
            work_duration -= break_duration
        
        # 计算每秒收益
        earnings_per_second = daily_salary / work_duration if work_duration > 0 else 0
        
        # 计算摸鱼收益 (摸鱼时间*秒级薪资)
        earnings = earnings_per_second * int(duration) * 60
        
        # 保存记录
        cur.execute('''INSERT INTO slacking_records (user_id, duration, project, earnings) 
                      VALUES (%s, %s, %s, %s)''',
                   (user_id, duration, project, earnings))
        conn.commit()
        
        return jsonify({'success': True, 'earnings': f'{earnings:.2f}'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/overtime-records', methods=['POST'])
def save_overtime_record():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    duration = request.form.get('overtime_duration')
    project = request.form.get('overtime_project')
    
    if not duration or not project:
        return jsonify({'success': False, 'error': '请填写完整信息'})
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT daily_salary, work_start_time, work_end_time, break_start_time, break_end_time FROM user_work_info WHERE user_id = %s', (user_id,))
        salary_info = cur.fetchone()
        
        if not salary_info or not salary_info[0] or not salary_info[1] or not salary_info[2]:
            return jsonify({'success': False, 'error': '请先设置完整的工作时间和日薪'})
        
        daily_salary = float(salary_info[0])
        work_start_time = salary_info[1]
        work_end_time = salary_info[2]
        break_start_time = salary_info[3]
        break_end_time = salary_info[4]
        
        # 计算工作时间(秒)
        work_duration = (
            datetime.combine(datetime.today(), work_end_time) - 
            datetime.combine(datetime.today(), work_start_time)
        ).total_seconds()
        
        # 如果工作时间跨过午夜
        if work_end_time < work_start_time:
            work_duration = (
                datetime.combine(datetime.today() + datetime.timedelta(days=1), work_end_time) - 
                datetime.combine(datetime.today(), work_start_time)
            ).total_seconds()
        
        # 减去休息时间
        if break_start_time and break_end_time:
            # 如果休息时间也跨过午夜
            if break_end_time < break_start_time:
                break_duration = (
                    datetime.combine(datetime.today() + datetime.timedelta(days=1), break_end_time) - 
                    datetime.combine(datetime.today(), break_start_time)
                ).total_seconds()
            else:
                break_duration = (
                    datetime.combine(datetime.today(), break_end_time) - 
                    datetime.combine(datetime.today(), break_start_time)
                ).total_seconds()
            work_duration -= break_duration
        
        # 计算每秒收益
        earnings_per_second = daily_salary / work_duration if work_duration > 0 else 0
        
        # 计算加班负收益 (加班时间*秒级薪资*3)
        earnings = earnings_per_second * int(duration) * 60 * 3
        
        # 保存记录
        cur.execute('''INSERT INTO overtime_records (user_id, duration, project, earnings) 
                      VALUES (%s, %s, %s, %s)''',
                   (user_id, duration, project, earnings))
        conn.commit()
        
        return jsonify({'success': True, 'earnings': f'{earnings:.2f}'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/slacking-record/<int:record_id>', methods=['GET'])
def get_slacking_record(record_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('''SELECT project, duration, earnings, created_at 
                      FROM slacking_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        record = cur.fetchone()
        
        if record:
            # 处理日期格式化，转换为UTC+8时间
            created_at_str = None
            if record[3]:
                try:
                    utc8_time = utc_to_utc8(record[3])
                    created_at_str = utc8_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    created_at_str = str(record[3])
            
            return jsonify({
                'success': True,
                'record': {
                    'project': record[0],
                    'duration': record[1],
                    'earnings': float(record[2]),
                    'created_at': created_at_str
                }
            })
        else:
            return jsonify({'success': False, 'error': '记录不存在'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/overtime-record/<int:record_id>', methods=['GET'])
def get_overtime_record(record_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        cur.execute('''SELECT project, duration, earnings, created_at 
                      FROM overtime_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        record = cur.fetchone()
        
        if record:
            # 处理日期格式化，转换为UTC+8时间
            created_at_str = None
            if record[3]:
                try:
                    utc8_time = utc_to_utc8(record[3])
                    created_at_str = utc8_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    created_at_str = str(record[3])
            
            return jsonify({
                'success': True,
                'record': {
                    'project': record[0],
                    'duration': record[1],
                    'earnings': float(record[2]),
                    'created_at': created_at_str
                }
            })
        else:
            return jsonify({'success': False, 'error': '记录不存在'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/slacking-record/<int:record_id>', methods=['DELETE'])
def delete_slacking_record(record_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        # 检查记录是否存在且属于当前用户
        cur.execute('''SELECT id FROM slacking_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        record = cur.fetchone()
        
        if not record:
            return jsonify({'success': False, 'error': '记录不存在或无权限删除'})
        
        # 删除记录
        cur.execute('''DELETE FROM slacking_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)

@api.route('/overtime-record/<int:record_id>', methods=['DELETE'])
def delete_overtime_record(record_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '未登录'})
    
    user_id = session['user_id']
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': '数据库连接失败'})
    
    cur = conn.cursor()
    
    try:
        # 检查记录是否存在且属于当前用户
        cur.execute('''SELECT id FROM overtime_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        record = cur.fetchone()
        
        if not record:
            return jsonify({'success': False, 'error': '记录不存在或无权限删除'})
        
        # 删除记录
        cur.execute('''DELETE FROM overtime_records 
                      WHERE id = %s AND user_id = %s''', (record_id, user_id))
        conn.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        current_app.put_db_connection(conn)