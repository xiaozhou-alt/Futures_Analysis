from flask import Flask, render_template, jsonify, request, make_response
import pymysql
from datetime import datetime
import os
from collections import defaultdict
import urllib.parse

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../templates'))
print(os.path.abspath(os.path.join(os.path.dirname(__file__), '../templates/index.html')))

# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'xxx',
    'password': 'your_password',
    'database': 'xxx',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**db_config)

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/types')
def get_types():
    """获取所有期货种类"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT DISTINCT type FROM data"
            cursor.execute(sql)
            types = [row['type'] for row in cursor.fetchall()]
            return jsonify(types)
    finally:
        connection.close()

@app.route('/api/data', methods=['GET'])
def get_data():
    """获取筛选后的数据"""
    start_date = request.args.get('start_date', '2025-04-01')
    end_date = request.args.get('end_date', '2025-04-29')
    selected_type = request.args.get('type', 'all')
    manual_type = request.args.get('manual_type', None)
    
    # 如果提供了手动输入的类型，则优先使用
    if manual_type and manual_type.strip():
        selected_type = manual_type.strip()
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 构建SQL查询（添加source字段）
            sql = """
            SELECT id, type, trend, reason, company, DATE_FORMAT(date, '%%Y-%%m-%%d') as date, source 
            FROM data 
            WHERE date BETWEEN %s AND %s
            """
            params = [start_date, end_date]
            
            if selected_type != 'all':
                sql += " AND type = %s"
                params.append(selected_type)
            
            sql += " ORDER BY date DESC, type"
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            # 组织数据结构
            organized_data = {}
            for row in results:
                key = (row['type'], row['date'])
                if key not in organized_data:
                    # 统计当前类型和日期的所有趋势
                    trends = [r['trend'] for r in results if (r['type'], r['date']) == key]
                    trend_counts = {
                        '看好': trends.count('看好'),
                        '看空': trends.count('看空'),
                        '震荡': trends.count('震荡')
                    }
                    
                    # 找出数量最多的趋势
                    max_count = max(trend_counts.values())
                    candidates = [t for t, count in trend_counts.items() if count == max_count]
                    
                    # 按照优先级选择趋势
                    selected_trend = '看空' if '看空' in candidates else \
                                    '震荡' if '震荡' in candidates else '看好'
                    
                    organized_data[key] = {
                        'type': row['type'],
                        'date': row['date'],
                        'trend': selected_trend,  # 使用选择出的趋势
                        'details': {}
                    }
                
                if row['trend'] not in organized_data[key]['details']:
                    organized_data[key]['details'][row['trend']] = []
                
                # 生成PDF文件名（将.txt替换为.pdf）
                pdf_filename = row['source'].replace('.txt', '.pdf') if row['source'] else None
                
                organized_data[key]['details'][row['trend']].append({
                    'company': row['company'],
                    'reason': row['reason'],
                    'source': row['source'],
                    'pdf_filename': pdf_filename  # 添加PDF文件名
                })
            
            # 转换为列表
            data_list = list(organized_data.values())
            
            # 统计每个期货种类的观点分布
            type_stats = {}
            for row in results:
                if row['type'] not in type_stats:
                    type_stats[row['type']] = {
                        '看好': {'count': 0, 'companies': set()},
                        '看空': {'count': 0, 'companies': set()},
                        '震荡': {'count': 0, 'companies': set()}
                    }
                
                type_stats[row['type']][row['trend']]['count'] += 1
                type_stats[row['type']][row['trend']]['companies'].add(row['company'])
            
            # 转换集合为列表
            for type_data in type_stats.values():
                for trend in type_data:
                    type_data[trend]['companies'] = list(type_data[trend]['companies'])
            
            return jsonify({
                'daily_data': data_list,
                'type_stats': type_stats
            })
    finally:
        connection.close()

@app.route('/api/chart_data', methods=['GET'])
def get_chart_data():
    """获取堆叠柱状图数据"""
    start_date = request.args.get('start_date', '2025-04-01')
    end_date = request.args.get('end_date', '2025-04-29')
    selected_type = request.args.get('type', 'all')
    manual_type = request.args.get('manual_type', None)
    
    # 如果提供了手动输入的类型，则优先使用
    if manual_type and manual_type.strip():
        selected_type = manual_type.strip()
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 获取所有日期
            date_sql = """
            SELECT DISTINCT DATE_FORMAT(date, '%%Y-%%m-%%d') as date 
            FROM data 
            WHERE date BETWEEN %s AND %s 
            ORDER BY date
            """
            cursor.execute(date_sql, [start_date, end_date])
            all_dates = [row['date'] for row in cursor.fetchall()]
            
            # 如果没有选择具体类型，统计所有期货
            if selected_type == 'all':
                sql = """
                SELECT 
                    DATE_FORMAT(date, '%%Y-%%m-%%d') as date,
                    trend,
                    COUNT(*) as count
                FROM data
                WHERE date BETWEEN %s AND %s
                GROUP BY date, trend
                ORDER BY date
                """
                params = [start_date, end_date]
            else:
                sql = """
                SELECT 
                    DATE_FORMAT(date, '%%Y-%%m-%%d') as date,
                    trend,
                    COUNT(*) as count
                FROM data
                WHERE date BETWEEN %s AND %s AND type = %s
                GROUP BY date, trend
                ORDER BY date
                """
                params = [start_date, end_date, selected_type]
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            # 组织数据结构：按日期->趋势->数量
            chart_data = defaultdict(lambda: {'看好': 0, '看空': 0, '震荡': 0})
            
            for row in results:
                chart_data[row['date']][row['trend']] = row['count']
            
            # 确保所有日期都有数据（即使是0）
            for date in all_dates:
                if date not in chart_data:
                    chart_data[date] = {'看好': 0, '看空': 0, '震荡': 0}
            
            # 转换为前端需要的格式
            labels = sorted(chart_data.keys())
            bullish_data = []
            bearish_data = []
            flat_data = []
            
            for date in labels:
                bullish_data.append(chart_data[date]['看好'])
                bearish_data.append(chart_data[date]['看空'])
                flat_data.append(chart_data[date]['震荡'])
            
            return jsonify({
                'labels': [d[5:] for d in labels],  # 只显示月-日格式
                'datasets': [
                    {
                        'label': '看好',
                        'data': bullish_data,
                        'backgroundColor': 'rgba(255, 99, 132, 0.7)'
                    },
                    {
                        'label': '看空',
                        'data': bearish_data,
                        'backgroundColor': 'rgba(75, 192, 192, 0.7)'
                    },
                    {
                        'label': '震荡',
                        'data': flat_data,
                        'backgroundColor': 'rgba(255, 206, 86, 0.7)'
                    }
                ]
            })
    finally:
        connection.close()

@app.route('/api/download_pdf', methods=['GET'])
def download_pdf():
    """下载PDF文件"""
    pdf_filename = request.args.get('pdf_filename')
    if not pdf_filename:
        return jsonify({'error': 'Missing PDF filename'}), 400
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 查询PDF文件内容
            sql = "SELECT file_content, file_name FROM pdf WHERE file_name = %s"
            cursor.execute(sql, (pdf_filename,))
            result = cursor.fetchone()
            
            if result:
                # 创建响应对象
                response = make_response(result['file_content'])
                response.headers['Content-Type'] = 'application/pdf'
                
                # 正确编码文件名
                encoded_filename = urllib.parse.quote(result['file_name'])
                response.headers['Content-Disposition'] = (
                    f"attachment; "
                    f"filename*=UTF-8''{encoded_filename}"
                )
                
                return response
            else:
                return jsonify({'error': 'PDF not found'}), 404
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)