# TDT4225 Exercise 3

Python and MongoDB implementation of Exercise 3.

## Setup

Requires Python 3.12 and Docker.

Create a virtual environment and install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the database passwords.

Start MongoDB:

```powershell
docker compose up -d
```

Download `The Movies Dataset`:

```powershell
python download_data.py
```

## Part 1

Run the exploratory data analysis:

```powershell
python eda.py
```

Create the database collections, clean the data, and import it:

```powershell
python load_data.py
```

## Part 2

Run the analytical queries:

```powershell
python queries.py
```
