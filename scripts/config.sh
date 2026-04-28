# ============================================================
# Linux Traffic Shaping - Configuration
# ============================================================

# Network interfaces
IFACE_WIFI="wlp0s20f3"
IFACE_ETH="enp0s31f6"

# TBF common parameters
BURST="10kb"
LATENCY="70ms"
MINBURST="1540"

# Rate tiers
RATE_064="64kbit"
RATE_128="128kbit"
RATE_256="256kbit"
RATE_384="384kbit"
RATE_512="512kbit"
RATE_1M="1mbit"
RATE_2M="2mbit"
RATE_3M="3mbit"
RATE_4M="4mbit"
RATE_5M="5mbit"
RATE_FULL="50mbit"

# Step duration in seconds
STEP_DURATION=30

# Speedometer scale
SPEED_SCALE=256
