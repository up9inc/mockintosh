#!/bin/bash

total=20
i=0

find ./tests/openapi-directory/APIs -type f | shuf -n $total | while read -d $'\n' file
do
    ((i++))
    echo -e "\n${i}/${total}"
    if prance validate $file ; then
        echo -e "Testing $file"
        mockintosh $file -c dev.json json || exit 1

        # TODO: Throws avalidation error in case of `exclusiveMaximum` is bool.
        # TODO: Setting `--validator Draft4Validator` causes more issues
        jsonschema -i dev.json mockintosh/schema.json || exit 1
    else
        echo -e "Passing $file"
    fi
done
