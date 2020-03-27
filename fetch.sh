#!/bin/sh

readonly app='eths_desk_clock'

set -eux

egg_url="$( curl "https://badge.team/eggs/get/${app}/json" |
	jq --raw-output '.releases | to_entries | max_by(.key) | .value[0].url' )"

curl "${egg_url}" | tar -xv
