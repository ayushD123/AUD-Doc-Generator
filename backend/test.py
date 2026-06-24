from dotenv import load_dotenv
load_dotenv()

import os
import oracledb

os.environ["TNS_ADMIN"] = os.getenv("TNS_ADMIN") or os.getenv("ORACLE_DB_WALLET_DIR")

print("USER:", os.getenv("ORACLE_DB_USER"))
print("DSN:", os.getenv("ORACLE_DB_DSN"))
print("TNS_ADMIN:", os.getenv("TNS_ADMIN"))

conn = oracledb.connect(
    user=os.getenv("ORACLE_DB_USER"),
    password=os.getenv("ORACLE_DB_PASSWORD"),
    dsn=os.getenv("ORACLE_DB_DSN"),
)
print("Connected:", conn.version)
conn.close()