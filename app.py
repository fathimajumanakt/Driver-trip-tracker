import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError
import hashlib
from datetime import date, datetime
import pandas as pd
import re
from contextlib import contextmanager

# ---------------- CONFIGURATION ----------------

st.set_page_config(
    page_title="Driver Trip & Salary Management System",
    page_icon="🚗",
    layout="wide"
)


# ---------------- DATABASE ----------------
# Reads connection details from .streamlit/secrets.toml locally
# and from Streamlit Community Cloud > App settings > Secrets online.

@contextmanager
def db():
    conn = psycopg2.connect(
        host=st.secrets["SUPABASE_HOST"],
        port=int(st.secrets.get("SUPABASE_PORT", 5432)),
        dbname=st.secrets.get("SUPABASE_DATABASE", "postgres"),
        user=st.secrets["SUPABASE_USER"],
        password=st.secrets["SUPABASE_PASSWORD"],
        sslmode="require",
        connect_timeout=15,
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_df(sql, params=None):
    """Run a SELECT query and return a pandas DataFrame."""
    with db() as con:
        with con.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return pd.DataFrame([dict(row) for row in rows])


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password, stored_hash):
    return hash_password(password) == stored_hash


def init_db():
    # The four tables have already been created in the Supabase SQL Editor.
    # This only ensures the settings row and initial admin account exist.
    with db() as con:
        with con.cursor() as cur:
            cur.execute("""
                INSERT INTO settings (id)
                VALUES (1)
                ON CONFLICT (id) DO NOTHING
            """)
            cur.execute("""
                INSERT INTO users
                    (username, full_name, password_hash, role, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
            """, (
                "admin",
                "Company Admin",
                hash_password("admin12345"),
                "admin",
                1,
                datetime.now().isoformat()
            ))


try:
    init_db()
except Exception as e:
    st.error("Could not connect to the online database. Check your Supabase secrets and database tables.")
    st.caption(str(e))
    st.stop()


# ---------------- COMMON FUNCTIONS ----------------

def money(value):
    return f"₹{float(value or 0):,.2f}"


def get_settings():
    with db() as con:
        with con.cursor() as cur:
            cur.execute("SELECT * FROM settings WHERE id=1")
            row = cur.fetchone()
    return dict(row) if row else {
        "rate_per_km": 0,
        "night_bata_rate": 0,
        "other_allowance": 0,
        "currency": "INR"
    }


