#!/bin/bash
echo "Content-type: text/plain"
echo "Status: 201 whatever"
echo
printenv
echo "------------------------"
if [ "$REQUEST_METHOD" = "POST" ] ; then
    echo -n "posted ==>"
    cat
    echo "<=="
fi
