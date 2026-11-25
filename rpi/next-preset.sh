#!/bin/sh
exec curl --silent --show-error --fail --max-time 30 -X POST -H 'X-RPiT3K: 1' http://127.0.0.1:8080/api/next
