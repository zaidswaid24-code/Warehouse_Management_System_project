# app.py
# Multi-Warehouse Stock Transfer Management System -- WEB VERSION (Streamlit + MySQL)
#
# Same business logic as the Tkinter desktop app (main_dbms.py):
# transactions, FOR UPDATE row locks, validation, friendly database errors.
#
# Run locally:   streamlit run app.py
# Database login is read from .streamlit/secrets.toml (see secrets.toml.example)
# or from environment variables DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

import os
import tempfile
from datetime import date, datetime

import mysql.connector
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Warehouse Management System", page_icon="📦", layout="wide")


# ---------------------------------------------------------------------------
# DB CONFIG
# ---------------------------------------------------------------------------
def load_config():
    cfg = {}
    try:
        if "mysql" in st.secrets:
            cfg = dict(st.secrets["mysql"])
    except Exception:
        cfg = {}
    if not cfg:
        cfg = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", "3306")),
            "user": os.environ.get("DB_USER", "root"),
            "password": os.environ.get("DB_PASSWORD", ""),
            "database": os.environ.get("DB_NAME", "warehouseDB"),
        }
    # Optional TLS (cloud databases such as Aiven require it): the CA
    # certificate text is stored in the secret "ssl_ca_pem".
    pem = cfg.pop("ssl_ca_pem", None)
    if pem:
        path = os.path.join(tempfile.gettempdir(), "db_ca.pem")
        with open(path, "w") as f:
            f.write(pem)
        cfg["ssl_ca"] = path
    cfg["port"] = int(cfg.get("port", 3306))
    return cfg


DB = load_config()


def conn():
    return mysql.connector.connect(**DB)


def run(sql, params=(), fetch=False):
    """One-shot query, auto-commit. Used for reads and simple writes."""
    c = conn()
    cur = c.cursor()
    try:
        cur.execute(sql, params)
        data = cur.fetchall() if fetch else None
        c.commit()
        return data
    finally:
        cur.close()
        c.close()


def run_dict(sql, params=()):
    c = conn()
    cur = c.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        c.close()


def with_transaction(func):
    """Runs func(cursor) in ONE transaction: commit on success, rollback on error."""
    c = conn()
    c.autocommit = False
    cur = c.cursor()
    try:
        result = func(cur)
        c.commit()
        return result
    except Exception:
        c.rollback()
        raise
    finally:
        cur.close()
        c.close()


def next_id(table, pk, cur=None):
    sql = f"SELECT COALESCE(MAX({pk}), 0) + 1 FROM {table}"
    if cur is not None:
        cur.execute(sql)
        return cur.fetchone()[0]
    return run(sql, fetch=True)[0][0]


def friendly_db_error(e):
    code = getattr(e, "errno", None)
    if code == 1451:
        return "Can't delete this -- other records still reference it. Delete those first."
    if code == 1452:
        return "Can't save this -- it refers to a record that doesn't exist."
    if code == 1062:
        return "That ID already exists. Try again."
    if code == 2003:
        return "Can't reach the database server."
    if code == 1045:
        return "Database login failed -- check the credentials in the secrets."
    if code == 1049:
        return "The database doesn't exist. Did you run schema_setup.sql?"
    if code == 1146:
        return "Tables are missing. Run schema_setup.sql on the database first."
    return str(e)


# ---------------------------------------------------------------------------
# Validation helpers -- raise ValueError with a user-facing message
# ---------------------------------------------------------------------------
def v_required(value, label):
    value = (value or "").strip()
    if value == "":
        raise ValueError(f"'{label}' is required.")
    return value


def v_int(value, label, minimum=0):
    value = (value or "").strip()
    if value == "":
        raise ValueError(f"'{label}' is required.")
    try:
        n = int(value)
    except ValueError:
        raise ValueError(f"'{label}' must be a whole number.")
    if minimum is not None and n < minimum:
        raise ValueError(f"'{label}' must be at least {minimum}.")
    return n


