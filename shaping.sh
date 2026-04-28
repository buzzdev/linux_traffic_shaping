#!/bin/bash
source "$(dirname "$0")/config.sh"

clear
echo "SHAPING begin"

IFACE="$IFACE_WIFI"

CLEAR="tc qdisc del dev $IFACE root"
SH_64="tc qdisc change dev $IFACE root tbf rate $RATE_064 burst $BURST latency $LATENCY peakrate 0.1mbit minburst $MINBURST"
SH_128="tc qdisc change dev $IFACE root tbf rate $RATE_128 burst $BURST latency $LATENCY peakrate 0.2mbit minburst $MINBURST"
SH_384="tc qdisc change dev $IFACE root tbf rate $RATE_384 burst $BURST latency $LATENCY peakrate 0.5mbit minburst $MINBURST"
SH_512="tc qdisc change dev $IFACE root tbf rate $RATE_512 burst $BURST latency $LATENCY peakrate 0.7mbit minburst $MINBURST"
SH_1024="tc qdisc change dev $IFACE root tbf rate $RATE_1M burst $BURST latency $LATENCY peakrate 1.2mbit minburst $MINBURST"
SH_2048="tc qdisc change dev $IFACE root tbf rate $RATE_2M burst $BURST latency $LATENCY peakrate 2.2mbit minburst $MINBURST"
SH_3072="tc qdisc change dev $IFACE root tbf rate $RATE_3M burst $BURST latency $LATENCY peakrate 3.3mbit minburst $MINBURST"
SH_4096="tc qdisc change dev $IFACE root tbf rate $RATE_4M burst $BURST latency $LATENCY peakrate 4.4mbit minburst $MINBURST"
SH_5120="tc qdisc change dev $IFACE root tbf rate $RATE_5M burst $BURST latency $LATENCY peakrate 5.5mbit minburst $MINBURST"

eval "tc qdisc add dev $IFACE root tbf rate $RATE_FULL burst $BURST latency $LATENCY peakrate 55mbit minburst $MINBURST"

# echo -e "Shaping $STEP_DURATION seconds @ full rate"
# sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 4mbit"
eval $SH_4096
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 3mbit"
eval $SH_3072
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 2mbit"
eval $SH_2048
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 1mbit"
eval $SH_1024
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 512kbit"
eval $SH_512
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 384kbit"
eval $SH_384
sleep $STEP_DURATION

echo -e "Shaping $STEP_DURATION seconds @ 128kbit"
eval $SH_128
sleep $STEP_DURATION

echo -e "Restoring full rate"
eval $CLEAR
