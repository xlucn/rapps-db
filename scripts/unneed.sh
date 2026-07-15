#!/bin/bash
comm -13 \
    <(python ./scripts/check.py --dump | sort) \
    <(find apps/ -type f -printf "%f\n" | sort)
