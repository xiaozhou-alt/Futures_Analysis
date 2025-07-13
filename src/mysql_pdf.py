import pymysql
import os
from datetime import datetime

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'xxx',
    'password': 'your_password',
    'database': 'xxx',
    'connect_timeout': 86400,  # 24小时 = 86400秒
    'read_timeout': 86400,   # 增加读取超时时间
    'write_timeout': 86400    # 增加写入超时时间
}

# 创建PDF信息表
def create_pdf_table():
    try:
        connection = pymysql.connect(**db_config)
        with connection.cursor() as cursor:
            # 先检查表是否存在，如果存在则删除
            cursor.execute("DROP TABLE IF EXISTS pdf")
            
            # 创建新表
            sql = """
            CREATE TABLE pdf (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_name VARCHAR(255) NOT NULL,
                file_content LONGBLOB NOT NULL,
                company_name VARCHAR(100) NOT NULL,
                file_date DATE NOT NULL,
                file_size BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            cursor.execute(sql)
        connection.commit()
        print("PDF文件表创建成功")
    except Exception as e:
        print(f"创建表失败: {e}")
    finally:
        if connection:
            connection.close()

# 从文件名提取公司名称
def extract_company_name(filename):
    # 假设文件名格式为: 公司名称_数字.pdf
    parts = filename.split('_')
    if len(parts) > 0:
        return parts[0]
    return "未知公司"

# 从文件夹路径提取日期
def extract_date_from_folder(folder_path):
    folder_name = os.path.basename(folder_path)
    if len(folder_name) == 8 and folder_name.isdigit():
        try:
            return datetime.strptime(folder_name, "%Y%m%d").date()
        except ValueError:
            return None
    return None

# 处理PDF文件并存入数据库
def process_pdf(pdf_dir):
    create_pdf_table()
    
    if not os.path.exists(pdf_dir):
        print(f"错误: PDF文件夹 {pdf_dir} 不存在")
        return
    
    print(f"开始处理PDF文件夹: {pdf_dir}")
    file_count = 0
    inserted_count = 0
    
    for root, dirs, files in os.walk(pdf_dir):
        print(f"正在处理目录: {root}")
        file_date = extract_date_from_folder(root)
        if not file_date:
            continue
            
        for file in files:
            if file.lower().endswith('.pdf'):
                file_count += 1
                file_path = os.path.join(root, file)
                company_name = extract_company_name(file)
                file_size = os.path.getsize(file_path)
                
                try:
                    with open(file_path, 'rb') as pdf_file:
                        pdf_content = pdf_file.read()
                        
                    # 为每个文件创建新连接
                    connection = pymysql.connect(**db_config)
                    with connection.cursor() as cursor:
                        insert_sql = """
                        INSERT INTO pdf 
                        (file_name, file_content, company_name, file_date, file_size)
                        VALUES (%s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_sql, (
                            file, 
                            pdf_content,
                            company_name, 
                            file_date, 
                            file_size
                        ))
                        connection.commit()
                except Exception as e:
                    print(f"处理文件 {file} 时出错: {e}")
                finally:
                    if connection:
                        connection.close()
    
    print(f"处理完成，共扫描 {file_count} 个PDF文件，成功插入 {inserted_count} 条记录")

if __name__ == "__main__":
    pdf_dir = r"h:\project\economy\output_pdf"
    process_pdf(pdf_dir)