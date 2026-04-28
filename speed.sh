#!/bin/bash
source "$(dirname "$0")/config.sh"

speedometer -k $SPEED_SCALE -r $IFACE_WIFI -s