def v_email(value, label="Email"):
    value = (value or "").strip()
    if value == "":
        raise ValueError(f"'{label}' is required.")
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError(f"'{label}' doesn't look like a valid email address.")
    return value


VALIDATORS = {"text": v_required, "int": v_int, "email": v_email}


# ---------------------------------------------------------------------------
# Table metadata (same as the desktop app)
# ---------------------------------------------------------------------------
TABLES = {
    "warehouse": {
        "pk": "warehouseID",
        "display_query": "SELECT warehouseID, warehouseName, location FROM warehouse ORDER BY warehouseID",
        "labels": ["ID", "Warehouse Name", "Location"],
        "add_fields": [
            {"column": "warehouseName", "label": "Warehouse Name", "kind": "text"},
            {"column": "location", "label": "Location", "kind": "text"},
        ],
    },
    "supplier": {
        "pk": "supplierID",
        "display_query": "SELECT supplierID, supplierName, phone, email FROM supplier ORDER BY supplierID",
        "labels": ["ID", "Supplier Name", "Phone", "Email"],
        "add_fields": [
            {"column": "supplierName", "label": "Supplier Name", "kind": "text"},
            {"column": "phone", "label": "Phone", "kind": "int"},
            {"column": "email", "label": "Email", "kind": "email"},
        ],
    },
    "product": {
        "pk": "productID",
        "display_query": """
            SELECT p.productID, p.productName, p.price, p.category, s.supplierName
            FROM product p LEFT JOIN supplier s ON p.supplierID = s.supplierID
            ORDER BY p.productID""",
        "labels": ["ID", "Product Name", "Price", "Category", "Supplier"],
        "add_fields": [
            {"column": "productName", "label": "Product Name", "kind": "text"},
            {"column": "price", "label": "Price", "kind": "int", "min": 0},
            {"column": "category", "label": "Category", "kind": "text"},
            {"column": "supplierID", "label": "Supplier", "kind": "fk",
             "choices_query": "SELECT supplierID, supplierName FROM supplier ORDER BY supplierName"},
        ],
    },
    "stock": {
        "pk": "stockID",
        "display_query": """
            SELECT s.stockID, w.warehouseName, p.productName, s.quantity,
                   COALESCE(s.binLocation, '')
            FROM stock s
            JOIN warehouse w ON s.warehouseID = w.warehouseID
            JOIN product p ON s.productID = p.productID
            ORDER BY s.stockID""",
        "labels": ["ID", "Warehouse", "Product", "Quantity", "Bin Location"],
        "add_fields": [
            {"column": "warehouseID", "label": "Warehouse", "kind": "fk",
             "choices_query": "SELECT warehouseID, warehouseName FROM warehouse ORDER BY warehouseName"},
            {"column": "productID", "label": "Product", "kind": "fk",
             "choices_query": "SELECT productID, productName FROM product ORDER BY productName"},
            {"column": "quantity", "label": "Quantity", "kind": "int", "min": 0},
            {"column": "binLocation", "label": "Bin Location", "kind": "text", "required": False},
        ],
        "add_button_label": "Receive Stock",
    },
    "transfer": {
        "pk": "transferID",
        "display_query": """
            SELECT t.transferID, wf.warehouseName, wt.warehouseName, t.transferData, t.status
            FROM transfer t
            JOIN warehouse wf ON t.from_warehouseID = wf.warehouseID
            JOIN warehouse wt ON t.to_warehouseID = wt.warehouseID
            ORDER BY t.transferID""",
        "labels": ["ID", "From Warehouse", "To Warehouse", "Date (YYYYMMDD)", "Status"],
        "add_fields": [
            {"column": "from_warehouseID", "label": "From Warehouse", "kind": "fk",
             "choices_query": "SELECT warehouseID, warehouseName FROM warehouse ORDER BY warehouseName"},
            {"column": "to_warehouseID", "label": "To Warehouse", "kind": "fk",
             "choices_query": "SELECT warehouseID, warehouseName FROM warehouse ORDER BY warehouseName"},
            {"column": "transferData", "label": "Date (YYYYMMDD)", "kind": "int", "min": 1},
        ],
        "fixed_values_on_insert": {"status": "Pending"},
        "add_button_label": "Initiate Transfer",
    },
    "transferDetails": {
        "pk": "transfer_DetailID",
        "display_query": """
            SELECT td.transfer_DetailID, td.transferID, p.productName, td.quantity
            FROM transferDetails td JOIN product p ON td.productID = p.productID
            ORDER BY td.transfer_DetailID""",
        "labels": ["ID", "Transfer ID", "Product", "Quantity"],
        "add_fields": [
            {"column": "transferID", "label": "Transfer (pending only)", "kind": "fk",
             "choices_query": "SELECT transferID, CONCAT('Transfer #', transferID) "
                              "FROM transfer WHERE status='Pending' ORDER BY transferID"},
            {"column": "productID", "label": "Product", "kind": "fk",
             "choices_query": "SELECT productID, productName FROM product ORDER BY productName"},
            {"column": "quantity", "label": "Quantity", "kind": "int", "min": 1},
        ],
        "add_button_label": "Add Line Item",
    },
    "dispatch": {
        "pk": "dispatchID",
        "display_query": """
            SELECT d.dispatchID, w.warehouseName, p.productName, d.quantity, d.destination, d.dispatchDate
            FROM dispatch d
            JOIN stock s ON d.stockID = s.stockID
            JOIN warehouse w ON s.warehouseID = w.warehouseID
            JOIN product p ON s.productID = p.productID
            ORDER BY d.dispatchID""",
        "labels": ["ID", "Warehouse", "Product", "Quantity", "Destination", "Date"],
    },
    "damagedStock": {
        "pk": "damageID",
        "display_query": """
            SELECT d.damageID, w.warehouseName, p.productName, d.quantity, d.reason, d.damageDate
            FROM damagedStock d
            JOIN stock s ON d.stockID = s.stockID
            JOIN warehouse w ON s.warehouseID = w.warehouseID
            JOIN product p ON s.productID = p.productID
            ORDER BY d.damageID""",
        "labels": ["ID", "Warehouse", "Product", "Quantity", "Reason", "Date"],
    },
    "reconciliation": {
        "pk": "reconID",
        "display_query": """
            SELECT r.reconID, w.warehouseName, p.productName, r.systemQty, r.countedQty,
                   r.difference, r.reconDate, r.note
            FROM reconciliation r
            JOIN stock s ON r.stockID = s.stockID
            JOIN warehouse w ON s.warehouseID = w.warehouseID
            JOIN product p ON s.productID = p.productID
            ORDER BY r.reconID""",
        "labels": ["ID", "Warehouse", "Product", "System Qty", "Counted Qty", "Difference", "Date", "Note"],
    },
}


