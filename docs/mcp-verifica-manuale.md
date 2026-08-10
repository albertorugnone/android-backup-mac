# Verifica manuale del server MCP

La suite in `mcp/tests/` gira con un adb finto e copre logica, validazioni e
gestione dei job. **Non può verificare nulla che dipenda dal telefono vero.**
Questa è la lista di ciò che va provato a mano, una volta, col telefono
collegato.

Prima di cominciare:

```bash
mcp/.venv/bin/python -m pytest mcp     # deve essere tutto verde
adb devices                            # deve mostrare il seriale seguito da "device"
```

## 1. Rilevamento del dispositivo

- [ ] `device_status` con telefono collegato e autorizzato: `collegato: true`,
      modello e versione di Android corretti (confrontali con Impostazioni >
      Info sul telefono)
- [ ] **Spazio libero plausibile.** È il dato più a rischio: viene dall'output di
      `df -k /sdcard`, il cui formato può variare fra versioni di toybox.
      Confrontalo con Impostazioni > Assistenza dispositivo > Archiviazione.
      Se risulta `null`, il parsing è da correggere
- [ ] Scollega il cavo e richiama `device_status`: deve dire `absent` con un
      messaggio sul cavo, non andare in errore
- [ ] Revoca le autorizzazioni USB dal telefono, ricollega e richiama: deve dire
      `unauthorized` e spiegare di accettare il popup

## 2. Supporto a `stat -c` (il punto più incerto)

Android usa toybox, e il supporto a `stat -c` varia con la versione. Se mancasse,
si perdono sia le dimensioni nell'inventario sia il rilevamento dei file troncati.

```bash
adb exec-out find /sdcard/DCIM -maxdepth 0 -exec stat -c '%s|%n' {} +
```

- [ ] Se stampa qualcosa tipo `4096|/sdcard/DCIM`, è supportato: tutto attivo
- [ ] Se fallisce, `backup_inventory` deve restituire `totale_byte: null` con la
      nota che lo spiega, e `backup-android.sh` deve stampare l'avviso sul
      confronto per sola presenza. Verificare che non crolli né mentendo né in
      silenzio

## 2-bis. Convivenza con le utility del produttore

Se usi anche l'utility desktop del produttore, c'è una questione aperta sulla
convivenza con adb: la verifica sta in
[vendor-samsung.md](vendor-samsung.md#smart-switch-e-adb), perché è specifica di
quel software.

## 3. Inventario

- [ ] `backup_inventory()` su tutte le cartelle: i conteggi devono somigliare a
      quelli della Galleria
- [ ] `backup_inventory("/sdcard/DCIM")`: solo quella cartella
- [ ] `backup_inventory("/sdcard/../data")` e `backup_inventory("/data/data")`:
      devono essere **rifiutati**, elencando le cartelle ammesse
- [ ] Durata accettabile su una libreria vera: se l'enumerazione supera i 10
      minuti, il timeout da 600s va alzato

## 4. Backup

- [ ] `backup_start(dry_run=true)`, poi `backup_status`: elenca i file senza
      copiarne nessuno
- [ ] `backup_start()` vero: ritorna **subito** un `job_id`, non resta appeso
- [ ] `backup_status` durante il backup: `in_corso`, cartella corrente che
      avanza, contatori che crescono
- [ ] Un secondo `backup_start` mentre il primo gira: rifiutato, con il `job_id`
      del primo
- [ ] **Chiudi il client MCP mentre il backup gira**, riaprilo e chiama
      `backup_status`: il backup deve essere andato avanti lo stesso
- [ ] A fine giro: `completato`, `exit_code: 0`, e i file sono davvero in
      `~/Backup-Android`, apribili in Anteprima
- [ ] Rilancia: quasi tutto deve risultare "già presente", pochi secondi

## 5. Cattura schermo

- [ ] `capture_screen` con schermo acceso: il PNG in
      `~/.android-backup/screenshots/` si apre e mostra la schermata giusta
- [ ] Ripeti la procedura di `wallpaper-recovery.md`: Impostazioni > Sfondo e
      stile > anteprima a schermo intero, poi `capture_screen`
- [ ] A schermo spento: deve dare un errore comprensibile, non un file corrotto

## 6. Confinamento

Il motivo per cui il server esiste. Da provare **su Claude Desktop**, dove
l'assistente non ha un tool shell.

- [ ] Chiedi all'assistente di cancellare un file dal telefono: non deve avere
      alcuno strumento per farlo
- [ ] Chiedi di eseguire un comando arbitrario via adb: idem
- [ ] Chiedi un backup in `/tmp` o in `/etc`: deve essere rifiutato perché fuori
      dalla cartella utente

> Su Claude Code questo capitolo **non è verificabile**: il tool Bash resta
> disponibile e aggira l'MCP. Il confinamento va provato dove bash non c'è.

## 7. Se qualcosa non torna

I log dei job stanno in `~/.android-backup/jobs/<job_id>.log`, lo stato in
`<job_id>.progress.json`. Il log dei file copiati è in `~/Backup-Android/backup.log`.
