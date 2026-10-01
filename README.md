# Warehouse Management System

Database Management Systems (DBMS) PBL project: a MySQL database and a Python (Tkinter) desktop application.

## Files
- `warehouse_db.sql` - creates the database, tables, and sample data (MySQL)
- `main_dbms.py` - the Python application

## Features
- Manage warehouses, suppliers, products, and stock (add, view, search, edit, delete)
- Receive stock and set bin locations
- Transfers between warehouses (Pending / Confirmed)
- Dispatch, damage entry, and stock reconciliation
- Six SQL reports (stock by warehouse, low stock, and more)

## How to run
1. Install MySQL and MySQL Workbench.
2. Run `warehouse_db.sql` in MySQL Workbench.
3. Install the driver: `pip install mysql-connector-python`
4. In `main_dbms.py`, replace `YOUR_PASSWORD` in the `DB` dictionary with your MySQL password.
5. Run: `python main_dbms.py`

## Author
ZAID SUWAID