def get_user_by_username(username):
    with db() as con:
        with con.cursor() as cur:
            cur.execute("""
                SELECT * FROM users
                WHERE username=%s AND active=1
            """, (username,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_trips(month, driver_id=None):
    query = """
        SELECT t.*, u.full_name AS driver_name, u.username
        FROM trips t
        JOIN users u ON u.id=t.driver_id
        WHERE substring(t.trip_date,1,7)=%s
    """
    params = [month]
    if driver_id is not None:
        query += " AND t.driver_id=%s"
        params.append(int(driver_id))
    query += " ORDER BY t.trip_date DESC, t.id DESC"
    return query_df(query, tuple(params))


def get_adjustment(driver_id, month):
    with db() as con:
        with con.cursor() as cur:
            cur.execute("""
                SELECT * FROM monthly_adjustments
                WHERE driver_id=%s AND month=%s
            """, (int(driver_id), month))
            row = cur.fetchone()
    if row:
        return dict(row)
    return {
        "advance": 0,
        "deductions": 0,
        "extra_allowance": 0,
        "paid_amount": 0,
        "notes": ""
    }


# ---------------- SALARY CALCULATION ----------------

def calc_summary(trips, settings, adjustment):
    if trips.empty:
        km = days = nights = trips_count = 0
        cash = credit = 0
        toll = parking = fuel = other_exp = 0
    else:
        km = trips["total_km"].sum()
        days = trips["travel_days"].sum()
        nights = trips["night_count"].sum()
        trips_count = len(trips)
        cash = trips.loc[trips.payment_type == "Cash", "client_amount"].sum()
        credit = trips.loc[trips.payment_type == "Credit", "client_amount"].sum()
        toll = trips["toll"].sum()
        parking = trips["parking"].sum()
        fuel = trips["fuel"].sum()
        other_exp = trips["other_expenses"].sum()

    km_earnings = km * float(settings["rate_per_km"])
    night_pay = nights * float(settings["night_bata_rate"])
    allowances = float(settings["other_allowance"]) + float(adjustment["extra_allowance"])
    gross = km_earnings + night_pay + allowances
    net = gross - float(adjustment["advance"]) - float(adjustment["deductions"])
    balance = net - float(adjustment["paid_amount"])
    reimbursable = toll + parking + fuel + other_exp

    return {
        "trips": trips_count, "km": km, "days": days, "nights": nights,
        "cash": cash, "credit": credit, "toll": toll, "parking": parking,
        "fuel": fuel, "other_exp": other_exp, "km_earnings": km_earnings,
        "night_pay": night_pay, "allowances": allowances, "gross": gross,
        "advance": adjustment["advance"], "deductions": adjustment["deductions"],
        "net": net, "paid": adjustment["paid_amount"], "balance": balance,
        "reimbursable": reimbursable
    }


# ---------------- LOGIN ----------------

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🚗 Driver Trip & Salary Management System")
st.caption(
    "Record completed trips, client payments, "
    "travel expenses and monthly driver earnings."
)

if st.session_state.user is None:
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        user = get_user_by_username(username.strip())
        if user and verify_password(password, user["password_hash"]):
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.info(
        "First-time admin login: Username: admin | Password: admin12345. "
        "Change this password immediately."
    )
    st.stop()

user = st.session_state.user


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.write(f"**Logged in:** {user['full_name']}")
    st.write(f"**Role:** {user['role'].title()}")
    if st.button("Log out", use_container_width=True):
        st.session_state.user = None
        st.rerun()
    st.divider()


# ---------------- CHANGE PASSWORD ----------------

def change_password_ui():
    st.subheader("Change Password")
    with st.form("change_password"):
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        go = st.form_submit_button("Update password")

    if go:
        if not verify_password(old, user["password_hash"]):
            st.error("Current password is incorrect.")
        elif len(new) < 8:
            st.error("Use at least 8 characters.")
        elif new != confirm:
            st.error("Passwords do not match.")
        else:
            new_hash = hash_password(new)
            with db() as con:
                with con.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET password_hash=%s WHERE id=%s",
                        (new_hash, int(user["id"]))
                    )
            user["password_hash"] = new_hash
            st.session_state.user = user
            st.success("Password updated successfully.")


# ---------------- ADD TRIP ----------------

def trip_entry(driver_id):
    st.subheader("Add a Completed Trip")
    st.caption("Enter one record after the journey is finished.")

    with st.form("trip_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        trip_date = c1.date_input("Travel date", value=date.today())
        start_place = c2.text_input("Starting place")
        destination = c3.text_input("Destination")
        visited = st.text_area("Other places visited")

        c1, c2, c3 = st.columns(3)
        start_km = c1.number_input("Starting KM", min_value=0.0, step=1.0)
        end_km = c2.number_input("Ending KM", min_value=0.0, step=1.0)
        c3.metric("Total KM", f"{max(0, end_km-start_km):,.1f}")

        c1, c2, c3 = st.columns(3)
        travel_days = c1.number_input("Travel days", min_value=1, value=1)
        night_drive = c2.selectbox("Night drive?", ["No", "Yes"])
        night_count = c3.number_input("Eligible nights", min_value=0, value=0)

        st.markdown("**Client Payment**")
        c1, c2, c3 = st.columns(3)
        client_name = c1.text_input("Client name")
        payment_type = c2.selectbox("Payment type", ["Not recorded", "Cash", "Credit"])
        client_amount = c3.number_input("Client amount (₹)", min_value=0.0, step=100.0)

        st.markdown("**Trip Expenses (₹)**")
        c1, c2, c3, c4 = st.columns(4)
        toll = c1.number_input("Toll", min_value=0.0, step=10.0)
        parking = c2.number_input("Parking", min_value=0.0, step=10.0)
        fuel = c3.number_input("Fuel", min_value=0.0, step=50.0)
        other_exp = c4.number_input("Other expenses", min_value=0.0, step=10.0)
        notes = st.text_area("Notes")
        save = st.form_submit_button("Save Trip", use_container_width=True)

    if save:
        if not start_place.strip() or not destination.strip():
            st.error("Enter starting place and destination.")
        elif end_km < start_km:
            st.error("Ending KM cannot be less than starting KM.")
        elif night_drive == "No" and night_count > 0:
            st.error("Select Yes for night drive or set nights to zero.")
        elif night_drive == "Yes" and night_count < 1:
            st.error("Enter at least one eligible night.")
        elif payment_type == "Not recorded" and client_amount > 0:
            st.error("Choose Cash or Credit for the client amount.")
        else:
            with db() as con:
                with con.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trips(
                            driver_id, trip_date, start_place, destination,
                            visited_places, start_km, end_km, total_km,
                            travel_days, night_drive, night_count, client_name,
                            payment_type, client_amount, toll, parking, fuel,
                            other_expenses, notes, created_at
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        int(driver_id), trip_date.isoformat(), start_place.strip(),
                        destination.strip(), visited.strip(), start_km, end_km,
                        end_km-start_km, int(travel_days),
                        1 if night_drive == "Yes" else 0, int(night_count),
                        client_name.strip(), payment_type, client_amount, toll,
                        parking, fuel, other_exp, notes.strip(),
                        datetime.now().isoformat()
                    ))
            st.success("Trip saved successfully!")
            st.rerun()


# ---------------- EDIT / DELETE TRIPS ----------------

def manage_trips(month, driver_id=None):
    trips = get_trips(month, driver_id)
    if trips.empty:
        st.info("No trips found for this month.")
        return

    display_cols = [
        "trip_date", "driver_name", "start_place", "destination",
        "total_km", "travel_days", "night_count", "payment_type",
        "client_amount", "toll", "parking", "fuel", "other_expenses"
    ]
    st.dataframe(trips[display_cols], use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("Edit or Delete Trip")

    trip_ids = trips["id"].astype(int).tolist()
    selected_id = st.selectbox(
        "Select trip",
        trip_ids,
        format_func=lambda x: (
            f"{trips.loc[trips.id == x, 'driver_name'].iloc[0]} | "
            f"{trips.loc[trips.id == x, 'trip_date'].iloc[0]} | "
            f"{trips.loc[trips.id == x, 'start_place'].iloc[0]} to "
            f"{trips.loc[trips.id == x, 'destination'].iloc[0]}"
        )
    )
    selected = trips[trips["id"] == selected_id].iloc[0]
    st.markdown("### Edit Trip Details")

    with st.form("edit_trip_form"):
        c1, c2, c3 = st.columns(3)
        edit_date = c1.date_input("Travel date", value=pd.to_datetime(selected["trip_date"]).date())
        edit_start = c2.text_input("Starting place", value=str(selected["start_place"]))
        edit_destination = c3.text_input("Destination", value=str(selected["destination"]))
        edit_visited = st.text_area("Other places visited", value=str(selected["visited_places"] or ""))

        c1, c2, c3 = st.columns(3)
        edit_start_km = c1.number_input("Starting KM", min_value=0.0, value=float(selected["start_km"]))
        edit_end_km = c2.number_input("Ending KM", min_value=0.0, value=float(selected["end_km"]))
        c3.metric("Total KM", f"{max(0, edit_end_km-edit_start_km):,.1f}")

        c1, c2, c3 = st.columns(3)
        edit_days = c1.number_input("Travel days", min_value=1, value=int(selected["travel_days"]))
        edit_night = c2.selectbox("Night drive?", ["No", "Yes"], index=int(selected["night_drive"]))
        edit_nights = c3.number_input("Eligible nights", min_value=0, value=int(selected["night_count"]))

        st.markdown("**Client Payment**")
        c1, c2, c3 = st.columns(3)
        edit_client = c1.text_input("Client name", value=str(selected["client_name"] or ""))
        payment_options = ["Not recorded", "Cash", "Credit"]
        current_payment = selected["payment_type"]
        if current_payment not in payment_options:
            current_payment = "Not recorded"
        edit_payment = c2.selectbox("Payment type", payment_options, index=payment_options.index(current_payment))
        edit_amount = c3.number_input("Client amount (₹)", min_value=0.0, value=float(selected["client_amount"]))

        st.markdown("**Trip Expenses (₹)**")
        c1, c2, c3, c4 = st.columns(4)
        edit_toll = c1.number_input("Toll", min_value=0.0, value=float(selected["toll"]))
        edit_parking = c2.number_input("Parking", min_value=0.0, value=float(selected["parking"]))
        edit_fuel = c3.number_input("Fuel", min_value=0.0, value=float(selected["fuel"]))
        edit_other = c4.number_input("Other expenses", min_value=0.0, value=float(selected["other_expenses"]))
        edit_notes = st.text_area("Notes", value=str(selected["notes"] or ""))
        update = st.form_submit_button("Save Changes", use_container_width=True)

    if update:
        if not edit_start.strip() or not edit_destination.strip():
            st.error("Starting place and destination are required.")
        elif edit_end_km < edit_start_km:
            st.error("Ending KM cannot be less than starting KM.")
        elif edit_night == "No" and edit_nights > 0:
            st.error("Select Yes for night drive or set nights to zero.")
        elif edit_night == "Yes" and edit_nights < 1:
            st.error("Enter at least one eligible night.")
        elif edit_payment == "Not recorded" and edit_amount > 0:
            st.error("Choose Cash or Credit.")
        else:
            sql = """
                UPDATE trips SET
                    trip_date=%s, start_place=%s, destination=%s,
                    visited_places=%s, start_km=%s, end_km=%s,
                    total_km=%s, travel_days=%s, night_drive=%s,
                    night_count=%s, client_name=%s, payment_type=%s,
                    client_amount=%s, toll=%s, parking=%s, fuel=%s,
                    other_expenses=%s, notes=%s
                WHERE id=%s
            """
            params = (
                edit_date.isoformat(), edit_start.strip(), edit_destination.strip(),
                edit_visited.strip(), edit_start_km, edit_end_km,
                edit_end_km-edit_start_km, int(edit_days),
                1 if edit_night == "Yes" else 0, int(edit_nights),
                edit_client.strip(), edit_payment, edit_amount, edit_toll,
                edit_parking, edit_fuel, edit_other, edit_notes.strip(),
                int(selected_id)
            )
            if driver_id is not None:
                sql += " AND driver_id=%s"
                params += (int(driver_id),)
            with db() as con:
                with con.cursor() as cur:
                    cur.execute(sql, params)
            st.success("Trip updated successfully!")
            st.rerun()

    st.divider()
    st.subheader("Delete Trip")
    confirm_delete = st.checkbox(
        "I confirm that I want to delete this trip.",
        key=f"confirm_delete_{selected_id}"
    )
    if st.button("Delete Selected Trip", disabled=not confirm_delete, type="primary", use_container_width=True):
        sql = "DELETE FROM trips WHERE id=%s"
        params = (int(selected_id),)
        if driver_id is not None:
            sql += " AND driver_id=%s"
            params += (int(driver_id),)
        with db() as con:
            with con.cursor() as cur:
                cur.execute(sql, params)
        st.success("Trip deleted successfully!")
        st.rerun()


# ---------------- SALARY VIEW ----------------

def salary_view(driver_id, month):
    settings = get_settings()
    trips = get_trips(month, driver_id)
    adjustment = get_adjustment(driver_id, month)
    s = calc_summary(trips, settings, adjustment)

    st.subheader(f"Monthly Summary — {month}")
    cols = st.columns(4)
    cols[0].metric("Total KM", f"{s['km']:,.1f}")
    cols[1].metric("Trips", int(s["trips"]))
    cols[2].metric("Travel Days", int(s["days"]))
    cols[3].metric("Night Count", int(s["nights"]))

    cols = st.columns(4)
    cols[0].metric("Cash Collected", money(s["cash"]))
    cols[1].metric("Credit to Company", money(s["credit"]))
    cols[2].metric("Trip Expenses", money(s["reimbursable"]))
    cols[3].metric("Night Bata", money(s["night_pay"]))

    st.markdown("### Salary Calculation")
    salary_df = pd.DataFrame([
        ["KM Earnings", s["km_earnings"]],
        ["Night Bata", s["night_pay"]],
        ["Allowances", s["allowances"]],
        ["Gross Earnings", s["gross"]],
        ["Advance", -s["advance"]],
        ["Deductions", -s["deductions"]],
        ["Net Salary", s["net"]],
        ["Already Paid", -s["paid"]],
        ["Remaining Salary Balance", s["balance"]]
    ], columns=["Description", "Amount (₹)"])
    st.dataframe(salary_df, use_container_width=True, hide_index=True)
    st.caption(
        "Cash and credit are client payment records, not driver salary. "
        "Trip expenses are shown separately."
    )
    st.markdown("### Trip Records")
    if not trips.empty:
        st.dataframe(trips, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Trip Report",
            trips.to_csv(index=False).encode("utf-8-sig"),
            f"trips_{driver_id}_{month}.csv",
            "text/csv"
        )
    else:
        st.info("No trips recorded for this month.")
    return s, trips


# =====================================================
# DRIVER PAGES
# =====================================================

if user["role"] == "driver":
    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Add Trip", "📋 My Trips", "💰 Monthly Salary", "🔐 Password"
    ])
    with tab1:
        trip_entry(user["id"])
    with tab2:
        month = st.selectbox(
            "Select Month",
            pd.period_range(end=pd.Timestamp.today(), periods=18, freq="M").astype(str)[::-1],
            key="driver_trip_month"
        )
        manage_trips(month, driver_id=user["id"])
    with tab3:
        month = st.selectbox(
            "Salary Month",
            pd.period_range(end=pd.Timestamp.today(), periods=18, freq="M").astype(str)[::-1],
            key="driver_salary_month"
        )
        salary_view(user["id"], month)
    with tab4:
        change_password_ui()