def stock_choices():
    rows = run("""
        SELECT s.stockID, p.productName, w.warehouseName, s.quantity
        FROM stock s
        JOIN product p ON s.productID = p.productID
        JOIN warehouse w ON s.warehouseID = w.warehouseID
        ORDER BY p.productName""", fetch=True) or []
    return {f"{pn} @ {wn} (Qty: {q}) [ID {sid}]": sid for sid, pn, wn, q in rows}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def flash(kind, msg):
    """Remember a message across the automatic rerun after an action."""
    st.session_state["_flash"] = (kind, msg)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        kind, msg = item
        {"success": st.success, "error": st.error, "warning": st.warning}.get(kind, st.info)(msg)


def table_view(table_name, key):
    """Searchable table (Refresh + Search)."""
    meta = TABLES[table_name]
    c1, c2 = st.columns([3, 1])
    term = c1.text_input("Search", key=f"{key}_search", placeholder="Type to filter rows...")
    c2.write("")
    c2.write("")
    c2.button("Refresh / View All", key=f"{key}_refresh")
    try:
        rows = run(meta["display_query"], fetch=True) or []
    except mysql.connector.Error as e:
        st.error(friendly_db_error(e))
        return []
    if term.strip():
        t = term.strip().lower()
        rows = [r for r in rows if any(t in str(cell).lower() for cell in r)]
    df = pd.DataFrame(rows, columns=meta["labels"])
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption(f"{len(df)} row(s)")
    return rows


