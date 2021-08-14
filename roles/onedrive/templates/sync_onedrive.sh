#!/usr/bin/env bash

docker container inspect {{ onedrive_container_name }} > /dev/null 2> /dev/null || \
  docker run -d --rm \
    --name {{ onedrive_container_name }} \
    -v {{ onedrive_installation_dir }}/rclone:/config/rclone \
    -v {{ onedrive_data_dir }}:/data \
    rclone/rclone sync \
      --checkers=28 \
      --transfers=28 \
      onedrive:/ /data
