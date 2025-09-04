# Powerplay Manager

Backend/web pro správu hokejového týmu – hráči, zápasy, statistiky a klubový portál.  
Postaveno na **Django 5.2** a **PostgreSQL 16** (DB lokálně přes Docker).  
Repo je připravené tak, aby si kdokoliv projekt stáhl a rovnou spustil.

---

## ✨ Funkce
- Evidence hráčů (fotky, kontakty, pozice), štábu a týmů
- Zápasy (liga / turnaj / přátelské), nominace, góly a tresty
- Statistiky hráčů (souhrny i per-game tabulky z `PlayerStats`)
- Veřejný web + interní portál (admin přes Django Admin + Jet Reboot)
- Management commandy pro demo data

---

## ⚙️ Požadavky
- Python 3.13
- Docker (kvůli PostgreSQL) – doporučeno  
  (alternativně nativní PostgreSQL 16+)
- pip + venv

Pozn.: `powerplay_manager/settings.py` je úmyslně ponechán beze změn (školní požadavek).  
Očekává DB na `127.0.0.1:5432` s názvem `powerplay_db`, uživatelem `postgres`, heslem `3133`.

---

## 🚀 Quick Start (bez úprav kódu)

### 0) Předpoklady
- Python 3.13
- Docker (nebo nativní PostgreSQL 16+)

### 1) Spusť databázi (Docker – doporučeno)
V kořeni repozitáře spusť:
    docker compose up -d db

Pokud Docker nemáš, viz níže „Alternativa bez Dockeru“.

### 2) Virtuální prostředí + závislosti
V kořeni repozitáře:
    python -m venv venvPowerPlay
    # Linux/macOS:
    source venvPowerPlay/bin/activate
    # Windows (PowerShell):
    # .\venvPowerPlay\Scripts\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt

### 3) Migrace + demo data
    python manage.py migrate
    # volitelné – naplní ukázkovými daty (týmy, hráči, zápasy…)
    python manage.py load_test_data
    # případně vytvoř admin účet:
    # python manage.py createsuperuser

### 4) Spusť aplikaci
    python manage.py runserver

Aplikace poběží na:
- Web: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

---

## 🐘 Alternativa bez Dockeru (nativní PostgreSQL)
Vytvoř uživatele a databázi (např. v psql jako superuser):
    CREATE USER postgres WITH PASSWORD '3133' SUPERUSER;
    CREATE DATABASE powerplay_db OWNER postgres;

Pak pokračuj od kroku 2) (venv + závislosti).

---

## 🗂️ Struktura projektu (zkráceně)
- powerplay_manager/ – Django projekt (settings, urls, wsgi/asgi)
- powerplay_app/ – hlavní aplikace (modely, admin, views, šablony, služby)
  - models/ – doménové modely (core, games, events, stats, …)
  - management/commands/ – load_test_data, clear_test_data, sync_results
  - site/ a portal/ – veřejná část a interní portál
  - static/, templates/ – statiky a šablony
  - tests/ – pytest testy
- media/ – ukázkové obrázky pro demo
- staticfiles/ – výstup pro collectstatic (v DEV není potřeba)
- docker-compose.yml – služba db (PostgreSQL 16)
- requirements.txt, requirements-dev.txt – závislosti

---

## 🔧 Užitečné příkazy
    # Naplnění demo dat
    python manage.py load_test_data

    # Vyčištění demo dat
    python manage.py clear_test_data

    # Synchronizace výsledků (pokud používáš)
    python manage.py sync_results

    # Vytvoření admin účtu
    python manage.py createsuperuser

---

## 🆘 Troubleshooting
- „connection refused“ na DB  
  Zkontroluj kontejner:
    docker compose ps
  Logy:
    docker compose logs db

- Port 5432 je obsazený  
  Zastav lokální PostgreSQL nebo uprav mapování portu v docker-compose.yml.

- Problém s psycopg2 bez Dockeru  
  Doinstaluj systémové balíčky (např. libpq-dev, postgresql) dle OS.

- Statické soubory v produkci  
  V DEV (DEBUG=True) není potřeba. V produkci:
    python manage.py collectstatic

---

## 📦 docker-compose.yml (DB služba)
V kořeni repozitáře měj soubor `docker-compose.yml` s obsahem:
    version: "3.8"
    services:
      db:
        image: postgres:16
        container_name: powerplay-postgres
        restart: unless-stopped
        environment:
          POSTGRES_DB: powerplay_db
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: "3133"
        ports:
          - "127.0.0.1:5432:5432"
        volumes:
          - pgdata:/var/lib/postgresql/data
    volumes:
      pgdata:

Pozn.: Django běží lokálně přes `runserver` (port 8000). V Dockeru je pouze databáze – jednodušší vývoj bez mountování kódu.

---

## 🔐 Poznámka k nastavení
`powerplay_manager/settings.py` zůstává přesně tak, jak je v repu (školní požadavek):  
`DEBUG=True`, `ALLOWED_HOSTS=[]`, pevný `SECRET_KEY` a DB přihlašovací údaje dle výše.

---

## 🤝 Contributing
PR jsou vítány. Před větší změnou prosím otevři issue k diskuzi.

---

## 📄 Licence
MIT