def fk_choices(field):
    rows = run(field["choices_query"], fetch=True) or []
    return {f"{name} (ID {i})": i for i, name in rows}


def record_form(table_name, mode, key, existing=None):
    """Generic Add / Edit form built from TABLES[...]['add_fields']."""
    meta = TABLES[table_name]
    existing = existing or {}
    pk_value = existing.get(meta["pk"], "new")
    verb = "Save changes" if mode == "edit" else meta.get("add_button_label", "Add")
    n = st.session_state.get(f"{key}_n", 0)  # bumped after a successful add => fresh empty form

    with st.form(f"{key}_{mode}_{pk_value}_{n}"):
        inputs = {}
        for field in meta["add_fields"]:
            col, label, kind = field["column"], field["label"], field["kind"]
            required = field.get("required", True)
            wlabel = label if required else f"{label} (optional)"
            wkey = f"{key}_{mode}_{pk_value}_{col}_{n}"
            if kind == "fk":
                choices = fk_choices(field)
                names = list(choices.keys())
                index = None
                if mode == "edit" and existing.get(col) is not None:
                    for i, n in enumerate(names):
                        if choices[n] == existing[col]:
                            index = i
                inputs[col] = (kind, st.selectbox(wlabel, names, index=index, key=wkey,
                                                  placeholder="Choose..."), choices, required)
            else:
                default = ""
                if mode == "edit" and existing.get(col) is not None:
                    default = str(existing[col])
                inputs[col] = (kind, st.text_input(wlabel, value=default, key=wkey), None, required)
        submitted = st.form_submit_button(verb, type="primary")

    if not submitted:
        return

    values = {}
    try:
        for col, (kind, raw, choices, required) in inputs.items():
            if kind == "fk":
                if raw is None:
                    if required:
                        raise ValueError(f"Please choose a '{col}'.")
                    continue
                values[col] = choices[raw]
            else:
                if (raw or "").strip() == "" and not required:
                    continue
                field = next(f for f in meta["add_fields"] if f["column"] == col)
                if kind == "int":
                    values[col] = v_int(raw, field["label"], field.get("min", 0))
                else:
                    values[col] = VALIDATORS[kind](raw, field["label"])
    except ValueError as ve:
        st.error(str(ve))
        return

    try:
        if mode == "add":
            pk = meta["pk"]
            fixed = meta.get("fixed_values_on_insert", {})
            new_id = next_id(table_name, pk)
            all_values = {**values, **fixed}
            columns = [pk] + list(all_values.keys())
            ph = ", ".join(["%s"] * len(columns))
            run(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({ph})",
                [new_id] + list(all_values.values()))
            flash("success", f"Added (ID {new_id}).")
            st.session_state[f"{key}_n"] = n + 1
        else:
            pk = meta["pk"]
            set_clause = ", ".join(f"{c} = %s" for c in values)
            run(f"UPDATE {table_name} SET {set_clause} WHERE {pk} = %s",
                list(values.values()) + [existing[pk]])
            flash("success", "Updated.")
    except mysql.connector.Error as e:
        st.error(friendly_db_error(e))
        return
    st.rerun()


def row_picker(rows, label, key):
    """Select box listing the displayed rows; returns the chosen ID or None."""
    options = {" | ".join(str(c) for c in r): r[0] for r in rows}
    choice = st.selectbox(label, list(options.keys()), index=None, key=key,
                          placeholder="Select a row...")
    return options.get(choice)


