#!/bin/bash

eval $(lesspipe)
lesspipe $1 > $2 2>&1
