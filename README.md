# Filemaker Backups

Simple script to backups Filemaker Server backups to Storage(SFTP).

Backup flow:
1. copy backups(folders) from Filemaker Server backups folder to folder on local drive
2. compress backups and upload to Storage if `upload_backup_types` set
3. remove copied folders and uploaded zip file(if uploaded to Storage)
4. keep `keep_not_uploaded_items` last items for not uploaded `backup_types`


## Config

 - `fpt_server` - storage server

 - `fpt_username` - storage username

 - `fpt_password` - storage password

 - `filemaker_path` - path where Filemaker Server crates backups

 - `backups_path` - local path where to keep backups

 - `branch` - "root" folder in bucket

 - `backup_types` - types of backups(folders) under `filemaker_path`

 - `upload_backup_types` - list of `backup_types` uploaded to Storage

 - `keep_not_uploaded_items` - if `backup_types` not uploaded to Storage keep `keep_not_uploaded_items` items in `backups_path`


Sample config file `config.json`
```json
{
  "fpt_server": "...",
  "fpt_username": "...",
  "fpt_password": "...",
  "filemaker_path": "C:\\Program Files\\FileMaker\\FileMaker Server\\Data\\Backups",
  "backups_path": "C:\\Users\\admin\\Backups",
  "branch": "palladium",
  "backup_types": [
    "daily",
    "hourly"
  ],
  "upload_backup_types": [
    "daily"
  ],
  "keep_not_uploaded_items": 2
}

```
