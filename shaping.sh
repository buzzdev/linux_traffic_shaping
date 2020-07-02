#!/bin/bash
clear
echo "SHAPING begin"

CLEAR='tc qdisc del dev wlo1 root'
SH_256='tc qdisc change dev wlo1 root tbf rate 256kbit burst 10kb latency 70ms peakrate 0.3mbit minburst 1540'
SH_384='tc qdisc change dev wlo1 root tbf rate 384kbit burst 10kb latency 70ms peakrate 0.4mbit minburst 1540'
SH_512='tc qdisc change dev wlo1 root tbf rate 512kbit burst 10kb latency 70ms peakrate 0.7mbit minburst 1540'
SH_1024='tc qdisc change dev wlo1 root tbf rate 1mbit burst 10kb latency 70ms peakrate 1.2mbit minburst 1540'
SH_2048='tc qdisc change dev wlo1 root tbf rate 2mbit burst 10kb latency 70ms peakrate 2.2mbit minburst 1540'
SH_3072='tc qdisc change dev wlo1 root tbf rate 3mbit burst 10kb latency 70ms peakrate 3.3mbit minburst 1540'
SH_4096='tc qdisc change dev wlo1 root tbf rate 4mbit burst 10kb latency 70ms peakrate 4.4mbit minburst 1540'
SH_5120='tc qdisc change dev wlo1 root tbf rate 5mbit burst 10kb latency 70ms peakrate 5.5mbit minburst 1540'

eval 'tc qdisc add dev wlo1 root tbf rate 50mbit burst 10kb latency 70ms peakrate 55mbit minburst 1540'

#echo -e "Playing 1 minute @ full rate"
#eval $CLEAR
#sleep 60

echo -e "Shaping 1 minute @ 4mbit"
eval $SH_4096
sleep 60

echo -e "Shaping 1 minute @ 3mbit"
eval $SH_3072
sleep 60

echo -e "Shaping 1 minute @ 2mbit"
eval $SH_2048
sleep 60

echo -e "Shaping 1 minute @ 1mbit"
eval $SH_1024
sleep 60

echo -e "Shaping 1 minute @ 512kbit"
eval $SH_512
sleep 60

#echo -e "Shaping 1 minute @ 384kbit"
#eval $SH_384
#sleep 60

#echo -e "Shaping 1 minute @ 256kbit"
#eval $SH_256
#sleep 60

echo -e "Shaping 2 minute @ 5mbit"
eval $SH_5120
sleep 120

echo -e "Shaping 1 minute @ 512kbit"
eval $SH_512
sleep 60

#echo -e "Shaping 1 minute @ 5mbit"
#eval $SH_5120
#sleep 60

#echo -e "Shaping 1 minute @ 384kbit"
#eval $SH_384
#sleep 60

echo -e "Restoring full rate"
eval $CLEAR