def crud_section(table_name, key, allow_edit=True, status_guard=False, extra=None):
    """Table + Add / Edit / Delete (+ optional extra actions)."""
    meta = TABLES[table_name]
    rows = table_view(table_name, key)

    labels = ["➕ " + meta.get("add_button_label", "Add")]
    if allow_edit:
        labels.append("✏️ Edit selected")
    labels.append("🗑️ Delete selected")
    if extra:
        labels += list(extra.keys())
    action = st.radio("Action", labels, horizontal=True, key=f"{key}_action", label_visibility="collapsed")

    if action == labels[0]:
        record_form(table_name, "add", key)

    elif allow_edit and action.startswith("✏️"):
        pk_value = row_picker(rows, "Row to edit", f"{key}_edit_pick")
        if pk_value is not None:
            if status_guard and transfer_status(pk_value) == "Confirmed":
                st.warning("Confirmed transfers can't be edited.")
            else:
                existing = run_dict(f"SELECT * FROM {table_name} WHERE {meta['pk']} = %s", (pk_value,))
                if existing:
                    record_form(table_name, "edit", key, existing[0])

    elif action.startswith("🗑️"):
        pk_value = row_picker(rows, "Row to delete", f"{key}_del_pick")
        if pk_value is not None:
            if status_guard and transfer_status(pk_value) == "Confirmed":
                st.warning("Confirmed transfers can't be deleted (stock already moved).")
            elif st.button(f"Confirm delete (ID {pk_value})", key=f"{key}_del_btn", type="primary"):
                try:
                    run(f"DELETE FROM {table_name} WHERE {meta['pk']} = %s", (pk_value,))
                    flash("success", "Deleted.")
                    st.rerun()
                except mysql.connector.Error as e:
                    st.error(friendly_db_error(e))

    elif extra and action in extra:
        extra[action](rows)


def transfer_status(transfer_id):
    rows = run("SELECT status FROM transfer WHERE transferID = %s", (transfer_id,), fetch=True)
    return rows[0][0] if rows else None


# ---------------------------------------------------------------------------
# Stock: Put-away
# ---------------------------------------------------------------------------
def put_away_action(rows):
    pk_value = row_picker(rows, "Stock row", "stock_put_pick")
    with st.form("put_away_form", clear_on_submit=True):
        bin_value = st.text_input("Bin location (e.g. A1-03)")
        ok = st.form_submit_button("Save bin location", type="primary")
    if ok:
        if pk_value is None:
            st.error("Select a stock row first.")
        elif bin_value.strip() == "":
            st.error("'Bin location' is required.")
        else:
            run("UPDATE stock SET binLocation = %s WHERE stockID = %s", (bin_value.strip(), pk_value))
            flash("success", "Bin location updated.")
            st.rerun()


