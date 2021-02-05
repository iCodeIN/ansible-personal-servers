#!/bin/sh

# configure route for VPN
/sbin/ip route add {{ openvpn_conf_server_v4.subnet }} via {{ openvpn_pihole_ipv4 }}

# start pihole
/s6-init
