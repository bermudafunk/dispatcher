## timers.csv

In dieser Datei können Timer / "Eieruhren" definiert werden. Damit kann nach der Zeitspannen von `timeout_seconds` automatisch eine Aktion
getriggert werden. Der Name des Triggers ist `<name>_timeout`, z.B. `immediate_state_timeout`.

Es gibt einen Sondertimer `next_hour`, der hier nicht aufgeführt ist. Dieser löst zur nächsten vollen Stunde den Trigger `next_hour` aus.

## states.csv

Diese Datei enthält alle Zustände, die der Zustandsautomat haben soll. Die Zustände `automat_on_air` und `studio_X_on_air` müssen vorhanden
sein. Bei diesen Zuständen wird entweder der Automat oder das Studio "X" aktiviert. Alle anderen Zustände haben keine Auswirkung auf die
ausgewählte Audioquelle.

### Studio-Binding

Im Zustandsnamen wird mit den Großbuchstaben `X` & `Y` kodiert, dass daran ein Studio gebunden werden soll.

### Timer Aktivierung

Wenn im Zustandsnamen der Name eines Timers enthalten ist, wird dieser aktiviert. Alle Timer die nicht im Zustandsnamen enthalten sind,
werden abgebrochen. Bei einem Zustandswechsel wird der Timer nicht neugestartet, sondern läuft weiter.

### Ansteuerung der LEDs in den Studios

Für jeden Zustand muss definiert werden, wie die LEDs der Studios angesteuert werden sollen. Für jedes Studio existiert eine `main`-LED.
Diese ist in allen Studio-Boxen parallel geschaltet. Für die Studios gibt es dann noch die `immediate`-LED. Diese ist nur im jeweiligen
Studio selbst zu sehen.

Die Studios werden die 3 Kategorien `X`, `Y` & `other` unterteilt.
`X` & `Y` beziehen sich auf das "Studio-Binding". Alle Studios, die nicht im aktuellen Zustand gebunden sind, sind `other`.

#### Zustandsoptionen der LEDs

Für jede LED können folgende Optionen gesetzt werden:

- Zustand
    - `off`
    - `on`
    - `blink`
    - `blink_fast`
- Farbe
    - `none`
    - `green`
    - `red`
    - `yellow`

## transitions.csv

In dieser Datei werden die möglichen Übergänge zwischen den Zuständen definiert. Die Namen in `source` & `dest` müssen mit denen aus
definierten Zustände in der `states.csv` übereinstimmen.

Jedes Studio hat 3 Knöpfe `release` (Freigabe), `takeover` (Übernahme) & `immediate` (Sofort). Die gebunden Studios im aktuellen Zustand
werden mit den Knöpfen zu einem Trigger verknüpft, z.B. `release_X`. Wenn noch kein Studio `X` im aktuellen Zustand gebunden ist, wird das
als Studio `X` angenommen. Wenn noch kein Studio `Y` im aktuellen Zustand gebunden ist, wird das als Studio `Y` angenommen. Sonst wird das
Studio als `other` angesehen.

Wenn bei dem Übergang die Zuordnung von den gebunden Studios `X` & `Y` vertauscht werden soll, z.B. vor dem Wechsel auf `studio_X_on_air`,
muss hier `true` gesetzt werden.
