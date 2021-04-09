#!/bin/bash

2>&1 echo "Beginning ACCRE MiniPilot (tm)"

export CONDOR_CONFIG=/gpfs52/home/meloam/projects/mini-pilot/condor-install/etc/condor_config
export PATH="/gpfs52/home/meloam/projects/mini-pilot/condor-install/bin:/gpfs52/home/meloam/projects/mini-pilot/condor-install/sbin:$PATH"

# Used in the condor configuration
export ACCRE_MINIPILOT_USER=$(whoami)
export ACCRE_NUM_CPUS=2
export ACCRE_MEMORY_LIMIT=2048
export ACCRE_NETWORK_INTERFACE=$(ip route get 10.0.0.1 | grep dev | awk '{ print $5 }')
export ACCRE_LOCAL_DIR=$(mktemp -d -t minipilot-XXXXXXXX)
# VERY INSECURE
cp /home/meloam/projects/mini-pilot/POOL $ACCRE_LOCAL_DIR
chown $(whoami) $ACCRE_LOCAL_DIR/POOL
chmod 600 $ACCRE_LOCAL_DIR/POOL
(set -x ; mkdir $ACCRE_LOCAL_DIR/{log,spool,execute})

for VAR in START NETWORK_INTERFACE NUM_SLOTS NUM_CPUS MEMORY_LIMIT LOCAL_DIR; do
    echo "$VAR is $(condor_config_val $VAR)"
done

# Now we're ready to do call condor_master - set up some traps to cleanup
prep_term()
{
    unset term_child_pid
    unset term_kill_needed
    trap 'handle_term' TERM INT
}

handle_term()
{
    echo "TERM TRAP"
    if [ "${term_child_pid}" ]; then
        kill -TERM "${term_child_pid}" 2>/dev/null
    else
        term_kill_needed="yes"
    fi
}

wait_term()
{
    term_child_pid=$!
    if [ "${term_kill_needed}" ]; then
        kill -TERM "${term_child_pid}" 2>/dev/null 
    fi
    wait ${term_child_pid} 2>/dev/null
    trap - TERM INT
    wait ${term_child_pid} 2>/dev/null
}

# Delete the temporary dir as well
handle_exit()
{
    echo "EXIT TRAP"
    if [ -n "$ACCRE_LOCAL_DIR" ]; then
        rm -rf "$ACCRE_LOCAL_DIR"
    fi
}
trap 'handle_exit' EXIT

# EXAMPLE USAGE
prep_term
condor_master -f &
wait_term

