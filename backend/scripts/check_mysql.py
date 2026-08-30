import pymysql

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3307,
        user='root',
        password='root',
        database='phd_entrance_db'
    )
    print("SUCCESSFULLY CONNECTED TO MYSQL DATABASE on 127.0.0.1:3307!")
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    print("Tables:", tables)
    conn.close()
except Exception as e:
    print("MySQL Connection Error:", type(e), e)
