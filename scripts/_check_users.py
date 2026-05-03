import psycopg2

conn = psycopg2.connect("postgresql://marine:marine_dev@localhost:5433/marine_risk")
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name = 'users' ORDER BY ordinal_position"
)
for row in cur.fetchall():
    print(row[0])
cur.close()
conn.close()
