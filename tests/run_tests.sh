#!/bin/bash

for TOPO in *.topo; do

  # For now, use a bulk extension ".out" for all output cases
  OUTFILE=${TOPO%.*topo}.out

  # Assign the first found switch as a single treeify root
  grep -E '^Switch' ${TOPO} | head -1 | awk '{print $3}' | sed 's/"//g' > t.tmp

  CMD_ARRAY=(
    "python3 ../src/ibtopotool.py                           -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -s                        -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -t t.tmp                  -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -s -t t.tmp               -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -s --shortlabels          -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -t t.tmp --shortlabels    -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py -s -t t.tmp --shortlabels -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py --slurm                   -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py --slurm -t t.tmp          -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py --slurm -s                -o ${OUTFILE} ${TOPO}"
    "python3 ../src/ibtopotool.py --slurm -s -t t.tmp       -o ${OUTFILE} ${TOPO}"
  )

  # Execute tests
  for (( i = 0; i < ${#CMD_ARRAY[@]}; i++ ))
  do
    CMD="${CMD_ARRAY[$i]}"
    ${CMD}
    CMD_RESULT="((1-$?))"
    (( ${CMD_RESULT} )) && echo "Success: ${CMD}"
    (( ${CMD_RESULT} )) || echo "Failure: ${CMD}"
  done

  # Cleanup
  if stat *.out 1>/dev/null 2>/dev/null; then rm *.out; fi
  if stat t.tmp 1>/dev/null 2>/dev/null; then rm t.tmp; fi

done
