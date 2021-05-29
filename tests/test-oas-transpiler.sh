#!/bin/bash

find ./tests/openapi-directory/APIs -type f -print0 | while read -d $'\0' file
do
    echo -e "\n"
    if prance validate $file ; then
        echo -e "Testing $file"
        mockintosh $file -c dev.yaml || exit 1
    else
        echo -e "Passing $file"
    fi
done
