curl -sIL "$@" | grep -i "^content-length" | tail -n1
