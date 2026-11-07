"""Costanti dell'integrazione Hydro Stove Thermorossi."""
from datetime import timedelta

DOMAIN = "hydrostove_thermorossi"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

# Registri della categoria 1 (verificati su IDRA 21, WiNet 0.81)
REG_STATE = 6        # parte bassa = fase, bit 256 = pompa, bit 2048 = Auto
REG_POWER = 12       # 0 spenta, 1-4 potenza, 5 Auto (scrivibile)
REG_WATER = 18       # temperatura acqua (°C)
REG_FLUE = 21        # temperatura fumi (°C)
REG_TARGET = 112     # temperatura target acqua (°C, scrivibile)

PHASE_OFF = 1
PHASE_START = 2
PHASE_WORK = 3
BIT_PUMP = 256

POWER_MIN, POWER_MAX, POWER_AUTO = 0, 5, 5
TARGET_MIN, TARGET_MAX = 65, 73
COOLING_FLUE_THRESHOLD = 60  # °C: sopra, con fase OFF, la stufa è in raffreddamento
