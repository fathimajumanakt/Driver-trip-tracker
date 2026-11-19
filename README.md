# Driver Trip & Salary Tracker

## Run on Windows

1. Install Python.
2. Open PowerShell in this folder.
3. Install packages:

   ```powershell
   py -m pip install -r requirements.txt
   ```

4. Start the app:

   ```powershell
   py -m streamlit run app.py
   ```

5. Open the local address Streamlit displays (usually http://localhost:8501).

## First login

- Username: `admin`
- Password: `admin12345`

Change the admin password immediately from the Password tab.

## Workflow

1. Log in as admin and create driver accounts.
2. Set the company's confirmed rate per kilometre, night bata and allowance.
3. Give each driver their username and temporary password.
4. Drivers log in from their phones/computers and add one completed trip after each journey.
5. Admin reviews company trip records and enters monthly advances, deductions, extra allowances and salary payments.
6. Drivers can see their own monthly summary and download trip CSV data.

## Important calculation rules

- KM earnings = total recorded KM × company rate per KM.
- Night bata = eligible night count × night bata rate.
- Net salary = KM earnings + night bata + allowances − advance − deductions.
- Cash and Credit are client payment categories, not driver salary.
- Toll, parking, fuel and other trip expenses are tracked separately and are not automatically added to salary.
- This starter version does not decide the company's actual rates or legal payroll rules. Admin must enter the confirmed company policy.

## Data and deployment

The app creates `driver_tracker.db` in the same folder. Keep this file backed up.
This is a starter prototype, not a production-hardened payroll platform. A local SQLite database is suitable for local testing, but not for multiple remote drivers accessing separate copies of the app. For internet deployment, use one shared hosted database, HTTPS, secure secret management, database backups, and production-grade authentication/access controls.
