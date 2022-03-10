#! /bin/bash
(
    source $HOME/.virtualenvs/helium-heartbeat/bin/postactivate
    source $HOME/.virtualenvs/helium-heartbeat/bin/activate

    # navigate to directory
    cd $HOME/helium-heartbeat

    # run script
    python3 helium_heartbeat_plot.py

    source $HOME/.virtualenvs/helium-heartbeat/bin/predeactivate
    deactivate

    # return home
    cd ~
) &
disown %1

# dont wait for shell to output, speeds up siri shortcut calls
# () & ; disown %1


# Put this in your crontab
#
# 0 */4 * * * bash $HOME/helium-heartbeat/crons/pi-cron-helium_heartbeat_plot.sh
#
# turn on logging with this
# 15 */4 * * * bash $HOME/helium-heartbeat/crons/pi-cron-helium_heartbeat_plot.sh > $HOME/helium-heartbeat/crons/logs/helium_heartbeat_plot-cron.log 2>&1
#
# modify schedule as needed
