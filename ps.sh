#!/bin/bash

while true
 do
  sleep 720
  echo Below is the container list
  docker ps
  echo Below is the process list
  ps auxff
 done
