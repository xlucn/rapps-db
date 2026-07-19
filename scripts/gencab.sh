#!/bin/sh
ROSDIR=${ROSDIR:-../reactos/}
sh "$ROSDIR/base/applications/rapps/CreateCabFile.sh" \
    "$ROSDIR/sdk/tools/cabman/cabman" \
    "$ROSDIR/sdk/tools/utf16le/utf16le" \
    .
