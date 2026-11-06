# Hydro Stove Thermorossi HA

Controllo **locale** (senza cloud) delle idrostufe a pellet Thermorossi con modulo Wi-Fi **WiNet**, per **Home Assistant**.

*English summary below.*

> ⚠️ **Avvertenza.** Progetto indipendente, non affiliato a Thermorossi né a Net Software (produttore del modulo WiNet).
> La mappa dei registri è stata ricavata osservando **un solo modello** (PIDRA 21, firmware WiNet 0.81).
> Scrivere registri della scheda è a tuo rischio: usa solo i comandi documentati e verificati.

## Perché

Il modulo WiNet espone un'API HTTP locale (`/ajax/get-registers`, `/ajax/set-register`), ma la mappa dei registri
non è pubblica e cambia da modello a modello. Le integrazioni esistenti leggono la categoria 2, che su questa
idrostufa è sempre a zero: qui i dati utili stanno nella **categoria 1**.

## Contenuto

| Cartella | Cosa contiene |
|---|---|
| [`docs/registri.md`](docs/registri.md) | Mappa dei registri verificata, codifiche e metodo di verifica |
| [`homeassistant/`](homeassistant/) | Package Home Assistant pronto: potenza (accensione/spegnimento), target, stato, temperature, pompa, orologio |
| [`recorder/`](recorder/) | Registratore web per mappare **la tua** stufa: salva ogni variazione dei registri in MySQL e ti fa annotare cosa vedi sul display |

## Home Assistant in breve

1. In `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
2. Copia `homeassistant/idrostufa_locale.yaml` in `/config/packages/` e sostituisci `IP_MODULO_WINET`
   con l'indirizzo del tuo modulo (meglio con IP fisso).
3. Controlla la configurazione e riavvia.

Entità create: selettore **potenza** (Spenta, 1–4, Auto), numero **target acqua** (65–73 °C),
sensori **stato**, **temperatura acqua**, **temperatura fumi**, **pompa**, **orologio stufa**.
I comandi limitano sempre i valori ai range ammessi.

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
See [`docs/registri.md`](docs/registri.md) for the full register map, `homeassistant/` for a ready-to-use package and
`recorder/` for a small web tool to map other models. Not affiliated with Thermorossi or Net Software; use at your own risk.
