-- Registratore idrostufa WiNet — schema per il DB `stufa`
-- Tutti i timestamp sono in UTC (come si aspetta Grafana).

CREATE TABLE IF NOT EXISTS registri (
  id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ts      DATETIME(3)       NOT NULL,
  cat     TINYINT UNSIGNED  NOT NULL,
  reg     SMALLINT UNSIGNED NOT NULL,
  valore  INT               NOT NULL,
  KEY idx_ts (ts),
  KEY idx_cat_reg_ts (cat, reg, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS eventi (
  id     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ts     DATETIME(3)  NOT NULL,
  testo  VARCHAR(255) NOT NULL,
  KEY idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS errori (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ts         DATETIME(3)  NOT NULL,
  messaggio  VARCHAR(500) NOT NULL,
  KEY idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabelle aggiunte nella v2 (l'app le crea comunque da sola all'avvio)
CREATE TABLE IF NOT EXISTS osservazioni (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY, ts DATETIME(3) NOT NULL,
  stato VARCHAR(100) NULL, potenza VARCHAR(20) NULL,
  acqua SMALLINT NULL, fumi SMALLINT NULL, target SMALLINT NULL,
  note VARCHAR(255) NULL, registri TEXT NOT NULL,
  KEY idx_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS nomi_registri (
  cat TINYINT UNSIGNED NOT NULL, reg SMALLINT UNSIGNED NOT NULL, nome VARCHAR(100) NOT NULL,
  PRIMARY KEY (cat, reg)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS significati (
  cat TINYINT UNSIGNED NOT NULL, reg SMALLINT UNSIGNED NOT NULL, valore INT NOT NULL,
  testo VARCHAR(100) NOT NULL, PRIMARY KEY (cat, reg, valore)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