# ---------------------------------------------------------------------------
# Transfers: Confirm (moves the real stock inside one transaction)
# ---------------------------------------------------------------------------
def confirm_transfer_action(rows):
    pending = [r for r in rows if r[4] == "Pending"]
    options = {f"Transfer #{r[0]}: {r[1]} → {r[2]}": r[0] for r in pending}
    choice = st.selectbox("Pending transfer to confirm", list(options.keys()), index=None,
                          key="tr_confirm_pick", placeholder="Select a pending transfer...")
    st.caption("Confirming moves the real stock quantities between the two warehouses.")
    if st.button("Confirm transfer", type="primary", key="tr_confirm_btn"):
        if choice is None:
            st.error("Select a transfer first.")
            return
        transfer_id = int(options[choice])

        def _do(cur):
            cur.execute("SELECT status, from_warehouseID, to_warehouseID FROM transfer "
                        "WHERE transferID = %s FOR UPDATE", (transfer_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Transfer not found.")
            status, from_wh, to_wh = row
            if status == "Confirmed":
                raise ValueError("This transfer is already confirmed.")
            cur.execute("SELECT productID, quantity FROM transferDetails WHERE transferID = %s", (transfer_id,))
            lines = cur.fetchall()
            if not lines:
                raise ValueError("This transfer has no line items yet -- add products in Transfer Details first.")
            for product_id, qty in lines:
                cur.execute("SELECT quantity FROM stock WHERE productID = %s AND warehouseID = %s FOR UPDATE",
                            (product_id, from_wh))
                src = cur.fetchone()
                available = src[0] if src else 0
                if available < qty:
                    raise ValueError(f"Not enough stock of product {product_id} in the source warehouse "
                                     f"(have {available}, need {qty}).")
            for product_id, qty in lines:
                cur.execute("UPDATE stock SET quantity = quantity - %s WHERE productID = %s AND warehouseID = %s",
                            (qty, product_id, from_wh))
                cur.execute("SELECT stockID FROM stock WHERE productID = %s AND warehouseID = %s",
                            (product_id, to_wh))
                dest = cur.fetchone()
                if dest:
                    cur.execute("UPDATE stock SET quantity = quantity + %s WHERE stockID = %s", (qty, dest[0]))
                else:
                    new_stock_id = next_id("stock", "stockID", cur)
                    cur.execute("INSERT INTO stock (stockID, warehouseID, productID, quantity) "
                                "VALUES (%s,%s,%s,%s)", (new_stock_id, to_wh, product_id, qty))
            cur.execute("UPDATE transfer SET status = 'Confirmed' WHERE transferID = %s", (transfer_id,))

        try:
            with_transaction(_do)
        except ValueError as ve:
            st.error(f"Can't confirm transfer: {ve}")
            return
        except mysql.connector.Error as e:
            st.error(friendly_db_error(e))
            return
        flash("success", f"Transfer #{transfer_id} confirmed and stock moved.")
        st.rerun()


# ---------------------------------------------------------------------------
# Dispatch / Damage / Reconciliation: audit logs tied to real stock changes
# ---------------------------------------------------------------------------
def movement_section(table_name, key, kind):
    meta = TABLES[table_name]
    rows = table_view(table_name, key)
    choices = stock_choices()

    st.subheader({"dispatch": "Dispatch stock", "damage": "Record damage",
                  "recon": "Record a stock count"}[kind])
    n = st.session_state.get(f"{key}_n", 0)  # bumped after success => fresh empty form
    with st.form(f"{key}_form_{n}"):
        stock_label = st.selectbox("Stock item", list(choices.keys()), index=None,
                                   placeholder="Choose a stock item...", key=f"{key}_stock_{n}")
        if kind == "recon":
            qty_raw = st.text_input("Counted Quantity", key=f"{key}_qty_{n}")
            note = st.text_input("Note (optional)", key=f"{key}_note_{n}")
            apply_adj = st.checkbox("Update system quantity to match the count", value=True,
                                    key=f"{key}_apply_{n}")
        else:
            qty_raw = st.text_input("Quantity", key=f"{key}_qty_{n}")
            text_label = "Destination" if kind == "dispatch" else "Reason"
            text_val = st.text_input(text_label, key=f"{key}_text_{n}")
            d = st.date_input("Date", value=date.today(), key=f"{key}_date_{n}")
        submitted = st.form_submit_button("Save", type="primary")

    if submitted:
        try:
            if stock_label is None:
                raise ValueError("Please choose a stock item.")
            stock_id = choices[stock_label]
            if kind == "recon":
                counted = v_int(qty_raw, "Counted Quantity", 0)
                result = save_reconciliation(stock_id, counted, note.strip(), apply_adj)
                flash("success", f"Reconciliation recorded (ID {result[0]}). Difference: {result[1]:+d}.")
            else:
                qty = v_int(qty_raw, "Quantity", 1)
                text_val = v_required(text_val, text_label)
                new_id = save_movement(kind, stock_id, qty, text_val, d.isoformat())
                flash("success", ("Dispatched" if kind == "dispatch" else "Damage recorded")
                      + f" (ID {new_id}). Stock updated.")
        except ValueError as ve:
            st.error(str(ve))
            return
        except mysql.connector.Error as e:
            st.error(friendly_db_error(e))
            return
        st.session_state[f"{key}_n"] = n + 1
        st.rerun()

    st.subheader("Delete a record")
    note_txt = ("This will ADD the quantity back to stock." if kind != "recon"
                else "Reconciliation records are deleted without changing stock.")
    pk_value = row_picker(rows, "Row to delete", f"{key}_del_pick")
    st.caption(note_txt)
    if pk_value is not None and st.button(f"Confirm delete (ID {pk_value})", key=f"{key}_del_btn", type="primary"):
        try:
            delete_movement(table_name, meta["pk"], pk_value, restore_stock=(kind != "recon"))
        except ValueError as ve:
            st.error(str(ve))
            return
        except mysql.connector.Error as e:
            st.error(friendly_db_error(e))
            return
        flash("success", "Deleted." if kind == "recon" else "Deleted and stock restored.")
        st.rerun()


def save_movement(kind, stock_id, qty, text_val, date_str):
    table, pk, text_col, date_col = (
        ("dispatch", "dispatchID", "destination", "dispatchDate") if kind == "dispatch"
        else ("damagedStock", "damageID", "reason", "damageDate"))

    def _do(cur):
        cur.execute("SELECT quantity FROM stock WHERE stockID = %s FOR UPDATE", (stock_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("That stock item no longer exists.")
        available = row[0]
        if qty > available:
            what = "dispatch" if kind == "dispatch" else "mark as damaged"
            raise ValueError(f"Only {available} available -- can't {what} {qty}.")
        new_id = next_id(table, pk, cur)
        cur.execute("UPDATE stock SET quantity = quantity - %s WHERE stockID = %s", (qty, stock_id))
        cur.execute(f"INSERT INTO {table} ({pk}, stockID, quantity, {text_col}, {date_col}) "
                    "VALUES (%s,%s,%s,%s,%s)", (new_id, stock_id, qty, text_val, date_str))
        return new_id

    return with_transaction(_do)


def save_reconciliation(stock_id, counted_qty, note, apply_adjustment):
    def _do(cur):
        cur.execute("SELECT quantity FROM stock WHERE stockID = %s FOR UPDATE", (stock_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("That stock item no longer exists.")
        system_qty = row[0]
        difference = counted_qty - system_qty
        new_id = next_id("reconciliation", "reconID", cur)
        cur.execute("INSERT INTO reconciliation (reconID, stockID, systemQty, countedQty, difference, reconDate, note) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id, stock_id, system_qty, counted_qty, difference, date.today().isoformat(), note))
        if apply_adjustment:
            cur.execute("UPDATE stock SET quantity = %s WHERE stockID = %s", (counted_qty, stock_id))
        return new_id, difference

    return with_transaction(_do)


def delete_movement(table, pk_col, pk_value, restore_stock):
    def _do(cur):
        if restore_stock:
            cur.execute(f"SELECT stockID, quantity FROM {table} WHERE {pk_col} = %s", (pk_value,))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Record not found.")
            cur.execute("UPDATE stock SET quantity = quantity + %s WHERE stockID = %s", (row[1], row[0]))
        cur.execute(f"DELETE FROM {table} WHERE {pk_col} = %s", (pk_value,))

    with_transaction(_do)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
REPORTS = {
    "Stock by Warehouse": ("""
        SELECT w.warehouseName, SUM(s.quantity) AS total
        FROM stock s JOIN warehouse w ON s.warehouseID = w.warehouseID
        GROUP BY w.warehouseName""", ["Warehouse", "Total Quantity"]),
    "Stock by Product": ("""
        SELECT p.productName, SUM(s.quantity) AS total
        FROM stock s JOIN product p ON s.productID = p.productID
        GROUP BY p.productName""", ["Product", "Total Quantity"]),
    "Low Stock Alert (< 10)": ("""
        SELECT p.productName, w.warehouseName, s.quantity
        FROM stock s
        JOIN product p ON s.productID = p.productID
        JOIN warehouse w ON s.warehouseID = w.warehouseID
        WHERE s.quantity < 10 ORDER BY s.quantity""", ["Product", "Warehouse", "Quantity"]),
    "Damaged Goods Summary": ("""
        SELECT p.productName, SUM(d.quantity) AS total_damaged
        FROM damagedStock d
        JOIN stock s ON d.stockID = s.stockID
        JOIN product p ON s.productID = p.productID
        GROUP BY p.productName""", ["Product", "Total Damaged"]),
    "Reconciliation Discrepancies": ("""
        SELECT p.productName, w.warehouseName, r.systemQty, r.countedQty, r.difference, r.reconDate
        FROM reconciliation r
        JOIN stock s ON r.stockID = s.stockID
        JOIN product p ON s.productID = p.productID
        JOIN warehouse w ON s.warehouseID = w.warehouseID
        WHERE r.difference <> 0 ORDER BY r.reconDate DESC""",
        ["Product", "Warehouse", "System Qty", "Counted Qty", "Difference", "Date"]),
    "Pending Transfers": ("""
        SELECT t.transferID, wf.warehouseName, wt.warehouseName, t.transferData
        FROM transfer t
        JOIN warehouse wf ON t.from_warehouseID = wf.warehouseID
        JOIN warehouse wt ON t.to_warehouseID = wt.warehouseID
        WHERE t.status = 'Pending'""", ["Transfer ID", "From", "To", "Date"]),
}


def report_tab():
    name = st.selectbox("Report", list(REPORTS.keys()), key="report_pick")
    sql, cols = REPORTS[name]
    try:
        rows = run(sql, fetch=True) or []
    except mysql.connector.Error as e:
        st.error(friendly_db_error(e))
        return
    st.subheader(name)
    if not rows:
        st.info("(no rows)")
        return
    df = pd.DataFrame(rows, columns=cols)
    st.dataframe(df, width="stretch", hide_index=True)
    if name in ("Stock by Warehouse", "Stock by Product"):
        chart = df.set_index(cols[0])[cols[1]].astype(int)
        st.bar_chart(chart)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
def main():
    st.title("📦 Warehouse Management System")
    st.caption("Multi-Warehouse Stock Transfer Management System · DBMS PBL · Web version (Streamlit + MySQL)")

    try:
        conn().close()
    except mysql.connector.Error as e:
        st.error(f"Database connection problem: {friendly_db_error(e)}")
        st.stop()

    # Fixed slot for messages: keeps the page layout stable so the selected tab
    # is not reset after an action.
    with st.container():
        show_flash()

    tabs = st.tabs(["Warehouses", "Suppliers", "Products", "Stock", "Transfers",
                    "Transfer Details", "Dispatch", "Damage Entry", "Reconciliation", "Report"])

    with tabs[0]:
        crud_section("warehouse", "wh")
    with tabs[1]:
        crud_section("supplier", "sup")
    with tabs[2]:
        crud_section("product", "prod")
    with tabs[3]:
        crud_section("stock", "stock", extra={"📍 Put-away (Set Bin)": put_away_action})
    with tabs[4]:
        crud_section("transfer", "tr", status_guard=True,
                     extra={"✅ Confirm transfer": confirm_transfer_action})
    with tabs[5]:
        crud_section("transferDetails", "td")
    with tabs[6]:
        movement_section("dispatch", "disp", "dispatch")
    with tabs[7]:
        movement_section("damagedStock", "dmg", "damage")
    with tabs[8]:
        movement_section("reconciliation", "rec", "recon")
    with tabs[9]:
        report_tab()


main()