# =====================================================
# ADMIN PAGES
# =====================================================

else:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Company Dashboard", "👥 Drivers", "⚙️ Salary Settings",
        "🧾 Monthly Adjustments", "✏️ Manage Trips", "🔐 Password"
    ])

    # ---------------- DASHBOARD ----------------
    with tab1:
        month = st.selectbox(
            "Report Month",
            pd.period_range(end=pd.Timestamp.today(), periods=18, freq="M").astype(str)[::-1],
            key="admin_dashboard_month"
        )
        all_trips = get_trips(month)
        if all_trips.empty:
            st.info("No trips recorded for this month.")
        else:
            total_km = all_trips.total_km.sum()
            total_cash = all_trips.loc[all_trips.payment_type == "Cash", "client_amount"].sum()
            total_credit = all_trips.loc[all_trips.payment_type == "Credit", "client_amount"].sum()
            total_exp = all_trips[["toll", "parking", "fuel", "other_expenses"]].sum().sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total KM", f"{total_km:,.1f}")
            c2.metric("Total Trips", len(all_trips))
            c3.metric("Cash Collected", money(total_cash))
            c4.metric("Credit to Company", money(total_credit))

            c1, c2, c3 = st.columns(3)
            c1.metric("Travel Days", int(all_trips.travel_days.sum()))
            c2.metric("Night Count", int(all_trips.night_count.sum()))
            c3.metric("Recorded Expenses", money(total_exp))

            st.markdown("### Driver-wise Kilometres")
            by_driver = all_trips.groupby("driver_name", as_index=False).agg(
                total_km=("total_km", "sum"),
                trips=("id", "count"),
                days=("travel_days", "sum")
            )
            st.bar_chart(by_driver.set_index("driver_name")["total_km"])
            st.dataframe(by_driver, use_container_width=True, hide_index=True)

            st.markdown("### All Trip Records")
            st.dataframe(all_trips, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Company Trip Report",
                all_trips.to_csv(index=False).encode("utf-8-sig"),
                f"company_trips_{month}.csv",
                "text/csv"
            )

        st.markdown("### Driver Salary Overview")
        drivers = query_df("""
            SELECT id, full_name, username
            FROM users
            WHERE role='driver' AND active=1
        """)
        if not drivers.empty:
            settings = get_settings()
            rows = []
            for _, d in drivers.iterrows():
                t = get_trips(month, int(d.id))
                a = get_adjustment(int(d.id), month)
                sm = calc_summary(t, settings, a)
                rows.append({
                    "Driver": d.full_name,
                    "KM": sm["km"],
                    "Trips": sm["trips"],
                    "Gross Salary": sm["gross"],
                    "Net Salary": sm["net"],
                    "Paid": sm["paid"],
                    "Balance": sm["balance"]
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ---------------- DRIVER MANAGEMENT ----------------
    with tab2:
        st.subheader("Add Driver Account")
        with st.form("add_driver"):
            full_name = st.text_input("Driver Full Name")
            username = st.text_input("Username")
            temp_password = st.text_input("Temporary Password", type="password")
            add = st.form_submit_button("Create Driver")

        if add:
            if not full_name.strip() or not username.strip():
                st.error("Name and username are required.")
            elif len(temp_password) < 8:
                st.error("Password must contain at least 8 characters.")
            else:
                try:
                    with db() as con:
                        with con.cursor() as cur:
                            cur.execute("""
                                INSERT INTO users(
                                    username, full_name, password_hash, role, active, created_at
                                )
                                VALUES(%s,%s,%s,%s,%s,%s)
                            """, (
                                username.strip(), full_name.strip(),
                                hash_password(temp_password), "driver", 1,
                                datetime.now().isoformat()
                            ))
                    st.success("Driver account created successfully.")
                except IntegrityError:
                    st.error("Username already exists.")

        st.divider()
        st.subheader("Driver Accounts")
        drivers = query_df("""
            SELECT id, full_name, username, active, created_at
            FROM users
            WHERE role='driver'
            ORDER BY full_name
        """)
        if not drivers.empty:
            st.dataframe(drivers, use_container_width=True, hide_index=True)
            selected_driver = st.selectbox(
                "Select Driver",
                drivers.id.tolist(),
                format_func=lambda x: drivers.loc[drivers.id == x, "full_name"].iloc[0]
            )
            active_choice = st.radio("Account Status", ["Active", "Inactive"], horizontal=True)
            if st.button("Update Driver Status"):
                with db() as con:
                    with con.cursor() as cur:
                        cur.execute(
                            "UPDATE users SET active=%s WHERE id=%s",
                            (1 if active_choice == "Active" else 0, int(selected_driver))
                        )
                st.success("Driver status updated.")
                st.rerun()

    # ---------------- SALARY SETTINGS ----------------
    with tab3:
        st.subheader("Company Salary Rules")
        settings = get_settings()
        with st.form("salary_settings"):
            rate = st.number_input(
                "Payment Rate per KM (₹)", min_value=0.0,
                value=float(settings["rate_per_km"]), step=0.5
            )
            night_rate = st.number_input(
                "Night Bata per Night (₹)", min_value=0.0,
                value=float(settings["night_bata_rate"]), step=50.0
            )
            allowance = st.number_input(
                "Standard Monthly Allowance (₹)", min_value=0.0,
                value=float(settings["other_allowance"]), step=100.0
            )
            save_settings = st.form_submit_button("Save Salary Settings")

        if save_settings:
            with db() as con:
                with con.cursor() as cur:
                    cur.execute("""
                        UPDATE settings
                        SET rate_per_km=%s, night_bata_rate=%s, other_allowance=%s
                        WHERE id=1
                    """, (rate, night_rate, allowance))
            st.success("Salary settings saved.")
        st.warning("Enter the actual company rates after confirming them.")

    # ---------------- MONTHLY ADJUSTMENTS ----------------
    with tab4:
        st.subheader("Monthly Advances, Deductions and Payments")
        drivers = query_df("""
            SELECT id, full_name
            FROM users
            WHERE role='driver' AND active=1
            ORDER BY full_name
        """)
        if drivers.empty:
            st.info("Create a driver account first.")
        else:
            with st.form("monthly_adjustment"):
                driver_id = st.selectbox(
                    "Driver",
                    drivers.id.tolist(),
                    format_func=lambda x: drivers.loc[drivers.id == x, "full_name"].iloc[0]
                )
                month = st.text_input("Month (YYYY-MM)", value=date.today().strftime("%Y-%m"))
                advance = st.number_input("Advance Paid (₹)", min_value=0.0)
                deductions = st.number_input("Other Deductions (₹)", min_value=0.0)
                extra_allowance = st.number_input("Extra Allowance (₹)", min_value=0.0)
                paid_amount = st.number_input("Salary Already Paid (₹)", min_value=0.0)
                notes = st.text_area("Notes")
                save_adj = st.form_submit_button("Save Monthly Adjustment")

            if save_adj:
                try:
                    datetime.strptime(month, "%Y-%m")
                    with db() as con:
                        with con.cursor() as cur:
                            cur.execute("""
                                INSERT INTO monthly_adjustments(
                                    driver_id, month, advance, deductions,
                                    extra_allowance, paid_amount, notes
                                )
                                VALUES(%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT(driver_id, month)
                                DO UPDATE SET
                                    advance=EXCLUDED.advance,
                                    deductions=EXCLUDED.deductions,
                                    extra_allowance=EXCLUDED.extra_allowance,
                                    paid_amount=EXCLUDED.paid_amount,
                                    notes=EXCLUDED.notes
                            """, (
                                int(driver_id), month, advance, deductions,
                                extra_allowance, paid_amount, notes
                            ))
                    st.success("Monthly adjustment saved.")
                except ValueError:
                    st.error("Enter month in YYYY-MM format.")

    # ---------------- ADMIN TRIP MANAGEMENT ----------------
    with tab5:
        st.subheader("Manage All Driver Trips")
        month = st.selectbox(
            "Select Month",
            pd.period_range(end=pd.Timestamp.today(), periods=18, freq="M").astype(str)[::-1],
            key="admin_manage_month"
        )
        manage_trips(month)

    # ---------------- ADMIN PASSWORD ----------------
    with tab6:
        change_password_ui()


# ---------------- FOOTER ----------------

st.divider()
st.caption("Driver Trip & Salary Management System | Online database powered by Supabase.")
