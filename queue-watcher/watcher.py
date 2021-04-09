#!/usr/bin/env python

import classad
import htcondor
import os

MAX_PENDING_PILOTS = 128
MAX_SUBMISSION_PER_CYCLE = 32

schedd = htcondor.Schedd()
# check the status of the jobs
ads = schedd.query(
    projection=["ClusterId", "ProcId", "JobStatus", "Owner"],
)

c_status = {}

for ad in ads:
    owner = ad['Owner']
    if owner not in c_status:
        c_status[owner] = {'idle': 0, 'running': 0}
    if ad['JobStatus'] == 1:
        c_status[owner]['idle'] += 1
    elif ad['JobStatus'] == 2:
        c_status[owner]['running'] += 1

print("Condor status:")
for owner in c_status:
    print(f"{owner}: {c_status[owner]['idle']} idle {c_status[owner]['running']} running")


import subprocess
success = False
s_stdout = None
for _ in range(3):
    user_str = ",".join(c_status.keys())
    p = subprocess.run(['squeue', '-a', '-r', '-h', '-u', user_str, '-n', 'minipilot', '-o', '%i %u %t'],
    #p = subprocess.run(['squeue', '-u', user_str, '-n', 'minipilot', '-h'],
                        stdout = subprocess.PIPE,
                        stderr = subprocess.PIPE,
                        encoding = 'utf-8',
                      )
    if p.returncode != 0:
        continue
    else:
        success = True
        s_stdout = p.stdout
        break

if success == False:
    raise Exception("Could not read SLURM info")

s_status = {o:{'idle':0, 'running':0} for o in c_status.keys()}
for line in s_stdout.split('\n'):
    try:
        jobid, user, status = line.split(' ')
    except ValueError:
        continue
    if user not in s_status:
        s_status[user] = {'idle': 0, 'running': 0}
    if status == 'R':
        s_status[user]['running'] += 1
    elif status == 'PD':
        s_status[user]['idle'] += 1

print("\nSLURM status")
for owner in s_status:
    print(f"{owner}: {s_status[owner]['idle']} idle {s_status[owner]['running']} running")

print("\nCalculating minipilots to submit")
to_submit = {}
for user in c_status:
    c_pending = c_status[user]['idle']
    s_pending = s_status[user]['idle']

    # Nothing waiting to run
    if c_pending <= 0:
        continue

    print(f"Processing user {user}")
    # There are already more slurm jobs pending than condor jobs, adding more
    # won't help speed things up
    if s_pending > c_pending:
        print("  - Enough SLURM jobs pending")
        continue

    if s_pending > MAX_PENDING_PILOTS:
        print("  - Max SLURM pending jobs reached")
        continue

    required_count = min(c_pending, MAX_SUBMISSION_PER_CYCLE)
    if required_count:
        to_submit[user] = required_count
        print(f"  - submitting {to_submit[user]} more minipilots")

if len(to_submit):
    print("\nSubmitting minipilots to cluster")
    if os.getuid() != 0:
        print("WARNING: operating in no-op mode since we are not root")
    for user, count in to_submit.items():
        print(f"  - Submitting {count} minipilots for {user}")
        if os.getuid() == 0:
            prepend_args = ["sudo", "-u", user]
        else:
            prepend_args = ["echo", "-n"]

        success = False
        s_stdout = None
        for _ in range(3):
            # Arrays are zero-indexed
            submit_tmp = count - 1
            args = prepend_args
            args.extend(['sbatch', '--array', "0-%d" % submit_tmp,
                          '-c', '1', '-J', 'minipilot',
                          '--mem=2048M',
                          '-t', '4:00:00',
                          '-o', '/dev/null',
			  '-e', '/dev/null',
                          '/home/meloam/projects/mini-pilot/queue-watcher/slurm_minipilot.sh'])
            p = subprocess.run(args,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.STDOUT,
                                encoding = 'utf-8',
                            )
            s_stdout = p.stdout
            if p.returncode != 0:
                continue
            else:
                success = True
                break
        if not success:
            print(f"  - Could not submit for {user}:\n:")
            print(s_stdout)
        else:
            print(s_stdout)
