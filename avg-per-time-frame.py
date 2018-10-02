#!/usr/bin/python 
from __future__ import print_function
import os
import pwd
import sys
import time
import shelve
import time
import argparse
import collections
import subprocess
import random

DESCRIPTION='''
Checks and warns on divergence from mean per hour of weekday average This means
that if it is wednesday at 15:45 the key will then be
<target>3__15 ie target<nr day of week (wednesday = 3)><hour 15>

SYNOPSIS
       [-H] [-s] [-S] [-w] [-c] [-t] [-l] [-D] [-d] [-r] -c command -c cmdargx -c cmdparg..

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

'''

def parse_args():
    parser = argparse.ArgumentParser(epilog=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-w', '--warn_cc', dest='warn',
            help='warn in percent of divergence from avg as low,high in prcnt',
            required=True)
    parser.add_argument('-c', '--crit_cc', dest='crit',
            help='crit in percent of divergence from avg as low,high in prcnt',
            required=True)
    parser.add_argument('-H', '--host_cc', dest='host', help='hostname if applicable')
    parser.add_argument('-s', '--service_cc', dest='service', help='service if applicable')
    parser.add_argument('-t', '--target_cc', dest='target',
            help='If not host and or service is available needed to name stats')
    parser.add_argument('-S', '--smoothing_cc', dest='smoothing',
            help='number of smoothing points per avg (higher=smoother)',
            default=50)
    parser.add_argument('-l', '--label_cc', dest='label', help='label for the value printout (example: bit/s)',
            default=False)
    parser.add_argument('-D', '--datapath_cc', dest='datapath',
            help='path to where to store data (need to be writable by user)',
            default='./')
    parser.add_argument('-d', '--debug_cc', dest='debug', help='debug output',
            default=False)
    parser.add_argument('-r', '--rate_cc', dest='rate', help='rate calculation', action='store_true',
            default=False)
    parser.add_argument('-F', '--field_cc', dest='fieldsep',
            help='If you need to extract the value from the output and need to specify field separator', default=None)
    parser.add_argument('-P', '--part_cc', dest='fieldnr',
            help='Which of the fields from the separated fields contain the value', default=1, type=int)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        assert len(args.warn.split(',')) > 1 and len(args.crit.split(',')) > 1
        args.warn = [int(i) for i in args.warn.split(',')]
        args.crit = [int(i) for i in args.crit.split(',')]
    except:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.debug:
        print(args)
    return args, parser

def datagetter(args, target):
    '''This could easily be changed to anything getting a data
    data poll intervals could matter'''

    # Get data from data collection command
    command = args.command
    
    # workaround for quoting in icinga2.. this is ugly as hell
    if 'icinga' in pwd.getpwuid(os.getuid()).pw_name:
        command = command[0].split()

    new_env = os.environ.copy()
    try:
        scmd = subprocess.Popen(command, env=new_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = scmd.communicate()
    except:
        print('Warning!!! Failed to execute data collection command:', command)
        print('\n\n', sys.exc_info())
        sys.exit(2)
    if scmd.returncode != 0:
        print('Warning!!! Failed to execute data collection command:', command, ';', stderr)
        sys.exit(2)
    
    # splitting out value according to directives
    if args.fieldsep:
        value = int(stdout.split(args.fieldsep)[args.fieldnr])
    else:
        value = int(stdout)

    # rate calculations
    if args.rate:
        d = shelve.open(os.path.join(args.datapath, target + '-data'), writeback=True)
        lastkey = 'lastrecording'
        now = int(time.time())
        try:
            lasttime, lastval = d[lastkey]
        except KeyError:
            d[lastkey] = (now, value)
            d.close()
            print("Setting initial value:")
            sys.exit(0)
        
        timediff = now - lasttime
        counterdiff = value - lastval # we do not handle wrapping!!
        # try to handle wrapping
        if counterdiff < 0:
            d[lastkey] = (now, value)
            d.close()
            print("Resetting; Initial value either wrapped or malfunction:")
            sys.exit(0)
        rate = counterdiff / timediff
        d[lastkey] = (now, value)
        d.close()
        return rate

    #return random.randrange(1000, 100000) ## For testing

def set_averages(hour, day, value, target, args):
    '''target could be host_service, hour of day and day of week
    set value.
    '''
    d = shelve.open(os.path.join(args.datapath, target + '-data'), writeback=True)
    dayhourkey = str(day) + '__' + str(hour)
    try:
        d[dayhourkey] = value
        d.close()
    except:
        print("Failed to set value: %s" % sys.exc_value)
        d.close()
        sys.exit(2)

def get_averages(hour, day, target, args):
    '''target could be host_service, hour of day and day of week'''
    d = shelve.open(os.path.join(args.datapath, target + '-data'), writeback=True)
    dayhourkey = str(day) + '__' + str(hour)
    try:
        val = d[dayhourkey]
        d.close()
        return val
    except KeyError:
        return None
        d.close()
    except:
        print("Failed to get/read value: %s" % sys.exc_value)
        sys.exit(2)
        d.close()

def datebreakdown():
    return time.localtime().tm_hour, time.localtime().tm_wday

def threshholds(newdata, averages, args):
    prcntdiv = (float(newdata) / float(averages)) * 100
    if prcntdiv < args.crit[0] or prcntdiv > args.crit[1]:
        sym = '<' if prcntdiv < args.crit[0] else '>'
        minmax = args.crit[0] if prcntdiv < args.crit[0] else args.crit[1] 
        print('Critical! %.1f%% of avg %s %s%%; period avg:%s; now:%s|avg=%s;curr=%s' % (prcntdiv, sym, minmax, averages, newdata, averages, newdata))
        sys.exit(2)
    if prcntdiv < args.warn[0] or prcntdiv > args.warn[1]:
        minmax = args.warn[0] if prcntdiv < args.warn[0] else args.warn[1] 
        sym = '<' if prcntdiv < args.warn[0] else '>'
        print('Warning! %.1f%% of avg %s %s%%; period avg:%s; now:%s|avg=%s;curr=%s' % (prcntdiv, sym, minmax, averages, newdata, averages, newdata))
        sys.exit(1)
    print('Ok! %.1f%% of avg; avg:%s; now:%s|avg=%s;curr=%s' % (prcntdiv, averages, newdata, averages, newdata))


def calcavg(newdata, averages, args):
    if averages == None:
        data = collections.deque([newdata], args.smoothing)
        return data, sum(data)/len(data)
    else:
        averages.append(newdata)
        return averages, sum(averages)/len(averages)

def targetName(args, parser):
    if not any((args.host,args.service,args.target)):
        print('Can not produce unique name for storage from host/service/target. At least one needed')
        parser.print_help(sys.stderr)
    name = '-'.join([n for n in (args.host, args.service, args.target) if n ]).strip('-')
    return name

def pathcheck(args,parser):
    if not os.path.isdir(args.datapath):
        try:
            os.mkdir(args.datapath, 0750)
        except:
            print('Datapath: "%s" does not exist or is not writable by user' % args.datapath)
            print(sys.exc_value)
            sys.exit(2)

def main():
    args, parser = parse_args()
    
    hour, day = datebreakdown()

    pathcheck(args, parser)

    target = targetName(args, parser)
    
    newdata = datagetter(args, target)
    
    oldaverages = get_averages(hour, day, target, args)
    
    avgdata, avg = calcavg(newdata, oldaverages, args)
    
    set_averages(hour, day, avgdata, target, args)

    threshholds(newdata, avg, args)


if __name__ in '__main__':
    main()
