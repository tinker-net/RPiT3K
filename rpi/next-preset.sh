#!/bin/sh
exec curl --noproxy '*' --silent --show-error --fail --max-time 30 -X POST -H 'X-RPiT3K: 1' http://127.0.0.1/api/next
