#!/bin/sh

{{ duplicati_volumes_config.mount }}/bh stop -e {{ backup_helper_exclude|join(' ') }}
