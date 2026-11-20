"""Crea una base NUEVA de pruebas en LocalDB; nunca reutiliza ni borra bases."""
from uuid import uuid4

import pyodbc
from sqlalchemy import URL


def main():
    drivers = pyodbc.drivers()
    driver = next((d for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server") if d in drivers), None)
    if driver is None:
        raise SystemExit("Instala Microsoft ODBC Driver 18 for SQL Server")
    database = "OviumPruebas_" + uuid4().hex[:12]
    server = r"(localdb)\MSSQLLocalDB"
    connection_string = f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes"
    with pyodbc.connect(connection_string, autocommit=True) as connection:
        connection.execute(f"CREATE DATABASE [{database}]")
    url = URL.create("mssql+pyodbc", host=server, database=database,
        query={"driver": driver, "TrustServerCertificate": "yes", "Trusted_Connection": "yes"})
    print(url.render_as_string(hide_password=False))


if __name__ == "__main__":
    main()
