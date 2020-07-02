#!/bin/bash
clear
echo "SHAPING begin"

CLEAR='tc qdisc del dev enp0s25 root'
SH_0='tc qdisc change dev enp0s25 root tbf rate 512kbit burst 10kb latency 70ms peakrate 0.7mbit minburst 1540'
SH_1='tc qdisc change dev enp0s25 root tbf rate 1mbit burst 10kb latency 70ms peakrate 1.2mbit minburst 1540'
SH_2='tc qdisc change dev enp0s25 root tbf rate 2mbit burst 10kb latency 70ms peakrate 2.2mbit minburst 1540'
SH_3='tc qdisc change dev enp0s25 root tbf rate 3mbit burst 10kb latency 70ms peakrate 3.3mbit minburst 1540'
SH_4='tc qdisc change dev enp0s25 root tbf rate 4mbit burst 10kb latency 70ms peakrate 4.4mbit minburst 1540'
SH_5='tc qdisc change dev enp0s25 root tbf rate 5mbit burst 10kb latency 70ms peakrate 5.5mbit minburst 1540'

eval 'tc qdisc add dev enp0s25 root tbf rate 50mbit burst 10kb latency 70ms peakrate 55mbit minburst 1540'

echo -e "Playing 1 minute @ full rate"
#eval $CLEAR
sleep 10

echo -e "Shaping 1 minute @ 4mbit"
beep
eval $SH_4
sleep 10

echo -e "Shaping 1 minute @ 3mbit"
beep
eval $SH_3
sleep 10

echo -e "Shaping 1 minute @ 2mbit"
beep
eval $SH_2
sleep 10

echo -e "Shaping 1 minute @ 1mbit"
beep
eval $SH_1
sleep 10

echo -e "Shaping 1 minute @ 512kbit"
beep
eval $SH_0
sleep 10

echo -e "Shaping 2 minutes @ 5mbit"
beep
eval $SH_5
sleep 10

echo -e "Shaping 1 minute @ 512kbit"
beep
eval $SH_0
sleep 10

echo -e "Restoring full rate"
beep
eval $CLEAR
