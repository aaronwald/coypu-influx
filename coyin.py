#!/usr/bin/env python
import argparse
import asyncio
import socket
import logging
import sys
import os
from aioinflux import InfluxDBClient
from datetime import datetime

async def main():
    async with InfluxDBClient(db='testdb', output='iterable') as client:

        #await client.create_database(db='testdb')
        for x in range(1,10):
            current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            point = {
                'time': current_time,
                'measurement': 'cpu_load_short',
                'tags': {'host': 'server01',
                         'region': 'us-west'},
                'fields': {'value': 0.64+x}
            }

            await client.write(point)
            await asyncio.sleep(.1)
        resp = await client.query('SELECT value FROM cpu_load_short', chunked=True, chunk_size=128)
        async for chunk in resp.iterchunks():
            yield chunk
            # or await process(chunk)

async def get_docs():
    for x in range(1,10):
        await asyncio.sleep(2)
        yield x

async def fetch():
    async for jdoc in main():
        results = jdoc['results']
        for v in results:
            for s in v['series']:
                names = s['name']
                columns = s['columns']
                values = s['values']
                for v in values:
                    print(names, columns, v)

async def vmstat(loop, cmd,  hostname, restart=True):
    proc = await asyncio.create_subprocess_shell(cmd,
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    
    # procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu----- -----timestamp-----
    # r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st                 UTC
    # 0  0   2048 286872 1318492 14039020    0    0     1     9    2    1  3  1 96  0  0 2019-01-11 23:11:04
    async with InfluxDBClient(db='testdb', output='iterable') as client:
        done = False
        while not done:
            line = await proc.stdout.readline()
            logging.debug(line)
            if not line:
                done = True
                continue
            
            l = line.strip().decode('ascii').split(' ')
            l = list(filter(None, l))
            if len(l) == 19:
                freeMem = float(l[3])
                us = float(l[12])
                dayStr = l[17]
                timeStr = l[18]
                points = []
                points.append({
                    'time': '%sT%sZ' % (dayStr, timeStr),
                    'measurement': 'cpu_load_short',
                    'tags': {'host': hostname },
                    'fields': {'value': us}
                })
                points.append({
                    'time': '%sT%sZ' % (dayStr, timeStr),
                    'measurement': 'free_mem',
                    'tags': {'host': hostname },
                    'fields': {'value': freeMem}
                })

                for point in points:
                    logging.debug(point)
                    await client.write(point)
            
        logging.info("%s: Return Code %s", cmd, proc.returncode)

        if restart:
            loop.create_task(vmstat(loop, cmd, hostname, restart))

            
async def perfTask(loop, cmd, pid, hostname, restart=True):
    proc = await asyncio.create_subprocess_shell(cmd,
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    
    async with InfluxDBClient(db='testdb', output='iterable') as client:
        done = False
        while not done:
            try:
                line = await proc.stdout.readline()

                if not line:
                    done = True
                    continue
                
                l = line.strip().decode('ascii').split('#')
                l = list(filter(None, l))
                logging.debug(l)
                current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                value = int (l[1])
                if value:
                    point = {
                        'time': current_time,
                        'measurement': 'perf_events',
                        'tags': { 'type': l[2], 'host': hostname, 'pid': pid },
                        'fields': {'value': int(l[1])}
                    }
                    logging.debug(point)
                
                    await client.write(point)
            except Exception as e:
                logging.error(e)
                done = True


        logging.info("%s: Return Code %s", cmd, proc.returncode)

        if restart:
            loop.create_task(vmstat(loop, cmd, pid, hostname, restart))

if __name__ == '__main__':
#    unbuffered = os.fdopen(sys.stdout.fileno(), 'w', 0)
#    sys.stdout = unbuffered

    parser = argparse.ArgumentParser()
    parser.add_argument("-pid", help="process to monitor")
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    args = parser.parse_args()
    if not args.pid:
        parser.print_help()
        exit(1)

    if args.verbose:
        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        hostname = socket.gethostname()
        loop.create_task(vmstat(loop, 'vmstat -nt 1', hostname))
        loop.create_task(perfTask(loop, "sudo perf stat -p %s -e 'syscalls:sys_enter_*,dTLB-loads,dTLB-load-misses,iTLB-loads,iTLB-load-misses' -I 1000 -x# 2>&1" % (args.pid), args.pid, hostname, False))
#        loop.create_task(perfTask(loop, "sudo perf stat -p %s -e 'dTLB-loads,dTLB-load-misses,iTLB-loads,iTLB-load-misses' -I 1000 -x# 2>&1" % (args.pid), args.pid, hostname, False))
        #loop.run_until_complete(fetch())
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
            
