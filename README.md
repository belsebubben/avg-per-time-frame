# avg-per-time-frame
## avg-per-time-frame: is a wrapper check for nagios / icinga etc creating an avg of hour/weekday and alarming on % thresholds divergences

Checks and warns on divergence from mean per hour of weekday average This means
that if it is wednesday at 15:45 the key will then be
<target>3__15 ie target<nr day of week (wednesday = 3)><hour 15>

<target>3__15 will contain n values (smoothing nr of values) of the last n
measurments.  The new current value will be checked agains sum(n)/len(n) for
its min/max threshold divergence in %

Important to understand is that it will take a while for smoothing of collected
values to occur. Thus first measurements will default to exactly 100%, and as
more averages are collected a better average will be calculated.

Rate calculation will be applicable when calling on a value that is a counter
rate will then be broken down to x per second since last, be ware of wrapping
counters (not handled). 

Wrapping is not handled as this scripts sample intervals should be near enough
to avoid any problems.

example usage:
./check_avg_per_time_frame.py -w 40,150 -c 20,200 -l 'bit/s' -H hostname1.tld
-s IF-MIB::ifInOctets.1 -r snmpget -v 2c -c public -Oqv hostname.tld IF-MIB::ifInOctets.1

```
optional arguments:
  -h, --help            show this help message and exit
  -w WARN, --warn_cc WARN
                        warn in percent of divergence from avg as low,high in prcnt
  -c CRIT, --crit_cc CRIT
                        crit in percent of divergence from avg as low,high in prcnt
  -H HOST, --host_cc HOST
                        hostname if applicable
  -s SERVICE, --service_cc SERVICE
                        service if applicable
  -t TARGET, --target_cc TARGET
                        If not host and or service is available needed to name stats
  -S SMOOTHING, --smoothing_cc SMOOTHING
                        number of smoothing points per avg (higher=smoother)
  -l LABEL, --label_cc LABEL
                        label for the value printout (example: bit/s)
  -D DATAPATH, --datapath_cc DATAPATH
                        path to where to store data (need to be writable by user)
  -d DEBUG, --debug_cc DEBUG
                        debug output
  -r, --rate_cc         rate calculation
  -F FIELDSEP, --field_cc FIELDSEP
                        If you need to extract the value from the output and need to specify field separator
  -P FIELDNR, --part_cc FIELDNR
                        Which of the fields from the separated fields contain the value
```


## Example icinga2 configs

### command
```
object CheckCommand "avg-per-time-frame" {
        // this is only a hack in order to fix the rate path that is normally hard to change
        // original check is in /usr/share/icinga2
        env = { "NAGIOS_PLUGIN_STATE_DIRECTORY" = "/var/tmp" }
        command = [ PluginDir + "/avg-per-time-frame.py" ]

        arguments = {
                "--warn_cc" = {
                        value = "$warn_cc$"
                        description = " warn in percent of divergence from avg as low,high in prcnt"
                        order = 1
                }
                "--crit_cc" = {
                        value = "$crit_cc$"
                        description = "crit in percent of divergence from avg as low,high in prcnt"
                        order = 2
                }
                "--host_cc" = {
                        value = "$host_cc$"
                        description = "hostname if applicable"
                        order = 3
                }
                "--service_c" = {
                        value = "$service_cc$"
                        description = "service if applicable"
                        order = 4
                }
                "--target_cc" = {
                        value = "$target_cc$"
                        description = "If not host and or service is available needed to name stats"
                        order = 5
                }
                "--smoothing_cc" = {
                        value = "$smoothing_cc$"
                        description = "number of smoothing points per avg (higher=smoother)"
                        order = 6
                }
                "--label_cc" = {
                        value = "$label_cc$"
                        description = "label for the value printout (example: bit/s)"
                        order = 7
                }
                "--datapath_cc" = {
                        value = "$datapath_cc$"
                        description = "path to where to store data (need to be writable by user)"
                        order = 8
                }
                "--debug_cc" = {
                        value = "$debug_cc$"
                        description = "debug output"
                        order = 9
                }
                "--rate_cc" = {
                        set_if = "$rate_cc$"
                        description = "rate calculation"
                        order = 10
                }
                "--field_cc" = {
                        value = "$field_cc$"
                        description = "If you need to extract the value from the output and need to specify field separator"
                        order = 11
                }
                "--part_cc" = {
                        value = "$part_cc$"
                        description = "Which of the fields from the separated fields contain the value"
                        order = 12
                }
                "arbitrary_cmd" = {
                        skip_key = true
                        value = "$arbitrary_cmd$"
                        description = "the command spitting out something"
                        order = 13
                }
        }
        vars.host_cc = "$address$"

}
```


### Service icinga2
```
template Service "avg-stats-per-time-frame" {
        import "generic-service"
        check_command = "avg-per-time-frame"
        check_interval = 300s
        retry_interval = 300s
        enable_perfdata = true
}

apply Service "ipInReceives-avg-per-hour" to Host {
        import "avg-stats-per-time-frame"
        vars.warn_cc =  "30,170"
        vars.crit_cc =  "15,225"
        vars.datapath_cc =  "/var/spool/icinga2/data"
        vars.label_cc =  "ipinReceieves"
        vars.target_cc =  "ipinReceieves"
        vars.host_cc =  host.address
        vars.rate_cc =  true
        vars.arbitrary_cmd =  "/usr/bin/snmpget -v 2c -c public -Oqv " + host.address + " ipInReceives.0"
        assign where host.vars.os == "Openbsd" && host.vars.checkbysnmp
}
```


