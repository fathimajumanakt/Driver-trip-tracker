# 🚗 Driver Trip & Salary Tracker

A web-based application developed using Python and Streamlit to manage company drivers' daily trips, travel expenses, payments and monthly salary calculations.

The application uses Supabase as its cloud database to store and manage driver trip records securely.

##  Project Overview

Managing daily driver trips, expenses and salary calculations manually can be time-consuming.

The Driver Trip & Salary Tracker simplifies this process by providing a centralized platform to record trips, monitor expenses, track payments and calculate monthly driver earnings.

##  Key Features

- **Driver Management:** Manage driver information and records.
- **Daily Trip Tracking:** Record daily trips, travel dates, destinations and kilometres travelled.
- **Expense Management:** Track toll charges and parking expenses.
- **Payment Tracking:** Differentiate between Cash and Credit payments.
- **Night Bata:** Record additional allowances for night travel.
- **Monthly Salary Calculation:** Track driver earnings and monthly adjustments.
- **Edit & Delete Records:** Update or remove incorrect trip entries.
- **Cloud Database:** Store and retrieve records using Supabase.
- **Data Persistence:** Access saved records even after restarting the application.

##  Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Streamlit | Web application development |
| Supabase | Cloud database and data storage |
| PostgreSQL | Database management |
| Pandas | Data manipulation and processing |

##  Database Structure

The application uses Supabase with the following tables:

- `users` – User information and authentication-related data.
- `trips` – Daily driver trip records.
- `monthly_adjustments` – Monthly salary adjustments.
- `settings` – Application settings.

##  Project Structure

```text
Driver-Trip-Tracker/
│
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
```

##  Installation & Setup

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Navigate to the Project Folder

```bash
cd Driver-Trip-Tracker
```

### 3. Install Dependencies

```bash
py -m pip install -r requirements.txt
```

### 4. Configure Supabase

- Create a project in Supabase.
- Configure the required database tables.
- Add your Supabase project URL and API key to your application's environment or Streamlit secrets configuration.
- Make sure the configuration matches the variable names used in `app.py`.

**Important:** Never upload your Supabase secret keys, passwords or private credentials to GitHub.

### 5. Run the Application

```bash
py -m streamlit run app.py
```

The application will open in your browser at:

```text
http://localhost:8501
```

##  Deployment

The application can be deployed using Streamlit Community Cloud.

Supabase is used as the cloud database, allowing trip records to remain stored independently of the Streamlit application.

##  Project Objective

The main objective of this project is to simplify driver trip management, reduce manual record-keeping and improve the accuracy of expense and salary calculations.

##  Developed By

**Fathima Jumana**




