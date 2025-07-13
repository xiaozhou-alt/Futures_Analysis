import pymysql
import os
import re

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'xxx',
    'password': 'your_password',
    'database': 'xxx'
}

# 创建表结构
def create_table():
    try:
        connection = pymysql.connect(**db_config)
        with connection.cursor() as cursor:
            sql = """
            CREATE TABLE IF NOT EXISTS data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type VARCHAR(255) NOT NULL,
                trend VARCHAR(255) NOT NULL,
                reason TEXT,
                company VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                source VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            cursor.execute(sql)
        connection.commit()
        print("表创建成功")
    except Exception as e:
        print(f"创建表失败: {e}")
    finally:
        if connection:
            connection.close()

# 在数据库插入逻辑中添加日期处理
def extract_date_from_folder(folder_path):
    folder_name = os.path.basename(folder_path)
    if len(folder_name) == 8 and folder_name.isdigit():
        return f"{folder_name[:4]}-{folder_name[4:6]}-{folder_name[6:8]}"
    return None

# 先创建表
create_table()

# 定义源文件夹路径
source_folder = os.path.join(os.getcwd(), "output_final")
print(f"正在扫描文件夹: {source_folder}")

# 定义正则表达式匹配三元组
pattern = re.compile(r'(.+?)-(.+?)-(.+)')

# 数据库插入逻辑
if os.path.exists(source_folder):
    print(f"找到源文件夹: {source_folder}")
    file_count = 0
    record_count = 0
    
    for root, dirs, files in os.walk(source_folder):
        print(f"正在处理目录: {root}")
        date_str = extract_date_from_folder(root)
        if not date_str:
            continue
            
        for file in files:
            if file.endswith('.txt'):
                file_count += 1
                source_path = os.path.join(root, file)
                company_name = file[:4]
                
                try:
                    with open(source_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    lines = content.splitlines()
                    for line in lines:
                        match = pattern.search(line)
                        if match:
                            try:
                                connection = pymysql.connect(**db_config)
                                with connection.cursor() as cursor:
                                    # 检查数据是否已存在
                                    check_sql = """
                                    SELECT COUNT(*) FROM data 
                                    WHERE type = %s AND trend = %s 
                                    AND reason = %s AND company = %s AND date = %s AND source = %s
                                    """
                                    cursor.execute(check_sql, (
                                        match.group(1),
                                        match.group(2),
                                        match.group(3),
                                        company_name,
                                        date_str,
                                        file
                                    ))
                                    if cursor.fetchone()[0] == 0:
                                        # 数据不存在时才插入
                                        insert_sql = """
                                        INSERT INTO data 
                                        (type, trend, reason, company, date, source) 
                                        VALUES (%s, %s, %s, %s, %s, %s)
                                        """
                                        cursor.execute(insert_sql, (
                                            match.group(1), 
                                            match.group(2), 
                                            match.group(3), 
                                            company_name,
                                            date_str,
                                            file
                                        ))
                                        record_count += 1
                                        connection.commit()
                                    else:
                                        print(f"数据已存在，跳过: {match.group(1)}-{match.group(2)}-{match.group(3)}-{company_name}-{date_str}-{file}")
                            except Exception as e:
                                print(f"数据库插入失败: {e}")
                            finally:
                                if connection:
                                    connection.close()
                except Exception as e:
                    print(f"处理文件 {file} 时出错: {e}")
    
    print(f"处理完成，共处理 {file_count} 个文件，插入 {record_count} 条记录")
else:
    print(f"错误: 源文件夹 {source_folder} 不存在")