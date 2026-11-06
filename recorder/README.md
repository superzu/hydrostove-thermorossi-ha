# Registratore registri WiNet

Piccola app web (Python/Flask) per **mappare i registri della tua stufa**: legge il modulo WiNet in sola lettura,
salva in MySQL/MariaDB solo i valori che cambiano e offre una pagina per:

- dichiarare cosa mostra il display (stato, potenza, temperature), salvato con la foto di tutti i registri;
- dare un nome ai registri e un significato ai valori (es. fase 3 = "WORK");
- annotare le azioni fatte sulla stufa;
- confrontare, se vuoi, i registri con le risposte del cloud Thermorossi (`GetStatus`, `GetPower`).

L'interfaccia è in italiano.

## Installazione

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env      # imposta STUFA_URL e i dati del database
venv/bin/python app.py    # poi apri http://<server>:8095
```
Le tabelle vengono create al primo avvio (`schema.sql` è solo di riferimento).
Avvia **un solo processo** e tieni la pagina raggiungibile solo dalla rete locale: non ha autenticazione.

### Avvio come servizio (systemd)

```ini
[Unit]
Description=Registratore idrostufa WiNet
After=network-online.target

[Service]
WorkingDirectory=/percorso/recorder
ExecStart=/percorso/recorder/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Query utili

Cosa è cambiato dopo ogni annotazione:
```sql
SELECT e.ts AS evento, e.testo, r.ts, r.cat, r.reg, r.valore
FROM eventi e
JOIN registri r ON r.ts BETWEEN e.ts - INTERVAL 10 SECOND AND e.ts + INTERVAL 2 MINUTE
ORDER BY e.ts DESC, r.ts LIMIT 300;
```
I timestamp sono in UTC.
