#!/usr/bin/env python
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from ftplib import FTP_TLS
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.addHandler(logging.FileHandler("backups.log", encoding="utf-8"))


@dataclass
class Config:
    fpt_server: str
    fpt_username: str
    fpt_password: str
    filemaker_path: str
    backups_path: str
    branch: str
    backup_types: list[str]
    upload_backup_types: list[str]
    keep_not_uploaded_items: int


class Storage:
    def __init__(self, server, username, password, branch):
        self.branch = branch
        self.sftp = FTP_TLS(server, username, password)

    def upload_file(self, file_to_upload: Path, upload_dir: str) -> None:
        root_dir = "/"
        branch_dir = f"{root_dir}{self.branch}"
        full_upload_path = f"{branch_dir}/{upload_dir}"

        # test if branch dir exists
        items = [x[0] for x in self.sftp.mlsd(root_dir)]
        if self.branch not in items:
            self.sftp.mkd(branch_dir)

        if upload_dir not in [x[0] for x in self.sftp.mlsd(branch_dir)]:
            self.sftp.mkd(full_upload_path)

        with open(file_to_upload, "rb") as f:
            self.sftp.storbinary(f"STOR {full_upload_path}/{file_to_upload.name}", f)

    def __del__(self):
        self.sftp.close()


class BackupTask:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.storage = Storage(config.fpt_server, config.fpt_username, config.fpt_password, config.branch)
        self.new_folders_to_compress: list[str] = []

    def _move_backups_from_filemaker_folder_to_home(self) -> None:
        """
        Move backups(folders) from default FileMaker backup dir to my dir.
        """
        for backup_type in self.config.backup_types:
            src_folder = Path(self.config.filemaker_path, backup_type)
            target_folder = Path(self.config.backups_path, backup_type)
            os.makedirs(target_folder, exist_ok=True)

            backup_name: str
            for backup_name in os.listdir(src_folder):
                logger.debug("Moving from: '%s' to: '%s'.", Path(src_folder, backup_name), target_folder)
                shutil.move(src_folder / backup_name, target_folder)
                self.new_folders_to_compress.append(backup_name)
        logger.debug("All file moved")

    def _compress_and_upload(self) -> None:
        """
        Compress moved backups(folders) and upload to S3 and delete archive if enabled.
        Always delete moved backups(folders).
        """
        for backup_type in self.config.backup_types:
            home_backup_path = Path(self.config.backups_path, backup_type)

            backup_folder_name: str
            for backup_folder_name in os.listdir(home_backup_path):
                # compress only new folders
                if backup_folder_name not in self.new_folders_to_compress:
                    continue

                # compress folder
                backup_folder_full_path = Path(home_backup_path, backup_folder_name)
                logger.debug("Compressing %s", backup_folder_full_path)
                archive_file_name = shutil.make_archive(
                    str(backup_folder_full_path),
                    format="zip",
                    root_dir=home_backup_path,
                    base_dir=backup_folder_name,
                )
                archive = Path(backup_folder_name, archive_file_name)
                if backup_type in self.config.upload_backup_types:
                    # upload to S3
                    logger.debug("Uploading %s", archive.name)
                    self.storage.upload_file(archive, backup_type)
                    # remove created archive
                    os.remove(archive)
                # remove backup folder
                shutil.rmtree(backup_folder_full_path, ignore_errors=True)

    def _remove_old_backups(self) -> None:
        """
        Some backups(zip files) are not uploaded to S3.
        Keep last X items in custom folder with backups.
        """
        for backup_type in self.config.backup_types:
            if backup_type in self.config.upload_backup_types:
                # skip backups uploaded to S3 because they're deleted immediately
                continue

            backups = []
            backup_type_root_folder = Path(self.config.backups_path, backup_type)
            backup: str
            for backup in os.listdir(backup_type_root_folder):
                backup_path = Path(backup_type_root_folder, backup)
                backups.append({"file": backup_path, "created": os.stat(backup_path).st_ctime})

            backups = sorted(backups, key=lambda x: x["created"], reverse=True)
            backup_item: dict
            for backup_item in backups[self.config.keep_not_uploaded_items :]:
                os.remove(backup_item["file"])

    def run(self) -> None:
        """
        Execute backup flow.
        """
        self._move_backups_from_filemaker_folder_to_home()
        self._compress_and_upload()
        self._remove_old_backups()


def main() -> None:
    """
    Open and validate config file and if it's valid execute backup flow.
    """
    try:
        with open("config.json", "r") as f:
            config_data = json.loads(f.read())
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        logger.exception("Config file not found or is not valid json file.")
        return

    try:
        config = Config(**dict(config_data.items()))
    except KeyError:
        logger.exception("Invalid config file!")
        return

    try:
        BackupTask(config).run()
    except Exception:
        logger.exception("Error")


if __name__ == "__main__":
    main()
