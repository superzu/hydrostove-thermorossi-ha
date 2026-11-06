# Hydro Stove Thermorossi HA

Controllo **locale** (senza cloud) delle idrostufe a pellet Thermorossi con modulo Wi-Fi **WiNet**, per **Home Assistant**.

*English summary below.*

> ⚠️ **Avvertenza.** Progetto indipendente, non affiliato a Thermorossi né a Net Software (produttore del modulo WiNet).
> La mappa dei registri è stata ricavata osservando **un solo modello** (IDRA 21, firmware WiNet 0.81).
> Scrivere registri della scheda è a tuo rischio: usa solo i comandi documentati e verificati.

## Perché

Il modulo WiNet espone un'API HTTP locale (`/ajax/get-registers`, `/ajax/set-register`), ma la mappa dei registri
non è pubblica e cambia da modello a modello. Le integrazioni esistenti leggono la categoria 2, che su questa
idrostufa è sempre a zero: qui i dati utili stanno nella **categoria 1**.

## Contenuto

| Cartella | Cosa contiene |
|---|---|
| [`custom_components/hydrostove_thermorossi/`](custom_components/hydrostove_thermorossi/) | **Integrazione Home Assistant** installabile da HACS, configurabile da interfaccia |
| [`docs/registri.md`](docs/registri.md) | Mappa dei registri verificata, codifiche e metodo di verifica |
| [`homeassistant/`](homeassistant/) | Alternativa senza HACS: package YAML da copiare a mano |
| [`recorder/`](recorder/) | Registratore web per mappare **la tua** stufa: salva ogni variazione dei registri in MySQL e ti fa annotare cosa vedi sul display |

## Installazione con HACS (consigliata)

1. In Home Assistant apri **HACS → ⋮ → Repository personalizzati**, aggiungi
   `https://github.com/superzu/hydrostove-thermorossi-ha` con tipo **Integrazione**.
2. Cerca **Hydro Stove Thermorossi**, scaricala e riavvia Home Assistant.
3. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Hydro Stove Thermorossi**,
   inserisci l'indirizzo IP del modulo WiNet (meglio se fisso).

Viene creato il dispositivo **Idrostufa** con:

| Entità | Tipo | Note |
|---|---|---|
| Potenza | selettore | Spenta, 1, 2, 3, 4, Auto: accende, spegne e cambia potenza |
| Target acqua | numero | 65–73 °C |
| Stato | sensore | Spenta, Raffreddamento, Accensione, Lavoro |
| Temperatura acqua / fumi / target | sensori | °C |
| Pompa di circolazione | sensore binario | |
| Orologio stufa, Segnale Wi-Fi, Registro di stato | diagnostica | gli ultimi due disattivati di default |

I comandi limitano sempre i valori ai range ammessi. Lettura ogni 10 secondi, tutto in rete locale.

## Installazione manuale (senza HACS)

Copia la cartella `custom_components/hydrostove_thermorossi` in `/config/custom_components/`, riavvia e aggiungi
l'integrazione come sopra. In alternativa puoi usare il package YAML in [`homeassistant/`](homeassistant/),
sostituendo `IP_MODULO_WINET` con l'indirizzo del modulo.

## Hai un modello diverso?

Usa il [registratore](recorder/) per vedere quali registri cambiano mentre usi la stufa e
contribuisci con una issue o una pull request a `docs/registri.md` indicando modello e firmware.

## Sicurezza della rete

L'API locale del WiNet è HTTP senza autenticazione: chiunque raggiunga il modulo può comandare la stufa.
Tienilo in una rete o VLAN raggiungibile solo da Home Assistant.

---

## English summary

Local (cloud-free) control of Thermorossi pellet **hydro stoves** with the **WiNet** Wi-Fi module, for Home Assistant.
Verified on a PIDRA 21 (WiNet firmware 0.81): useful data lives in **register category 1**; register 12 (power 0–5)
switches the stove on/off and sets power, register 112 sets the water target (65–73 °C).
Install it with HACS as a custom repository (category: Integration) and add it from the UI by entering the module IP.
See [`docs/registri.md`](docs/registri.md) for the full register map, `homeassistant/` for a plain YAML alternative and
`recorder/` for a small web tool to map other models. Not affiliated with Thermorossi or Net Software; use at your own risk.
