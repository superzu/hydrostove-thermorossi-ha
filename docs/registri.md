# Mappa dei registri — Thermorossi IDRA 21 (WiNet 0.81)

Verificata osservando la stufa reale e confrontando con display, app e API cloud Thermorossi.
Altri modelli potrebbero differire: verifica prima di scrivere.

## API locale del modulo WiNet

Lettura:
```
POST http://<modulo>/ajax/get-registers
Content-Type: application/x-www-form-urlencoded

key=020&category=1
```
Risposta: `{"key":20, "rssi":-64, "cat":1, "registers":[[reg, valore], ...], ...}`

Scrittura:
```
POST http://<modulo>/ajax/set-register
Content-Type: application/x-www-form-urlencoded

key=002&memory=1&regId=<registro>&value=<valore>
```
Risposta: `{"result":true}`

## Categoria 1

| Reg. | Significato | Codifica | Scrivibile | Verifica |
|---|---|---|---|---|
| 6 | Stato | parte bassa (`v % 256`) = fase; bit 256 = pompa; bit 2048 = Auto (probabile) | no | ✔ |
| 12 | Potenza | 0 spenta, 1–4 potenza, 5 Auto | **sì** | ✔ (Auto in scrittura da confermare) |
| 18 | Temperatura acqua | °C | no | ✔ |
| 21 | Temperatura fumi | °C | no | ✔ per andamento (non visibile sul display) |
| 22 | Orologio stufa | `giorno*2048 + ore*64 + minuti`, giorno 0 = lunedì (display 1–7) | — | ✔ |
| 112 | Temperatura target acqua | °C, range 65–73 | **sì** | ✔ |
| 0 | Contatore eventi/comandi | `0x8000 + n`, si azzera togliendo corrente | no | ✔ |
| 1 | Valore momentaneo durante comandi o test pompa | — | no | da chiarire |
| 7 | Segnali a bit | 128 durante START e WORK, 0 da spenta | no | parziale |
| 23 | Segnale momentaneo dopo una modifica | — | no | da chiarire |
| 3, 15 | Costanti (8198, 160) | configurazione | no | — |

### Fasi (registro 6, parte bassa)

| Valore | Fase (cloud) | Note |
|---|---|---|
| 1 | OFF | comprende anche la procedura di spegnimento/raffreddamento |
| 2 | START | accensione, a potenza 1 |
| 3 | WORK | fiamma in lavoro |

Da individuare: stati di allarme/blocco, eventuale modulazione/standby a temperatura raggiunta.

### Comportamenti osservati

- **Accensione / spegnimento**: scrivere il registro 12 (0 = spegni, 1–5 = accendi a quella potenza), come il tasto
  del pannello che cicla 1, 2, 3, 4, Auto, 0. La stufa non memorizza la potenza: da spenta vale 0.
- **Pompa** (bit 256 del registro 6): termostatica sull'acqua, si accende a circa 61 °C e si spegne a circa 57 °C,
  anche a stufa spenta (calore residuo).
- **Spegnimento**: la fase passa subito a 1; i fumi salgono per circa 30 s (picco), poi scendono in modo regolare
  (~17 minuti per scendere sotto 60 °C nel caso osservato).
- **Cloud Thermorossi**: `GetStatus` restituisce il registro 6 grezzo (es. 259) e ha una descrizione solo per i valori
  senza bit alti; `GetPower` corrisponde al registro 12.
- **Orologio**: sopravvive al taglio di corrente; non si aggiorna da solo al cambio dell'ora legale.

## Altre categorie

- Categoria 2 (registri 24–65): sempre a zero su questo modello.
- Categoria 3 (registri 128–212): stringhe ASCII di identificazione firmware ("Nome Firmware xx 27-02-2024", "PWB.v. 2016-05-1…").
