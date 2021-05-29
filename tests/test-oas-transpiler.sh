#!/bin/bash

total=$(find ./tests/openapi-directory/APIs -type f | wc -l)
i=0

find ./tests/openapi-directory/APIs -type f -print0 | while read -d $'\0' file
do
    ((i++))
    echo -e "\n${i}/${total}"
    if prance validate $file ; then
        echo -e "Testing $file"
        mockintosh $file -c dev.json json || exit 1

        # TODO: Throws avalidation error in case of `exclusiveMaximum` is bool.
        # TODO: Setting `--validator Draft4Validator` causes more issues
        jsonschema -i dev.json mockintosh/schema.json
    else
        echo -e "Passing $file"
    fi
done
