# Restoring the database from the weekly copy

Batch X4 (DS44-03, #257, #268). Neon's free plan can undo a mistake only within six hours.
Past that, this is the way back: the weekly encrypted copy GitHub Actions keeps for 90 days
(newest 8), restored into a **new Neon branch**, checked, and only then switched to.

**Never restore over the live database.** A restore that goes wrong on a branch costs
nothing; the live database stays as it was until the switch.

## What a copy holds, and what a restore therefore costs

Every table, as of the copy's moment (Sundays 03:30 UTC; the 1st of the month too), except
credentials, which the backup role cannot read:

| Not in the copy | So after a restore |
|---|---|
| PIN hashes | Both people are signed out. Craig sets each PIN with `set_pin` (step 6) |
| Refresh tokens | Both phones ask to sign in again |
| Push devices | Each phone asks for notifications again: Settings → turn them on |
| Calendar-feed tokens | The calendar subscription link changes: Settings gives the new one |
| eBay sign-in (`ebay_accounts`) | Connect eBay again (`OWNER-ACTIONS.md` 29) |
| Movie-night invite links | New ones are issued; old links stop working |
| Rate-limit counters | Reset, which is harmless |

Anything written after the copy's moment is lost; the manifest says when that was.

## Steps

You need: the Mac, `age` (`~/.local/bin/age`), the private key
(`~/.mcu-secrets/backup-age-key.txt`, and its copy in your password manager), and the Neon
console. Each command is one line; never `cd` into `apps/api` (autoenv prints its secrets).

1. **Pick the copy.** GitHub → Actions → Backup: the newest green run from before the
   mistake. Download its artifact (`db-backup-<date>-<run>`):

   ```bash
   gh run download <run-id> -R CraigR973/mcu-app -D ~/restore
   ```

2. **Decrypt it** (the artifact holds one `.age` file):

   ```bash
   mkdir -p ~/restore/copy && ~/.local/bin/age -d -i ~/.mcu-secrets/backup-age-key.txt ~/restore/db-backup-*/*.tar.gz.age | tar -xz -C ~/restore/copy
   ```

   `~/restore/copy/manifest.json` names the migration it was taken at and each table's
   rows.

3. **Make a branch to restore into.** Neon console → Branches → New branch from `main`
   (current data), named `restore-<date>`. Copy its **direct** connection string (connection
   pooling off) as the owner. Then, on that branch only, in the SQL Editor:
   `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`. Check the editor says the branch,
   not `main`, before running it.

4. **Restore and check.** The address goes in an environment variable, never on the command
   line:

   ```bash
   read -rs RESTORE_DATABASE_URL && export RESTORE_DATABASE_URL
   ```

   ```bash
   PYTHONPATH=/Users/craigrobinson/mcu_app/apps/api /Users/craigrobinson/mcu_app/apps/api/.venv/bin/python3.12 -m src.scripts.backup restore --from ~/restore/copy
   ```

   It migrates the branch to the copy's migration, loads every table, and ends with
   "every table's rows match the copy", or names the tables that differ and changes nothing.

5. **Switch to it.** Either point every Railway service's `DATABASE_URL` at the branch's
   pooled address (`api` and each `cron-*`), or use Neon's restore of `main` from the branch
   if the console offers it, which keeps the address. Both are hosting changes, so Craig's.
   The next deploy runs any newer migrations against it.

6. **Sign-in, then the rest.** Set each PIN against the restored database:

   ```bash
   PYTHONPATH=/Users/craigrobinson/mcu_app/apps/api /Users/craigrobinson/mcu_app/apps/api/.venv/bin/python3.12 -m src.scripts.set_pin Craig
   ```

   (and `Mark`), with `DATABASE_URL` exported the same way as in step 4. Then on each phone:
   sign in, turn notifications on, and, for Craig, Connect eBay.

7. **Tidy up.** Delete the decrypted copy, and the branch once it is no longer needed:

   ```bash
   rm -rf ~/restore
   ```

## The monthly drill

The backup run on the 1st of each month restores the copy it has just taken into a throwaway
Postgres on the runner and compares every table's rows with the manifest, and fails if the
copy is not at the code's newest migration. A failure fails the run, which GitHub emails.
It restores the copy before encryption, because the runner never holds the private key; the
key itself was checked once on 14 Oct by decrypting the first artifact on the Mac.
