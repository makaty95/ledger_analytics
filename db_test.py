import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="makaty",
    database="learning_db"
)

cursor = conn.cursor()

cursor.execute("SELECT * FROM customers")

for row in cursor.fetchall():
    print(row)

cursor.close()
conn.close()