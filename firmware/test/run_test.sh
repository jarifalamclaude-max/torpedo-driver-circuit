#!/bin/sh
# Host-side test of the firmware logic: bit-banged I2C against a behavioural ADS1115, self-test cases,
# arming, firing limits. Needs only g++.   sh run_test.sh
cd "$(dirname "$0")" && g++ -std=c++17 -Wall -Wno-unused-parameter -Wno-unused-function -Istubs -o host_test host_test.cpp && ./host_test
